from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from scifact_rag.evaluation import ComponentRevision
from scifact_rag.retrieval_evaluation import (
    RETRIEVAL_DEFAULT_STRATEGIES,
    RetrievalRunManifest,
    canonical_qrels_sha256,
    sha256_file,
)
from scifact_rag.strategies import RetrievalStrategyName


def _manifest(**overrides: object) -> RetrievalRunManifest:
    values: dict[str, object] = {
        "schema_version": "retrieval-run-manifest/v1",
        "run_id": "retrieval-validation-1",
        "repository_commit": "a" * 40,
        "corpus_sha256": "b" * 64,
        "queries_sha256": "c" * 64,
        "qrels_sha256": "d" * 64,
        "source_split": "train-validation",
        "evidence_class": "internal-comparative",
        "strategies": RETRIEVAL_DEFAULT_STRATEGIES,
        "cutoff": 10,
        "components": (
            ComponentRevision("vector-model", "minilm", "1"),
            ComponentRevision("application-image", "scifact-rag", "sha256:123"),
        ),
        "started_at": "2026-09-15T12:00:00Z",
        "completed_at": None,
        "host": "spark-3a8f",
        "results_path": "artifacts/retrieval-validation-1/results.jsonl",
        "test_qrels_inspected": True,
    }
    values.update(overrides)
    return RetrievalRunManifest(**values)  # type: ignore[arg-type]


def test_retrieval_run_manifest_emits_canonical_frozen_boundary() -> None:
    payload = json.loads(_manifest().to_json())

    assert set(payload) == {
        "schema_version",
        "run_id",
        "repository_commit",
        "corpus_sha256",
        "queries_sha256",
        "qrels_sha256",
        "source_split",
        "evidence_class",
        "strategies",
        "cutoff",
        "components",
        "started_at",
        "completed_at",
        "host",
        "results_path",
        "test_qrels_inspected",
    }
    assert payload["schema_version"] == "retrieval-run-manifest/v1"
    assert payload["source_split"] == "train-validation"
    assert payload["evidence_class"] == "internal-comparative"
    assert payload["strategies"] == [strategy.value for strategy in RETRIEVAL_DEFAULT_STRATEGIES]
    assert payload["cutoff"] == 10
    assert [item["component"] for item in payload["components"]] == [
        "application-image",
        "vector-model",
    ]
    assert _manifest().to_json().endswith("\n")


def test_retrieval_run_manifest_round_trips_canonical_json() -> None:
    manifest = _manifest(completed_at="2026-09-15T12:30:00Z")

    assert RetrievalRunManifest.from_json(manifest.to_json()) == manifest


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "retrieval-run-manifest/v2"),
        ("run_id", "../escape"),
        ("repository_commit", "A" * 40),
        ("corpus_sha256", "b" * 63),
        ("queries_sha256", "C" * 64),
        ("qrels_sha256", "not-a-digest"),
        ("source_split", "test"),
        ("evidence_class", "confirmation"),
        ("strategies", tuple(reversed(RETRIEVAL_DEFAULT_STRATEGIES))),
        ("cutoff", 20),
        ("components", ()),
        ("started_at", "2026-09-15 12:00:00"),
        ("completed_at", "2026-09-15T11:59:59Z"),
        ("host", "  "),
        ("results_path", "/tmp/results.jsonl"),
        ("results_path", "artifacts/../results.jsonl"),
        ("results_path", "artifacts/results.json"),
        ("test_qrels_inspected", False),
    ],
)
def test_retrieval_run_manifest_rejects_boundary_drift(field: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _manifest(**{field: value})


def test_retrieval_run_manifest_rejects_duplicate_components() -> None:
    component = ComponentRevision("application-image", "scifact-rag", "sha256:123")

    with pytest.raises(ValueError, match="unique"):
        _manifest(components=(component, replace(component, revision="sha256:456")))


@pytest.mark.parametrize("serialized", ["[]", "{}", '{"schema_version":"unknown"}'])
def test_retrieval_run_manifest_rejects_invalid_json_shape(serialized: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        RetrievalRunManifest.from_json(serialized)


def test_retrieval_run_manifest_rejects_unknown_strategy_on_parse() -> None:
    payload = json.loads(_manifest().to_json())
    payload["strategies"][0] = "unknown"

    with pytest.raises(ValueError):
        RetrievalRunManifest.from_json(json.dumps(payload))


def test_frozen_strategy_order_names_the_three_default_candidates() -> None:
    assert RETRIEVAL_DEFAULT_STRATEGIES == (
        RetrievalStrategyName.BM25_TOKEN_WINDOW_RRF,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_CONTENT_MAX_COLBERT,
    )


def test_qrels_digest_is_stable_across_mapping_order() -> None:
    left = {"2": {"20": 1, "10": 2}, "1": {"30": 1}}
    right = {"1": {"30": 1}, "2": {"10": 2, "20": 1}}

    assert canonical_qrels_sha256(left) == canonical_qrels_sha256(right)


def test_qrels_digest_preserves_relevance_grades() -> None:
    assert canonical_qrels_sha256({"1": {"10": 1}}) != canonical_qrels_sha256(
        {"1": {"10": 2}}
    )


@pytest.mark.parametrize(
    "qrels",
    [
        {},
        {"": {"10": 1}},
        {1: {"10": 1}},
        {"1": {"": 1}},
        {"1": {10: 1}},
        {"1": {"10": True}},
        {"1": {"10": 1.0}},
        {"1": {"10": -1}},
    ],
)
def test_qrels_digest_rejects_invalid_boundaries(qrels: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        canonical_qrels_sha256(qrels)  # type: ignore[arg-type]


def test_sha256_file_hashes_exact_bytes(tmp_path: Path) -> None:
    source = tmp_path / "data.jsonl"
    source.write_bytes(b"one\ntwo\n")

    assert sha256_file(source) == hashlib.sha256(b"one\ntwo\n").hexdigest()
