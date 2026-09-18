from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from .generation import GenerationContextStrategyName
from .strategies import RetrievalStrategyName

_DEFAULT_PAGES_ORIGIN = "https://stauntonjr.github.io"


class DependencyName(StrEnum):
    RETRIEVAL_STORE = "retrieval-store"
    GENERATOR = "generator"
    RERANKER = "reranker"
    LATE_INTERACTION = "late-interaction"
    RANKLLM = "rankllm"


@dataclass(frozen=True, slots=True)
class PublicDemoSettings:
    enabled: bool = False
    pages_origin: str | None = None

    @classmethod
    def from_environment(cls) -> PublicDemoSettings:
        raw_enabled = os.getenv("SCIFACT_PUBLIC_DEMO_ENABLED", "false")
        if raw_enabled not in {"true", "false"}:
            raise ValueError("SCIFACT_PUBLIC_DEMO_ENABLED must be exactly 'true' or 'false'")
        if raw_enabled == "false":
            return cls()

        origin = os.getenv("SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN", _DEFAULT_PAGES_ORIGIN)
        if not _is_valid_origin(origin):
            raise ValueError("SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN must be an HTTPS origin")
        return cls(enabled=True, pages_origin=origin)


def _is_valid_origin(value: str) -> bool:
    parsed = urlsplit(value)
    return (
        bool(
            parsed.scheme == "https"
            and parsed.netloc
            and parsed.hostname
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
        )
        and value == f"https://{parsed.netloc}"
    )


_RERANKER_STRATEGIES = frozenset(
    {
        RetrievalStrategyName.RERANK_MSMARCO,
        RetrievalStrategyName.POOLED_MSMARCO_RRF,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_MSMARCO,
    }
)
_LATE_INTERACTION_STRATEGIES = frozenset(
    {
        RetrievalStrategyName.POOLED_COLBERT,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT,
        RetrievalStrategyName.POOLED_COREF_NOMINAL_DP_COLBERT,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_MULTIVIEW_COLBERT,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_CONTENT_MAX_COLBERT,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_RAW_MEAN_COLBERT,
    }
)
_RANKLLM_STRATEGIES = frozenset({RetrievalStrategyName.POOLED_COREF_INTERVAL_RANKZEPHYR})


def retrieval_dependencies(strategy: RetrievalStrategyName) -> frozenset[DependencyName]:
    dependencies = {DependencyName.RETRIEVAL_STORE}
    if strategy in _RERANKER_STRATEGIES:
        dependencies.add(DependencyName.RERANKER)
    if strategy in _LATE_INTERACTION_STRATEGIES:
        dependencies.add(DependencyName.LATE_INTERACTION)
    if strategy in _RANKLLM_STRATEGIES:
        dependencies.add(DependencyName.RANKLLM)
    return frozenset(dependencies)


def context_dependencies(
    strategy: GenerationContextStrategyName,
) -> frozenset[DependencyName]:
    if strategy in {
        GenerationContextStrategyName.TOP_DP_CHUNKS,
        GenerationContextStrategyName.ADAPTIVE,
    }:
        return frozenset({DependencyName.LATE_INTERACTION})
    return frozenset()
