from __future__ import annotations

import pytest

from scifact_rag.generation import GenerationContextStrategyName
from scifact_rag.public_demo import (
    CapabilitySnapshot,
    DependencyName,
    PublicDemoCapabilityService,
    PublicDemoSettings,
    context_dependencies,
    retrieval_dependencies,
)
from scifact_rag.strategies import RetrievalStrategyName


def test_public_demo_is_disabled_without_explicit_enablement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SCIFACT_PUBLIC_DEMO_ENABLED", raising=False)
    monkeypatch.delenv("SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN", raising=False)

    settings = PublicDemoSettings.from_environment()

    assert settings.enabled is False
    assert settings.pages_origin is None


def test_public_demo_accepts_exact_pages_origin_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCIFACT_PUBLIC_DEMO_ENABLED", "true")
    monkeypatch.setenv(
        "SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN",
        "https://stauntonjr.github.io",
    )

    settings = PublicDemoSettings.from_environment()

    assert settings.enabled is True
    assert settings.pages_origin == "https://stauntonjr.github.io"


@pytest.mark.parametrize("value", ["yes", "1", "TRUE ", "false ", "on"])
def test_public_demo_rejects_noncanonical_boolean(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("SCIFACT_PUBLIC_DEMO_ENABLED", value)

    with pytest.raises(ValueError, match="SCIFACT_PUBLIC_DEMO_ENABLED"):
        PublicDemoSettings.from_environment()


@pytest.mark.parametrize(
    "origin",
    [
        "http://stauntonjr.github.io",
        "https://stauntonjr.github.io/",
        "https://stauntonjr.github.io/path",
        "https://user:secret@stauntonjr.github.io",
        "*",
    ],
)
def test_public_demo_rejects_non_origin_pages_value(
    monkeypatch: pytest.MonkeyPatch,
    origin: str,
) -> None:
    monkeypatch.setenv("SCIFACT_PUBLIC_DEMO_ENABLED", "true")
    monkeypatch.setenv("SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN", origin)

    with pytest.raises(ValueError, match="SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN") as error:
        PublicDemoSettings.from_environment()

    assert "secret" not in str(error.value)


def test_every_authoritative_strategy_has_dependency_requirements() -> None:
    assert {
        strategy: retrieval_dependencies(strategy) for strategy in RetrievalStrategyName
    }.keys() == set(RetrievalStrategyName)
    assert {
        strategy: context_dependencies(strategy) for strategy in GenerationContextStrategyName
    }.keys() == set(GenerationContextStrategyName)


def test_hosted_retrieval_dependencies_are_explicit() -> None:
    assert retrieval_dependencies(RetrievalStrategyName.RERANK_MSMARCO) == frozenset(
        {DependencyName.RETRIEVAL_STORE, DependencyName.RERANKER}
    )
    assert retrieval_dependencies(RetrievalStrategyName.POOLED_COLBERT) == frozenset(
        {DependencyName.RETRIEVAL_STORE, DependencyName.LATE_INTERACTION}
    )
    assert retrieval_dependencies(
        RetrievalStrategyName.POOLED_COREF_INTERVAL_RANKZEPHYR
    ) == frozenset({DependencyName.RETRIEVAL_STORE, DependencyName.RANKLLM})
    assert retrieval_dependencies(RetrievalStrategyName.BM25) == frozenset(
        {DependencyName.RETRIEVAL_STORE}
    )


def test_generation_context_dependencies_are_explicit() -> None:
    assert context_dependencies(GenerationContextStrategyName.WHOLE_DOCUMENT) == frozenset()
    assert context_dependencies(GenerationContextStrategyName.ADAPTIVE) == frozenset(
        {DependencyName.LATE_INTERACTION}
    )
    assert context_dependencies(GenerationContextStrategyName.TOP_DP_CHUNKS) == frozenset(
        {DependencyName.LATE_INTERACTION}
    )


class RecordingProbe:
    def __init__(self, available: bool) -> None:
        self.result = available
        self.calls = 0

    def available(self) -> bool:
        self.calls += 1
        return self.result


def make_probes(available: bool = True) -> dict[DependencyName, RecordingProbe]:
    return {dependency: RecordingProbe(available) for dependency in DependencyName}


def test_capability_snapshot_reports_all_strategies_and_ready_defaults() -> None:
    probes = make_probes()

    snapshot = PublicDemoCapabilityService(probes).snapshot()

    assert isinstance(snapshot, CapabilitySnapshot)
    assert snapshot.status == "ready"
    assert snapshot.search.available is True
    assert snapshot.answer.available is True
    assert snapshot.effective_retrieval_default == RetrievalStrategyName(
        RetrievalStrategyName.POOLED_COREF_INTERVAL_CONTENT_MAX_COLBERT
    )
    assert snapshot.effective_context_default is GenerationContextStrategyName.WHOLE_DOCUMENT
    assert [item.name for item in snapshot.retrieval] == [
        strategy.value for strategy in RetrievalStrategyName
    ]
    assert [item.name for item in snapshot.context] == [
        strategy.value for strategy in GenerationContextStrategyName
    ]
    assert all(probe.calls == 1 for probe in probes.values())


def test_capability_snapshot_uses_bm25_fallback_when_default_colbert_is_unavailable() -> None:
    probes = make_probes()
    probes[DependencyName.LATE_INTERACTION].result = False

    snapshot = PublicDemoCapabilityService(probes).snapshot()

    assert snapshot.status == "degraded"
    assert snapshot.search.available is True
    assert snapshot.answer.available is True
    assert snapshot.effective_retrieval_default == RetrievalStrategyName.BM25_TOKEN_WINDOW_RRF
    default = next(
        item
        for item in snapshot.retrieval
        if item.name == RetrievalStrategyName.POOLED_COREF_INTERVAL_CONTENT_MAX_COLBERT.value
    )
    assert default.available is False
    assert default.reason == "late_interaction_unavailable"


def test_capability_snapshot_fails_closed_when_store_is_unavailable() -> None:
    probes = make_probes()
    probes[DependencyName.RETRIEVAL_STORE].result = False

    snapshot = PublicDemoCapabilityService(probes).snapshot()

    assert snapshot.status == "unavailable"
    assert snapshot.search.available is False
    assert snapshot.search.reason == "retrieval_store_unavailable"
    assert snapshot.answer.available is False
    assert snapshot.answer.reason == "retrieval_store_unavailable"
    assert snapshot.effective_retrieval_default is None


def test_capability_snapshot_reports_generator_loss_without_hiding_search() -> None:
    probes = make_probes()
    probes[DependencyName.GENERATOR].result = False

    snapshot = PublicDemoCapabilityService(probes).snapshot()

    assert snapshot.status == "degraded"
    assert snapshot.search.available is True
    assert snapshot.answer.available is False
    assert snapshot.answer.reason == "generator_unavailable"


def test_capability_probe_exception_fails_closed_without_exposing_exception() -> None:
    class FailingProbe(RecordingProbe):
        def available(self) -> bool:
            self.calls += 1
            raise RuntimeError("claim-secret")

    probes = make_probes()
    probes[DependencyName.RETRIEVAL_STORE] = FailingProbe(True)

    snapshot = PublicDemoCapabilityService(probes).snapshot()

    assert snapshot.search.reason == "retrieval_store_unavailable"
    assert "claim-secret" not in repr(snapshot)
