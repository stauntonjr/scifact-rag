from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .domain import (
    CandidateFeatureMatrix,
    CandidateHit,
    CandidateScore,
    CoreferenceAnalysis,
    EvidenceChunk,
    EvidenceDocument,
    GeneratedAnswer,
    RetrievalCandidate,
    SearchHit,
    SentenceSpan,
)

if TYPE_CHECKING:
    from .proposition import GroundedProposition
    from .proposition_evaluation import PropositionSource
    from .scientific_inference import (
        EvidenceBundle,
        InferenceRequest,
        InferenceResponse,
    )


class CorpusSource(Protocol):
    def documents(self) -> Iterable[EvidenceDocument]: ...

    def queries(self) -> Mapping[str, str]: ...

    def qrels(self) -> Mapping[str, Mapping[str, int]]: ...


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class RepresentationStrategy(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def representations(self) -> tuple[str, ...]: ...

    def chunks(self, documents: Sequence[EvidenceDocument]) -> list[EvidenceChunk]: ...


class CoreferenceAnalyzer(Protocol):
    def analyze(self, texts: Sequence[str]) -> list[CoreferenceAnalysis]: ...

    def sentences(self, text: str) -> list[str]: ...

    def sentence_spans(self, text: str) -> list[SentenceSpan]: ...


class Retriever(Protocol):
    def search(self, query: str, limit: int) -> list[SearchHit]: ...


class CandidateGenerator(Protocol):
    @property
    def name(self) -> str: ...

    def generate(self, query: str, limit: int) -> list[CandidateHit]: ...


class CandidateScorer(Protocol):
    @property
    def name(self) -> str: ...

    def score(
        self,
        query: str,
        documents: Sequence[EvidenceDocument],
    ) -> list[CandidateScore]: ...


class FeatureMatrixBuilder(Protocol):
    def build(
        self,
        candidates: Sequence[RetrievalCandidate],
    ) -> CandidateFeatureMatrix: ...


class ScoreNormalizer(Protocol):
    def normalize(self, matrix: CandidateFeatureMatrix) -> CandidateFeatureMatrix: ...


class RankingPolicy(Protocol):
    def rank(
        self,
        matrix: CandidateFeatureMatrix,
        limit: int,
    ) -> list[SearchHit]: ...


class RankAggregator(RankingPolicy, Protocol):
    """Compatibility name for ranking policies used by existing pooled strategies."""


@runtime_checkable
class CandidateDiagnosticRetriever(Protocol):
    @property
    def generator_limit(self) -> int: ...

    @property
    def maximum_pool_size(self) -> int: ...

    def search_with_candidates(
        self,
        query: str,
        limit: int,
    ) -> tuple[list[SearchHit], list[RetrievalCandidate]]: ...


class CandidatePoolSource(Protocol):
    def retrieve_pool(
        self,
        query: str,
        *,
        limit: int,
    ) -> tuple[list[SearchHit], list[RetrievalCandidate]]: ...


class Reranker(Protocol):
    def score(self, query: str, documents: Sequence[SearchHit]) -> list[float]: ...


class StoredChunkSource(Protocol):
    def load_chunks(
        self,
        document_ids: Sequence[str],
        representations: Sequence[str],
    ) -> list[EvidenceChunk]: ...


class EvidenceStore(StoredChunkSource, Protocol):
    def initialize(self) -> None: ...

    def upsert(
        self,
        documents: Sequence[EvidenceDocument],
        chunks: Sequence[EvidenceChunk],
        embeddings: Sequence[Sequence[float] | None],
    ) -> None: ...

    def search_vector(
        self,
        embedding: Sequence[float],
        limit: int,
        representations: Sequence[str],
    ) -> list[SearchHit]: ...

    def search_keyword(self, query: str, limit: int) -> list[SearchHit]: ...

    def search_bm25(self, query: str, limit: int) -> list[SearchHit]: ...

    def retrieve_vector_candidates(
        self,
        embedding: Sequence[float],
        limit: int,
        representations: Sequence[str],
    ) -> list[CandidateHit]: ...

    def retrieve_bm25_candidates(self, query: str, limit: int) -> list[CandidateHit]: ...

    def score_vector_candidates(
        self,
        embedding: Sequence[float],
        document_ids: Sequence[str],
        representations: Sequence[str],
    ) -> list[CandidateScore]: ...

    def score_bm25_candidates(
        self,
        query: str,
        document_ids: Sequence[str],
    ) -> list[CandidateScore]: ...


class AnswerGenerator(Protocol):
    @property
    def model(self) -> str: ...

    def generate(self, query: str, evidence: Sequence[SearchHit]) -> str: ...


@runtime_checkable
class MeasuredAnswerGenerator(Protocol):
    @property
    def model(self) -> str: ...

    def generate_with_metrics(
        self,
        query: str,
        evidence: Sequence[SearchHit],
    ) -> GeneratedAnswer: ...


class GenerationContextAssembler(Protocol):
    def assemble(self, query: str, evidence: Sequence[SearchHit]) -> list[SearchHit]: ...


class PairTokenBudget(Protocol):
    @property
    def maximum_pair_tokens(self) -> int: ...

    def pair_token_count(self, premise: str, hypothesis: str) -> int: ...


class ScientificInferenceClient(Protocol):
    def classify(self, request: InferenceRequest) -> InferenceResponse: ...


class PropositionExtractor(Protocol):
    def extract(self, source: PropositionSource) -> tuple[GroundedProposition, ...]: ...


class EvidenceBundleAssembler(Protocol):
    def assemble(self, claim: str, document: EvidenceDocument) -> EvidenceBundle: ...
