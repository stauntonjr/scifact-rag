from __future__ import annotations

import json

import pytest

from scifact_rag.evaluation import (
    ComponentRevision,
    EvaluationPurpose,
    GenerationEvaluationCase,
    GenerationEvaluationSet,
    GenerationRunManifest,
    GeneratorSettings,
    GoldRationale,
    ScientificStance,
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


def _case(
    query_id: str = "2",
    *,
    stance: ScientificStance = ScientificStance.CONTRADICT,
    rationales: tuple[GoldRationale, ...] = (
        GoldRationale(
            doc_id="13734012",
            label=ScientificStance.CONTRADICT,
            sentence_indices=(4,),
            sentences=("The measured prevalence was different.",),
        ),
    ),
) -> GenerationEvaluationCase:
    return GenerationEvaluationCase(
        schema_version="generation-evaluation-case/v1",
        query_id=query_id,
        claim="1 in 5 million in UK have abnormal PrP positivity.",
        source_split="train-validation",
        expected_stance=stance,
        cited_document_ids=("13734012",),
        rationales=rationales,
    )


def test_generation_evaluation_set_emits_sorted_canonical_jsonl_and_summary() -> None:
    support = GenerationEvaluationCase(
        schema_version="generation-evaluation-case/v1",
        query_id="9",
        claim="A supported claim.",
        source_split="train-validation",
        expected_stance=ScientificStance.SUPPORT,
        cited_document_ids=("20", "10"),
        rationales=(
            GoldRationale(
                doc_id="20",
                label=ScientificStance.SUPPORT,
                sentence_indices=(2, 3),
                sentences=("First evidence.", "Second evidence."),
            ),
        ),
    )
    no_evidence = _case(
        "0",
        stance=ScientificStance.NOT_ENOUGH_INFO,
        rationales=(),
    )

    evaluation_set = GenerationEvaluationSet((support, no_evidence))

    rows = [json.loads(line) for line in evaluation_set.to_jsonl().splitlines()]
    assert [row["query_id"] for row in rows] == ["0", "9"]
    assert rows[1]["cited_document_ids"] == ["10", "20"]
    assert rows[1]["rationales"][0]["sentence_indices"] == [2, 3]
    summary = evaluation_set.summary()
    assert summary.cases == 2
    assert summary.support == 1
    assert summary.contradict == 0
    assert summary.not_enough_info == 1
    assert summary.annotated_cases == 1
    assert summary.rationale_sets == 1
    assert summary.evidence_sentences == 2
    assert summary.sha256 == evaluation_set.sha256


def test_generation_evaluation_case_enforces_stance_and_rationale_consistency() -> None:
    with pytest.raises(ValueError, match="requires at least one rationale"):
        _case(rationales=())

    with pytest.raises(ValueError, match="must not have rationales"):
        _case(stance=ScientificStance.NOT_ENOUGH_INFO)

    with pytest.raises(ValueError, match="rationale label must match"):
        _case(
            stance=ScientificStance.SUPPORT,
            rationales=(
                GoldRationale(
                    doc_id="13734012",
                    label=ScientificStance.CONTRADICT,
                    sentence_indices=(4,),
                    sentences=("Evidence.",),
                ),
            ),
        )


def test_gold_rationale_rejects_invalid_sentence_alignment() -> None:
    with pytest.raises(ValueError, match="same non-zero length"):
        GoldRationale(
            doc_id="1",
            label=ScientificStance.SUPPORT,
            sentence_indices=(0,),
            sentences=(),
        )

    with pytest.raises(ValueError, match="strictly increasing"):
        GoldRationale(
            doc_id="1",
            label=ScientificStance.SUPPORT,
            sentence_indices=(1, 1),
            sentences=("One.", "One again."),
        )


def test_generation_evaluation_set_rejects_duplicates_and_mixed_splits() -> None:
    with pytest.raises(ValueError, match="query IDs must be unique"):
        GenerationEvaluationSet((_case(), _case()))

    development = GenerationEvaluationCase(
        schema_version="generation-evaluation-case/v1",
        query_id="3",
        claim="Development claim.",
        source_split="train-development",
        expected_stance=ScientificStance.NOT_ENOUGH_INFO,
        cited_document_ids=("1",),
        rationales=(),
    )
    with pytest.raises(ValueError, match="one source split"):
        GenerationEvaluationSet((_case(), development))
