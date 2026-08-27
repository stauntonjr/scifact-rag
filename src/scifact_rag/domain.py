from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvidenceDocument:
    doc_id: str
    title: str
    text: str


@dataclass(frozen=True, slots=True)
class EvidenceChunk:
    doc_id: str
    ordinal: int
    text: str
    representation: str = "token-window"
    embedding_required: bool = True


@dataclass(frozen=True, slots=True)
class CoreferenceMention:
    start: int
    end: int
    text: str
    pos_tags: tuple[str, ...]
    is_possessive: bool = False


@dataclass(frozen=True, slots=True)
class CoreferenceAnalysis:
    text: str
    clusters: tuple[tuple[CoreferenceMention, ...], ...]


@dataclass(frozen=True, slots=True)
class SentenceSpan:
    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class SearchHit:
    doc_id: str
    title: str
    text: str
    score: float


@dataclass(frozen=True, slots=True)
class CandidateHit:
    document: EvidenceDocument
    score: float
    representation: str
    chunk_ordinal: int | None = None
    matched_text: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateScore:
    doc_id: str
    score: float
    representation: str
    chunk_ordinal: int | None = None
    matched_text: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalSignal:
    channel: str
    representation: str
    score: float
    rank: int
    generated_candidate: bool
    chunk_ordinal: int | None = None
    matched_text: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    document: EvidenceDocument
    signals: tuple[RetrievalSignal, ...]


@dataclass(frozen=True, slots=True)
class RankingFeature:
    channel: str
    raw_score: float
    rank: int
    representation: str
    chunk_ordinal: int | None = None
    matched_text: str | None = None
    normalized_score: float | None = None


@dataclass(frozen=True, slots=True)
class CandidateFeatureRow:
    document: EvidenceDocument
    features: tuple[RankingFeature, ...]


@dataclass(frozen=True, slots=True)
class CandidateFeatureMatrix:
    channels: tuple[str, ...]
    rows: tuple[CandidateFeatureRow, ...]


@dataclass(frozen=True, slots=True)
class IngestResult:
    documents: int


@dataclass(frozen=True, slots=True)
class Answer:
    query: str
    text: str
    citations: tuple[str, ...]
    model: str
    evidence: tuple[SearchHit, ...]


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    queries: int
    cutoff: int
    ndcg: float
    mean_average_precision: float
    recall: float
    precision: float
    mean_reciprocal_rank: float


@dataclass(frozen=True, slots=True)
class ChannelCandidateMetrics:
    channel: str
    recall: float
    query_hit_rate: float


@dataclass(frozen=True, slots=True)
class CandidateDiagnostics:
    queries: int
    generator_limit: int
    maximum_pool_size: int
    mean_pool_size: float
    candidate_recall: float
    candidate_query_hit_rate: float
    oracle_ndcg: float
    ranking: RetrievalMetrics
    channels: tuple[ChannelCandidateMetrics, ...]
