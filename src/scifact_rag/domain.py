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


@dataclass(frozen=True, slots=True)
class SearchHit:
    doc_id: str
    title: str
    text: str
    score: float


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
