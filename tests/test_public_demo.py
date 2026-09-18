from __future__ import annotations

import pytest

from scifact_rag.generation import GenerationContextStrategyName
from scifact_rag.public_demo import (
    DependencyName,
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
