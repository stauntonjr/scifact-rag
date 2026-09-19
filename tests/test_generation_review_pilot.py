from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scifact_rag.generation_review_pilot import (
    AgentReviewValidationError,
    agreement_summary,
    build_article_family_groups,
    build_pilot_selection,
    build_review_v2_worksheet,
    build_source_inventory,
    project_agent_reviews,
    validate_agent_review,
)

RESPONSE_ID = "0123456789abcdef0123456789abcdef"


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
    raw_output = '{"judgment":"fixture"}'
    return {
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
            "population_generalization": "yes",
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
            "input_sha256": "a" * 64,
            "latency_ms": None,
            "model": "fixture-model",
            "model_revision": None,
            "prompt_sha256": "b" * 64,
            "prompt_version": "reviewer-r1/v1",
            "provider": "fixture-provider",
            "raw_output": raw_output,
            "raw_output_sha256": hashlib.sha256(raw_output.encode()).hexdigest(),
            "request_id": None,
            "rubric_sha256": "c" * 64,
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


def test_validate_agent_review_accepts_exact_source_bound_envelope() -> None:
    validated = validate_agent_review(_review(), _source_row())

    assert validated["response_id"] == RESPONSE_ID
    assert validated["review_v2"]["causal_strengthening"] == "yes"


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


def test_project_agent_reviews_emits_strict_review_v2_and_separate_adequacy() -> None:
    source = {
        "completed_at": None,
        "reviewer": None,
        "rows": [_source_row()],
        "schema_version": "generation-human-review/v2",
        "selection_protocol": "docs/project/generation-review-pilot-v1.md",
    }

    projected, adequacy = project_agent_reviews(source, [_review()], role="r1")
    expected_adequacy = _review()["adequacy"]
    assert isinstance(expected_adequacy, dict)

    assert projected["schema_version"] == "generation-human-review/v2"
    assert projected["reviewer"] == "agent-role:r1"
    assert projected["rows"][0]["review"]["population_generalization"] == "yes"
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
        project_agent_reviews(source, [_review(), _review()], role="r1")


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
    assert {row["response_id"] for row in worksheet["rows"]} == {
        RESPONSE_ID,
        "fedcba9876543210fedcba9876543210",
    }
    assert all(row["review"]["grounded"] is None for row in worksheet["rows"])


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
