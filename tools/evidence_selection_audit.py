"""Deterministic, model-free audit of the frozen Evidence Inference selection results."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from evidence_inference_reader import (
    ARMS,
    NATIVE,
    digest,
    evaluate,
    load_prepared,
    parse_label,
    span_coverage,
    union_intervals,
)
from evidence_inference_reader_run import arm_order, parse_scores, preflight_ids

PREPARATION_SHA256 = "888834d7ff034b391f6d90edb9cc819f88e8265823fdf25579f35fce6c88fc20"
RUNTIME_SHA256 = "891d04c4be3175c803fd1308f1eb24cc6c56c386885d25851752dbac4ce2db9d"
LEDGER_SHA256 = "e5f629cd330609a436df7959a115508252b6e510166eb1a81d23c5c4862cd9e2"


EXPECTED_COUNTS = {
    "articles": 20,
    "prompts": 101,
    "reader_calls": 303,
    "selector_calls": 101,
    "pairs": 1599,
}
EXPECTED_CORRECT = {"full": 92, "selected": 79, "oracle": 92}
EXPECTED_ABSTENTIONS = {"full": 0, "selected": 5, "oracle": 1}


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


def write_json(path: Path, value: object) -> None:
    """Write an audit output once; retained evidence is never overwritten."""
    try:
        with path.open("x") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise AuditError("audit output exists") from exc


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def bind_inputs(root: Path, public_results: Path) -> AuditInputs:
    """Bind the exact, locally retained reader inputs without modifying them."""
    root, public_results = root.resolve(), public_results.resolve()
    if not root.is_dir():
        raise AuditError("reader artifact root must be an existing directory")
    prepared = root / "prepared-002"
    run = root / "live-20260919-001"
    ledger = run / "ledger.jsonl"
    evaluation = root / "evaluation-20260919-001" / "report.json"
    required = (
        prepared / "manifest.json",
        run / "runtime.json",
        ledger,
        evaluation,
        public_results,
    )
    missing = next((path for path in required if not path.is_file()), None)
    if missing is not None:
        raise AuditError(
            f"missing required retained path: {missing.name if not missing.is_relative_to(root) else missing.relative_to(root)}"
        )
    if sha256_file(prepared / "manifest.json") != PREPARATION_SHA256:
        raise AuditError("preparation manifest SHA-256 mismatch")
    if sha256_file(run / "runtime.json") != RUNTIME_SHA256:
        raise AuditError("runtime SHA-256 mismatch")
    if sha256_file(ledger) != LEDGER_SHA256:
        raise AuditError("ledger SHA-256 mismatch")
    return AuditInputs(root, prepared, run, ledger, evaluation, public_results)


def _index_unique(
    rows: list[dict[str, object]], field: str, label: str
) -> dict[str, dict[str, object]]:
    if any(not isinstance(row.get(field), str) or not row[field] for row in rows):
        raise AuditError(f"invalid {label} identity")
    indexed = {row[field]: row for row in rows}
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
    events = {(row["prompt_id"], row["arm"]): row for row in terminal_events}
    if len(events) != len(terminal_events) or set(prompts) != set(refs):
        raise AuditError("duplicate terminal event or prompt membership mismatch")
    if set(events) != {(pid, arm) for pid in prompts for arm in ARMS}:
        raise AuditError("terminal prompt/arm membership mismatch")
    rows = []
    for prompt in prepared:
        prompt_id = prompt["prompt_id"]
        reference = refs[prompt_id]
        article_id = prompt["article_id"]
        if not isinstance(article_id, str) or article_id != reference["article_id"]:
            raise AuditError("prompt/reference article mismatch")
        predictions = {}
        for arm in ARMS:
            event = events.get((prompt_id, arm))
            if not isinstance(event, dict) or event.get("status") != "completed":
                raise AuditError("missing completed terminal event")
            if event.get("article_id") != article_id:
                raise AuditError("terminal event article mismatch")
            try:
                content = event["response"]["choices"][0]["message"]["content"]
                prediction = parse_label(content)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise AuditError("invalid retained reader response") from exc
            predictions[arm] = prediction
        target = reference["target"]
        if target not in NATIVE:
            raise AuditError("invalid reference label")
        rows.append(
            OutcomeRow(
                prompt_id=prompt_id,
                article_id=article_id,
                target=target,
                predictions=predictions,
                correctness={arm: predictions[arm] == target for arm in ARMS},
                abstentions={arm: predictions[arm] == "insufficient_evidence" for arm in ARMS},
            )
        )
    return rows


def validate_intervals(intervals, length=None):
    if not isinstance(intervals, list) or not intervals:
        raise AuditError("empty or invalid intervals")
    for interval in intervals:
        if (
            not isinstance(interval, (list, tuple))
            or len(interval) != 2
            or any(type(x) is not int for x in interval)
            or not 0 <= interval[0] < interval[1]
            or (length is not None and interval[1] > length)
        ):
            raise AuditError("invalid or out-of-bounds interval")


def validate_source_windows(windows):
    if not windows:
        raise AuditError("source windows must not be empty")
    intervals = [[w["start"], w["end"]] for w in windows]
    validate_intervals(intervals)
    ordered = sorted(intervals)
    for previous, current in itertools.pairwise(ordered):
        if current[0] < previous[1]:
            raise AuditError("overlapping source windows")


def coverage(reference, selected):
    """Count touching/overlapping half-open reference spans exactly once."""
    validate_intervals(reference)
    validate_intervals(selected)
    return span_coverage(selected, reference)


def two_window_upper_bound(windows, reference):
    validate_source_windows(windows)
    ordered = sorted(windows, key=lambda w: (w["start"], w["end"]))
    # For nonnegative overlap, a pair weakly dominates either constituent.
    # Prefer two windows when available, matching the frozen context budget.
    pairs = itertools.combinations(ordered, 2) if len(ordered) > 1 else [(ordered[0],)]

    def rank(pair):
        intervals = [[w["start"], w["end"]] for w in pair]
        return (
            -coverage(reference, intervals)["intersection_characters"],
            tuple(map(tuple, intervals)),
        )

    best = min(pairs, key=rank)
    intervals = [[w["start"], w["end"]] for w in best]
    return {"intervals": tuple(map(tuple, intervals)), **coverage(reference, intervals)}


def rank_windows(windows, response, reference, selected):
    validate_source_windows(windows)
    try:
        scores = parse_scores(response, len(windows))
    except (ValueError, TypeError, KeyError) as exc:
        raise AuditError("invalid selector score response") from exc
    indexes = sorted(range(len(windows)), key=lambda i: (-scores[i], windows[i]["start"]))
    expected = sorted([[windows[i]["start"], windows[i]["end"]] for i in indexes[:2]])
    if selected != expected:
        raise AuditError("selected intervals differ from score rank and tie order")
    ranks = {index: rank for rank, index in enumerate(indexes, 1)}
    return [
        {
            "start": w["start"],
            "end": w["end"],
            "score": scores[i],
            "rank": ranks[i],
            "selected": i in indexes[:2],
            "reference_overlap_characters": coverage(reference, [[w["start"], w["end"]]])[
                "intersection_characters"
            ],
        }
        for i, w in enumerate(windows)
    ]


def validate_inference_order(prompts, run, events):
    """Reconstruct the preflight/rotating schedule independently of preparation order."""
    preflight = preflight_ids(prompts)
    ordered = sorted(
        prompts, key=lambda p: (digest(f"ei-reader-v1:{p['article_id']}".encode()), p["prompt_id"])
    )
    schedule = [{"prompt_id": p["prompt_id"], "arms": arm_order(i)} for i, p in enumerate(ordered)]
    if run.get("preflight") != preflight or run.get("schedule") != schedule:
        raise AuditError("inference schedule mismatch")
    tasks = [(pid, arm) for pid in preflight for arm in ["selector", *ARMS]]
    tasks += [
        (item["prompt_id"], arm)
        for item in schedule
        if item["prompt_id"] not in preflight
        for arm in ["selector", *item["arms"]]
    ]
    expected = [(pid, arm, status) for pid, arm in tasks for status in ("started", "completed")]
    if [(e["prompt_id"], e["arm"], e["status"]) for e in events] != expected:
        raise AuditError("inference event order or membership mismatch")
    prompts_by_id = _index_unique(prompts, "prompt_id", "prompt")
    for event in events:
        if event["article_id"] != prompts_by_id[event["prompt_id"]]["article_id"]:
            raise AuditError("ledger article identity mismatch")
        kind = "selector" if event["arm"] == "selector" else "reader"
        if (
            event["request_id"] != f"{kind}:{event['prompt_id']}:{event['arm']}"
            or event["kind"] != kind
        ):
            raise AuditError("ledger request identity mismatch")


def population(rows):
    return {"prompt_count": len(rows), "article_count": len({r.article_id for r in rows})}


def partition_key(row):
    return "|".join(f"{arm}={int(row.correctness[arm])}" for arm in ARMS)


def aggregate_outcomes(rows):
    partitions = {
        "|".join(f"{a}={b}" for a, b in zip(ARMS, bits)): population(
            [r for r in rows if tuple(int(r.correctness[a]) for a in ARMS) == bits]
        )
        for bits in itertools.product((0, 1), repeat=3)
    }
    labels = NATIVE + ["insufficient_evidence"]
    transitions, contrasts = {}, {}
    for a, b in itertools.combinations(ARMS, 2):
        transitions[f"{a}_to_{b}"] = {
            la: {
                lb: population(
                    [r for r in rows if r.predictions[a] == la and r.predictions[b] == lb]
                )
                for lb in labels
            }
            for la in labels
        }
        for winner, loser in ((a, b), (b, a)):
            contrasts[f"{winner}_correct_{loser}_wrong"] = population(
                [r for r in rows if r.correctness[winner] and not r.correctness[loser]]
            )
    return {
        "correct": {a: sum(r.correctness[a] for r in rows) for a in ARMS},
        "abstentions": {a: sum(r.abstentions[a] for r in rows) for a in ARMS},
        "partition": partitions,
        "paired_label_transitions": transitions,
        "contrasts": contrasts,
        "error_population": population([r for r in rows if not all(r.correctness.values())]),
    }


def article_summaries(case_rows):
    """Use stable sorted ordinals rather than source identities in publication."""
    result = []
    for ordinal, article in enumerate(sorted({c["article_id"] for c in case_rows}), 1):
        cases = [c for c in case_rows if c["article_id"] == article]
        result.append(
            {
                "article_ordinal": ordinal,
                "prompt_count": len(cases),
                "correct": {a: sum(c["correctness"][a] for c in cases) for a in ARMS},
                "wrong": {a: sum(not c["correctness"][a] for c in cases) for a in ARMS},
                "abstentions": {a: sum(c["abstentions"][a] for c in cases) for a in ARMS},
                "geometry": {
                    f"{relation}|{complete}": sum(
                        c["geometry"] == f"{relation}|{complete}" for c in cases
                    )
                    for relation in ("actual_equals_maximum", "actual_below_maximum")
                    for complete in ("maximum_complete", "maximum_incomplete")
                },
                "mean_actual_recall": sum(c["actual"]["recall"] for c in cases) / len(cases),
                "mean_maximum_recall": sum(c["maximum"]["recall"] for c in cases) / len(cases),
            }
        )
    return result


def public_summary(summary):
    """Project only numerical aggregates, fixed labels and verified digest strings."""
    required = (
        "input_digests",
        "prompt_count",
        "article_count",
        "outcomes",
        "geometry",
        "decision",
        "per_article",
    )
    if any(k not in summary for k in required):
        raise AuditError("audit summary is incomplete")
    # Aggregate branches have no free-text values. Reject rather than redact a
    # malformed nested payload: accidental case content must stop publication.
    allowed_keys = set(
        ARMS
        + NATIVE
        + [
            "insufficient_evidence",
            "correct",
            "abstentions",
            "partition",
            "paired_label_transitions",
            "contrasts",
            "error_population",
            "prompt_count",
            "article_count",
            "actual_equals_maximum",
            "actual_below_maximum",
            "maximum_complete",
            "maximum_incomplete",
            "cells",
            "by_partition",
            "by_contrast",
            "selected_correct",
            "selected_wrong",
            "max_complete",
            "wrong",
            "article_ordinal",
            "geometry",
            "mean_actual_recall",
            "mean_maximum_recall",
        ]
    )
    allowed_keys.update(f"{a}_to_{b}" for a, b in itertools.combinations(ARMS, 2))
    allowed_keys.update(f"{a}_correct_{b}_wrong" for a in ARMS for b in ARMS if a != b)
    allowed_keys.update(
        "|".join(f"{a}={b}" for a, b in zip(ARMS, bits))
        for bits in itertools.product((0, 1), repeat=3)
    )
    allowed_keys.update(
        f"{a}|{b}"
        for a in ("actual_equals_maximum", "actual_below_maximum")
        for b in ("maximum_complete", "maximum_incomplete")
    )

    def validate_numeric(value):
        if isinstance(value, dict):
            if not set(value) <= allowed_keys:
                raise AuditError("nonaggregate key in public summary")
            for key, item in value.items():
                if key in ("mean_actual_recall", "mean_maximum_recall"):
                    if type(item) not in (int, float) or not 0 <= item <= 1:
                        raise AuditError("invalid mean recall in public summary")
                else:
                    validate_numeric(item)
        elif type(value) is not int or value < 0:
            raise AuditError("nonaggregate value in public summary")

    for key in ("outcomes", "geometry"):
        validate_numeric(summary[key])
    for key in ("prompt_count", "article_count"):
        validate_numeric(summary[key])
    articles = summary["per_article"]
    article_keys = {
        "article_ordinal",
        "prompt_count",
        "correct",
        "wrong",
        "abstentions",
        "geometry",
        "mean_actual_recall",
        "mean_maximum_recall",
    }
    if not isinstance(articles, list) or len(articles) != summary["article_count"]:
        raise AuditError("invalid article summary membership")
    for ordinal, article in enumerate(articles, 1):
        if (
            not isinstance(article, dict)
            or set(article) != article_keys
            or article["article_ordinal"] != ordinal
        ):
            raise AuditError("invalid article summary schema")
        validate_numeric(article)
    if sum(article["prompt_count"] for article in articles) != summary["prompt_count"]:
        raise AuditError("article prompt totals mismatch")
    hashes = summary["input_digests"]
    if not set(hashes) <= {
        "preparation",
        "runtime",
        "ledger",
        "evaluation",
        "public_results",
    } or any(
        not isinstance(v, str) or len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
        for v in hashes.values()
    ):
        raise AuditError("invalid public digest")
    if summary["decision"] not in ("no-intervention", "unresolved-no-intervention"):
        raise AuditError("unbounded audit decision")
    return {
        "schema_version": "evidence-selection-error-audit-summary/v1",
        "claim_boundary": "deterministic overlap and rank audit only",
        **{k: summary[k] for k in required},
    }


def _input_hashes(inputs):
    files = [
        p
        for directory in (inputs.prepared, inputs.run)
        for p in directory.rglob("*")
        if p.is_file()
    ]
    files.append(inputs.evaluation)
    result = {str(p.relative_to(inputs.root)): sha256_file(p) for p in sorted(files)}
    result["published-results.json"] = sha256_file(inputs.public_results)
    return result


def _validate_inputs(inputs):
    # Rebind at execution, not only at CLI argument parsing.
    if bind_inputs(inputs.root, inputs.public_results) != inputs:
        raise AuditError("input layout mismatch")
    manifest, prompts = load_prepared(inputs.prepared)
    refs = read_jsonl(inputs.prepared / "references.jsonl")
    windows = _index_unique(
        read_jsonl(inputs.prepared / "windows.jsonl"), "article_id", "source article"
    )
    events = read_jsonl(inputs.ledger)
    run = json.loads((inputs.run / "run.json").read_text())
    validate_inference_order(prompts, run, events)
    articles = {p["article_id"] for p in prompts}
    if (
        set(windows) != articles
        or len(articles) != EXPECTED_COUNTS["articles"]
        or len(prompts) != EXPECTED_COUNTS["prompts"]
        or len(refs) != len(prompts)
    ):
        raise AuditError("retained article/prompt membership totals mismatch")
    if (
        manifest["selector_pairs"] != EXPECTED_COUNTS["pairs"]
        or sum(p["selector"]["pairs"] for p in prompts) != EXPECTED_COUNTS["pairs"]
    ):
        raise AuditError("selector pair totals mismatch")
    started = [e for e in events if e["status"] == "started"]
    selectors = [e for e in started if e["arm"] == "selector"]
    if (
        len(selectors) != EXPECTED_COUNTS["selector_calls"]
        or len(started) - len(selectors) != EXPECTED_COUNTS["reader_calls"]
        or sum(e["pairs"] for e in selectors) != EXPECTED_COUNTS["pairs"]
    ):
        raise AuditError("request totals mismatch")
    expected_paths = {f"selected-{p['prompt_id']}.json" for p in prompts}
    if {p.name for p in inputs.run.glob("selected-*.json")} != expected_paths:
        raise AuditError("selected artifact membership mismatch")
    refs_by_id = _index_unique(refs, "prompt_id", "reference")
    for p in prompts:
        source = windows[p["article_id"]]["windows"]
        validate_source_windows(source)
        if source != sorted(source, key=lambda w: w["start"]):
            raise AuditError("source window order mismatch")
        full = json.loads(p["full"]["payload"]["messages"][1]["content"])["evidence"]
        if len(full) != 1:
            raise AuditError("full source cardinality mismatch")
        text = full[0]
        validate_intervals(refs_by_id[p["prompt_id"]]["intervals"], len(text))
        validate_intervals([[w["start"], w["end"]] for w in source], len(text))
        if any(text[w["start"] : w["end"]] != w["text"] for w in source):
            raise AuditError("source window coordinate mismatch")
        if p["selector"]["pairs"] != len(source):
            raise AuditError("prompt selector pair mismatch")
    # Existing evaluator supplies payload hash, selected evidence, native metric,
    # token accounting and terminal reconciliation. Only derived output is temporary.
    with tempfile.TemporaryDirectory(prefix="selection-audit-validation-") as temporary:
        reproduced = evaluate(inputs.prepared, inputs.ledger, Path(temporary) / "evaluation")
    retained = json.loads(inputs.evaluation.read_text())
    published = json.loads(inputs.public_results.read_text())
    if reproduced != retained or any(
        k not in published or published[k] != v for k, v in retained.items()
    ):
        raise AuditError("retained/published evaluation does not reconcile")
    if (
        reproduced["status"] != "complete_accounting"
        or reproduced["complete_triplets"] != EXPECTED_COUNTS["prompts"]
    ):
        raise AuditError("incomplete retained accounting")
    terminals = [e for e in events if e["status"] == "completed"]
    rows = reconcile_outcomes(prompts, refs, [e for e in terminals if e["arm"] in ARMS])
    if {a: sum(r.correctness[a] for r in rows) for a in ARMS} != EXPECTED_CORRECT or {
        a: sum(r.abstentions[a] for r in rows) for a in ARMS
    } != EXPECTED_ABSTENTIONS:
        raise AuditError("frozen outcome totals do not reconcile")
    return rows, refs_by_id, windows, {(e["prompt_id"], e["arm"]): e for e in terminals}


def run_audit(inputs, output):
    """Read immutable evidence; publish a predeclared manifest and text-free audit."""
    output = output.resolve()
    if output.exists() or output.is_relative_to(inputs.root.resolve()):
        raise AuditError("audit output exists or is inside the retained input tree")
    try:
        before = _input_hashes(inputs)
        rows, refs, windows, events = _validate_inputs(inputs)
        if _input_hashes(inputs) != before:
            raise AuditError("retained inputs changed during validation")
        audit_manifest = {
            "schema_version": "evidence-selection-audit/v1",
            "reader_artifact_root": str(inputs.root),
            "script_sha256": sha256_file(Path(__file__)),
            "input_hashes_before": before,
            "counts": EXPECTED_COUNTS,
            "definitions": {
                "coordinates": "half-open LF character offsets; reference intervals unioned",
                "score_rank": "descending finite score, then ascending source offset",
                "maximum": "at most two distinct existing windows; maximize integer reference intersection; ascending offset ties",
                "partitions": "all eight full/selected/oracle native-correctness triples; abstention is wrong",
                "population": "all retained prompts; error population is any arm wrong or abstaining; reverse contrasts included",
                "geometry": "integer intersection equality or below maximum; maximum equals reference union length or is incomplete",
                "article_counts": "distinct articles within each cell; cells may share articles",
                "per_article": "ascending article identity mapped to one-based ordinal; wrong includes abstentions; means weight each prompt once",
            },
        }
        output.mkdir(parents=True)
        write_json(output / "selection-audit-manifest.json", audit_manifest)
        case_rows = []
        for row in rows:
            pid = row.prompt_id
            selection = json.loads((inputs.run / f"selected-{pid}.json").read_text())
            intervals = selection["intervals"]
            reference = refs[pid]["intervals"]
            source = windows[row.article_id]["windows"]
            ranks = rank_windows(
                source, events[(pid, "selector")]["response"], reference, intervals
            )
            actual, maximum = (
                coverage(reference, intervals),
                two_window_upper_bound(source, reference),
            )
            relation = (
                "actual_equals_maximum"
                if actual["intersection_characters"] == maximum["intersection_characters"]
                else "actual_below_maximum"
            )
            complete = (
                "maximum_complete"
                if maximum["intersection_characters"] == maximum["reference_characters"]
                else "maximum_incomplete"
            )
            case_rows.append(
                {
                    "prompt_id": pid,
                    "article_id": row.article_id,
                    "target": row.target,
                    "predictions": row.predictions,
                    "correctness": row.correctness,
                    "abstentions": row.abstentions,
                    "error_population": not all(row.correctness.values()),
                    "partition": partition_key(row),
                    "reference_intervals": union_intervals(reference),
                    "selected_intervals": intervals,
                    "actual": actual,
                    "maximum": maximum,
                    "windows": ranks,
                    "geometry": f"{relation}|{complete}",
                }
            )
        outcomes = aggregate_outcomes(rows)
        geometry = {"cells": {}, "by_partition": {}, "by_contrast": {}}
        for key in (
            f"{a}|{b}"
            for a in ("actual_equals_maximum", "actual_below_maximum")
            for b in ("maximum_complete", "maximum_incomplete")
        ):
            subset = [r for r, c in zip(rows, case_rows) if c["geometry"] == key]
            geometry["cells"][key] = population(subset)
            suboutcomes = aggregate_outcomes(subset)
            geometry["by_partition"][key] = suboutcomes["partition"]
            geometry["by_contrast"][key] = suboutcomes["contrasts"]
        for tag in (
            "actual_equals_maximum",
            "actual_below_maximum",
            "maximum_complete",
            "maximum_incomplete",
        ):
            geometry[tag] = population(
                [r for r, c in zip(rows, case_rows) if tag in c["geometry"].split("|")]
            )
        for correct in (True, False):
            geometry["selected_correct" if correct else "selected_wrong"] = {
                key: population(
                    [
                        r
                        for r, c in zip(rows, case_rows)
                        if r.correctness["selected"] == correct and c["geometry"] == key
                    ]
                )
                for key in geometry["cells"]
            }
        geometry["mean_actual_recall"] = sum(c["actual"]["recall"] for c in case_rows) / len(
            case_rows
        )
        geometry["mean_maximum_recall"] = sum(c["maximum"]["recall"] for c in case_rows) / len(
            case_rows
        )
        after = _input_hashes(inputs)
        if after != before:
            raise AuditError("retained inputs changed during audit")
        summary = {
            "input_digests": {
                "preparation": PREPARATION_SHA256,
                "runtime": RUNTIME_SHA256,
                "ledger": LEDGER_SHA256,
                "evaluation": sha256_file(inputs.evaluation),
                "public_results": sha256_file(inputs.public_results),
            },
            "prompt_count": len(rows),
            "article_count": len({r.article_id for r in rows}),
            "outcomes": outcomes,
            "per_article": article_summaries(case_rows),
            "geometry": geometry,
            "decision": "unresolved-no-intervention",
        }
        public_summary(summary)
        # The preanalysis manifest remains immutable. A separate final receipt
        # records the postanalysis input snapshot and binds every result output.
        with (output / "case-rows.jsonl").open("x") as handle:
            for row in case_rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        write_json(output / "summary.json", summary)
        write_json(
            output / "verification.json",
            {
                "input_hashes_after": after,
                "input_hashes_unchanged": True,
                "manifest_sha256": sha256_file(output / "selection-audit-manifest.json"),
                "case_rows_sha256": sha256_file(output / "case-rows.jsonl"),
                "summary_sha256": sha256_file(output / "summary.json"),
            },
        )
        return summary
    except AuditError:
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise AuditError("retained audit validation failed; no successful audit published") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["run"], default="run")
    parser.add_argument("--reader-artifact-root", type=Path, required=True)
    parser.add_argument("--public-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = run_audit(
            bind_inputs(args.reader_artifact_root, args.public_results), args.output
        )
    except AuditError as exc:
        parser.exit(1, f"Audit stopped: {exc}\n")
    print(json.dumps(public_summary(summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
