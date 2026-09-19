from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from scifact_rag.generation_review_pilot import (
    AgentReviewValidationError,
    agreement_summary,
    build_agent_review_envelope,
    build_article_family_groups,
    build_pilot_selection,
    build_presentation_order,
    build_review_v2_worksheet,
    build_source_inventory,
    project_agent_reviews,
    validate_agent_review,
)

RESPONSE_ID = "0123456789abcdef0123456789abcdef"


def _strict_review_module() -> ModuleType:
    path = Path(__file__).parents[1] / "tools" / "generation_review.py"
    spec = importlib.util.spec_from_file_location("strict_generation_review", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_row() -> dict[str, object]:
    return {
        "answer": "Treatment A causes improvement in all patients.",
        "claim": "Treatment A is associated with improvement in adults.",
        "evidence": [
            {
                "document_id": "12",
                "text": "Treatment A was associated with improvement in adults.",
                "title": "A controlled study",
            }
        ],
        "response_id": RESPONSE_ID,
        "review": {
            "causal_strengthening": None,
            "comparison_omission": None,
            "grounded": None,
            "intervention_omission": None,
            "material_errors": [],
            "material_overstatement": None,
            "negation_omission": None,
            "notes": None,
            "outcome_omission": None,
            "population_generalization": None,
            "population_omission": None,
            "qualifier_omission": None,
        },
    }


def _review(*, role: str = "r1") -> dict[str, object]:
    identities = {
        "r1": {
            "model": "gpt-5.6-sol",
            "prompt_sha256": "8cb970ec763e364cd1b20733a15258875c3f25522aba171311d79ecf7c17a325",
            "prompt_version": "preflight2-r1/v1",
        },
        "r2": {
            "model": "gpt-5.5",
            "prompt_sha256": "94f340a8507c2d4fdc7c368c8fae4c35f866facdc1077b32e462e4e9a1458612",
            "prompt_version": "preflight2-r2/v1",
        },
    }
    identity = identities[role]
    review: dict[str, object] = {
        "schema_version": "generation-agent-review-envelope/v1",
        "response_id": RESPONSE_ID,
        "role": role,
        "review_v2": {
            "causal_strengthening": "yes",
            "comparison_omission": "not_applicable",
            "grounded": "no",
            "intervention_omission": "not_applicable",
            "material_errors": [
                {
                    "answer_span": {"start": 12, "end": 18},
                    "category": "causal_strengthening",
                    "evidence_absent": False,
                    "evidence_spans": [{"evidence_index": 0, "start": 12, "end": 22}],
                }
            ],
            "material_overstatement": "present",
            "negation_omission": "not_applicable",
            "notes": "The answer changes association to causation.",
            "outcome_omission": "not_applicable",
            "population_generalization": "no",
            "population_omission": "not_applicable",
            "qualifier_omission": "no",
        },
        "adequacy": {
            "answer_adequacy": "inadequate",
            "insufficiency_handling": "not_applicable",
            "rationale": "The context supports a narrower associative answer.",
            "supplied_context_answerability": "answerable",
        },
        "rationale": {
            "answer_quotes": ["causes", "all patients"],
            "evidence_quotes": [
                {"document_id": "12", "quote": "associated with improvement in adults"}
            ],
            "summary": "Causation and population are stronger than the supplied evidence.",
        },
        "provenance": {
            "input_sha256": hashlib.sha256(
                (json.dumps(_source_row(), sort_keys=True, separators=(",", ":")) + "\n").encode()
            ).hexdigest(),
            "latency_ms": None,
            "model": identity["model"],
            "model_revision": None,
            "prompt_sha256": identity["prompt_sha256"],
            "prompt_version": identity["prompt_version"],
            "provider": "OpenAI-Codex-subscription",
            "raw_output": "",
            "raw_output_sha256": "",
            "request_id": None,
            "rubric_sha256": "773a0f254364a68585376a6315f95852814999d187dfd3ff4a4c7d6d6d3d045d",
            "rubric_version": "generation-review-pilot/v1",
            "session_id": "fixture-session",
            "submitted_at": "2026-09-19T15:00:00Z",
            "usage": {
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
            },
        },
    }
    judgment = {
        "review_v2": review["review_v2"],
        "adequacy": review["adequacy"],
        "rationale": review["rationale"],
    }
    raw_output = json.dumps(judgment, separators=(",", ":"))
    provenance = review["provenance"]
    assert isinstance(provenance, dict)
    provenance["raw_output"] = raw_output
    provenance["raw_output_sha256"] = hashlib.sha256(raw_output.encode()).hexdigest()
    return review


def _refresh_raw(review: dict[str, object]) -> None:
    judgment = {
        "review_v2": review["review_v2"],
        "adequacy": review["adequacy"],
        "rationale": review["rationale"],
    }
    raw_output = json.dumps(judgment, separators=(",", ":"))
    provenance = review["provenance"]
    assert isinstance(provenance, dict)
    provenance["raw_output"] = raw_output
    provenance["raw_output_sha256"] = hashlib.sha256(raw_output.encode()).hexdigest()


def test_validate_agent_review_accepts_exact_source_bound_envelope() -> None:
    validated = validate_agent_review(_review(), _source_row())

    assert validated["response_id"] == RESPONSE_ID
    assert validated["review_v2"]["causal_strengthening"] == "yes"


def test_build_agent_review_envelope_adds_provenance_and_validates() -> None:
    expected = _review()
    judgment = {
        "review_v2": expected["review_v2"],
        "adequacy": expected["adequacy"],
        "rationale": expected["rationale"],
    }
    raw_output = json.dumps(judgment, separators=(",", ":"))

    envelope = build_agent_review_envelope(
        judgment,
        _source_row(),
        role="r1",
        provider="OpenAI-Codex-subscription",
        model="gpt-5.6-sol",
        model_revision=None,
        session_id="fixture-session",
        request_id=None,
        submitted_at="2026-09-19T15:00:00Z",
        prompt_version="preflight2-r1/v1",
        prompt_sha256="8cb970ec763e364cd1b20733a15258875c3f25522aba171311d79ecf7c17a325",
        rubric_version="generation-review-pilot/v1",
        rubric_sha256="773a0f254364a68585376a6315f95852814999d187dfd3ff4a4c7d6d6d3d045d",
        raw_output=raw_output,
    )

    assert (
        envelope["provenance"]["raw_output_sha256"]
        == hashlib.sha256(raw_output.encode()).hexdigest()
    )
    assert (
        envelope["provenance"]["input_sha256"]
        == hashlib.sha256(
            (json.dumps(_source_row(), sort_keys=True, separators=(",", ":")) + "\n").encode()
        ).hexdigest()
    )


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda value: value.update({"unexpected": True}), "unexpected fields"),
        (
            lambda value: value["rationale"]["answer_quotes"].append("not in answer"),
            "answer quote",
        ),
        (
            lambda value: value["adequacy"].update(
                {
                    "supplied_context_answerability": "not_answerable",
                    "answer_adequacy": "adequate",
                }
            ),
            "not_applicable",
        ),
        (
            lambda value: value["provenance"].update({"raw_output_sha256": "d" * 64}),
            "raw_output_sha256",
        ),
    ],
)
def test_validate_agent_review_fails_closed(
    mutation: object,
    match: str,
) -> None:
    review = _review()
    assert callable(mutation)
    mutation(review)

    with pytest.raises(AgentReviewValidationError, match=match):
        validate_agent_review(review, _source_row())


def test_validate_agent_review_binds_source_raw_judgment_and_frozen_identity() -> None:
    wrong_source = _review()
    provenance = wrong_source["provenance"]
    assert isinstance(provenance, dict)
    provenance["input_sha256"] = "d" * 64
    with pytest.raises(AgentReviewValidationError, match="input_sha256"):
        validate_agent_review(wrong_source, _source_row())

    changed_judgment = _review()
    review_v2 = changed_judgment["review_v2"]
    assert isinstance(review_v2, dict)
    review_v2["notes"] = "Changed after raw output was frozen."
    with pytest.raises(AgentReviewValidationError, match="raw_output does not match"):
        validate_agent_review(changed_judgment, _source_row())

    changed_model = _review()
    changed_provenance = changed_model["provenance"]
    assert isinstance(changed_provenance, dict)
    changed_provenance["model"] = "replacement-model"
    with pytest.raises(AgentReviewValidationError, match="model does not match"):
        validate_agent_review(changed_model, _source_row())


def test_validate_agent_review_enforces_material_error_consistency() -> None:
    duplicate = _review()
    duplicate_review = duplicate["review_v2"]
    assert isinstance(duplicate_review, dict)
    material_errors = duplicate_review["material_errors"]
    assert isinstance(material_errors, list)
    material_errors.append(copy.deepcopy(material_errors[0]))
    _refresh_raw(duplicate)
    with pytest.raises(AgentReviewValidationError, match="duplicate material error"):
        validate_agent_review(duplicate, _source_row())

    missing_category = _review()
    missing_review = missing_category["review_v2"]
    assert isinstance(missing_review, dict)
    missing_review["material_errors"] = []
    _refresh_raw(missing_category)
    with pytest.raises(AgentReviewValidationError, match="matching material error"):
        validate_agent_review(missing_category, _source_row())

    clean_with_error = _review()
    clean_review = clean_with_error["review_v2"]
    assert isinstance(clean_review, dict)
    clean_review["causal_strengthening"] = "no"
    clean_review["grounded"] = "yes"
    clean_review["material_overstatement"] = "none"
    _refresh_raw(clean_with_error)
    with pytest.raises(AgentReviewValidationError, match="clean pass"):
        validate_agent_review(clean_with_error, _source_row())


def test_validate_agent_review_rejects_ambiguous_rationale_quotes() -> None:
    repeated_answer_source = _source_row()
    repeated_answer_source["answer"] = (
        "Treatment A causes improvement in all patients, but whether it causes durable "
        "improvement is unknown."
    )
    repeated_answer = _review()
    repeated_answer_provenance = repeated_answer["provenance"]
    assert isinstance(repeated_answer_provenance, dict)
    repeated_answer_provenance["input_sha256"] = hashlib.sha256(
        (json.dumps(repeated_answer_source, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()
    with pytest.raises(AgentReviewValidationError, match="answer quote 0 is ambiguous"):
        validate_agent_review(repeated_answer, repeated_answer_source)

    repeated_evidence_source = _source_row()
    repeated_evidence = repeated_evidence_source["evidence"]
    assert isinstance(repeated_evidence, list)
    repeated_evidence[0]["text"] = (
        "Treatment A was associated with improvement in adults; a second analysis was also "
        "associated with improvement in adults."
    )
    repeated_evidence_review = _review()
    repeated_evidence_provenance = repeated_evidence_review["provenance"]
    assert isinstance(repeated_evidence_provenance, dict)
    repeated_evidence_provenance["input_sha256"] = hashlib.sha256(
        (
            json.dumps(repeated_evidence_source, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
    ).hexdigest()
    with pytest.raises(AgentReviewValidationError, match="quote is ambiguous"):
        validate_agent_review(repeated_evidence_review, repeated_evidence_source)

    overlapping_source = _source_row()
    overlapping_source["answer"] = "Treatment A causes improvement in all patients. aaaa"
    overlapping_review = _review()
    overlapping_rationale = overlapping_review["rationale"]
    assert isinstance(overlapping_rationale, dict)
    overlapping_rationale["answer_quotes"] = ["aaa"]
    overlapping_provenance = overlapping_review["provenance"]
    assert isinstance(overlapping_provenance, dict)
    overlapping_provenance["input_sha256"] = hashlib.sha256(
        (json.dumps(overlapping_source, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()
    _refresh_raw(overlapping_review)
    with pytest.raises(AgentReviewValidationError, match="answer quote 0 is ambiguous"):
        validate_agent_review(overlapping_review, overlapping_source)


def test_validate_agent_review_rejects_bidirectional_judgment_contradictions() -> None:
    extra_category = _review()
    extra_review = extra_category["review_v2"]
    assert isinstance(extra_review, dict)
    extra_errors = extra_review["material_errors"]
    assert isinstance(extra_errors, list)
    population_error = copy.deepcopy(extra_errors[0])
    population_error["category"] = "population_generalization"
    population_error["answer_span"] = {"start": 34, "end": 46}
    extra_errors.append(population_error)
    _refresh_raw(extra_category)
    with pytest.raises(AgentReviewValidationError, match="contradicts top-level fields"):
        validate_agent_review(extra_category, _source_row())

    grounded_contradiction = _review()
    grounded_review = grounded_contradiction["review_v2"]
    assert isinstance(grounded_review, dict)
    grounded_review["grounded"] = "yes"
    grounded_review["material_overstatement"] = "none"
    _refresh_raw(grounded_contradiction)
    with pytest.raises(AgentReviewValidationError, match="material errors require grounded=no"):
        validate_agent_review(grounded_contradiction, _source_row())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("answer_adequacy", "inadequate"),
        ("answer_adequacy", "uncertain"),
        ("supplied_context_answerability", "uncertain"),
        ("insufficiency_handling", "inappropriate"),
        ("insufficiency_handling", "uncertain"),
    ],
)
def test_validate_agent_review_requires_nonpass_adequacy_rationale(field: str, value: str) -> None:
    review = _review()
    adequacy = review["adequacy"]
    assert isinstance(adequacy, dict)
    adequacy[field] = value
    if field == "supplied_context_answerability":
        adequacy["answer_adequacy"] = "not_applicable"
    adequacy["rationale"] = ""
    _refresh_raw(review)

    with pytest.raises(AgentReviewValidationError, match="rationale must be non-empty"):
        validate_agent_review(review, _source_row())


def test_project_agent_reviews_emits_strict_review_v2_and_separate_adequacy() -> None:
    source = {
        "completed_at": None,
        "reviewer": None,
        "rows": [_source_row()],
        "schema_version": "generation-human-review/v2",
        "selection_protocol": "docs/project/generation-review-pilot-v1.md",
    }

    projected, adequacy = project_agent_reviews(
        source,
        [_review()],
        role="r1",
    )
    expected_adequacy = _review()["adequacy"]
    assert isinstance(expected_adequacy, dict)

    assert projected["schema_version"] == "generation-human-review/v2"
    assert projected["reviewer"] == "agent-role:r1"
    assert projected["completed_at"] == "2026-09-19T15:00:00Z"
    assert projected["rows"][0]["review"]["causal_strengthening"] == "yes"
    _strict_review_module().validate_worksheet(projected, require_complete=True)
    assert adequacy == {
        "schema_version": "generation-agent-adequacy/v1",
        "role": "r1",
        "rows": [
            {
                "response_id": RESPONSE_ID,
                **expected_adequacy,
                "agent_review_sha256": hashlib.sha256(
                    (json.dumps(_review(), sort_keys=True, separators=(",", ":")) + "\n").encode()
                ).hexdigest(),
            }
        ],
    }


def test_project_agent_reviews_rejects_missing_reordered_and_repeated_ids() -> None:
    first = _source_row()
    second = copy.deepcopy(first)
    second["response_id"] = "fedcba9876543210fedcba9876543210"
    source = {
        "completed_at": None,
        "reviewer": None,
        "rows": [first, second],
        "schema_version": "generation-human-review/v2",
        "selection_protocol": "docs/project/generation-review-pilot-v1.md",
    }

    with pytest.raises(AgentReviewValidationError, match="ordered response IDs"):
        project_agent_reviews(source, [_review()], role="r1")
    with pytest.raises(AgentReviewValidationError, match="ordered response IDs"):
        project_agent_reviews(
            source,
            [_review(), _review()],
            role="r1",
        )


def test_article_family_groups_use_connected_source_components() -> None:
    rows = [
        {"response_id": "a", "claim_id": "c1", "document_ids": ["1", "2"]},
        {"response_id": "b", "claim_id": "c2", "document_ids": ["2", "3"]},
        {"response_id": "c", "claim_id": "c3", "document_ids": ["9"]},
        {"response_id": "d", "claim_id": "c3", "document_ids": ["10"]},
    ]

    groups = build_article_family_groups(rows)

    assert groups == (("a", "b"), ("c", "d"))


def test_source_inventory_reconciles_worksheet_map_and_raw_result_stream() -> None:
    source_row = _source_row()
    result = {
        "result": {
            "answer_text": source_row["answer"],
            "query_id": "claim-1",
            "supplied_contexts": [
                {
                    "doc_id": "12",
                    "text": "Treatment A was associated with improvement in adults.",
                    "title": "A controlled study",
                }
            ],
            "supplied_parent_ids": ["12"],
        }
    }
    result_line = json.dumps(result, separators=(",", ":")).encode()
    results_bytes = result_line + b"\n"
    worksheet = {"rows": [source_row]}
    mapping = {
        "result_sha256": hashlib.sha256(results_bytes).hexdigest(),
        "rows": [
            {
                "equivalent_policies": ["whole-document"],
                "query_id": "claim-1",
                "response_id": RESPONSE_ID,
                "result_line_sha256": hashlib.sha256(result_line).hexdigest(),
            }
        ],
    }

    inventory = build_source_inventory(
        worksheet,
        mapping,
        results_bytes,
        worksheet_sha256="a" * 64,
        mapping_sha256="b" * 64,
    )

    assert inventory["rows"][0]["document_ids"] == ["12"]
    assert inventory["article_family_groups"][0]["response_ids"] == [RESPONSE_ID]
    assert inventory["source"]["results_sha256"] == hashlib.sha256(results_bytes).hexdigest()


def test_source_inventory_rejects_altered_result_and_answer() -> None:
    source_row = _source_row()
    results_bytes = (
        b'{"result":{"answer_text":"changed","query_id":"claim-1",'
        b'"supplied_contexts":[{"doc_id":"12","text":"Treatment A was associated '
        b'with improvement in adults.","title":"A controlled study"}],'
        b'"supplied_parent_ids":["12"]}}\n'
    )
    line = results_bytes.rstrip(b"\n")
    mapping = {
        "result_sha256": hashlib.sha256(results_bytes).hexdigest(),
        "rows": [
            {
                "equivalent_policies": ["whole-document"],
                "query_id": "claim-1",
                "response_id": RESPONSE_ID,
                "result_line_sha256": hashlib.sha256(line).hexdigest(),
            }
        ],
    }

    with pytest.raises(AgentReviewValidationError, match="answer does not match"):
        build_source_inventory(
            {"rows": [source_row]},
            mapping,
            results_bytes,
            worksheet_sha256="a" * 64,
            mapping_sha256="b" * 64,
        )

    with pytest.raises(AgentReviewValidationError, match="digest"):
        build_source_inventory(
            {"rows": [source_row]},
            mapping,
            results_bytes + b" ",
            worksheet_sha256="a" * 64,
            mapping_sha256="b" * 64,
        )


def test_review_v2_worksheet_is_label_free_and_seeded() -> None:
    first = _source_row()
    first["review"] = {"grounded": "no"}
    second = copy.deepcopy(_source_row())
    second["response_id"] = "fedcba9876543210fedcba9876543210"

    worksheet = build_review_v2_worksheet(
        {"rows": [first, second]},
        [RESPONSE_ID, "fedcba9876543210fedcba9876543210"],
        order_seed="frozen-seed",
    )

    assert worksheet["schema_version"] == "generation-human-review/v2"
    expected_ids = [RESPONSE_ID, "fedcba9876543210fedcba9876543210"]
    assert [row["response_id"] for row in worksheet["rows"]] == sorted(expected_ids)
    assert all(row["review"]["grounded"] is None for row in worksheet["rows"])
    _strict_review_module().validate_worksheet(worksheet, require_complete=False)

    order = build_presentation_order(expected_ids, order_seed="frozen-seed")
    assert set(order["response_ids"]) == set(expected_ids)


def test_pilot_selection_keeps_groups_whole_and_enforces_clarification_ceiling() -> None:
    inventory = {
        "article_family_groups": [
            {"article_family_group_id": "afg-001", "response_ids": ["a", "b"]},
            {"article_family_group_id": "afg-002", "response_ids": ["c"]},
        ],
        "rows": [],
        "schema_version": "generation-review-pilot-inventory/v1",
        "source": {},
    }

    selection = build_pilot_selection(inventory, ["afg-002"])

    assert selection["clarification"]["response_ids"] == ["c"]
    assert selection["assessment"]["response_ids"] == ["a", "b"]

    inventory["article_family_groups"] = [
        {"article_family_group_id": "afg-001", "response_ids": [str(index) for index in range(13)]}
    ]
    with pytest.raises(AgentReviewValidationError, match="12-response ceiling"):
        build_pilot_selection(inventory, ["afg-001"])


def test_agreement_counts_uncertainty_as_nonagreement_and_keeps_resolved_coverage() -> None:
    summary = agreement_summary(
        ["yes", "no", "uncertain", "uncertain", "yes"],
        ["yes", "no", "uncertain", "yes", "no"],
        positive="yes",
        negative="no",
    )

    assert summary.scheduled == 5
    assert summary.exact_agreements == 2
    assert summary.exact_agreement == pytest.approx(0.4)
    assert summary.uncertain_or_missing == 2
    assert summary.resolved_rows == 3
    assert summary.resolved_binary_agreement == pytest.approx(2 / 3)
    assert summary.positive_agreement == pytest.approx(2 / 3)
    assert summary.negative_agreement == pytest.approx(2 / 3)


def test_agreement_reports_undefined_class_agreement() -> None:
    summary = agreement_summary(["no"], ["no"], positive="yes", negative="no")

    assert summary.positive_agreement is None
    assert summary.negative_agreement == 1.0
