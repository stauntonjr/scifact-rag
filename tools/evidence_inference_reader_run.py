"""Single-coordinator fixed-reader execution; network disabled unless explicit."""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import time
from pathlib import Path

from evidence_inference_reader import (
    ARMS,
    READER,
    SELECTOR,
    SELECTOR_REVISION,
    digest,
    encoded,
    load_prepared,
    load_tokenizers,
    read_jsonl,
    reader_payload,
    write_json,
)


def parse_scores(payload, count):
    """The VllmColbertReranker index contract, additionally rejecting nonfinite scores."""
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != count:
        raise ValueError("wrong selector cardinality")
    scores = [None] * count
    for result in results:
        index = result["index"]
        if type(index) is not int or not 0 <= index < count or scores[index] is not None:
            raise ValueError("duplicate or invalid selector index")
        score = float(result["relevance_score"])
        if not math.isfinite(score):
            raise ValueError("nonfinite selector score")
        scores[index] = score
    if any(s is None for s in scores):
        raise ValueError("missing selector score")
    return scores


def preflight_ids(prompts):
    articles = {}
    for p in sorted(prompts, key=lambda p: p["prompt_id"]):
        if p["full"]["fits"] and p["oracle"]["fits"]:
            articles.setdefault(p["article_id"], p)
    ordered = sorted(articles.values(), key=lambda p: (p["full"]["input_tokens"], p["article_id"]))
    if len(ordered) < 3:
        raise ValueError("fewer than three eligible preflight articles")
    return [ordered[i]["prompt_id"] for i in (0, (len(ordered) - 1) // 2, len(ordered) - 1)]


def arm_order(index):
    shift = index % 3
    return ARMS[shift:] + ARMS[:shift]


class Coordinator:
    def __init__(self, ledger, transport, clock=time.monotonic):
        self.ledger, self.transport, self.clock = ledger, transport, clock
        self.started_at = None
        self.halted = False
        self.counts = {"reader": 0, "selector": 0}
        self.pairs = 0
        self.seen = set()

    def append(self, event):
        with self.ledger.open("a") as handle:
            handle.write(encoded(event).decode() + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def elapsed(self):
        return 0 if self.started_at is None else self.clock() - self.started_at

    def dispatch(self, kind, payload, prompt_id, article_id, arm, ceiling=5400, **metadata):
        key = (prompt_id, arm)
        if self.halted or key in self.seen:
            raise RuntimeError("halted or duplicate dispatch")
        if self.started_at is None:
            self.started_at = self.clock()
        if min(5400, ceiling) - self.elapsed() < 60:
            self.halted = True
            raise RuntimeError("insufficient remaining deadline")
        pairs = len(payload.get("documents", [])) if kind == "selector" else 0
        if (
            self.counts[kind] >= {"reader": 303, "selector": 101}[kind]
            or self.pairs + pairs > 20000
        ):
            self.halted = True
            raise RuntimeError("request ceiling")
        self.seen.add(key)
        self.counts[kind] += 1
        self.pairs += pairs
        request_id = f"{kind}:{prompt_id}:{arm}"
        event = {
            "request_id": request_id,
            "kind": kind,
            "prompt_id": prompt_id,
            "article_id": article_id,
            "arm": arm,
            "payload_sha256": digest(encoded(payload)),
            "payload": payload,
            "status": "started",
            "start_seconds": self.elapsed(),
            "pairs": pairs,
            **metadata,
        }
        self.append(event)
        start = self.clock()
        try:
            response = self.transport(kind, payload)
            seconds = self.clock() - start
            if seconds >= 60 or self.elapsed() > min(5400, ceiling):
                raise TimeoutError("total request deadline")
            terminal = {**event, "status": "completed", "response": response, "seconds": seconds}
        except Exception as exc:  # noqa: BLE001 - any uncertain transport outcome halts dispatch
            self.halted = True
            terminal = {
                **event,
                "status": "unknown",
                "error_type": type(exc).__name__,
                "seconds": self.clock() - start,
            }
        self.append(terminal)
        return terminal


class HttpTransport:
    """SIGALRM enforces elapsed time even when the HTTP peer keeps sending bytes."""

    def __init__(self, runtime):
        self.runtime = runtime

    def __call__(self, kind, payload):
        import httpx

        def timeout(signum, frame):
            raise TimeoutError("60-second total deadline")

        previous = signal.signal(signal.SIGALRM, timeout)
        signal.setitimer(signal.ITIMER_REAL, 60)
        try:
            role = "reader" if kind == "reader" else "selector"
            suffix = "/v1/chat/completions" if kind == "reader" else "/rerank"
            with httpx.Client(
                timeout=httpx.Timeout(60, connect=5), transport=httpx.HTTPTransport(retries=0)
            ) as client:
                response = client.post(
                    self.runtime[role]["base_url"].rstrip("/") + suffix, json=payload
                )
                response.raise_for_status()
                return response.json()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)


def validate_runtime(runtime, manifest):
    if runtime.get("tokenizer_identity") != manifest["tokenizer_identity"]:
        raise ValueError("runtime tokenizer identity mismatch")
    for role, model in (("reader", READER), ("selector", SELECTOR)):
        item = runtime[role]
        if (
            item.get("model") != model
            or item.get("weight_revision") != manifest["tokenizer_identity"][role]["revision"]
        ):
            raise ValueError("model revision mismatch")
        for key in (
            "serving_image_digest",
            "runtime_version",
            "startup_configuration",
            "identity_evidence",
            "availability_evidence",
            "base_url",
        ):
            if not item.get(key):
                raise ValueError(f"missing runtime evidence: {role}.{key}")
    if (
        runtime["selector"]["weight_revision"] != SELECTOR_REVISION
        or runtime["reader"].get("max_model_len") != 32768
    ):
        raise ValueError("runtime limits mismatch")
    if (
        runtime["reader"].get("chat_template_sha256")
        != manifest["tokenizer_identity"]["reader"]["chat_template_sha256"]
    ):
        raise ValueError("runtime template mismatch")
    if (
        not runtime.get("resource_owner_release")
        or not runtime.get("gpu_process_observation")
        or runtime.get("exclusive_device_available") is not True
        or not runtime.get("token_accounting_verified")
    ):
        raise ValueError("missing exclusive resource or token accounting evidence")


def run(
    prepared,
    runtime,
    output,
    execute=False,
    *,
    reader_tokenizer=None,
    transport=None,
    clock=time.monotonic,
):
    if output.exists():
        raise ValueError("output exists; automatic resume is forbidden")
    manifest, prompts = load_prepared(prepared)
    config = json.loads(runtime.read_text())
    validate_runtime(config, manifest)
    if sum(p["selector"]["pairs"] for p in prompts) > 20000:
        raise ValueError("selector pair ceiling")
    preflight = preflight_ids(prompts)
    ordered = sorted(
        prompts, key=lambda p: (digest(f"ei-reader-v1:{p['article_id']}".encode()), p["prompt_id"])
    )
    schedule = [{"prompt_id": p["prompt_id"], "arms": arm_order(i)} for i, p in enumerate(ordered)]
    summary = {
        "execute": execute,
        "preflight": preflight,
        "schedule": schedule,
        "prepared_sha256": digest((prepared / "manifest.json").read_bytes()),
        "runtime_sha256": digest(runtime.read_bytes()),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "status": "validated_network_disabled",
    }
    if not execute:
        return summary
    if reader_tokenizer is None:
        raise ValueError("verified local reader tokenizer required")
    output.mkdir(parents=True)
    write_json(output / "run.json", summary)
    with (output / "runtime.json").open("xb") as handle:
        handle.write(runtime.read_bytes())
        handle.flush()
        os.fsync(handle.fileno())
    coordinator = Coordinator(output / "ledger.jsonl", transport or HttpTransport(config), clock)
    by_id = {p["prompt_id"]: p for p in prompts}
    windows = {r["article_id"]: r["windows"] for r in read_jsonl(prepared / "windows.jsonl")}
    selected = {}
    reader_seconds, selector_per_pair = [], []
    stop = None

    def perform(p, arms, ceiling):
        nonlocal stop
        pid, aid = p["prompt_id"], p["article_id"]
        event = coordinator.dispatch(
            "selector", p["selector"]["payload"], pid, aid, "selector", ceiling
        )
        if event["status"] != "completed":
            raise RuntimeError("selector uncertainty")
        scores = parse_scores(event["response"], len(windows[aid]))
        selector_per_pair.append(event["seconds"] / len(scores))
        indexes = sorted(
            sorted(range(len(scores)), key=lambda i: (-scores[i], windows[aid][i]["start"]))[:2],
            key=lambda i: windows[aid][i]["start"],
        )
        chosen = [windows[aid][i] for i in indexes]
        selected[pid] = reader_payload(p, [w["text"] for w in chosen], reader_tokenizer)
        selected[pid]["intervals"] = [[w["start"], w["end"]] for w in chosen]
        write_json(output / f"selected-{pid}.json", selected[pid])
        if ceiling == 600 and not selected[pid]["fits"]:
            raise RuntimeError("preflight selected overflow")
        for arm in arms:
            request = selected[pid] if arm == "selected" else p[arm]
            if not request["fits"]:
                coordinator.append(
                    {
                        "request_id": f"reader:{pid}:{arm}",
                        "kind": "reader",
                        "prompt_id": pid,
                        "article_id": aid,
                        "arm": arm,
                        "status": "context_overflow",
                        "input_tokens": request["input_tokens"],
                    }
                )
                continue
            event = coordinator.dispatch(
                "reader",
                request["payload"],
                pid,
                aid,
                arm,
                ceiling,
                input_tokens=request["input_tokens"],
                intervals=request.get("intervals"),
            )
            reader_seconds.append(event["seconds"])
            if event["status"] != "completed":
                raise RuntimeError("reader uncertainty")
            response = event["response"]
            if (
                response.get("model") != READER
                or response.get("usage", {}).get("prompt_tokens") != request["input_tokens"]
            ):
                raise RuntimeError("live identity or token accounting mismatch")

    try:
        for pid in preflight:
            perform(by_id[pid], ARMS, 600)
        remaining = [p for p in ordered if p["prompt_id"] not in preflight]
        remaining_reader = sum(
            int(p[arm]["fits"]) if arm != "selected" else 1 for p in remaining for arm in ARMS
        )
        remaining_pairs = sum(p["selector"]["pairs"] for p in remaining)
        projection = coordinator.elapsed() + 1.5 * (
            remaining_reader * max(reader_seconds) + remaining_pairs * max(selector_per_pair)
        )
        summary["preflight_projection"] = {
            "elapsed": coordinator.elapsed(),
            "remaining_reader_calls": remaining_reader,
            "remaining_selector_pairs": remaining_pairs,
            "max_reader_seconds": max(reader_seconds),
            "max_selector_seconds_per_pair": max(selector_per_pair),
            "projected_seconds": projection,
        }
        write_json(output / "preflight.json", summary["preflight_projection"])
        if projection > 5400:
            raise RuntimeError("preflight projection exceeds budget")
        for item in schedule:
            if item["prompt_id"] not in preflight:
                perform(by_id[item["prompt_id"]], item["arms"], 5400)
    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
        stop = str(exc)
    summary.update(
        status="partial" if stop else "complete",
        stop_reason=stop,
        elapsed_seconds=coordinator.elapsed(),
        request_counts=coordinator.counts,
        selector_pairs=coordinator.pairs,
    )
    write_json(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--tokenizer-identity", type=Path)
    parser.add_argument("--reader-tokenizer-dir", type=Path)
    parser.add_argument("--selector-tokenizer-dir", type=Path)
    args = parser.parse_args()
    reader = None
    if args.execute:
        reader, _, identity = load_tokenizers(
            args.tokenizer_identity, args.reader_tokenizer_dir, args.selector_tokenizer_dir
        )
        if identity != json.loads(args.runtime.read_text())["tokenizer_identity"]:
            raise ValueError("runtime local tokenizer mismatch")
    print(
        json.dumps(
            run(args.prepared, args.runtime, args.output, args.execute, reader_tokenizer=reader),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
