from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol

from .domain import EvidenceDocument, SearchHit


class CorpusSource(Protocol):
    def documents(self) -> Iterable[EvidenceDocument]: ...

    def queries(self) -> Mapping[str, str]: ...

    def qrels(self) -> Mapping[str, Mapping[str, int]]: ...


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class EvidenceStore(Protocol):
    def initialize(self) -> None: ...

    def upsert(
        self, documents: Sequence[EvidenceDocument], embeddings: Sequence[Sequence[float]]
    ) -> None: ...

    def search(self, embedding: Sequence[float], limit: int) -> list[SearchHit]: ...


class AnswerGenerator(Protocol):
    @property
    def model(self) -> str: ...

    def generate(self, query: str, evidence: Sequence[SearchHit]) -> str: ...
