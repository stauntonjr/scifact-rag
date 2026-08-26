from __future__ import annotations

import re
from collections.abc import Sequence

from .domain import (
    Answer,
    EvidenceChunk,
    EvidenceDocument,
    IngestResult,
    RetrievalMetrics,
    SearchHit,
)
from .metrics import evaluate_rankings
from .ports import AnswerGenerator, CorpusSource, Embedder, EvidenceStore

_CITATION = re.compile(r"\[([^\[\]]+)\]")
_INSUFFICIENT = "insufficient evidence"


def _embedding_text(document: EvidenceDocument) -> str:
    return f"{document.title}\n{document.text}".strip()


class RagApplication:
    def __init__(
        self,
        *,
        store: EvidenceStore,
        embedder: Embedder,
        generator: AnswerGenerator,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._generator = generator

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
        chunks = [
            EvidenceChunk(document.doc_id, ordinal, text)
            for document in documents
            for ordinal, text in enumerate(
                self._embedder.document_chunks(_embedding_text(document))
            )
        ]
        embeddings = self._embedder.embed([chunk.text for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError("embedder returned the wrong number of vectors")
        self._store.upsert(documents, chunks, embeddings)

    def search(self, query: str, *, limit: int = 5) -> list[SearchHit]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if limit < 1:
            raise ValueError("limit must be positive")
        vectors = self._embedder.embed([query])
        if len(vectors) != 1:
            raise ValueError("embedder returned the wrong number of query vectors")
        return self._store.search(vectors[0], limit)

    def ask(self, query: str, *, limit: int = 5) -> Answer:
        evidence = tuple(self.search(query, limit=limit))
        if not evidence:
            return Answer(query, _INSUFFICIENT, (), self._generator.model, ())
        generated = self._generator.generate(query, evidence).strip()
        allowed = {hit.doc_id for hit in evidence}
        citations = tuple(dict.fromkeys(_CITATION.findall(generated)))
        if generated.lower() == _INSUFFICIENT:
            return Answer(query, _INSUFFICIENT, (), self._generator.model, evidence)
        if not citations or any(citation not in allowed for citation in citations):
            return Answer(query, _INSUFFICIENT, (), self._generator.model, evidence)
        return Answer(query, generated, citations, self._generator.model, evidence)

    def evaluate(self, corpus: CorpusSource, *, cutoff: int = 10) -> RetrievalMetrics:
        queries = corpus.queries()
        qrels = corpus.qrels()
        rankings = {
            query_id: [hit.doc_id for hit in self.search(queries[query_id], limit=cutoff)]
            for query_id in qrels
        }
        return evaluate_rankings(qrels, rankings, cutoff)
