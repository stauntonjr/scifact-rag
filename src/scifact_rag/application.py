from __future__ import annotations

import re
from collections.abc import Sequence

from .domain import (
    Answer,
    CandidateDiagnostics,
    ChannelCandidateMetrics,
    EvidenceDocument,
    IngestResult,
    RetrievalMetrics,
    SearchHit,
)
from .generation import WholeDocumentContextAssembler
from .metrics import evaluate_rankings
from .ports import (
    AnswerGenerator,
    CandidateDiagnosticRetriever,
    CorpusSource,
    Embedder,
    EvidenceStore,
    GenerationContextAssembler,
    RepresentationStrategy,
    Retriever,
)

_CITATION = re.compile(r"\[([^\[\]]+)\]")
_INSUFFICIENT = "insufficient evidence"


def finalize_generated_answer(
    generated: str,
    allowed_document_ids: set[str],
) -> tuple[str, tuple[str, ...], bool]:
    """Apply the product citation gate while retaining parsed citation evidence."""
    stripped = generated.strip()
    citations = tuple(dict.fromkeys(_CITATION.findall(stripped)))
    if stripped.lower() == _INSUFFICIENT:
        return _INSUFFICIENT, (), True
    citation_valid = bool(citations) and all(
        citation in allowed_document_ids for citation in citations
    )
    return (stripped if citation_valid else _INSUFFICIENT), citations, citation_valid


class RagApplication:
    def __init__(
        self,
        *,
        store: EvidenceStore,
        embedder: Embedder | None,
        generator: AnswerGenerator,
        strategy: RepresentationStrategy,
        retriever: Retriever,
        context_assembler: GenerationContextAssembler | None = None,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._generator = generator
        self._strategy = strategy
        self._retriever = retriever
        self._context_assembler = context_assembler or WholeDocumentContextAssembler()

    def ingest(self, corpus: CorpusSource, *, batch_size: int = 64) -> IngestResult:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._store.initialize()
        pending: list[EvidenceDocument] = []
        total = 0
        for document in corpus.documents():
            pending.append(document)
            if len(pending) >= batch_size:
                self._upsert_batch(pending)
                total += len(pending)
                pending.clear()
        if pending:
            self._upsert_batch(pending)
            total += len(pending)
        return IngestResult(documents=total)

    def _upsert_batch(self, documents: Sequence[EvidenceDocument]) -> None:
        chunks = self._strategy.chunks(documents)
        embedder = self._embedder
        embedded_positions = [
            position for position, chunk in enumerate(chunks) if chunk.embedding_required
        ]
        if embedded_positions and embedder is None:
            raise ValueError("the document strategy requires an embedder")
        embedded = (
            embedder.embed([chunks[position].text for position in embedded_positions])
            if embedded_positions and embedder
            else []
        )
        if len(embedded) != len(embedded_positions):
            raise ValueError("embedder returned the wrong number of vectors")
        embeddings: list[Sequence[float] | None] = [None] * len(chunks)
        for position, vector in zip(embedded_positions, embedded, strict=True):
            embeddings[position] = vector
        self._store.upsert(documents, chunks, embeddings)

    def search(self, query: str, *, limit: int = 5) -> list[SearchHit]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if limit < 1:
            raise ValueError("limit must be positive")
        return self._retriever.search(query, limit)

    def ask(self, query: str, *, limit: int = 5) -> Answer:
        retrieved = tuple(self.search(query, limit=limit))
        if not retrieved:
            return Answer(query, _INSUFFICIENT, (), self._generator.model, ())
        evidence = tuple(self._context_assembler.assemble(query, retrieved))
        allowed = {hit.doc_id for hit in retrieved}
        if not evidence or any(hit.doc_id not in allowed for hit in evidence):
            raise ValueError("generation context must contain retrieved parent documents")
        generated = self._generator.generate(query, evidence)
        answer_text, citations, citation_valid = finalize_generated_answer(generated, allowed)
        return Answer(
            query,
            answer_text,
            citations if citation_valid and answer_text != _INSUFFICIENT else (),
            self._generator.model,
            evidence,
        )

    def evaluate(self, corpus: CorpusSource, *, cutoff: int = 10) -> RetrievalMetrics:
        queries = corpus.queries()
        qrels = corpus.qrels()
        rankings = {
            query_id: [hit.doc_id for hit in self.search(queries[query_id], limit=cutoff)]
            for query_id in qrels
        }
        return evaluate_rankings(qrels, rankings, cutoff)

    def diagnose_candidates(
        self,
        corpus: CorpusSource,
        *,
        cutoff: int = 10,
    ) -> CandidateDiagnostics:
        if cutoff < 1:
            raise ValueError("cutoff must be positive")
        if not isinstance(self._retriever, CandidateDiagnosticRetriever):
            raise TypeError("candidate diagnostics require a pooled ranking strategy")

        queries = corpus.queries()
        qrels = corpus.qrels()
        rankings: dict[str, list[str]] = {}
        oracle_rankings: dict[str, list[str]] = {}
        total_pool_size = 0
        total_recall = 0.0
        query_hits = 0
        channel_recall: dict[str, float] = {}
        channel_hits: dict[str, int] = {}

        for query_id, relevance in qrels.items():
            hits, candidates = self._retriever.search_with_candidates(
                queries[query_id],
                cutoff,
            )
            rankings[query_id] = [hit.doc_id for hit in hits]
            candidate_ids = {candidate.document.doc_id for candidate in candidates}
            relevant = {doc_id for doc_id, grade in relevance.items() if grade > 0}
            retrieved_relevant = relevant.intersection(candidate_ids)
            total_pool_size += len(candidates)
            total_recall += len(retrieved_relevant) / len(relevant) if relevant else 0.0
            query_hits += bool(retrieved_relevant)
            oracle_rankings[query_id] = sorted(
                candidate_ids,
                key=lambda doc_id: (-relevance.get(doc_id, 0), doc_id),
            )[:cutoff]

            channel_documents: dict[str, set[str]] = {}
            for candidate in candidates:
                for signal in candidate.signals:
                    if signal.generated_candidate:
                        channel_documents.setdefault(signal.channel, set()).add(
                            candidate.document.doc_id
                        )
            for channel, document_ids in channel_documents.items():
                channel_relevant = relevant.intersection(document_ids)
                channel_recall[channel] = channel_recall.get(channel, 0.0) + (
                    len(channel_relevant) / len(relevant) if relevant else 0.0
                )
                channel_hits[channel] = channel_hits.get(channel, 0) + bool(channel_relevant)

        count = len(qrels)
        if count == 0:
            raise ValueError("qrels must not be empty")
        oracle = evaluate_rankings(qrels, oracle_rankings, cutoff)
        return CandidateDiagnostics(
            queries=count,
            generator_limit=self._retriever.generator_limit,
            maximum_pool_size=self._retriever.maximum_pool_size,
            mean_pool_size=total_pool_size / count,
            candidate_recall=total_recall / count,
            candidate_query_hit_rate=query_hits / count,
            oracle_ndcg=oracle.ndcg,
            ranking=evaluate_rankings(qrels, rankings, cutoff),
            channels=tuple(
                ChannelCandidateMetrics(
                    channel=channel,
                    recall=channel_recall[channel] / count,
                    query_hit_rate=channel_hits[channel] / count,
                )
                for channel in sorted(channel_recall)
            ),
        )
