from __future__ import annotations

import json

import pytest

from scifact_rag.evaluation import (
    ComponentRevision,
    EvaluationPurpose,
    GenerationRunManifest,
    GeneratorSettings,
)


def _manifest(**overrides: object) -> GenerationRunManifest:
    values: dict[str, object] = {
        "schema_version": "generation-run-manifest/v1",
        "run_id": "generation-validation-20260914T120000Z",
        "repository_commit": "a" * 40,
        "corpus_sha256": "b" * 64,
        "evaluation_manifest_sha256": "c" * 64,
        "source_split": "train-validation",
        "purpose": EvaluationPurpose.DEFAULT_SELECTION,
        "retrieval_strategy": "pooled-coref-interval-colbert",
        "context_strategy": "adaptive",
        "retrieval_limit": 10,
        "components": (
            ComponentRevision("generator-model", "qwen", "qwen-revision"),
            ComponentRevision("embedding-model", "minilm", "minilm-revision"),
        ),
        "generator": GeneratorSettings(
            temperature=0.1,
            maximum_answer_tokens=512,
            thinking_enabled=False,
        ),
        "started_at": "2026-09-14T12:00:00Z",
        "completed_at": None,
        "host": "spark-3a8f",
        "results_path": "artifacts/generation-validation/results.jsonl",
        "test_qrels_inspected": True,
    }
    values.update(overrides)
    return GenerationRunManifest(**values)  # type: ignore[arg-type]


def test_generation_run_manifest_emits_canonical_json() -> None:
    manifest = _manifest()

    payload = manifest.to_json()

    assert payload.endswith("\n")
    assert json.loads(payload) == {
        "completed_at": None,
        "components": [
            {
                "component": "embedding-model",
                "identifier": "minilm",
                "revision": "minilm-revision",
            },
            {
                "component": "generator-model",
                "identifier": "qwen",
                "revision": "qwen-revision",
            },
        ],
        "context_strategy": "adaptive",
        "corpus_sha256": "b" * 64,
        "evaluation_manifest_sha256": "c" * 64,
        "generator": {
            "maximum_answer_tokens": 512,
            "temperature": 0.1,
            "thinking_enabled": False,
        },
        "host": "spark-3a8f",
        "purpose": "default-selection",
        "repository_commit": "a" * 40,
        "results_path": "artifacts/generation-validation/results.jsonl",
        "retrieval_limit": 10,
        "retrieval_strategy": "pooled-coref-interval-colbert",
        "run_id": "generation-validation-20260914T120000Z",
        "schema_version": "generation-run-manifest/v1",
        "source_split": "train-validation",
        "started_at": "2026-09-14T12:00:00Z",
        "test_qrels_inspected": True,
    }


def test_generation_run_manifest_round_trips_only_complete_known_fields() -> None:
    original = _manifest()

    restored = GenerationRunManifest.from_json(original.to_json())

    assert restored == original

    incomplete = json.loads(original.to_json())
    del incomplete["repository_commit"]
    with pytest.raises(ValueError, match="fields do not match"):
        GenerationRunManifest.from_json(json.dumps(incomplete))

    unknown = json.loads(original.to_json())
    unknown["untracked_setting"] = True
    with pytest.raises(ValueError, match="fields do not match"):
        GenerationRunManifest.from_json(json.dumps(unknown))


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"repository_commit": "not-a-commit"}, "repository_commit"),
        ({"corpus_sha256": "short"}, "corpus_sha256"),
        ({"retrieval_limit": 0}, "retrieval_limit"),
        ({"results_path": "/tmp/results.jsonl"}, "results_path"),
        ({"started_at": "2026-09-14T12:00:00-04:00"}, "started_at"),
        ({"components": ()}, "components"),
    ],
)
def test_generation_run_manifest_rejects_non_reproducible_values(
    override: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _manifest(**override)


def test_default_selection_cannot_use_the_inspected_test_qrels() -> None:
    with pytest.raises(ValueError, match="inspected test qrels"):
        _manifest(source_split="test")


def test_component_names_are_unique() -> None:
    with pytest.raises(ValueError, match="component names must be unique"):
        _manifest(
            components=(
                ComponentRevision("generator-model", "qwen", "first"),
                ComponentRevision("generator-model", "qwen", "second"),
            )
        )


@pytest.mark.parametrize(
    "settings",
    [
        {"temperature": "0.1", "maximum_answer_tokens": 512, "thinking_enabled": False},
        {"temperature": 0.1, "maximum_answer_tokens": True, "thinking_enabled": False},
        {"temperature": 0.1, "maximum_answer_tokens": 512, "thinking_enabled": 0},
    ],
)
def test_generator_settings_reject_wrong_python_types(settings: dict[str, object]) -> None:
    with pytest.raises(TypeError):
        GeneratorSettings(**settings)  # type: ignore[arg-type]


def test_manifest_json_rejects_a_non_object_document() -> None:
    with pytest.raises(TypeError, match="JSON object"):
        GenerationRunManifest.from_json("[]")
