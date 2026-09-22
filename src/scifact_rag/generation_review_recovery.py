"""Owner-authorized flat recovery; retains every attempt and earliest valid judgment."""

from __future__ import annotations

import copy
import hashlib
import json
import signal
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scifact_rag import generation_review_workflow as w


def request_for(manifest, source, cohort, stage, records):
    request = {
        "case": source,
        "stage": stage,
        "cohort": cohort,
        "requested_model": w.MODELS[stage],
        "prompt": w.PROMPT,
        "rubric": manifest["rubric"],
        "schema": w.judgment_schema(final=stage == "adjudicator-final"),
    }
    if stage == "adjudicator-final":
        previous = {
            k: records[(source["response_id"], k)] for k in ("r1", "r2", "adjudicator-initial")
        }
        request.update(
            initial=previous["adjudicator-initial"], peers={k: previous[k] for k in ("r1", "r2")}
        )
        request.update(
            {
                f"{name}_sha256": w.canonical_json_sha256(previous[key])
                for name, key in [("initial", "adjudicator-initial"), ("r1", "r1"), ("r2", "r2")]
            }
        )
    return request


def normalize_quote_delimiters(value, source, *, late=False):
    """Strip one syntax delimiter pair only when the exact unique source proves it."""
    from scifact_rag.generation_review_pilot import _occurrence_count

    result = copy.deepcopy(value)
    edits = []
    if not isinstance(result, dict):
        return result, edits
    judgment = result.get("judgment", result)
    if not isinstance(judgment, dict) or not isinstance(judgment.get("rationale"), dict):
        return result, edits
    rationale = judgment["rationale"]

    def canonical(quote, texts, path):
        if not isinstance(quote, str) or len(quote) < 3:
            return quote
        texts = set(texts)

        def occurrences(candidate):
            return sum(_occurrence_count(text, candidate) for text in texts)

        if occurrences(quote) != 0:
            return quote
        candidate = quote
        pairs = [('"', '"')] + ([("“", "”")] if late else [])
        if (quote[0], quote[-1]) in pairs:
            candidate = quote[1:-1]
        if candidate != quote and occurrences(candidate) == 1:
            edits.append(path)
            return candidate
        if (
            late
            and candidate.endswith(".")
            and not candidate.endswith("..")
            and occurrences(candidate) == 0
            and occurrences(candidate[:-1]) == 1
        ):
            edits.append(path + ":terminal-period")
            return candidate[:-1]
        return quote

    if isinstance(rationale.get("answer_quotes"), list):
        rationale["answer_quotes"] = [
            canonical(q, [source["answer"]], f"rationale.answer_quotes[{i}]")
            for i, q in enumerate(rationale["answer_quotes"])
        ]
    if isinstance(rationale.get("evidence_quotes"), list):
        for i, item in enumerate(rationale["evidence_quotes"]):
            if isinstance(item, dict) and "quote" in item:
                texts = [
                    row["text"]
                    for row in source["evidence"]
                    if row["document_id"] == item.get("document_id")
                ]
                item["quote"] = canonical(
                    item["quote"], texts, f"rationale.evidence_quotes[{i}].quote"
                )
    return result, edits


def validate(value, request):
    if request["stage"] == "adjudicator-final":
        w.validate_final(value, request)
    else:
        w.validate_judgment(value, request["case"])


def retain(manifest, sources, audit=None):
    records, sessions, snapshots = {}, set(), {}
    attempted = failed = duplicates = 0
    scheduled = {
        (row["response_id"], stage): (row, cohort, stage)
        for cohort in ("clarification", "assessment")
        for stage in w.MODELS
        for row in manifest["cases"]
        if row["response_id"] in manifest["split"][cohort]
    }
    for root in sources:
        old = json.loads((root / "manifest.json").read_text())
        if w._scientific_manifest_sha256(old) != w._scientific_manifest_sha256(manifest):
            raise w.WorkflowStop("recovery_input_drift")
        if not (root / "terminal.json").is_file():
            raise w.WorkflowStop("recovery_unknown_outcome")
        terminal = json.loads((root / "terminal.json").read_text())
        actual = {p.name: w._file_digest(p) for p in sorted((root / "attempts").glob("*.json"))}
        if actual != terminal["artifact_digests"]:
            raise w.WorkflowStop("recovery_artifact_digest_mismatch")
        snapshots[str(root.resolve())] = w._directory_snapshot_sha256(root)
        for path in sorted((root / "attempts").glob("*.start.json")):
            start = json.loads(path.read_text())
            end = path.with_name(path.name.replace(".start.", ".result."))
            if not end.exists():
                raise w.WorkflowStop("recovery_unknown_outcome")
            result = json.loads(end.read_text())
            if result["attempt_start_sha256"] != w.canonical_json_sha256(start):
                raise w.WorkflowStop("recovery_attempt_digest_mismatch")
            key = (start["response_id"], start["stage"])
            row, cohort, stage = scheduled[key]
            request = request_for(manifest, row, cohort, stage, records)
            if (
                start["request_sha256"] != w.canonical_json_sha256(request)
                or start["input_sha256"] != w.canonical_json_sha256(row)
                or start["schema_sha256"] != w.canonical_json_sha256(request["schema"])
                or start["requested_model"] != request["requested_model"]
            ):
                raise w.WorkflowStop("recovery_request_drift")
            attempted += 1
            output = result.get("transport") or {}
            session = output.get("session_id")
            if session:
                if session in sessions:
                    raise w.WorkflowStop("recovery_duplicate_session")
                sessions.add(session)
            if output.get("exit_status") != 0:
                failed += 1
                continue
            if (
                not session
                or not output.get("provider")
                or output.get("model") not in (None, request["requested_model"])
                or output.get("runtime_selected_model") not in (None, request["requested_model"])
            ):
                raise w.WorkflowStop("recovery_identity_mismatch")
            value = None
            edits = []
            try:
                value = w._decode(output["raw_output"])
                value, edits = normalize_quote_delimiters(value, row)
                validate(value, request)
                valid = True
                error = None
            except (w.WorkflowStop, ValueError, TypeError, KeyError) as exc:
                valid = False
                error = str(exc)
            if audit is not None:
                audit.append(
                    {
                        "source_result": str(end.resolve()),
                        "source_sha256": w._file_digest(end),
                        "original_status": result["status"],
                        "current_valid": valid,
                        "normalization_paths": edits,
                        "error": error,
                    }
                )
            if not valid:
                failed += 1
                continue
            if result["status"] != "completed":
                result = {
                    **result,
                    "status": "completed",
                    "judgment": value,
                    "validation_errors": [],
                    "revalidation": {
                        "source_result": str(end.resolve()),
                        "source_sha256": w._file_digest(end),
                        "reason": "Corrected multi-excerpt document lookup; raw output unchanged",
                    },
                }
            if edits and result.get("judgment") != value:
                result = {**result, "judgment": value}
            if edits and "normalization" not in result:
                result = {
                    **result,
                    "normalization": {
                        "paths": edits,
                        "raw_sha256": hashlib.sha256(output["raw_output"].encode()).hexdigest(),
                    },
                }
            if key in records:
                duplicates += 1
            else:
                records[key] = result
    return records, sessions, snapshots, attempted, failed, duplicates


def fill_missing_quotes(manifest, sources, selected):
    """Versioned completion policy: frozen selections cannot be overwritten."""
    records = dict(selected)
    repairs = []
    cases = {row["response_id"]: row for row in manifest["cases"]}
    for root in sources:
        for path in sorted((root / "attempts").glob("*.start.json")):
            start = json.loads(path.read_text())
            key = (start["response_id"], start["stage"])
            if key in records:
                continue
            if key[1] == "adjudicator-final" and any(
                (key[0], role) not in records for role in ("r1", "r2", "adjudicator-initial")
            ):
                continue
            end = path.with_name(path.name.replace(".start.", ".result."))
            original = json.loads(end.read_text())
            output = original.get("transport") or {}
            if output.get("exit_status") != 0:
                continue
            source = cases[key[0]]
            request = request_for(manifest, source, start["cohort"], key[1], records)
            if start["request_sha256"] != w.canonical_json_sha256(request):
                continue
            try:
                value, edits = normalize_quote_delimiters(
                    w._decode(output["raw_output"]), source, late=True
                )
                if not edits:
                    continue
                validate(value, request)
            except (w.WorkflowStop, ValueError, TypeError, KeyError):
                continue
            repair = {
                "policy": "missing-slot-quote-syntax/v1",
                "source_result": str(end.resolve()),
                "source_sha256": w._file_digest(end),
                "normalization_paths": edits,
                "raw_sha256": hashlib.sha256(output["raw_output"].encode()).hexdigest(),
            }
            records[key] = {
                **original,
                "status": "completed",
                "judgment": value,
                "validation_errors": [],
                "late_normalization": repair,
            }
            repairs.append(repair)
    return records, repairs


def run(
    root: Path,
    manifest: dict[str, Any],
    transport,
    sources: list[Path],
    max_attempts=5,
    *,
    complete_missing_format=False,
):
    """Finish the frozen schedule; failures remain counted and never become valid by repair."""
    expected = w.prepare_manifest(
        manifest["cases"],
        manifest["split"],
        manifest["families"],
        inventory_sha256=manifest["inventory_sha256"],
        selection_sha256=manifest["selection_sha256"],
        rubric=manifest["rubric"],
        mode=manifest["mode"],
    )
    if expected != manifest:
        raise w.WorkflowStop("manifest_identity_changed")
    live = isinstance(transport, w.CodexTransport)
    if not live and (transport.kind != "offline_fake" or manifest["mode"] != "fictional"):
        raise w.WorkflowStop("unverified_runtime_enforcement")
    audit = []
    records, sessions, snapshots, attempted, failed, duplicates = retain(manifest, sources, audit)
    late_repairs = []
    if complete_missing_format:
        records, late_repairs = fill_missing_quotes(manifest, sources, records)
        failed -= len(late_repairs)
    retained = len(records)
    state = None
    if live:
        w.runtime_profile(transport.profile_id)
        state = transport.campaign.accounting()
        if state["unknown_turns"] or state["development_turns"] != attempted:
            raise w.WorkflowStop("recovery_campaign_mismatch")
        transport.budget_kind = "development"
    w.freeze(root, manifest)
    w._write(root / "revalidation.json", audit)
    w._write(root / "late-normalization.json", late_repairs)
    w._write(
        root / "recovery.json",
        {
            "authorized_by": "human:jrs",
            "authority": "Continue through timeouts and bugs; complete frozen 42-case assessment.",
            "source_snapshots": snapshots,
            "selection": "earliest valid judgment in source order",
            "retained_judgments": retained,
            "prior_attempts": attempted,
            "prior_failures": failed,
            "prior_duplicate_completions": duplicates,
            "max_attempts_per_missing_judgment": max_attempts,
            "campaign_accounting_before": state,
            "runtime_profile": transport.profile_id if live else "offline_fake",
            "recovery_code_sha256": w._file_digest(Path(__file__)),
        },
    )
    attempts = root / "attempts"
    attempts.mkdir()
    campaign_start = None
    if live:
        (transport.campaign.root / "active-run").mkdir()
        campaign_start = (
            transport.campaign.root
            / "runs"
            / f"{len(list((transport.campaign.root / 'runs').glob('*.start.json'))) + 1:03d}.start.json"
        )
        w._write(
            campaign_start,
            {
                "kind": "development",
                "manifest_sha256": w.canonical_json_sha256(manifest),
                "implementation_sha256": manifest["implementation_sha256"],
                "rubric_sha256": manifest["rubric_sha256"],
                "started_at": w._now(),
                "recovery_root": str(root.resolve()),
            },
        )
    fatal = None
    drain = []
    previous_handler = None
    if live:
        previous_handler = signal.signal(signal.SIGUSR1, lambda *_: drain.append(True))
    for cohort in ("clarification", "assessment"):
        rows = [r for r in manifest["cases"] if r["response_id"] in manifest["split"][cohort]]
        for stage, model in w.MODELS.items():
            if stage == "adjudicator-initial":
                w._write(root / f"{cohort}-first-pass-agreement.json", w._agreement(rows, records))
            for source in rows:
                key = (source["response_id"], stage)
                if key in records:
                    continue
                if stage == "adjudicator-final" and any(
                    (source["response_id"], k) not in records
                    for k in ("r1", "r2", "adjudicator-initial")
                ):
                    continue
                request = request_for(manifest, source, cohort, stage, records)
                for retry in range(max_attempts):
                    if drain:
                        fatal = "maintenance_drain_requested"
                        break
                    if live:
                        # Admission/budget failures happen before an attempt, never retried.
                        try:
                            w.runtime_profile(transport.profile_id)
                            current = transport.campaign.accounting()
                            if (
                                current["unknown_turns"]
                                or current["elapsed_seconds"] >= w.LIMITS["live_seconds"]
                                or current["development_turns"] >= w.LIMITS["development_turns"]
                            ):
                                raise w.WorkflowStop("recovery_budget_or_unknown")
                        except w.WorkflowStop as exc:
                            fatal = str(exc)
                            break
                    start = {
                        "ordinal": attempted + 1,
                        "response_id": source["response_id"],
                        "stage": stage,
                        "cohort": cohort,
                        "requested_model": model,
                        "started_at": w._now(),
                        "retry": retry,
                        "request_sha256": w.canonical_json_sha256(request),
                        "input_sha256": w.canonical_json_sha256(source),
                        "schema_sha256": w.canonical_json_sha256(request["schema"]),
                        "prompt_sha256": w.canonical_json_sha256(w.PROMPT),
                        "manifest_sha256": w.canonical_json_sha256(manifest),
                        "config_sha256": transport.config_sha256
                        if live
                        else w.canonical_json_sha256({"kind": transport.kind}),
                    }
                    attempted += 1
                    base = f"{attempted:03d}"
                    w._write(attempts / f"{base}.start.json", start)
                    output = None
                    began = time.monotonic()
                    try:
                        output = transport.dispatch(request, w.LIMITS["call_seconds"])
                        if output.exit_status != 0:
                            raise w.WorkflowStop("transport_exit")
                        if (
                            not output.session_id
                            or output.session_id in sessions
                            or not output.provider
                            or output.model not in (None, model)
                            or output.runtime_selected_model not in (None, model)
                        ):
                            raise w.WorkflowStop("missing_or_duplicate_observed_identity")
                        sessions.add(output.session_id)
                        value = w._decode(output.raw_output)
                        value, edits = normalize_quote_delimiters(value, source)
                        validate(value, request)
                        result = {"status": "completed", "judgment": value, "validation_errors": []}
                        if edits:
                            result["normalization"] = {
                                "paths": edits,
                                "raw_sha256": hashlib.sha256(
                                    output.raw_output.encode()
                                ).hexdigest(),
                            }
                    except Exception as exc:  # noqa: BLE001 - persist attributable failures
                        failed += 1
                        result = {
                            "status": "failed",
                            "judgment": None,
                            "validation_errors": [
                                str(exc) if isinstance(exc, w.WorkflowStop) else type(exc).__name__
                            ],
                        }
                        if live and output is None:
                            fatal = "dispatch_without_attributable_result"
                        if (
                            isinstance(exc, w.WorkflowStop)
                            and str(exc) == "missing_or_duplicate_observed_identity"
                        ):
                            fatal = str(exc)
                        if output and output.session_id:
                            sessions.add(output.session_id)
                    result.update(
                        attempt_start_sha256=w.canonical_json_sha256(start),
                        completed_at=w._now(),
                        latency_ms=(time.monotonic() - began) * 1000,
                        transport=asdict(output) if output else None,
                    )
                    w._write(attempts / f"{base}.result.json", result)
                    print(
                        json.dumps(
                            {
                                "attempt": attempted,
                                "completed": len(records) + (result["status"] == "completed"),
                                "stage": stage,
                                "cohort": cohort,
                                "status": result["status"],
                                "errors": result["validation_errors"],
                            }
                        ),
                        flush=True,
                    )
                    if result["status"] == "completed":
                        records[key] = result
                        break
                    if fatal:
                        break
                if fatal:
                    break
            if fatal:
                break
        if fatal:
            break
    rows = [r for r in manifest["cases"] if r["response_id"] in manifest["split"]["assessment"]]
    metrics = w._agreement(rows, records)
    complete = len(records) == len(manifest["cases"]) * 4
    outcome, coverage = (
        w.qualification(rows, records, manifest["families"], metrics)
        if complete
        else ("not_assessed", {})
    )
    report = {
        "schema_version": "generation-review-recovery-report/v1",
        "execution_status": "execution_complete" if complete else "execution_failed",
        "assessment_status": outcome,
        "scheduled_cases": len(manifest["cases"]),
        "scheduled_turns": len(manifest["cases"]) * 4,
        "attempted_turns": attempted,
        "completed_turns": len(records),
        "failed_turns": failed,
        "duplicate_completed_turns": duplicates,
        "unknown_turns": transport.campaign.accounting()["unknown_turns"] if live else 0,
        "missing_judgments": len(manifest["cases"]) * 4 - len(records),
        "agreement": metrics,
        "adjudicated_category_coverage": coverage,
        "stop_reason": fatal,
        "manifest_sha256": w.canonical_json_sha256(manifest),
        "campaign_accounting": transport.campaign.accounting() if live else None,
    }
    w._write(
        root / "selected-judgments.json",
        [{"response_id": k[0], "stage": k[1], "result": v} for k, v in records.items()],
    )
    w._write(
        root / "terminal.json",
        {
            "stopped": not complete,
            "ended_at": w._now(),
            "artifact_digests": {
                p.name: w._file_digest(p) for p in sorted(attempts.glob("*.json"))
            },
        },
    )
    w._write(root / "report.json", report)
    if live and campaign_start is not None:
        transport.campaign.end_run(campaign_start, report)
        signal.signal(signal.SIGUSR1, previous_handler)
    return report
