"""Strict contracts and analysis helpers for the development-only reviewer pilot."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

AGENT_REVIEW_SCHEMA = "generation-agent-review-envelope/v1"
ADEQUACY_SCHEMA = "generation-agent-adequacy/v1"
REVIEW_V2_SCHEMA = "generation-human-review/v2"
ROLES = {"r1", "r2", "adjudicator"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RESPONSE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

ENVELOPE_FIELDS = {
    "adequacy",
    "provenance",
    "rationale",
    "response_id",
    "review_v2",
    "role",
    "schema_version",
}
REVIEW_FIELDS = {
    "causal_strengthening",
    "comparison_omission",
    "grounded",
    "intervention_omission",
    "material_errors",
    "material_overstatement",
    "negation_omission",
    "notes",
    "outcome_omission",
    "population_generalization",
    "population_omission",
    "qualifier_omission",
}
TRISTATE_FIELDS = {
    "causal_strengthening",
    "comparison_omission",
    "intervention_omission",
    "negation_omission",
    "outcome_omission",
    "population_generalization",
    "population_omission",
    "qualifier_omission",
}
TRISTATE_OPTIONS = {"yes", "no", "not_applicable", "uncertain"}
MATERIAL_CATEGORIES = {
    "causal_strengthening",
    "comparison_change",
    "intervention_change",
    "negation_loss",
    "outcome_change",
    "population_generalization",
    "qualifier_loss",
    "unsupported_claim",
}
MATERIAL_ERROR_FIELDS = {"answer_span", "category", "evidence_absent", "evidence_spans"}
ADEQUACY_FIELDS = {
    "answer_adequacy",
    "insufficiency_handling",
    "rationale",
    "supplied_context_answerability",
}
RATIONALE_FIELDS = {"answer_quotes", "evidence_quotes", "summary"}
EVIDENCE_QUOTE_FIELDS = {"document_id", "quote"}
PROVENANCE_FIELDS = {
    "input_sha256",
    "latency_ms",
    "model",
    "model_revision",
    "prompt_sha256",
    "prompt_version",
    "provider",
    "raw_output",
    "raw_output_sha256",
    "request_id",
    "rubric_sha256",
    "rubric_version",
    "session_id",
    "submitted_at",
    "usage",
}
USAGE_FIELDS = {"input_tokens", "output_tokens", "total_tokens"}


class AgentReviewValidationError(ValueError):
    """An agent-review artifact violates the frozen pilot contract."""


def _strict_object(
    value: object, expected: set[str], location: str, errors: list[str]
) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        errors.append(f"{location} must be an object")
        return None
    missing = expected - set(value)
    extras = set(value) - expected
    if missing:
        errors.append(f"{location} is missing fields: {', '.join(sorted(missing))}")
    if extras:
        errors.append(f"{location} has unexpected fields: {', '.join(sorted(extras))}")
    return value


def _nonempty_text(value: object, location: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{location} must be non-empty text")


def _nullable_nonempty_text(value: object, location: str, errors: list[str]) -> None:
    if value is not None:
        _nonempty_text(value, location, errors)


def _sha256(value: object, location: str, errors: list[str]) -> None:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        errors.append(f"{location} must be a lowercase SHA-256 digest")


def _span(
    value: object,
    text: object,
    location: str,
    errors: list[str],
    *,
    evidence: bool = False,
) -> None:
    expected = {"evidence_index", "start", "end"} if evidence else {"start", "end"}
    item = _strict_object(value, expected, location, errors)
    if item is None:
        return
    start = item.get("start")
    end = item.get("end")
    if (
        isinstance(start, bool)
        or not isinstance(start, int)
        or isinstance(end, bool)
        or not isinstance(end, int)
        or not isinstance(text, str)
        or not 0 <= start < end <= len(text)
    ):
        errors.append(f"{location} must satisfy 0 <= start < end <= text length")


def _validate_review(review: object, source: Mapping[str, Any], errors: list[str]) -> None:
    item = _strict_object(review, REVIEW_FIELDS, "review_v2", errors)
    if item is None:
        return
    for field in TRISTATE_FIELDS:
        if item.get(field) not in TRISTATE_OPTIONS:
            errors.append(f"review_v2.{field} is invalid")
    if item.get("grounded") not in {"yes", "no", "uncertain"}:
        errors.append("review_v2.grounded is invalid")
    if item.get("material_overstatement") not in {"none", "present", "uncertain"}:
        errors.append("review_v2.material_overstatement is invalid")
    if not isinstance(item.get("notes"), str):
        errors.append("review_v2.notes must be text")

    annotations = item.get("material_errors")
    if not isinstance(annotations, list):
        errors.append("review_v2.material_errors must be a list")
        return
    evidence_items = source.get("evidence")
    evidence_rows = evidence_items if isinstance(evidence_items, list) else []
    for index, annotation in enumerate(annotations):
        location = f"review_v2.material_errors[{index}]"
        error = _strict_object(annotation, MATERIAL_ERROR_FIELDS, location, errors)
        if error is None:
            continue
        if error.get("category") not in MATERIAL_CATEGORIES:
            errors.append(f"{location}.category is invalid")
        _span(error.get("answer_span"), source.get("answer"), f"{location}.answer_span", errors)
        evidence_absent = error.get("evidence_absent")
        spans = error.get("evidence_spans")
        if not isinstance(evidence_absent, bool):
            errors.append(f"{location}.evidence_absent must be a boolean")
        if not isinstance(spans, list):
            errors.append(f"{location}.evidence_spans must be a list")
            continue
        if bool(spans) == (evidence_absent is True):
            errors.append(f"{location} must use evidence spans or evidence_absent=true")
        for span_index, span in enumerate(spans):
            span_location = f"{location}.evidence_spans[{span_index}]"
            if not isinstance(span, Mapping):
                _span(span, None, span_location, errors, evidence=True)
                continue
            evidence_index = span.get("evidence_index")
            if (
                isinstance(evidence_index, bool)
                or not isinstance(evidence_index, int)
                or not 0 <= evidence_index < len(evidence_rows)
            ):
                errors.append(f"{span_location}.evidence_index is out of bounds")
                continue
            evidence_row = evidence_rows[evidence_index]
            text = evidence_row.get("text") if isinstance(evidence_row, Mapping) else None
            _span(span, text, span_location, errors, evidence=True)


def _validate_adequacy(value: object, errors: list[str]) -> None:
    item = _strict_object(value, ADEQUACY_FIELDS, "adequacy", errors)
    if item is None:
        return
    answerability = item.get("supplied_context_answerability")
    adequacy = item.get("answer_adequacy")
    if answerability not in {"answerable", "not_answerable", "uncertain"}:
        errors.append("adequacy.supplied_context_answerability is invalid")
    if adequacy not in {"adequate", "inadequate", "uncertain", "not_applicable"}:
        errors.append("adequacy.answer_adequacy is invalid")
    if answerability == "answerable" and adequacy == "not_applicable":
        errors.append("adequacy.answer_adequacy must be assessed when context is answerable")
    if answerability != "answerable" and adequacy != "not_applicable":
        errors.append("adequacy.answer_adequacy must be not_applicable unless context is answerable")
    if item.get("insufficiency_handling") not in {
        "appropriate",
        "inappropriate",
        "not_applicable",
        "uncertain",
    }:
        errors.append("adequacy.insufficiency_handling is invalid")
    if not isinstance(item.get("rationale"), str):
        errors.append("adequacy.rationale must be text")


def _validate_rationale(
    value: object, source: Mapping[str, Any], errors: list[str]
) -> None:
    item = _strict_object(value, RATIONALE_FIELDS, "rationale", errors)
    if item is None:
        return
    _nonempty_text(item.get("summary"), "rationale.summary", errors)
    answer_quotes = item.get("answer_quotes")
    if not isinstance(answer_quotes, list) or not answer_quotes:
        errors.append("rationale.answer_quotes must be a non-empty list")
    else:
        answer = source.get("answer")
        for index, quote in enumerate(answer_quotes):
            if not isinstance(quote, str) or not quote or not isinstance(answer, str) or quote not in answer:
                errors.append(f"rationale.answer quote {index} is not exact")
    evidence_quotes = item.get("evidence_quotes")
    if not isinstance(evidence_quotes, list) or not evidence_quotes:
        errors.append("rationale.evidence_quotes must be a non-empty list")
        return
    evidence = source.get("evidence")
    evidence_rows = evidence if isinstance(evidence, list) else []
    evidence_by_id = {
        row.get("document_id"): row.get("text")
        for row in evidence_rows
        if isinstance(row, Mapping)
    }
    for index, evidence_quote in enumerate(evidence_quotes):
        location = f"rationale.evidence_quotes[{index}]"
        quote_item = _strict_object(evidence_quote, EVIDENCE_QUOTE_FIELDS, location, errors)
        if quote_item is None:
            continue
        document_id = quote_item.get("document_id")
        quote = quote_item.get("quote")
        text = evidence_by_id.get(document_id)
        if not isinstance(quote, str) or not quote or not isinstance(text, str) or quote not in text:
            errors.append(f"{location}.quote is not exact for the named document")


def _validate_provenance(value: object, errors: list[str]) -> None:
    item = _strict_object(value, PROVENANCE_FIELDS, "provenance", errors)
    if item is None:
        return
    for field in ("provider", "model", "prompt_version", "rubric_version", "session_id"):
        _nonempty_text(item.get(field), f"provenance.{field}", errors)
    for field in ("model_revision", "request_id"):
        _nullable_nonempty_text(item.get(field), f"provenance.{field}", errors)
    for field in ("input_sha256", "prompt_sha256", "raw_output_sha256", "rubric_sha256"):
        _sha256(item.get(field), f"provenance.{field}", errors)
    raw_output = item.get("raw_output")
    _nonempty_text(raw_output, "provenance.raw_output", errors)
    if isinstance(raw_output, str) and hashlib.sha256(raw_output.encode()).hexdigest() != item.get(
        "raw_output_sha256"
    ):
        errors.append("provenance.raw_output_sha256 does not match raw_output")
    submitted_at = item.get("submitted_at")
    if not isinstance(submitted_at, str):
        errors.append("provenance.submitted_at must be an ISO-8601 timestamp with timezone")
    else:
        try:
            parsed = datetime.fromisoformat(submitted_at)
            if parsed.tzinfo is None:
                raise ValueError
        except ValueError:
            errors.append("provenance.submitted_at must be an ISO-8601 timestamp with timezone")
    latency = item.get("latency_ms")
    if latency is not None and (
        isinstance(latency, bool) or not isinstance(latency, (int, float)) or latency < 0
    ):
        errors.append("provenance.latency_ms must be unavailable or non-negative")
    usage = _strict_object(item.get("usage"), USAGE_FIELDS, "provenance.usage", errors)
    if usage is not None:
        for field in USAGE_FIELDS:
            count = usage.get(field)
            if count is not None and (
                isinstance(count, bool) or not isinstance(count, int) or count < 0
            ):
                errors.append(f"provenance.usage.{field} must be unavailable or non-negative")


def validate_agent_review(
    value: object, source_row: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate one attributable agent judgment against its exact source row."""
    errors: list[str] = []
    item = _strict_object(value, ENVELOPE_FIELDS, "agent review", errors)
    if item is None:
        raise AgentReviewValidationError("; ".join(errors))
    if item.get("schema_version") != AGENT_REVIEW_SCHEMA:
        errors.append(f"schema_version must be {AGENT_REVIEW_SCHEMA}")
    response_id = item.get("response_id")
    if not isinstance(response_id, str) or RESPONSE_ID_PATTERN.fullmatch(response_id) is None:
        errors.append("response_id must be a random-128-bit/v1 lowercase identifier")
    if response_id != source_row.get("response_id"):
        errors.append("response_id does not match the source row")
    if item.get("role") not in ROLES:
        errors.append("role must be r1, r2, or adjudicator")
    _validate_review(item.get("review_v2"), source_row, errors)
    _validate_adequacy(item.get("adequacy"), errors)
    _validate_rationale(item.get("rationale"), source_row, errors)
    _validate_provenance(item.get("provenance"), errors)
    if errors:
        raise AgentReviewValidationError("; ".join(errors))
    return dict(item)


def canonical_json_sha256(value: object) -> str:
    """Digest canonical newline-terminated JSON used by pilot artifacts."""
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(encoded).hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _review_answer_candidates(result: Mapping[str, Any]) -> set[str]:
    candidates = {answer for answer in (result.get("answer_text"),) if isinstance(answer, str)}
    raw = result.get("raw_generated_text")
    if isinstance(raw, str):
        first_line, separator, remainder = raw.partition("\n")
        if separator and re.fullmatch(
            r"VERDICT: (?:SUPPORT|CONTRADICT|NOT_ENOUGH_INFO)", first_line.strip()
        ):
            candidates.add(remainder.strip())
    return candidates


def build_source_inventory(
    worksheet: Mapping[str, Any],
    mapping: Mapping[str, Any],
    results_bytes: bytes,
    *,
    worksheet_sha256: str,
    mapping_sha256: str,
) -> dict[str, Any]:
    """Reconcile the retained worksheet, opaque map, and raw result stream."""
    rows = worksheet.get("rows")
    mapping_rows = mapping.get("rows")
    if not isinstance(rows, list) or not isinstance(mapping_rows, list):
        raise AgentReviewValidationError("worksheet and mapping rows must be lists")
    if len(rows) != len(mapping_rows) or not rows:
        raise AgentReviewValidationError("worksheet and mapping must have the same non-zero rows")
    if mapping.get("result_sha256") != _bytes_sha256(results_bytes):
        raise AgentReviewValidationError("result stream digest does not match the opaque map")

    results_by_sha: dict[str, Mapping[str, Any]] = {}
    for line_number, line in enumerate(results_bytes.splitlines(), start=1):
        line_sha256 = _bytes_sha256(line)
        if line_sha256 in results_by_sha:
            raise AgentReviewValidationError("result stream contains repeated rows")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AgentReviewValidationError(
                f"result stream line {line_number} is not valid JSON"
            ) from exc
        if not isinstance(record, Mapping) or not isinstance(record.get("result"), Mapping):
            raise AgentReviewValidationError(f"result stream line {line_number} is malformed")
        results_by_sha[line_sha256] = record["result"]

    source_by_id = {
        row.get("response_id"): row for row in rows if isinstance(row, Mapping)
    }
    if len(source_by_id) != len(rows) or None in source_by_id:
        raise AgentReviewValidationError("worksheet response IDs must be present and unique")
    inventory_rows: list[dict[str, Any]] = []
    seen_mapping_ids: set[str] = set()
    for map_index, map_row in enumerate(mapping_rows):
        if not isinstance(map_row, Mapping):
            raise AgentReviewValidationError(f"mapping row {map_index} must be an object")
        response_id = map_row.get("response_id")
        if not isinstance(response_id, str) or response_id in seen_mapping_ids:
            raise AgentReviewValidationError("mapping response IDs must be present and unique")
        seen_mapping_ids.add(response_id)
        source_row = source_by_id.get(response_id)
        if source_row is None:
            raise AgentReviewValidationError("mapping response IDs must exactly match the worksheet")
        result_line_sha256 = map_row.get("result_line_sha256")
        if not isinstance(result_line_sha256, str):
            raise AgentReviewValidationError("mapped result line digest is invalid")
        result = results_by_sha.get(result_line_sha256)
        if result is None:
            raise AgentReviewValidationError("mapped result line is missing or altered")
        if result.get("query_id") != map_row.get("query_id"):
            raise AgentReviewValidationError("mapped query ID does not match its result")
        if source_row.get("answer") not in _review_answer_candidates(result):
            raise AgentReviewValidationError("worksheet answer does not match its mapped result")
        evidence = source_row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise AgentReviewValidationError("worksheet evidence must be a non-empty list")
        document_ids = [
            item.get("document_id") if isinstance(item, Mapping) else None for item in evidence
        ]
        if any(not isinstance(document_id, str) for document_id in document_ids):
            raise AgentReviewValidationError("worksheet evidence document IDs are invalid")
        result_evidence = result.get("supplied_contexts")
        if not isinstance(result_evidence, list):
            raise AgentReviewValidationError("mapped result supplied contexts are invalid")
        normalized_result_evidence = [
            {
                "document_id": item.get("doc_id"),
                "text": item.get("text"),
                "title": item.get("title"),
            }
            if isinstance(item, Mapping)
            else None
            for item in result_evidence
        ]
        if evidence != normalized_result_evidence:
            raise AgentReviewValidationError("worksheet evidence does not match the mapped result")
        policies = map_row.get("equivalent_policies")
        if not isinstance(policies, list) or not policies or any(
            not isinstance(policy, str) or not policy for policy in policies
        ):
            raise AgentReviewValidationError("mapping equivalent policies are invalid")
        inventory_rows.append(
            {
                "answer_sha256": canonical_json_sha256(source_row.get("answer")),
                "claim_id": map_row.get("query_id"),
                "claim_sha256": canonical_json_sha256(source_row.get("claim")),
                "context_policies": policies,
                "document_ids": document_ids,
                "response_id": response_id,
                "result_line_sha256": result_line_sha256,
                "source_row_sha256": canonical_json_sha256(source_row),
            }
        )
    if seen_mapping_ids != set(source_by_id):
        raise AgentReviewValidationError("mapping response IDs must exactly match the worksheet")
    groups = build_article_family_groups(inventory_rows)
    group_rows = []
    by_id = {row["response_id"]: row for row in inventory_rows}
    for index, group in enumerate(groups, start=1):
        group_rows.append(
            {
                "article_family_group_id": f"afg-{index:03d}",
                "claim_ids": sorted({by_id[response_id]["claim_id"] for response_id in group}),
                "document_ids": sorted(
                    {
                        document_id
                        for response_id in group
                        for document_id in by_id[response_id]["document_ids"]
                    }
                ),
                "response_ids": list(group),
            }
        )
    return {
        "schema_version": "generation-review-pilot-inventory/v1",
        "source": {
            "mapping_sha256": mapping_sha256,
            "results_sha256": _bytes_sha256(results_bytes),
            "worksheet_sha256": worksheet_sha256,
        },
        "rows": inventory_rows,
        "article_family_groups": group_rows,
    }


def build_review_v2_worksheet(
    source_worksheet: Mapping[str, Any],
    response_ids: Sequence[str],
    *,
    order_seed: str,
) -> dict[str, Any]:
    """Create a label-free, shuffled review-v2 worksheet from exposed source rows."""
    rows = source_worksheet.get("rows")
    if not isinstance(rows, list):
        raise AgentReviewValidationError("source worksheet rows must be a list")
    source_by_id = {
        row.get("response_id"): row for row in rows if isinstance(row, Mapping)
    }
    if len(response_ids) != len(set(response_ids)) or set(response_ids) - set(source_by_id):
        raise AgentReviewValidationError("requested response IDs must be unique source rows")
    selected = [source_by_id[response_id] for response_id in response_ids]
    random.Random(order_seed).shuffle(selected)
    blank_review = {
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
    }
    projected_rows = [
        {
            "answer": row.get("answer"),
            "claim": row.get("claim"),
            "evidence": row.get("evidence"),
            "response_id": row.get("response_id"),
            "review": dict(blank_review),
        }
        for row in selected
    ]
    return {
        "completed_at": None,
        "reviewer": None,
        "rows": projected_rows,
        "schema_version": REVIEW_V2_SCHEMA,
        "selection_protocol": "docs/project/generation-review-pilot-v1.md",
    }


def build_pilot_selection(
    inventory: Mapping[str, Any], clarification_group_ids: Sequence[str]
) -> dict[str, Any]:
    """Freeze a group-contained clarification/assessment split."""
    groups = inventory.get("article_family_groups")
    if not isinstance(groups, list) or not groups:
        raise AgentReviewValidationError("inventory article-family groups must be a non-empty list")
    group_by_id = {
        group.get("article_family_group_id"): group
        for group in groups
        if isinstance(group, Mapping)
        and isinstance(group.get("article_family_group_id"), str)
        and isinstance(group.get("response_ids"), list)
    }
    requested = list(clarification_group_ids)
    if len(requested) != len(set(requested)) or set(requested) - set(group_by_id):
        raise AgentReviewValidationError("clarification group IDs must be unique inventory groups")
    clarification_ids = [
        response_id
        for group_id in requested
        for response_id in group_by_id[group_id]["response_ids"]
    ]
    if len(clarification_ids) > 12:
        raise AgentReviewValidationError("clarification selection exceeds the 12-response ceiling")
    assessment_groups = [group_id for group_id in group_by_id if group_id not in set(requested)]
    assessment_ids = [
        response_id
        for group_id in assessment_groups
        for response_id in group_by_id[group_id]["response_ids"]
    ]
    if len(assessment_ids) > 48:
        raise AgentReviewValidationError("assessment selection exceeds the 48-response ceiling")
    return {
        "schema_version": "generation-review-pilot-selection/v1",
        "inventory_sha256": canonical_json_sha256(inventory),
        "clarification": {
            "article_family_group_ids": requested,
            "response_ids": clarification_ids,
        },
        "assessment": {
            "article_family_group_ids": assessment_groups,
            "response_ids": assessment_ids,
        },
    }


def project_agent_reviews(
    source_worksheet: Mapping[str, Any],
    reviews: Sequence[object],
    *,
    role: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project ordered agent envelopes into review-v2 plus a separate adequacy artifact."""
    if role not in ROLES:
        raise AgentReviewValidationError("role must be r1, r2, or adjudicator")
    source_rows = source_worksheet.get("rows")
    if not isinstance(source_rows, list):
        raise AgentReviewValidationError("source worksheet rows must be a list")
    source_ids = [row.get("response_id") if isinstance(row, Mapping) else None for row in source_rows]
    review_ids = [review.get("response_id") if isinstance(review, Mapping) else None for review in reviews]
    if review_ids != source_ids or len(set(review_ids)) != len(review_ids):
        raise AgentReviewValidationError("agent reviews must match the ordered response IDs exactly")

    projected_rows: list[dict[str, Any]] = []
    adequacy_rows: list[dict[str, Any]] = []
    for source_row, review in zip(source_rows, reviews, strict=True):
        if not isinstance(source_row, Mapping):
            raise AgentReviewValidationError("source worksheet rows must be objects")
        validated = validate_agent_review(review, source_row)
        if validated["role"] != role:
            raise AgentReviewValidationError("every agent review role must match the projection role")
        projected_row = dict(source_row)
        projected_row["review"] = validated["review_v2"]
        projected_rows.append(projected_row)
        adequacy_rows.append(
            {
                "response_id": validated["response_id"],
                **validated["adequacy"],
                "agent_review_sha256": canonical_json_sha256(validated),
            }
        )
    return (
        {
            "completed_at": None,
            "reviewer": f"agent-role:{role}",
            "rows": projected_rows,
            "schema_version": REVIEW_V2_SCHEMA,
            "selection_protocol": source_worksheet.get("selection_protocol"),
        },
        {"schema_version": ADEQUACY_SCHEMA, "role": role, "rows": adequacy_rows},
    )


def build_article_family_groups(rows: Sequence[Mapping[str, object]]) -> tuple[tuple[str, ...], ...]:
    """Group response IDs by connected claims or shared source document IDs."""
    identifiers: list[str] = []
    claims: list[str] = []
    documents: list[set[str]] = []
    for index, row in enumerate(rows):
        response_id = row.get("response_id")
        document_ids = row.get("document_ids")
        if not isinstance(response_id, str) or not isinstance(document_ids, list) or not document_ids:
            raise ValueError(f"inventory row {index} lacks response_id or document_ids")
        if any(not isinstance(document_id, str) or not document_id for document_id in document_ids):
            raise ValueError(f"inventory row {index} has invalid document_ids")
        claim_id = row.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise ValueError(f"inventory row {index} lacks claim_id")
        identifiers.append(response_id)
        claims.append(claim_id)
        documents.append(set(document_ids))
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("inventory response IDs must be unique")

    remaining = set(range(len(rows)))
    groups: list[tuple[str, ...]] = []
    while remaining:
        seed = min(remaining)
        component = {seed}
        frontier = [seed]
        remaining.remove(seed)
        while frontier:
            current = frontier.pop()
            linked = {
                candidate
                for candidate in remaining
                if claims[current] == claims[candidate] or documents[current] & documents[candidate]
            }
            for candidate in sorted(linked):
                remaining.remove(candidate)
                component.add(candidate)
                frontier.append(candidate)
        groups.append(tuple(identifiers[index] for index in sorted(component)))
    return tuple(groups)


@dataclass(frozen=True, slots=True)
class AgreementSummary:
    scheduled: int
    exact_agreements: int
    exact_agreement: float | None
    uncertain_or_missing: int
    resolved_rows: int
    resolved_binary_agreement: float | None
    positive_agreement: float | None
    negative_agreement: float | None

    def to_dict(self) -> dict[str, int | float | None]:
        return asdict(self)


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def agreement_summary(
    left: Sequence[str | None],
    right: Sequence[str | None],
    *,
    positive: str,
    negative: str,
) -> AgreementSummary:
    """Calculate frozen all-row and resolved binary reviewer agreement."""
    if len(left) != len(right) or not left:
        raise ValueError("reviewer judgments must be non-empty and aligned")
    scheduled = len(left)
    resolved_pairs = [
        (first, second)
        for first, second in zip(left, right, strict=True)
        if first in {positive, negative} and second in {positive, negative}
    ]
    a = sum(first == positive and second == positive for first, second in resolved_pairs)
    d = sum(first == negative and second == negative for first, second in resolved_pairs)
    b = sum(first == positive and second == negative for first, second in resolved_pairs)
    c = sum(first == negative and second == positive for first, second in resolved_pairs)
    exact_agreements = sum(
        first == second and first not in {None, "uncertain"}
        for first, second in zip(left, right, strict=True)
    )
    uncertain_or_missing = sum(
        first in {None, "uncertain"} or second in {None, "uncertain"}
        for first, second in zip(left, right, strict=True)
    )
    resolved_rows = len(resolved_pairs)
    resolved_agreements = a + d
    return AgreementSummary(
        scheduled=scheduled,
        exact_agreements=exact_agreements,
        exact_agreement=_ratio(exact_agreements, scheduled),
        uncertain_or_missing=uncertain_or_missing,
        resolved_rows=resolved_rows,
        resolved_binary_agreement=_ratio(resolved_agreements, resolved_rows),
        positive_agreement=_ratio(2 * a, 2 * a + b + c),
        negative_agreement=_ratio(2 * d, 2 * d + b + c),
    )


def percentage(value: float | None) -> str:
    """Render a finite agreement value without converting undefined values to zero."""
    if value is None:
        return "undefined"
    if not math.isfinite(value):
        raise ValueError("percentage value must be finite")
    return f"{value:.1%}"
