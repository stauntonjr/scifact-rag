"""Fail-closed input binding for the retained evidence-selection audit."""

from __future__ import annotations

import hashlib
import itertools
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from evidence_inference_reader import ARMS, NATIVE, parse_label, span_coverage

PREPARATION_SHA256 = "888834d7ff034b391f6d90edb9cc819f88e8265823fdf25579f35fce6c88fc20"
RUNTIME_SHA256 = "891d04c4be3175c803fd1308f1eb24cc6c56c386885d25851752dbac4ce2db9d"
LEDGER_SHA256 = "e5f629cd330609a436df7959a115508252b6e510166eb1a81d23c5c4862cd9e2"


class AuditError(ValueError):
    """The retained input tree cannot support a reproducible audit."""


@dataclass(frozen=True, slots=True)
class AuditInputs:
    root: Path
    prepared: Path
    run: Path
    ledger: Path
    evaluation: Path
    public_results: Path


@dataclass(frozen=True, slots=True)
class OutcomeRow:
    prompt_id: str
    article_id: str
    target: str
    predictions: dict[str, str]
    correctness: dict[str, bool]
    abstentions: dict[str, bool]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind_inputs(root: Path, public_results: Path) -> AuditInputs:
    """Bind the exact, locally retained reader inputs without modifying them."""
    if not root.is_dir() or os.access(root, os.W_OK):
        raise AuditError("reader artifact root must be an existing read-only directory")
    prepared = root / "prepared-002"
    run = root / "live-20260919-001"
    ledger = run / "ledger.jsonl"
    evaluation = root / "evaluation-20260919-001" / "report.json"
    required = (prepared / "manifest.json", run / "runtime.json", ledger, evaluation, public_results)
    missing = next((path for path in required if not path.is_file()), None)
    if missing is not None:
        raise AuditError(f"missing required retained path: {missing.relative_to(root)}")
    if sha256_file(prepared / "manifest.json") != PREPARATION_SHA256:
        raise AuditError("preparation manifest SHA-256 mismatch")
    if sha256_file(run / "runtime.json") != RUNTIME_SHA256:
        raise AuditError("runtime SHA-256 mismatch")
    if sha256_file(ledger) != LEDGER_SHA256:
        raise AuditError("ledger SHA-256 mismatch")
    return AuditInputs(root, prepared, run, ledger, evaluation, public_results)


def _index_unique(rows: list[dict[str, object]], field: str, label: str) -> dict[str, dict[str, object]]:
    indexed = {str(row[field]): row for row in rows}
    if len(indexed) != len(rows):
        raise AuditError(f"duplicate {label} identity")
    return indexed


def reconcile_outcomes(
    prepared: list[dict[str, object]],
    references: list[dict[str, object]],
    terminal_events: list[dict[str, object]],
) -> list[OutcomeRow]:
    """Join retained records by IDs, preserving preparation order only for rendering."""
    prompts = _index_unique(prepared, "prompt_id", "prepared prompt")
    refs = _index_unique(references, "prompt_id", "reference")
    events = {(str(row["prompt_id"]), str(row["arm"])): row for row in terminal_events}
    if len(events) != len(terminal_events) or set(prompts) != set(refs):
        raise AuditError("duplicate terminal event or prompt membership mismatch")
    rows = []
    for prompt in prepared:
        prompt_id = str(prompt["prompt_id"])
        reference = refs[prompt_id]
        article_id = str(prompt["article_id"])
        if article_id != str(reference["article_id"]):
            raise AuditError("prompt/reference article mismatch")
        predictions = {}
        for arm in ARMS:
            event = events.get((prompt_id, arm))
            if not isinstance(event, dict) or event.get("status") != "completed":
                raise AuditError("missing completed terminal event")
            if str(event.get("article_id")) != article_id:
                raise AuditError("terminal event article mismatch")
            try:
                content = event["response"]["choices"][0]["message"]["content"]
                prediction = parse_label(content)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise AuditError("invalid retained reader response") from exc
            predictions[arm] = prediction
        target = str(reference["target"])
        if target not in NATIVE:
            raise AuditError("invalid reference label")
        rows.append(OutcomeRow(
            prompt_id=prompt_id,
            article_id=article_id,
            target=target,
            predictions=predictions,
            correctness={arm: predictions[arm] == target for arm in ARMS},
            abstentions={arm: predictions[arm] == "insufficient_evidence" for arm in ARMS},
        ))
    return rows


def validate_source_windows(windows: list[dict[str, object]]) -> None:
    ordered = sorted(windows, key=lambda row: (int(row["start"]), int(row["end"])))
    for previous, current in itertools.pairwise(ordered):
        if int(current["start"]) < int(previous["end"]):
            raise AuditError("overlapping source windows")


def coverage(reference: list[list[int]], selected: list[list[int]]) -> dict[str, float | int]:
    """Count valid touching/overlapping reference spans exactly once."""
    return span_coverage(selected, reference)


def two_window_upper_bound(
    windows: list[dict[str, object]], reference: list[list[int]]
) -> dict[str, object]:
    validate_source_windows(windows)
    if not windows:
        raise AuditError("source windows must not be empty")
    pairs = list(itertools.combinations(windows, 2)) or [(windows[0],)]
    def rank(pair: tuple[dict[str, object], ...]) -> tuple[float, tuple[tuple[int, int], ...]]:
        intervals = [[int(row["start"]), int(row["end"])] for row in pair]
        result = coverage(reference, intervals)
        return (-float(result["intersection_characters"]), tuple(map(tuple, intervals)))
    selected = min(pairs, key=rank)
    intervals = [[int(row["start"]), int(row["end"])] for row in selected]
    result = coverage(reference, intervals)
    return {"intervals": tuple(map(tuple, intervals)), **result}
