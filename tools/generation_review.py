#!/usr/bin/env python3
"""Build and validate the offline SciFact generation-review worksheet."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION_V1 = "generation-human-review/v1"
SCHEMA_VERSION_V2 = "generation-human-review/v2"
SCHEMA_VERSION = SCHEMA_VERSION_V1
FROZEN_WORKSHEET_SHA256 = "f6a64a24a031ab4cf2cfc3764419ca37276c0d8174581e302d173e3bac72f0d2"
TOP_LEVEL_FIELDS = {"completed_at", "reviewer", "rows", "schema_version", "selection_protocol"}
ROW_FIELDS = {"answer", "claim", "evidence", "response_id", "review"}
EVIDENCE_FIELDS = {"document_id", "text", "title"}
REVIEW_OPTIONS = {
    "comparison_omission": {"yes", "no", "not_applicable", "uncertain"},
    "grounded": {"yes", "no", "uncertain"},
    "intervention_omission": {"yes", "no", "not_applicable", "uncertain"},
    "material_overstatement": {"none", "present", "uncertain"},
    "negation_omission": {"yes", "no", "not_applicable", "uncertain"},
    "outcome_omission": {"yes", "no", "not_applicable", "uncertain"},
    "population_omission": {"yes", "no", "not_applicable", "uncertain"},
    "qualifier_omission": {"yes", "no", "not_applicable", "uncertain"},
}
REVIEW_FIELDS = set(REVIEW_OPTIONS) | {"notes"}
REVIEW_OPTIONS_V2 = {
    **REVIEW_OPTIONS,
    "causal_strengthening": {"yes", "no", "not_applicable", "uncertain"},
    "population_generalization": {"yes", "no", "not_applicable", "uncertain"},
}
REVIEW_FIELDS_V2 = set(REVIEW_OPTIONS_V2) | {"material_errors", "notes"}
MATERIAL_ERROR_CATEGORIES = {
    "causal_strengthening",
    "comparison_change",
    "intervention_change",
    "negation_loss",
    "outcome_change",
    "population_generalization",
    "qualifier_loss",
    "unsupported_claim",
}
SPAN_FIELDS = {"end", "start"}
EVIDENCE_SPAN_FIELDS = {"end", "evidence_index", "start"}
MATERIAL_ERROR_FIELDS = {"answer_span", "category", "evidence_absent", "evidence_spans"}
MATERIAL_ERROR_CATEGORY_FIELDS = {
    "causal_strengthening": "causal_strengthening",
    "comparison_omission": "comparison_change",
    "intervention_omission": "intervention_change",
    "negation_omission": "negation_loss",
    "outcome_omission": "outcome_change",
    "population_generalization": "population_generalization",
    "population_omission": "population_generalization",
    "qualifier_omission": "qualifier_loss",
}
RESPONSE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class ReviewValidationError(ValueError):
    """The review artifact violates the frozen worksheet contract."""


def _unexpected(actual: object, expected: set[str], location: str, errors: list[str]) -> None:
    if not isinstance(actual, dict):
        errors.append(f"{location} must be an object")
        return
    extras = set(actual) - expected
    missing = expected - set(actual)
    if extras:
        errors.append(f"{location} has unexpected fields: {', '.join(sorted(extras))}")
    if missing:
        errors.append(f"{location} is missing fields: {', '.join(sorted(missing))}")


def _nonempty_text(value: object, location: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{location} must be non-empty text")


def _validate_span(
    value: object,
    text: object,
    location: str,
    errors: list[str],
    *,
    expected_fields: set[str] = SPAN_FIELDS,
) -> tuple[int, int] | None:
    _unexpected(value, expected_fields, location, errors)
    if not isinstance(value, dict):
        return None
    start = value.get("start")
    end = value.get("end")
    if (
        isinstance(start, bool)
        or not isinstance(start, int)
        or isinstance(end, bool)
        or not isinstance(end, int)
    ):
        errors.append(f"{location} offsets must be integers")
        return None
    if not isinstance(text, str) or not 0 <= start < end <= len(text):
        errors.append(f"{location} must satisfy 0 <= start < end <= text length")
        return None
    return start, end


def _validate_v2_material_errors(
    row: dict[str, Any],
    review: dict[str, Any],
    location: str,
    errors: list[str],
    *,
    require_complete: bool,
) -> None:
    annotations = review.get("material_errors")
    annotation_location = f"{location}.review.material_errors"
    if not isinstance(annotations, list):
        errors.append(f"{annotation_location} must be a list")
        return
    if not require_complete and annotations:
        errors.append(f"{annotation_location} must be empty in build input")

    evidence = row.get("evidence")
    evidence_items = evidence if isinstance(evidence, list) else []
    duplicate_keys: set[tuple[str, int, int]] = set()
    valid_categories: set[str] = set()
    for annotation_index, annotation in enumerate(annotations):
        item_location = f"{annotation_location}[{annotation_index}]"
        error_count = len(errors)
        _unexpected(annotation, MATERIAL_ERROR_FIELDS, item_location, errors)
        if not isinstance(annotation, dict):
            continue

        category = annotation.get("category")
        if category not in MATERIAL_ERROR_CATEGORIES:
            errors.append(f"{item_location}.category is invalid")
        answer_span = _validate_span(
            annotation.get("answer_span"),
            row.get("answer"),
            f"{item_location}.answer_span",
            errors,
        )

        evidence_absent = annotation.get("evidence_absent")
        if not isinstance(evidence_absent, bool):
            errors.append(f"{item_location}.evidence_absent must be a boolean")
        evidence_spans = annotation.get("evidence_spans")
        if not isinstance(evidence_spans, list):
            errors.append(f"{item_location}.evidence_spans must be a list")
            evidence_spans = []
        elif bool(evidence_spans) == (evidence_absent is True):
            errors.append(
                f"{item_location} must use exactly one of evidence_spans or evidence_absent=true"
            )

        for span_index, span in enumerate(evidence_spans):
            span_location = f"{item_location}.evidence_spans[{span_index}]"
            _unexpected(span, EVIDENCE_SPAN_FIELDS, span_location, errors)
            if not isinstance(span, dict):
                continue
            evidence_index = span.get("evidence_index")
            if (
                isinstance(evidence_index, bool)
                or not isinstance(evidence_index, int)
                or not 0 <= evidence_index < len(evidence_items)
            ):
                errors.append(f"{span_location}.evidence_index is out of bounds")
                continue
            evidence_item = evidence_items[evidence_index]
            evidence_text = evidence_item.get("text") if isinstance(evidence_item, dict) else None
            _validate_span(
                span,
                evidence_text,
                span_location,
                errors,
                expected_fields=EVIDENCE_SPAN_FIELDS,
            )

        if isinstance(category, str) and answer_span is not None:
            duplicate_key = (category, *answer_span)
            if duplicate_key in duplicate_keys:
                errors.append(f"{item_location} is a duplicate material error")
            duplicate_keys.add(duplicate_key)
        if len(errors) == error_count and isinstance(category, str):
            valid_categories.add(category)

    if not require_complete:
        return

    required_categories = {
        category
        for field, category in MATERIAL_ERROR_CATEGORY_FIELDS.items()
        if review.get(field) == "yes"
    }
    summary_nonpass = (
        review.get("grounded") == "no" or review.get("material_overstatement") == "present"
    )
    if summary_nonpass and not required_categories:
        required_categories.add("unsupported_claim")
    missing_categories = required_categories - valid_categories
    if missing_categories:
        errors.append(
            f"{location}.review requires a material error annotation; "
            "missing matching material error categories: " + ", ".join(sorted(missing_categories))
        )
    elif not required_categories and annotations:
        errors.append(f"{location}.review clean pass must not contain material errors")


def validate_worksheet(data: object, *, require_complete: bool) -> dict[str, Any]:
    """Validate a frozen blank worksheet or a completed human-review export."""
    errors: list[str] = []
    _unexpected(data, TOP_LEVEL_FIELDS, "worksheet", errors)
    if not isinstance(data, dict):
        raise ReviewValidationError("; ".join(errors))
    schema_version = data.get("schema_version")
    if schema_version == SCHEMA_VERSION_V1:
        review_options = REVIEW_OPTIONS
        review_fields = REVIEW_FIELDS
    elif schema_version == SCHEMA_VERSION_V2:
        review_options = REVIEW_OPTIONS_V2
        review_fields = REVIEW_FIELDS_V2
    else:
        errors.append(f"schema_version must be {SCHEMA_VERSION_V1} or {SCHEMA_VERSION_V2}")
        review_options = REVIEW_OPTIONS
        review_fields = REVIEW_FIELDS
    _nonempty_text(data.get("selection_protocol"), "selection_protocol", errors)
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        errors.append("rows must be a non-empty list")
        rows = []

    reviewer = data.get("reviewer")
    completed_at = data.get("completed_at")
    if require_complete:
        if not isinstance(reviewer, str) or not reviewer.strip():
            errors.append("reviewer is required")
        if not isinstance(completed_at, str) or not completed_at.strip():
            errors.append("completed_at is required")
        else:
            try:
                parsed = datetime.fromisoformat(completed_at)
                if parsed.tzinfo is None:
                    raise ValueError
            except ValueError:
                errors.append("completed_at must be an ISO-8601 timestamp with timezone")
    elif reviewer is not None or completed_at is not None:
        errors.append("build input must be the untouched incomplete worksheet")

    response_ids: list[str] = []
    incomplete_rows: list[int] = []
    for index, row in enumerate(rows):
        location = f"rows[{index}]"
        _unexpected(row, ROW_FIELDS, location, errors)
        if not isinstance(row, dict):
            continue
        _nonempty_text(row.get("answer"), f"{location}.answer", errors)
        _nonempty_text(row.get("claim"), f"{location}.claim", errors)
        response_id = row.get("response_id")
        if not isinstance(response_id, str) or not RESPONSE_ID_PATTERN.fullmatch(response_id):
            errors.append(f"{location}.response_id must be 32 lowercase hexadecimal characters")
        else:
            response_ids.append(response_id)

        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{location}.evidence must be a non-empty list")
        else:
            for evidence_index, item in enumerate(evidence):
                evidence_location = f"{location}.evidence[{evidence_index}]"
                _unexpected(item, EVIDENCE_FIELDS, evidence_location, errors)
                if not isinstance(item, dict):
                    continue
                for field in sorted(EVIDENCE_FIELDS):
                    _nonempty_text(item.get(field), f"{evidence_location}.{field}", errors)

        review = row.get("review")
        _unexpected(review, review_fields, f"{location}.review", errors)
        if not isinstance(review, dict):
            continue
        row_incomplete = False
        for field, allowed in review_options.items():
            value = review.get(field)
            if require_complete:
                if value not in allowed:
                    row_incomplete = True
            elif value is not None:
                errors.append(f"{location}.review.{field} must be null in build input")
        notes = review.get("notes")
        if require_complete:
            if not isinstance(notes, str):
                row_incomplete = True
        elif notes is not None:
            errors.append(f"{location}.review.notes must be null in build input")
        if schema_version == SCHEMA_VERSION_V2:
            _validate_v2_material_errors(
                row,
                review,
                location,
                errors,
                require_complete=require_complete,
            )
        if row_incomplete:
            incomplete_rows.append(index)

    if len(response_ids) != len(set(response_ids)):
        errors.append("response_id values must be unique")
    if response_ids != sorted(response_ids):
        errors.append("rows must be sorted by response_id")
    if require_complete and incomplete_rows:
        errors.append(
            "review fields are incomplete for rows: "
            + ", ".join(str(index) for index in incomplete_rows)
        )
    if errors:
        raise ReviewValidationError("; ".join(errors))
    return data


def load_worksheet(
    path: Path,
    *,
    require_complete: bool,
    expected_sha256: str | None = None,
    expected_rows: int = 42,
) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise ReviewValidationError(
            f"worksheet SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReviewValidationError(f"worksheet is not valid JSON: {exc}") from exc
    validated = validate_worksheet(data, require_complete=require_complete)
    if len(validated["rows"]) != expected_rows:
        raise ReviewValidationError(
            f"worksheet must contain exactly {expected_rows} rows, got {len(validated['rows'])}"
        )
    return validated, raw


RUBRIC_V1 = [
    [
        "grounded",
        "Grounded",
        "Is every material answer claim directly supported by the supplied evidence?",
        ["yes", "no", "uncertain"],
    ],
    [
        "material_overstatement",
        "Material overstatement",
        "Does the answer materially strengthen the evidence?",
        ["none", "present", "uncertain"],
    ],
    [
        "negation_omission",
        "Negation omission",
        "Is a material negation lost?",
        ["yes", "no", "not_applicable", "uncertain"],
    ],
    [
        "qualifier_omission",
        "Qualifier omission",
        "Is a material limitation or qualifier lost?",
        ["yes", "no", "not_applicable", "uncertain"],
    ],
    [
        "population_omission",
        "Population omission",
        "Is the studied population changed or omitted materially?",
        ["yes", "no", "not_applicable", "uncertain"],
    ],
    [
        "intervention_omission",
        "Intervention omission",
        "Is the intervention or exposure changed or omitted materially?",
        ["yes", "no", "not_applicable", "uncertain"],
    ],
    [
        "comparison_omission",
        "Comparison omission",
        "Is the comparator changed or omitted materially?",
        ["yes", "no", "not_applicable", "uncertain"],
    ],
    [
        "outcome_omission",
        "Outcome omission",
        "Is the measured outcome changed or omitted materially?",
        ["yes", "no", "not_applicable", "uncertain"],
    ],
]
RUBRIC_V2_ADDITIONS = [
    [
        "causal_strengthening",
        "Causal strengthening",
        "Does the answer strengthen association into causation or a stronger causal claim?",
        ["yes", "no", "not_applicable", "uncertain"],
    ],
    [
        "population_generalization",
        "Population generalization",
        "Does the answer extend the finding beyond the studied population or species?",
        ["yes", "no", "not_applicable", "uncertain"],
    ],
]


def _reviewer_config(schema_version: object) -> dict[str, object]:
    config: dict[str, object] = {
        "rubric": RUBRIC_V1,
        "material_error": None,
        "export_filename": "generation-validation-v2-human-review.completed.json",
    }
    if schema_version == SCHEMA_VERSION_V2:
        config["rubric"] = [*RUBRIC_V1, *RUBRIC_V2_ADDITIONS]
        config["material_error"] = {
            "categories": sorted(MATERIAL_ERROR_CATEGORIES),
            "category_fields": MATERIAL_ERROR_CATEGORY_FIELDS,
            "labels": {
                "add_error": "Add material error",
                "add_evidence": "Add evidence span",
                "answer_end": "Answer span end",
                "answer_start": "Answer span start",
                "category": "Error category",
                "evidence_absent": "Evidence absent",
                "evidence_end": "Evidence span end",
                "evidence_index": "Evidence item",
                "evidence_start": "Evidence span start",
                "heading": "Material error spans",
                "remove": "Remove",
            },
        }
        config["export_filename"] = "generation-fidelity-v2-human-review.completed.json"
    return config


BROWSER_VALIDATION_JAVASCRIPT = r"""
    function validateMaterialErrors(row, review, config) {
      if (!config) return [];
      const errors = [];
      const annotations = review.material_errors;
      if (!Array.isArray(annotations)) return ['material_errors must be a list'];
      const validCategories = new Set();
      const duplicateKeys = new Set();
      const boundedSpan = (span, text, location) => {
        const textLength = typeof text === 'string' ? Array.from(text).length : -1;
        if (!span || typeof span !== 'object'
            || !Number.isInteger(span.start) || !Number.isInteger(span.end)
            || span.start < 0 || span.start >= span.end || span.end > textLength) {
          errors.push(`${location} is invalid`);
          return false;
        }
        return true;
      };
      annotations.forEach((annotation, annotationIndex) => {
        const initialErrorCount = errors.length;
        const location = `material_errors[${annotationIndex}]`;
        if (!annotation || typeof annotation !== 'object') {
          errors.push(`${location} must be an object`);
          return;
        }
        if (!config.categories.includes(annotation.category)) {
          errors.push(`${location}.category is invalid`);
        }
        const answerValid = boundedSpan(annotation.answer_span, row.answer, `${location}.answer_span`);
        if (typeof annotation.evidence_absent !== 'boolean') {
          errors.push(`${location}.evidence_absent must be a boolean`);
        }
        const evidenceSpans = annotation.evidence_spans;
        if (!Array.isArray(evidenceSpans)) {
          errors.push(`${location}.evidence_spans must be a list`);
        } else {
          if ((evidenceSpans.length > 0) === (annotation.evidence_absent === true)) {
            errors.push(`${location} must use exactly one evidence mode`);
          }
          evidenceSpans.forEach((span, spanIndex) => {
            const spanLocation = `${location}.evidence_spans[${spanIndex}]`;
            if (!span || typeof span !== 'object'
                || !Number.isInteger(span.evidence_index)
                || span.evidence_index < 0 || span.evidence_index >= row.evidence.length) {
              errors.push(`${spanLocation}.evidence_index is invalid`);
              return;
            }
            boundedSpan(span, row.evidence[span.evidence_index].text, spanLocation);
          });
        }
        if (answerValid && typeof annotation.category === 'string') {
          const key = `${annotation.category}:${annotation.answer_span.start}:${annotation.answer_span.end}`;
          if (duplicateKeys.has(key)) errors.push(`${location} is a duplicate`);
          duplicateKeys.add(key);
        }
        if (errors.length === initialErrorCount) validCategories.add(annotation.category);
      });
      const requiredCategories = new Set();
      Object.entries(config.category_fields).forEach(([field, category]) => {
        if (review[field] === 'yes') requiredCategories.add(category);
      });
      const summaryNonpass = review.grounded === 'no' || review.material_overstatement === 'present';
      if (summaryNonpass && requiredCategories.size === 0) requiredCategories.add('unsupported_claim');
      const missing = [...requiredCategories].filter(category => !validCategories.has(category));
      if (missing.length) errors.push(`missing matching material error categories: ${missing.join(', ')}`);
      if (!requiredCategories.size && annotations.length) errors.push('clean pass must not contain material errors');
      return errors;
    }
"""


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; form-action 'none'; base-uri 'none'">
  <title>SciFact blinded generation review</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #172033;
      --muted: #5d6878;
      --paper: #fbfaf7;
      --card: #ffffff;
      --line: #d9ddd8;
      --accent: #126a5b;
      --accent-soft: #e6f3ef;
      --answer: #f4f0e8;
      --warn: #9a4d17;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--paper); color: var(--ink); line-height: 1.5; }
    button, input, select, textarea { font: inherit; }
    .topbar { position: sticky; top: 0; z-index: 10; background: rgba(251,250,247,.96); border-bottom: 1px solid var(--line); backdrop-filter: blur(8px); }
    .topbar-inner, main { width: min(1040px, calc(100% - 32px)); margin: 0 auto; }
    .topbar-inner { padding: 14px 0 12px; }
    .eyebrow { color: var(--accent); font-size: .74rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
    h1 { margin: 2px 0 8px; font-size: clamp(1.25rem, 3vw, 1.8rem); }
    .status-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; color: var(--muted); font-size: .9rem; }
    progress { width: min(360px, 100%); accent-color: var(--accent); }
    main { padding: 24px 0 80px; }
    .intro, .card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; box-shadow: 0 8px 24px rgba(28,39,35,.05); }
    .intro { padding: 18px 20px; margin-bottom: 18px; }
    .intro p { margin: 0; }
    .reviewer { display: grid; grid-template-columns: minmax(180px, 1fr) auto; gap: 12px; margin-top: 14px; align-items: end; }
    label > span, legend { font-weight: 750; }
    input[type=text], textarea { width: 100%; border: 1px solid #b8c0bd; border-radius: 9px; padding: 10px 12px; background: #fff; color: var(--ink); }
    input[type=text]:focus, textarea:focus { outline: 3px solid var(--accent-soft); border-color: var(--accent); }
    .card { padding: clamp(18px, 4vw, 30px); }
    .response-heading { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; margin-bottom: 18px; }
    .response-heading h2 { margin: 0; font-size: 1.1rem; }
    .response-id { color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .78rem; }
    .section { margin: 18px 0; }
    .section h3 { margin: 0 0 6px; font-size: .82rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
    .claim { font-size: 1.16rem; font-weight: 700; }
    .answer { padding: 15px 17px; background: var(--answer); border-left: 4px solid #a5854e; border-radius: 8px; white-space: pre-wrap; }
    .evidence-list { display: grid; gap: 12px; }
    .evidence { border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
    .evidence strong { display: block; margin-bottom: 4px; }
    .doc-id { color: var(--muted); font-size: .82rem; }
    .rubric { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 24px; }
    fieldset { min-width: 0; margin: 0; border: 1px solid var(--line); border-radius: 10px; padding: 12px; }
    legend { padding: 0 5px; }
    .question { color: var(--muted); font-size: .84rem; min-height: 2.6em; margin: 2px 0 10px; }
    .options { display: flex; flex-wrap: wrap; gap: 7px; }
    .option { cursor: pointer; }
    .option input { position: absolute; opacity: 0; pointer-events: none; }
    .option span { display: inline-block; padding: 7px 10px; border: 1px solid #b8c0bd; border-radius: 999px; font-size: .84rem; }
    .option input:checked + span { background: var(--accent); border-color: var(--accent); color: white; }
    .option input:focus-visible + span { outline: 3px solid var(--accent-soft); }
    .notes { grid-column: 1 / -1; }
    textarea { min-height: 92px; resize: vertical; margin-top: 8px; }
    .material-errors { grid-column: 1 / -1; border-top: 1px solid var(--line); padding-top: 18px; }
    .material-error { border: 1px solid var(--line); border-radius: 10px; padding: 14px; margin: 10px 0; }
    .material-error-grid, .evidence-span { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; align-items: end; }
    .material-error label, .evidence-span label { color: var(--muted); font-size: .82rem; }
    .material-error input[type=number], .material-error select { width: 100%; margin-top: 4px; border: 1px solid #b8c0bd; border-radius: 8px; padding: 8px; background: white; }
    .evidence-spans { display: grid; gap: 8px; margin: 12px 0; }
    .checkbox { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
    .controls { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 18px; flex-wrap: wrap; }
    .control-group { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    button { border: 1px solid #9da7a3; border-radius: 9px; padding: 9px 13px; background: white; color: var(--ink); cursor: pointer; font-weight: 700; }
    button.primary { background: var(--accent); color: white; border-color: var(--accent); }
    button:disabled { opacity: .45; cursor: not-allowed; }
    .message { min-height: 1.5em; color: var(--muted); font-size: .88rem; }
    .message.warn { color: var(--warn); }
    @media (max-width: 720px) {
      .rubric { grid-template-columns: 1fr; }
      .notes { grid-column: auto; }
      .reviewer, .material-error-grid, .evidence-span { grid-template-columns: 1fr; }
      .topbar-inner, main { width: min(100% - 20px, 1040px); }
    }
    @media print { .topbar, .controls, .intro { display: none; } body { background: white; } .card { box-shadow: none; border: 0; } }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="eyebrow">Blinded human review</div>
      <h1>SciFact answer groundedness</h1>
      <div class="status-row">
        <strong id="progress-text">0 of 0 responses complete</strong>
        <progress id="progress" value="0" max="1"></progress>
        <span id="save-state">Progress stays in this browser.</span>
      </div>
    </div>
  </header>
  <main>
    <section class="intro">
      <p>Judge only the claim, supplied evidence, and answer shown. Policy identity, expected stance, automatic scores, and aggregate results are intentionally absent.</p>
      <div class="reviewer">
        <label><span>Human reviewer name</span><input id="reviewer" type="text" autocomplete="name" placeholder="Required for export"></label>
        <button id="export" class="primary" disabled>Export completed review</button>
      </div>
      <div id="message" class="message" role="status" aria-live="polite"></div>
    </section>
    <article class="card" id="review-card"></article>
    <nav class="controls" aria-label="Response navigation">
      <div class="control-group">
        <button id="previous">Previous</button>
        <button id="next">Next</button>
      </div>
      <div class="control-group">
        <label for="jump"><strong>Go to</strong></label>
        <select id="jump"></select>
      </div>
    </nav>
  </main>
  <script id="worksheet-data" type="application/json">__WORKSHEET_JSON__</script>
  <script>
    'use strict';
__BROWSER_VALIDATION_JAVASCRIPT__
    const source = JSON.parse(document.getElementById('worksheet-data').textContent);
    const reviewConfig = __REVIEW_CONFIG__;
    const storageKey = '__STORAGE_KEY__';
    const sourceDigest = '__SOURCE_DIGEST__';
    const rubric = reviewConfig.rubric;
    const categoricalFields = rubric.map(([field]) => field);
    const materialErrorConfig = reviewConfig.material_error;
    const allowedByField = Object.fromEntries(rubric.map(([field,,, options]) => [field, new Set(options)]));
    let current = 0;
    let state = { reviewer: '', reviews: {} };
    const card = document.getElementById('review-card');
    const reviewer = document.getElementById('reviewer');
    const message = document.getElementById('message');
    const exportButton = document.getElementById('export');

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
    }
    function loadState() {
      try {
        const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
        state = normalizeState(saved);
      } catch (error) {
        message.textContent = 'Saved browser progress could not be read; export frequently.';
        message.className = 'message warn';
      }
      reviewer.value = state.reviewer || '';
    }
    function normalizeState(candidate) {
      const normalized = {
        reviewer: candidate && typeof candidate.reviewer === 'string' ? candidate.reviewer : '',
        reviews: {}
      };
      for (const row of source.rows) {
        const saved = candidate && candidate.reviews && candidate.reviews[row.response_id];
        if (!saved || typeof saved !== 'object') continue;
        const review = { notes: typeof saved.notes === 'string' ? saved.notes : '' };
        for (const field of categoricalFields) {
          if (allowedByField[field].has(saved[field])) review[field] = saved[field];
        }
        if (materialErrorConfig) {
          review.material_errors = Array.isArray(saved.material_errors)
            ? saved.material_errors.map(normalizeMaterialError).filter(Boolean)
            : [];
        }
        normalized.reviews[row.response_id] = review;
      }
      return normalized;
    }
    function integerOrZero(value) {
      return Number.isInteger(value) && value >= 0 ? value : 0;
    }
    function normalizeMaterialError(candidate) {
      if (!candidate || typeof candidate !== 'object') return null;
      const categories = materialErrorConfig.categories;
      const evidenceSpans = Array.isArray(candidate.evidence_spans) ? candidate.evidence_spans : [];
      return {
        category: categories.includes(candidate.category) ? candidate.category : categories[0],
        answer_span: {
          start: integerOrZero(candidate.answer_span && candidate.answer_span.start),
          end: integerOrZero(candidate.answer_span && candidate.answer_span.end)
        },
        evidence_spans: evidenceSpans.filter(span => span && typeof span === 'object').map(span => ({
          evidence_index: integerOrZero(span.evidence_index),
          start: integerOrZero(span.start),
          end: integerOrZero(span.end)
        })),
        evidence_absent: candidate.evidence_absent === true
      };
    }
    function saveState() {
      try {
        localStorage.setItem(storageKey, JSON.stringify(state));
        document.getElementById('save-state').textContent = 'Saved locally in this browser.';
      } catch (error) {
        document.getElementById('save-state').textContent = 'Browser storage unavailable; export before closing.';
        document.getElementById('save-state').className = 'warn';
      }
      updateProgress();
    }
    function reviewFor(row) {
      if (!state.reviews[row.response_id]) {
        state.reviews[row.response_id] = materialErrorConfig
          ? { notes: '', material_errors: [] }
          : { notes: '' };
      }
      return state.reviews[row.response_id];
    }
    function rowComplete(row) {
      const review = state.reviews[row.response_id] || {};
      return categoricalFields.every(field => allowedByField[field].has(review[field]))
        && (!materialErrorConfig
          || validateMaterialErrors(row, review, materialErrorConfig).length === 0);
    }
    function updateProgress() {
      const complete = source.rows.filter(rowComplete).length;
      const total = source.rows.length;
      document.getElementById('progress-text').textContent = `${complete} of ${total} responses complete`;
      const progress = document.getElementById('progress');
      progress.max = total;
      progress.value = complete;
      exportButton.disabled = complete !== total || !reviewer.value.trim();
      [...document.getElementById('jump').options].forEach((option, index) => {
        option.textContent = `${index + 1}. ${rowComplete(source.rows[index]) ? '✓' : '○'} ${source.rows[index].response_id}`;
      });
    }
    function evidenceSpanHtml(row, span, errorIndex, spanIndex) {
      const labels = materialErrorConfig.labels;
      const evidenceOptions = row.evidence.map((item, index) =>
        `<option value="${index}" ${span.evidence_index === index ? 'selected' : ''}>${index + 1}. ${escapeHtml(item.title)}</option>`
      ).join('');
      return `<div class="evidence-span">
        <label>${escapeHtml(labels.evidence_index)}<select data-error="${errorIndex}" data-span="${spanIndex}" data-span-field="evidence_index">${evidenceOptions}</select></label>
        <label>${escapeHtml(labels.evidence_start)}<input type="number" min="0" value="${span.start}" data-error="${errorIndex}" data-span="${spanIndex}" data-span-field="start"></label>
        <label>${escapeHtml(labels.evidence_end)}<input type="number" min="0" value="${span.end}" data-error="${errorIndex}" data-span="${spanIndex}" data-span-field="end"></label>
      </div>`;
    }
    function materialErrorsHtml(row, review) {
      if (!materialErrorConfig) return '';
      const labels = materialErrorConfig.labels;
      const annotations = review.material_errors || [];
      const items = annotations.map((annotation, errorIndex) => {
        const categories = materialErrorConfig.categories.map(category =>
          `<option value="${category}" ${annotation.category === category ? 'selected' : ''}>${escapeHtml(category.replaceAll('_', ' '))}</option>`
        ).join('');
        const evidenceSpans = annotation.evidence_spans.map((span, spanIndex) =>
          evidenceSpanHtml(row, span, errorIndex, spanIndex)
        ).join('');
        return `<div class="material-error">
          <div class="material-error-grid">
            <label>${escapeHtml(labels.category)}<select data-error="${errorIndex}" data-error-field="category">${categories}</select></label>
            <label>${escapeHtml(labels.answer_start)}<input type="number" min="0" value="${annotation.answer_span.start}" data-error="${errorIndex}" data-answer-field="start"></label>
            <label>${escapeHtml(labels.answer_end)}<input type="number" min="0" value="${annotation.answer_span.end}" data-error="${errorIndex}" data-answer-field="end"></label>
          </div>
          <label class="checkbox"><input type="checkbox" data-error="${errorIndex}" data-error-field="evidence_absent" ${annotation.evidence_absent ? 'checked' : ''}> ${escapeHtml(labels.evidence_absent)}</label>
          <div class="evidence-spans">${evidenceSpans}</div>
          <div class="control-group">
            <button type="button" data-add-evidence="${errorIndex}">${escapeHtml(labels.add_evidence)}</button>
            <button type="button" data-remove-error="${errorIndex}">${escapeHtml(labels.remove)}</button>
          </div>
        </div>`;
      }).join('');
      return `<section class="material-errors">
        <h3>${escapeHtml(labels.heading)}</h3>
        <div class="question">Record the smallest answer span and its supporting evidence span, or explicitly mark evidence absent.</div>
        ${items}
        <button type="button" data-add-error>${escapeHtml(labels.add_error)}</button>
      </section>`;
    }
    function bindMaterialErrorControls(row, review) {
      if (!materialErrorConfig) return;
      card.querySelector('[data-add-error]').addEventListener('click', () => {
        review.material_errors.push({
          category: materialErrorConfig.categories[0],
          answer_span: { start: 0, end: Math.min(1, row.answer.length) },
          evidence_spans: [],
          evidence_absent: true
        });
        saveState();
        render();
      });
      card.querySelectorAll('[data-remove-error]').forEach(button => button.addEventListener('click', event => {
        review.material_errors.splice(Number(event.currentTarget.dataset.removeError), 1);
        saveState();
        render();
      }));
      card.querySelectorAll('[data-add-evidence]').forEach(button => button.addEventListener('click', event => {
        const annotation = review.material_errors[Number(event.currentTarget.dataset.addEvidence)];
        annotation.evidence_absent = false;
        annotation.evidence_spans.push({ evidence_index: 0, start: 0, end: Math.min(1, row.evidence[0].text.length) });
        saveState();
        render();
      }));
      card.querySelectorAll('[data-answer-field]').forEach(input => input.addEventListener('input', event => {
        const annotation = review.material_errors[Number(event.target.dataset.error)];
        annotation.answer_span[event.target.dataset.answerField] = integerOrZero(Number(event.target.value));
        saveState();
      }));
      card.querySelectorAll('[data-span-field]').forEach(input => input.addEventListener('input', event => {
        const annotation = review.material_errors[Number(event.target.dataset.error)];
        const span = annotation.evidence_spans[Number(event.target.dataset.span)];
        span[event.target.dataset.spanField] = integerOrZero(Number(event.target.value));
        saveState();
      }));
      card.querySelectorAll('[data-error-field]').forEach(input => input.addEventListener('change', event => {
        const annotation = review.material_errors[Number(event.target.dataset.error)];
        if (event.target.dataset.errorField === 'category') {
          annotation.category = event.target.value;
        } else {
          annotation.evidence_absent = event.target.checked;
          if (event.target.checked) annotation.evidence_spans = [];
        }
        saveState();
        render();
      }));
    }
    function render() {
      const row = source.rows[current];
      const review = reviewFor(row);
      const evidence = row.evidence.map(item => `
        <div class="evidence"><strong>${escapeHtml(item.title)}</strong>
        <div class="doc-id">Document ${escapeHtml(item.document_id)}</div>
        <div>${escapeHtml(item.text)}</div></div>`).join('');
      const fields = rubric.map(([field, title, question, options]) => `
        <fieldset><legend>${escapeHtml(title)}</legend><div class="question">${escapeHtml(question)}</div>
        <div class="options">${options.map(option => `
          <label class="option"><input type="radio" name="${field}" value="${option}" ${review[field] === option ? 'checked' : ''}>
          <span>${escapeHtml(option.replace('_', ' '))}</span></label>`).join('')}</div></fieldset>`).join('');
      card.innerHTML = `
        <div class="response-heading"><h2>Response ${current + 1} of ${source.rows.length}</h2><span class="response-id">${row.response_id}</span></div>
        <section class="section"><h3>Claim</h3><div class="claim">${escapeHtml(row.claim)}</div></section>
        <section class="section"><h3>Supplied evidence</h3><div class="evidence-list">${evidence}</div></section>
        <section class="section"><h3>Answer</h3><div class="answer">${escapeHtml(row.answer)}</div></section>
        <section class="rubric" aria-label="Groundedness rubric">${fields}
          ${materialErrorsHtml(row, review)}
          <label class="notes"><span>Notes</span><div class="question">For a non-pass or uncertainty, cite the smallest evidence and answer span that explains it.</div>
          <textarea id="notes" placeholder="Optional for a clean pass">${escapeHtml(review.notes || '')}</textarea></label>
        </section>`;
      card.querySelectorAll('input[type=radio]').forEach(input => input.addEventListener('change', event => {
        review[event.target.name] = event.target.value;
        saveState();
      }));
      document.getElementById('notes').addEventListener('input', event => {
        review.notes = event.target.value;
        saveState();
      });
      bindMaterialErrorControls(row, review);
      document.getElementById('jump').value = String(current);
      document.getElementById('previous').disabled = current === 0;
      document.getElementById('next').disabled = current === source.rows.length - 1;
      updateProgress();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    function exportReview() {
      state = normalizeState(state);
      if (!reviewer.value.trim() || !source.rows.every(rowComplete)) {
        message.textContent = 'Complete every categorical judgment and the reviewer name before export.';
        message.className = 'message warn';
        updateProgress();
        return;
      }
      const rows = source.rows.map(row => ({
        ...row,
        review: { ...state.reviews[row.response_id], notes: state.reviews[row.response_id].notes || '' }
      }));
      const completed = {
        ...source,
        completed_at: new Date().toISOString(),
        reviewer: reviewer.value.trim(),
        rows
      };
      const blob = new Blob([JSON.stringify(completed, null, 2) + '\n'], {type: 'application/json'});
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = reviewConfig.export_filename;
      link.click();
      URL.revokeObjectURL(link.href);
      message.textContent = `Exported ${rows.length} completed responses from source ${sourceDigest.slice(0, 12)}…`;
      message.className = 'message';
    }
    reviewer.addEventListener('input', event => { state.reviewer = event.target.value; saveState(); });
    document.getElementById('previous').addEventListener('click', () => { if (current > 0) { current -= 1; render(); } });
    document.getElementById('next').addEventListener('click', () => { if (current < source.rows.length - 1) { current += 1; render(); } });
    document.getElementById('jump').addEventListener('change', event => { current = Number(event.target.value); render(); });
    exportButton.addEventListener('click', exportReview);
    source.rows.forEach((row, index) => document.getElementById('jump').add(new Option(`${index + 1}. ○ ${row.response_id}`, String(index))));
    loadState();
    render();
  </script>
</body>
</html>
"""


def build_reviewer(
    worksheet: Path,
    output: Path,
    *,
    expected_sha256: str = FROZEN_WORKSHEET_SHA256,
    expected_rows: int = 42,
) -> dict[str, object]:
    data, raw = load_worksheet(
        worksheet,
        require_complete=False,
        expected_sha256=expected_sha256,
        expected_rows=expected_rows,
    )
    digest = hashlib.sha256(raw).hexdigest()
    embedded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    embedded = embedded.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    reviewer_config = json.dumps(
        _reviewer_config(data["schema_version"]),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    reviewer_config = (
        reviewer_config.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    )
    browser_validation = (
        BROWSER_VALIDATION_JAVASCRIPT if data["schema_version"] == SCHEMA_VERSION_V2 else ""
    )
    html = (
        HTML_TEMPLATE.replace("__WORKSHEET_JSON__", embedded)
        .replace("__BROWSER_VALIDATION_JAVASCRIPT__", browser_validation)
        .replace("__REVIEW_CONFIG__", reviewer_config)
        .replace("__STORAGE_KEY__", f"scifact-generation-human-review:{digest}")
        .replace("__SOURCE_DIGEST__", digest)
    )
    staged = output.with_name(f".{output.name}.tmp")
    if os.path.lexists(output):
        raise ReviewValidationError(f"output already exists: {output}")
    if os.path.lexists(staged):
        raise ReviewValidationError(f"staging output already exists: {staged}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with staged.open("x", encoding="utf-8") as stream:
        stream.write(html)
    os.chmod(staged, 0o644)
    staged.replace(output)
    return {
        "output": str(output),
        "rows": len(data["rows"]),
        "schema_version": data["schema_version"],
        "source_sha256": digest,
    }


def _source_projection(data: dict[str, Any]) -> dict[str, object]:
    return {
        "rows": [
            {field: row[field] for field in sorted(ROW_FIELDS - {"review"})} for row in data["rows"]
        ],
        "schema_version": data["schema_version"],
        "selection_protocol": data["selection_protocol"],
    }


def validate_completed(
    worksheet: Path,
    source: Path,
    *,
    expected_sha256: str = FROZEN_WORKSHEET_SHA256,
    expected_rows: int = 42,
) -> dict[str, object]:
    data, _ = load_worksheet(worksheet, require_complete=True, expected_rows=expected_rows)
    source_data, _ = load_worksheet(
        source,
        require_complete=False,
        expected_sha256=expected_sha256,
        expected_rows=expected_rows,
    )
    if _source_projection(data) != _source_projection(source_data):
        raise ReviewValidationError("non-review content differs from the frozen source")
    return {
        "completed_at": data["completed_at"],
        "reviewer": data["reviewer"],
        "rows": len(data["rows"]),
        "status": "complete",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Build the standalone blinded reviewer")
    build.add_argument("--worksheet", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    validate = subparsers.add_parser("validate", help="Validate an exported completed review")
    validate.add_argument("--source", type=Path, required=True)
    validate.add_argument("--worksheet", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = (
            build_reviewer(args.worksheet, args.output)
            if args.command == "build"
            else validate_completed(args.worksheet, args.source)
        )
    except (OSError, ReviewValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
