from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import cast

import pytest

from scifact_rag import composition
from scifact_rag.application import RagApplication
from scifact_rag.composition import Settings
from scifact_rag.domain import (
    CandidateHit,
    CandidateScore,
    EvidenceChunk,
    EvidenceDocument,
    RetrievalCandidate,
    RetrievalSignal,
    SearchHit,
)
from scifact_rag.generation import (
    DpChunkContextAssembler,
    GenerationContextStrategyName,
    WholeDocumentContextAssembler,
)
from scifact_rag.retrievers import PooledRankingRetriever
from scifact_rag.strategies import DocumentOnlyStrategy, RetrievalStrategyName


class FakeCorpus:
    def documents(self) -> Iterable[EvidenceDocument]:
        return (
            EvidenceDocument("1", "one", "first"),
            EvidenceDocument("2", "two", "second"),
            EvidenceDocument("3", "three", "third"),
        )

    def queries(self) -> Mapping[str, str]:
        return {"q1": "first"}

    def qrels(self) -> Mapping[str, Mapping[str, int]]:
        return {"q1": {"1": 1}}


class FakeEmbedder:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]

    def token_windows(self, text: str) -> list[str]:
        return [text]

    def content_token_count(self, text: str) -> int:
        return len(text.split())

    def bounded_token_windows(self, text: str) -> list[str]:
        return [text]


class FakeStrategy:
    name = "fake"
    representations = ("fake",)

    def chunks(self, documents: Sequence[EvidenceDocument]) -> list[EvidenceChunk]:
        return [EvidenceChunk(document.doc_id, 0, document.text, "fake") for document in documents]


class FakeStore:
    def __init__(self, hits: Sequence[SearchHit] = ()) -> None:
        self.initialized = False
        self.batches: list[list[EvidenceDocument]] = []
        self.chunk_batches: list[list[EvidenceChunk]] = []
        self.embedding_batches: list[list[Sequence[float] | None]] = []
        self.hits = list(hits)

    def initialize(self) -> None:
        self.initialized = True

    def upsert(
        self,
        documents: Sequence[EvidenceDocument],
        chunks: Sequence[EvidenceChunk],
        embeddings: Sequence[Sequence[float] | None],
    ) -> None:
        assert len(chunks) == len(embeddings)
        self.batches.append(list(documents))
        self.chunk_batches.append(list(chunks))
        self.embedding_batches.append(list(embeddings))

    def search_vector(
        self,
        embedding: Sequence[float],
        limit: int,
        representations: Sequence[str],
    ) -> list[SearchHit]:
        assert tuple(representations) == FakeStrategy.representations
        return self.hits[:limit]

    def search_keyword(self, query: str, limit: int) -> list[SearchHit]:
        return self.hits[:limit]

    def search_bm25(self, query: str, limit: int) -> list[SearchHit]:
        return self.hits[:limit]

    def retrieve_vector_candidates(
        self,
        embedding: Sequence[float],
        limit: int,
        representations: Sequence[str],
    ) -> list[CandidateHit]:
        raise NotImplementedError

    def retrieve_bm25_candidates(self, query: str, limit: int) -> list[CandidateHit]:
        raise NotImplementedError

    def score_vector_candidates(
        self,
        embedding: Sequence[float],
        document_ids: Sequence[str],
        representations: Sequence[str],
    ) -> list[CandidateScore]:
        raise NotImplementedError

    def score_bm25_candidates(
        self,
        query: str,
        document_ids: Sequence[str],
    ) -> list[CandidateScore]:
        raise NotImplementedError

    def load_chunks(
        self,
        document_ids: Sequence[str],
        representations: Sequence[str],
    ) -> list[EvidenceChunk]:
        raise NotImplementedError


class FakeRetriever:
    def __init__(self, hits: Sequence[SearchHit] = ()) -> None:
        self.hits = list(hits)

    def search(self, query: str, limit: int) -> list[SearchHit]:
        return self.hits[:limit]


class FakePooledRetriever:
    generator_limit = 50
    maximum_pool_size = 100

    def search(self, query: str, limit: int) -> list[SearchHit]:
        return [SearchHit("1", "one", "first", 1.0)][:limit]

    def search_with_candidates(
        self,
        query: str,
        limit: int,
    ) -> tuple[list[SearchHit], list[RetrievalCandidate]]:
        candidates = [
            RetrievalCandidate(
                EvidenceDocument("1", "one", "first"),
                (
                    RetrievalSignal("bm25", "title-abstract", 1.0, 1, True),
                    RetrievalSignal("dense", "window", 0.9, 1, False, 0, "first"),
                ),
            ),
            RetrievalCandidate(
                EvidenceDocument("2", "two", "second"),
                (
                    RetrievalSignal("dense", "window", 1.0, 1, True, 0, "second"),
                    RetrievalSignal("bm25", "title-abstract", 0.1, 2, False),
                ),
            ),
        ]
        return self.search(query, limit), candidates


class FakeGenerator:
    model = "fake-model"

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[str, list[SearchHit]]] = []

    def generate(self, query: str, evidence: Sequence[SearchHit]) -> str:
        self.calls.append((query, list(evidence)))
        return self.text


class FakeContextAssembler:
    def __init__(self, evidence: Sequence[SearchHit]) -> None:
        self.evidence = list(evidence)
        self.calls: list[tuple[str, list[SearchHit]]] = []

    def assemble(self, query: str, evidence: Sequence[SearchHit]) -> list[SearchHit]:
        self.calls.append((query, list(evidence)))
        return self.evidence


def test_ingest_batches_every_document() -> None:
    store = FakeStore()
    application = RagApplication(
        store=store,
        embedder=FakeEmbedder(),
        generator=FakeGenerator(""),
        strategy=FakeStrategy(),
        retriever=FakeRetriever(),
    )

    result = application.ingest(FakeCorpus(), batch_size=2)

    assert store.initialized
    assert result.documents == 3
    assert [[document.doc_id for document in batch] for batch in store.batches] == [
        ["1", "2"],
        ["3"],
    ]
    assert [[chunk.doc_id for chunk in batch] for batch in store.chunk_batches] == [
        ["1", "2"],
        ["3"],
    ]


def test_application_exposes_complete_pooled_candidates_without_changing_search() -> None:
    ranked = [SearchHit("2", "Second", "body", 0.9)]
    candidates = [RetrievalCandidate(EvidenceDocument("1", "First", "body"), ())]

    class RecordingCandidateRetriever:
        generator_limit = 50
        maximum_pool_size = 100

        def search(self, query: str, limit: int) -> list[SearchHit]:
            return ranked[:limit]

        def search_with_candidates(
            self, query: str, limit: int
        ) -> tuple[list[SearchHit], list[RetrievalCandidate]]:
            return ranked[:limit], candidates

    application = RagApplication(
        store=FakeStore(),
        embedder=None,
        generator=FakeGenerator(""),
        strategy=FakeStrategy(),
        retriever=RecordingCandidateRetriever(),
    )

    actual_ranked, actual_candidates = application.retrieve_pool("claim", limit=10)

    assert actual_ranked == ranked
    assert actual_candidates == candidates
    assert application.search("claim", limit=10) == ranked


def test_ingest_embeds_only_retrieval_chunks_and_preserves_score_only_alignment() -> None:
    class MixedStrategy:
        name = "mixed"
        representations = ("retrieval", "scorer-only")

        def chunks(self, documents: Sequence[EvidenceDocument]) -> list[EvidenceChunk]:
            return [
                EvidenceChunk(documents[0].doc_id, 0, "embed me", "retrieval"),
                EvidenceChunk(
                    documents[0].doc_id,
                    0,
                    "store me raw",
                    "scorer-only",
                    embedding_required=False,
                ),
            ]

    store = FakeStore()
    application = RagApplication(
        store=store,
        embedder=FakeEmbedder(),
        generator=FakeGenerator(""),
        strategy=MixedStrategy(),
        retriever=FakeRetriever(),
    )

    application.ingest(FakeCorpus(), batch_size=1)

    assert store.embedding_batches[0] == [[8.0], None]


@pytest.mark.parametrize(
    "strategy_name",
    (RetrievalStrategyName.KEYWORD, RetrievalStrategyName.BM25),
)
def test_lexical_ingest_stores_documents_without_loading_an_embedder(
    strategy_name: RetrievalStrategyName,
) -> None:
    store = FakeStore()
    application = RagApplication(
        store=store,
        embedder=None,
        generator=FakeGenerator(""),
        strategy=DocumentOnlyStrategy(strategy_name),
        retriever=FakeRetriever(),
    )

    result = application.ingest(FakeCorpus(), batch_size=3)

    assert result.documents == 3
    assert store.chunk_batches == [[]]


def test_ask_accepts_only_retrieved_document_citations() -> None:
    hit = SearchHit("42", "evidence", "supported text", 0.9)
    store = FakeStore([hit])
    grounded = RagApplication(
        store=store,
        embedder=FakeEmbedder(),
        generator=FakeGenerator("Supported answer [42]"),
        strategy=FakeStrategy(),
        retriever=FakeRetriever([hit]),
    )
    ungrounded = RagApplication(
        store=store,
        embedder=FakeEmbedder(),
        generator=FakeGenerator("Unsupported answer [99]"),
        strategy=FakeStrategy(),
        retriever=FakeRetriever([hit]),
    )

    accepted = grounded.ask("question")
    rejected = ungrounded.ask("question")

    assert accepted.citations == ("42",)
    assert accepted.text == "Supported answer [42]"
    assert rejected.citations == ()
    assert rejected.text == "insufficient evidence"


def test_ask_without_evidence_does_not_call_generator() -> None:
    application = RagApplication(
        store=FakeStore(),
        embedder=FakeEmbedder(),
        generator=FakeGenerator("ignored"),
        strategy=FakeStrategy(),
        retriever=FakeRetriever(),
    )

    answer = application.ask("question")

    assert answer.text == "insufficient evidence"
    assert answer.evidence == ()


def test_ask_generates_from_assembled_context_and_keeps_parent_citation_gate() -> None:
    parent = SearchHit("42", "evidence", "whole abstract", 0.9)
    chunk = SearchHit("42", "evidence", "selected chunk", 0.9)
    generator = FakeGenerator("Supported answer [42]")
    assembler = FakeContextAssembler([chunk])
    application = RagApplication(
        store=FakeStore([parent]),
        embedder=FakeEmbedder(),
        generator=generator,
        strategy=FakeStrategy(),
        retriever=FakeRetriever([parent]),
        context_assembler=assembler,
    )

    answer = application.ask("question")

    assert assembler.calls == [("question", [parent])]
    assert generator.calls == [("question", [chunk])]
    assert answer.evidence == (chunk,)
    assert answer.citations == ("42",)


def test_ask_rejects_context_from_an_unretrieved_parent_before_generation() -> None:
    parent = SearchHit("42", "evidence", "whole abstract", 0.9)
    generator = FakeGenerator("Unsupported [99]")
    application = RagApplication(
        store=FakeStore([parent]),
        embedder=FakeEmbedder(),
        generator=generator,
        strategy=FakeStrategy(),
        retriever=FakeRetriever([parent]),
        context_assembler=FakeContextAssembler([SearchHit("99", "foreign", "foreign chunk", 1.0)]),
    )

    with pytest.raises(ValueError, match="retrieved parent"):
        application.ask("question")

    assert generator.calls == []


@pytest.mark.parametrize(
    ("context_strategy", "adaptive"),
    (
        (GenerationContextStrategyName.TOP_DP_CHUNKS, True),
        (GenerationContextStrategyName.ADAPTIVE, True),
    ),
)
def test_composition_wires_both_dp_names_to_the_adaptive_policy(
    monkeypatch: pytest.MonkeyPatch,
    context_strategy: GenerationContextStrategyName,
    adaptive: bool,
) -> None:
    monkeypatch.setattr(composition, "PostgresEvidenceStore", lambda database_url: FakeStore())
    monkeypatch.setattr(composition, "MiniLmEmbedder", lambda model: FakeEmbedder())
    monkeypatch.setattr(composition, "VllmColbertReranker", lambda *args: object())
    monkeypatch.setattr(
        composition,
        "OpenAiCompatibleGenerator",
        lambda **kwargs: FakeGenerator(""),
    )
    settings = Settings(
        database_url="postgresql://unused",
        embedding_model="minilm",
        generator_base_url="http://generator",
        generator_model="generator",
        generator_api_key=None,
        coreference_model="coref",
        coreference_device="cpu",
        coreference_max_tokens=4000,
        reranker_base_url="http://reranker",
        late_interaction_base_url="http://colbert",
        late_interaction_model="colbert",
        rank_llm_base_url="http://rankllm",
    )

    application = composition.build_application(
        settings,
        retrieval_strategy=RetrievalStrategyName.TITLE_TOKEN_WINDOW_RRF,
        generation_context_strategy=context_strategy,
    )

    assembler = cast(DpChunkContextAssembler, application._context_assembler)
    assert assembler._adaptive is adaptive
    assert assembler._chunks_per_document == 2
    assert assembler._representation == "coref-nominal-dp-colbert"


def test_composition_defaults_to_whole_document_generation_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(composition, "PostgresEvidenceStore", lambda database_url: FakeStore())
    monkeypatch.setattr(composition, "MiniLmEmbedder", lambda model: FakeEmbedder())
    monkeypatch.setattr(
        composition,
        "OpenAiCompatibleGenerator",
        lambda **kwargs: FakeGenerator(""),
    )

    application = composition.build_application()

    assert isinstance(application._context_assembler, WholeDocumentContextAssembler)


def test_composition_builds_only_the_two_distinct_generation_context_policies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore()
    generator = FakeGenerator("")
    monkeypatch.setattr(composition, "PostgresEvidenceStore", lambda database_url: store)
    monkeypatch.setattr(composition, "MiniLmEmbedder", lambda model: FakeEmbedder())
    monkeypatch.setattr(composition, "VllmColbertReranker", lambda *args: object())
    monkeypatch.setattr(composition, "OpenAiCompatibleGenerator", lambda **kwargs: generator)

    evaluator = composition.build_generation_evaluator()

    assert set(evaluator._assemblers) == {
        GenerationContextStrategyName.WHOLE_DOCUMENT,
        GenerationContextStrategyName.ADAPTIVE,
    }
    assert isinstance(
        evaluator._assemblers[GenerationContextStrategyName.WHOLE_DOCUMENT],
        WholeDocumentContextAssembler,
    )
    adaptive = cast(
        DpChunkContextAssembler,
        evaluator._assemblers[GenerationContextStrategyName.ADAPTIVE],
    )
    assert adaptive._store is store
    assert adaptive._adaptive is True
    assert evaluator._generator is generator


def test_candidate_diagnostics_report_pool_oracle_channel_and_ranking_metrics() -> None:
    application = RagApplication(
        store=FakeStore(),
        embedder=FakeEmbedder(),
        generator=FakeGenerator("ignored"),
        strategy=FakeStrategy(),
        retriever=FakePooledRetriever(),
    )

    diagnostics = application.diagnose_candidates(FakeCorpus(), cutoff=1)

    assert diagnostics.queries == 1
    assert diagnostics.generator_limit == 50
    assert diagnostics.maximum_pool_size == 100
    assert diagnostics.mean_pool_size == 2
    assert diagnostics.candidate_recall == 1
    assert diagnostics.candidate_query_hit_rate == 1
    assert diagnostics.oracle_ndcg == 1
    assert diagnostics.ranking.ndcg == 1
    assert diagnostics.channels[0].channel == "bm25"
    assert diagnostics.channels[0].recall == 1
    assert diagnostics.channels[1].channel == "dense"
    assert diagnostics.channels[1].recall == 0


def test_interval_rankzephyr_composition_uses_six_generators_and_one_listwise_scorer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(composition, "PostgresEvidenceStore", lambda database_url: FakeStore())
    monkeypatch.setattr(composition, "MiniLmEmbedder", lambda model: FakeEmbedder())
    monkeypatch.setattr(composition, "FastCorefAnalyzer", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        composition,
        "OpenAiCompatibleGenerator",
        lambda **kwargs: FakeGenerator(""),
    )
    settings = Settings(
        database_url="postgresql://unused",
        embedding_model="minilm",
        generator_base_url="http://generator",
        generator_model="generator",
        generator_api_key=None,
        coreference_model="coref",
        coreference_device="cpu",
        coreference_max_tokens=4000,
        reranker_base_url="http://reranker",
        late_interaction_base_url="http://colbert",
        late_interaction_model="colbert",
        rank_llm_base_url="http://rankllm",
    )

    application = composition.build_application(
        settings,
        retrieval_strategy=RetrievalStrategyName.POOLED_COREF_INTERVAL_RANKZEPHYR,
    )

    assert application._strategy.representations == (
        "title",
        "token-window",
        "coref-propn-sentence",
        "coref-nominal-sentence",
        "coref-interval-pack",
    )
    retriever = cast(PooledRankingRetriever, application._retriever)
    assert [generator.name for generator in retriever._generators] == [
        "bm25",
        "title",
        "token-window",
        "coref-propn",
        "coref-nominal",
        "coref-interval-pack",
    ]
    assert [scorer.name for scorer in retriever._scorers] == ["rankzephyr"]


def test_dual_dp_colbert_composition_uses_exact_four_generator_pool_and_two_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    budget_instances: list[tuple[str, int, str | None]] = []

    class FakeTokenBudget:
        def __init__(
            self,
            model: str,
            maximum_content_tokens: int,
            revision: str | None = None,
        ) -> None:
            self.model = model
            self.maximum_content_tokens = maximum_content_tokens
            self.revision = revision
            budget_instances.append((model, maximum_content_tokens, revision))

        def content_token_count(self, text: str) -> int:
            return len(text.split())

        def bounded_source_windows(self, text: str) -> list[str]:
            return [text]

    class FakeColbert:
        def score(self, query: str, documents: Sequence[SearchHit]) -> list[float]:
            return [0.0] * len(documents)

    fake_store = FakeStore()
    fake_colbert = FakeColbert()
    monkeypatch.setattr(composition, "PostgresEvidenceStore", lambda database_url: fake_store)
    monkeypatch.setattr(composition, "MiniLmEmbedder", lambda model: FakeEmbedder())
    monkeypatch.setattr(composition, "FastCorefAnalyzer", lambda *args, **kwargs: object())
    monkeypatch.setattr(composition, "HuggingFaceTokenBudget", FakeTokenBudget)
    monkeypatch.setattr(
        composition,
        "VllmColbertReranker",
        lambda base_url, model: fake_colbert,
    )
    monkeypatch.setattr(
        composition,
        "OpenAiCompatibleGenerator",
        lambda **kwargs: FakeGenerator(""),
    )
    settings = Settings(
        database_url="postgresql://unused",
        embedding_model="minilm",
        generator_base_url="http://generator",
        generator_model="generator",
        generator_api_key=None,
        coreference_model="coref",
        coreference_device="cpu",
        coreference_max_tokens=4000,
        reranker_base_url="http://reranker",
        late_interaction_base_url="http://colbert",
        late_interaction_model="colbert",
        rank_llm_base_url="http://rankllm",
    )

    application = composition.build_application(
        settings,
        retrieval_strategy=RetrievalStrategyName.POOLED_COREF_NOMINAL_DP_COLBERT,
    )

    assert application._strategy.representations == (
        "title",
        "coref-nominal-sentence",
        "coref-nominal-dp-minilm",
        "coref-nominal-dp-colbert",
    )
    retriever = cast(PooledRankingRetriever, application._retriever)
    assert [generator.name for generator in retriever._generators] == [
        "bm25",
        "title",
        "coref-nominal",
        "coref-nominal-dp",
    ]
    assert [scorer.name for scorer in retriever._scorers] == [
        "colbert-title",
        "colbert-content",
    ]
    assert retriever._normalizer.__class__.__name__ == "RobustScoreNormalizer"
    assert retriever._aggregator.__class__.__name__ == "EqualScoreFusionPolicy"
    assert budget_instances == [
        ("minilm", 126, None),
        ("colbert", 510, "c72aa89bc61afdd85373643f3a1a75b2aad6e0fe"),
    ]


@pytest.mark.parametrize(
    ("retrieval_strategy", "expected_scorers", "expected_normalizer"),
    (
        (
            RetrievalStrategyName.POOLED_COREF_INTERVAL_MULTIVIEW_COLBERT,
            ["colbert-title", "colbert-content"],
            "RobustScoreNormalizer",
        ),
        (
            RetrievalStrategyName.POOLED_COREF_INTERVAL_CONTENT_MAX_COLBERT,
            ["colbert-content"],
            "IdentityScoreNormalizer",
        ),
        (
            RetrievalStrategyName.POOLED_COREF_INTERVAL_RAW_MEAN_COLBERT,
            ["colbert-title", "colbert-content"],
            "IdentityScoreNormalizer",
        ),
    ),
)
def test_interval_pool_colbert_component_ablations_reuse_fixed_pool_and_scorers(
    monkeypatch: pytest.MonkeyPatch,
    retrieval_strategy: RetrievalStrategyName,
    expected_scorers: list[str],
    expected_normalizer: str,
) -> None:
    budget_instances: list[tuple[str, int, str | None]] = []

    class FakeTokenBudget:
        def __init__(
            self,
            model: str,
            maximum_content_tokens: int,
            revision: str | None = None,
        ) -> None:
            budget_instances.append((model, maximum_content_tokens, revision))

        def content_token_count(self, text: str) -> int:
            return len(text.split())

        def bounded_source_windows(self, text: str) -> list[str]:
            return [text]

    class FakeColbert:
        def score(self, query: str, documents: Sequence[SearchHit]) -> list[float]:
            return [0.0] * len(documents)

    fake_store = FakeStore()
    monkeypatch.setattr(composition, "PostgresEvidenceStore", lambda database_url: fake_store)
    monkeypatch.setattr(composition, "MiniLmEmbedder", lambda model: FakeEmbedder())
    monkeypatch.setattr(composition, "FastCorefAnalyzer", lambda *args, **kwargs: object())
    monkeypatch.setattr(composition, "HuggingFaceTokenBudget", FakeTokenBudget)
    monkeypatch.setattr(
        composition,
        "VllmColbertReranker",
        lambda base_url, model: FakeColbert(),
    )
    monkeypatch.setattr(
        composition,
        "OpenAiCompatibleGenerator",
        lambda **kwargs: FakeGenerator(""),
    )
    settings = Settings(
        database_url="postgresql://unused",
        embedding_model="minilm",
        generator_base_url="http://generator",
        generator_model="generator",
        generator_api_key=None,
        coreference_model="coref",
        coreference_device="cpu",
        coreference_max_tokens=4000,
        reranker_base_url="http://reranker",
        late_interaction_base_url="http://colbert",
        late_interaction_model="colbert",
        rank_llm_base_url="http://rankllm",
    )

    application = composition.build_application(
        settings,
        retrieval_strategy=retrieval_strategy,
    )

    assert application._strategy.representations == (
        "title",
        "token-window",
        "coref-propn-sentence",
        "coref-nominal-sentence",
        "coref-nominal-dp-minilm",
        "coref-nominal-dp-colbert",
        "coref-interval-pack",
    )
    retriever = cast(PooledRankingRetriever, application._retriever)
    assert [generator.name for generator in retriever._generators] == [
        "bm25",
        "title",
        "token-window",
        "coref-propn",
        "coref-nominal",
        "coref-interval-pack",
    ]
    assert [scorer.name for scorer in retriever._scorers] == expected_scorers
    assert retriever._normalizer.__class__.__name__ == expected_normalizer
    assert retriever._aggregator.__class__.__name__ == "EqualScoreFusionPolicy"
    assert budget_instances == [
        ("minilm", 126, None),
        ("colbert", 510, "c72aa89bc61afdd85373643f3a1a75b2aad6e0fe"),
    ]
