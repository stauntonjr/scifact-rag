from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from threading import BoundedSemaphore
from typing import Literal, Protocol
from urllib.parse import urlsplit

from .generation import GenerationContextStrategyName
from .strategies import DEFAULT_RETRIEVAL_STRATEGY, RetrievalStrategyName

_DEFAULT_PAGES_ORIGIN = "https://stauntonjr.github.io"


class DependencyName(StrEnum):
    RETRIEVAL_STORE = "retrieval-store"
    GENERATOR = "generator"
    RERANKER = "reranker"
    LATE_INTERACTION = "late-interaction"
    RANKLLM = "rankllm"


class PublicReason(StrEnum):
    RETRIEVAL_STORE_UNAVAILABLE = "retrieval_store_unavailable"
    GENERATOR_UNAVAILABLE = "generator_unavailable"
    RERANKER_UNAVAILABLE = "reranker_unavailable"
    LATE_INTERACTION_UNAVAILABLE = "late_interaction_unavailable"
    RANKLLM_UNAVAILABLE = "rankllm_unavailable"
    NO_AVAILABLE_STRATEGY = "no_available_strategy"


class DependencyProbe(Protocol):
    def available(self) -> bool: ...


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


@dataclass(frozen=True, slots=True)
class StrategyCapability:
    name: str
    available: bool
    reason: PublicReason | None


@dataclass(frozen=True, slots=True)
class OperationCapability:
    available: bool
    reason: PublicReason | None


@dataclass(frozen=True, slots=True)
class CapabilitySnapshot:
    status: Literal["ready", "degraded", "unavailable"]
    search: OperationCapability
    answer: OperationCapability
    retrieval: tuple[StrategyCapability, ...]
    context: tuple[StrategyCapability, ...]
    effective_retrieval_default: RetrievalStrategyName | None
    effective_context_default: GenerationContextStrategyName | None


class CapabilityProvider(Protocol):
    def snapshot(self) -> CapabilitySnapshot: ...


class InferenceGate:
    def __init__(self) -> None:
        self._semaphore = BoundedSemaphore(1)

    @contextmanager
    def acquire(self) -> Iterator[bool]:
        acquired = self._semaphore.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                self._semaphore.release()


@dataclass(frozen=True, slots=True)
class PublicDemoRuntime:
    settings: PublicDemoSettings
    capabilities: CapabilityProvider
    gate: InferenceGate


_REASON_BY_DEPENDENCY = {
    DependencyName.RETRIEVAL_STORE: PublicReason.RETRIEVAL_STORE_UNAVAILABLE,
    DependencyName.GENERATOR: PublicReason.GENERATOR_UNAVAILABLE,
    DependencyName.RERANKER: PublicReason.RERANKER_UNAVAILABLE,
    DependencyName.LATE_INTERACTION: PublicReason.LATE_INTERACTION_UNAVAILABLE,
    DependencyName.RANKLLM: PublicReason.RANKLLM_UNAVAILABLE,
}


class PublicDemoCapabilityService:
    def __init__(self, probes: Mapping[DependencyName, DependencyProbe]) -> None:
        self._probes = probes

    def snapshot(self) -> CapabilitySnapshot:
        availability = {
            dependency: self._probe(probe) for dependency, probe in self._probes.items()
        }
        retrieval = tuple(
            self._retrieval_capability(strategy, availability) for strategy in RetrievalStrategyName
        )
        context = tuple(
            self._context_capability(strategy, availability)
            for strategy in GenerationContextStrategyName
        )
        effective_retrieval = self._effective_retrieval_default(retrieval)
        effective_context = self._effective_context_default(context)
        retrieval_reason = self._unavailable_reason(
            retrieval,
            DEFAULT_RETRIEVAL_STRATEGY.value,
            PublicReason.NO_AVAILABLE_STRATEGY,
        )
        search = OperationCapability(
            available=effective_retrieval is not None,
            reason=None if effective_retrieval is not None else retrieval_reason,
        )
        generator_available = availability.get(DependencyName.GENERATOR, False)
        answer_reason = None
        if not generator_available:
            answer_reason = PublicReason.GENERATOR_UNAVAILABLE
        elif not search.available:
            answer_reason = search.reason
        elif effective_context is None:
            answer_reason = PublicReason.NO_AVAILABLE_STRATEGY
        answer = OperationCapability(
            available=answer_reason is None,
            reason=answer_reason,
        )
        configured_retrieval = self._is_available(retrieval, DEFAULT_RETRIEVAL_STRATEGY.value)
        configured_context = self._is_available(
            context, GenerationContextStrategyName.WHOLE_DOCUMENT.value
        )
        status: Literal["ready", "degraded", "unavailable"]
        if search.available and answer.available and configured_retrieval and configured_context:
            status = "ready"
        elif search.available or answer.available:
            status = "degraded"
        else:
            status = "unavailable"
        return CapabilitySnapshot(
            status=status,
            search=search,
            answer=answer,
            retrieval=retrieval,
            context=context,
            effective_retrieval_default=effective_retrieval,
            effective_context_default=effective_context,
        )

    @staticmethod
    def _probe(probe: DependencyProbe) -> bool:
        try:
            return bool(probe.available())
        except Exception:  # noqa: BLE001 - probes fail closed for any adapter failure
            return False

    def _retrieval_capability(
        self,
        strategy: RetrievalStrategyName,
        availability: Mapping[DependencyName, bool],
    ) -> StrategyCapability:
        dependencies = retrieval_dependencies(strategy)
        reason = self._missing_reason(dependencies, availability)
        return StrategyCapability(strategy.value, reason is None, reason)

    def _context_capability(
        self,
        strategy: GenerationContextStrategyName,
        availability: Mapping[DependencyName, bool],
    ) -> StrategyCapability:
        dependencies = context_dependencies(strategy)
        reason = self._missing_reason(dependencies, availability)
        return StrategyCapability(strategy.value, reason is None, reason)

    @staticmethod
    def _missing_reason(
        dependencies: frozenset[DependencyName],
        availability: Mapping[DependencyName, bool],
    ) -> PublicReason | None:
        for dependency in DependencyName:
            if dependency in dependencies and not availability.get(dependency, False):
                return _REASON_BY_DEPENDENCY[dependency]
        return None

    @staticmethod
    def _is_available(capabilities: tuple[StrategyCapability, ...], name: str) -> bool:
        return any(item.name == name and item.available for item in capabilities)

    @staticmethod
    def _unavailable_reason(
        capabilities: tuple[StrategyCapability, ...],
        name: str,
        fallback: PublicReason,
    ) -> PublicReason:
        for item in capabilities:
            if item.name == name and item.reason is not None:
                return item.reason
        return fallback

    @staticmethod
    def _effective_retrieval_default(
        capabilities: tuple[StrategyCapability, ...],
    ) -> RetrievalStrategyName | None:
        if PublicDemoCapabilityService._is_available(
            capabilities, DEFAULT_RETRIEVAL_STRATEGY.value
        ):
            return DEFAULT_RETRIEVAL_STRATEGY
        fallback = RetrievalStrategyName.BM25_TOKEN_WINDOW_RRF
        return (
            fallback
            if PublicDemoCapabilityService._is_available(capabilities, fallback.value)
            else None
        )

    @staticmethod
    def _effective_context_default(
        capabilities: tuple[StrategyCapability, ...],
    ) -> GenerationContextStrategyName | None:
        whole_document = GenerationContextStrategyName.WHOLE_DOCUMENT
        return (
            whole_document
            if PublicDemoCapabilityService._is_available(capabilities, whole_document.value)
            else None
        )
