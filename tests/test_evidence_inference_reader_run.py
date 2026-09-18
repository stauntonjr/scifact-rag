"""Finite coordinator contracts; all transports are offline fakes."""

import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
spec = importlib.util.spec_from_file_location(
    "reader_run", Path(__file__).parents[1] / "tools/evidence_inference_reader_run.py"
)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)


def setup_module():
    assert spec and spec.loader and spec.origin
    assert Path(spec.origin).exists(), "runner implementation missing"
    spec.loader.exec_module(runner)


def test_selector_requires_unique_finite_complete_scores():
    assert runner.parse_scores(
        {"results": [{"index": 1, "relevance_score": 3}, {"index": 0, "relevance_score": 2}]}, 2
    ) == [2, 3]
    for results in (
        [{"index": 0, "relevance_score": 1}] * 2,
        [{"index": 0, "relevance_score": float("nan")}, {"index": 1, "relevance_score": 2}],
    ):
        with pytest.raises(ValueError):
            runner.parse_scores({"results": results}, 2)


def test_preflight_uses_article_lengths_not_labels_and_rotation():
    prompts = [
        {
            "prompt_id": str(i),
            "article_id": str(i),
            "full": {"fits": True, "input_tokens": 50 - i},
            "oracle": {"fits": True},
        }
        for i in range(5)
    ]
    assert runner.preflight_ids(prompts) == ["4", "2", "0"]
    assert runner.arm_order(0) == ["full", "selected", "oracle"]
    assert runner.arm_order(1) == ["selected", "oracle", "full"]


def test_started_is_durable_before_send_and_unknown_halts(tmp_path):
    now = [0.0]

    def transport(kind, payload):
        events = runner.read_jsonl(tmp_path / "ledger.jsonl")
        assert events[-1]["status"] == "started"
        now[0] = 61
        return {"ok": True}

    coordinator = runner.Coordinator(tmp_path / "ledger.jsonl", transport, lambda: now[0])
    event = coordinator.dispatch("reader", {"x": 1}, "p", "a", "full", 600)
    assert event["status"] == "unknown"
    with pytest.raises(RuntimeError):
        coordinator.dispatch("reader", {}, "q", "a", "oracle", 600)
    assert len(runner.read_jsonl(tmp_path / "ledger.jsonl")) == 2


def test_no_dispatch_with_less_than_sixty_seconds_remaining(tmp_path):
    coordinator = runner.Coordinator(
        tmp_path / "ledger.jsonl", lambda *args: pytest.fail("unexpected dispatch"), lambda: 541.0
    )
    coordinator.started_at = 0
    with pytest.raises(RuntimeError):
        coordinator.dispatch("reader", {}, "p", "a", "full", 600)
    assert not (tmp_path / "ledger.jsonl").exists()


def synthetic_run(tmp_path, monkeypatch, *, fail=False, reader_failure=None, third_response=None):
    import importlib

    reader = importlib.import_module("evidence_inference_reader")
    from test_evidence_inference_reader import Characters

    prompts = {str(i): {"Intervention": "I", "Comparator": "C", "Outcome": "O"} for i in range(4)}
    views = {str(i): reader.canonical_view(b"synthetic evidence") for i in range(4)}
    refs = [
        {"prompt_id": str(i), "article_id": str(i), "target": "decreased", "intervals": [[0, 9]]}
        for i in range(4)
    ]
    monkeypatch.setattr(reader, "qualified_inputs", lambda *args: ({}, prompts, views, refs, []))
    cohort = tmp_path / "cohort.json"
    cohort.write_text("{}")
    identity = {
        "reader": {
            "model": reader.READER,
            "revision": "reader-revision",
            "files": {"tokenizer.json": "hash"},
            "chat_template_sha256": "template-hash",
        },
        "selector": {
            "model": reader.SELECTOR,
            "revision": reader.SELECTOR_REVISION,
            "files": {"tokenizer.json": "hash"},
        },
    }
    prepared = tmp_path / "prepared"
    reader.prepare(
        cohort,
        cohort,
        cohort,
        cohort,
        prepared,
        reader_tokenizer=Characters(),
        selector_tokenizer=Characters(),
        tokenizer_identity=identity,
    )
    runtime = {
        "tokenizer_identity": identity,
        "exclusive_device_available": True,
        "resource_owner_release": "synthetic owner grant",
        "gpu_process_observation": "synthetic empty device",
        "token_accounting_verified": "synthetic accounting",
    }
    for role in ("reader", "selector"):
        runtime[role] = {
            "model": identity[role]["model"],
            "weight_revision": identity[role]["revision"],
            "serving_image_digest": "sha256:image",
            "runtime_version": "synthetic",
            "startup_configuration": "synthetic",
            "identity_evidence": "synthetic",
            "availability_evidence": "synthetic",
            "base_url": "http://invalid.test",
            "max_model_len": 32768,
            "chat_template_sha256": "template-hash",
        }
    runtime_path = tmp_path / "runtime.json"
    reader.write_json(runtime_path, runtime)
    output = tmp_path / "run"
    calls = []
    now = [0.0]

    def transport(kind, payload):
        calls.append((kind, payload))
        now[0] += 1
        if fail:
            raise TimeoutError("uncertain")
        if kind == "selector":
            return {
                "results": [
                    {"index": i, "relevance_score": 1} for i in range(len(payload["documents"]))
                ]
            }
        third_reader = sum(k == "reader" for k, _ in calls) == 3
        response = {
            "model": "wrong-model" if third_reader and reader_failure == "model" else reader.READER,
            "choices": [{"message": {"content": '{"label":"decreased"}'}}],
            "usage": {
                "prompt_tokens": sum(len(m["content"]) for m in payload["messages"])
                + 10
                + int(third_reader and reader_failure == "tokens"),
                "completion_tokens": 6,
            },
        }
        return third_response(response) if third_reader and third_response else response

    result = runner.run(
        prepared,
        runtime_path,
        output,
        True,
        reader_tokenizer=Characters(),
        transport=transport,
        clock=lambda: now[0],
    )
    return reader, prepared, runtime_path, output, calls, result


def test_fake_run_preflight_is_counted_once_and_evaluation_matches(tmp_path, monkeypatch):
    reader, prepared, runtime, output, calls, result = synthetic_run(tmp_path, monkeypatch)
    assert result["status"] == "complete"
    assert result["request_counts"] == {"reader": 12, "selector": 4}
    assert len(calls) == 16
    assert result["preflight_projection"]["remaining_reader_calls"] == 3
    report = reader.evaluate(prepared, output / "ledger.jsonl", tmp_path / "evaluation")
    assert report["complete_triplets"] == 4
    assert report["arms"]["full"]["accuracy"] == 1
    assert report["arms"]["selected"]["total_seconds_including_selector"] == 8
    with pytest.raises(ValueError, match="resume"):
        runner.run(prepared, runtime, output)


def test_timeout_preserves_partial_unknown_without_retry(tmp_path, monkeypatch):
    reader, prepared, _, output, calls, result = synthetic_run(tmp_path, monkeypatch, fail=True)
    assert result["status"] == "partial"
    assert len(calls) == 1
    report = reader.evaluate(prepared, output / "ledger.jsonl", tmp_path / "evaluation")
    assert report["status"] == "partial"
    assert report["arms"]["full"]["undispatched"] == 4


def test_run_network_disabled_and_identity_mismatch_blocked(tmp_path, monkeypatch):
    _, prepared, runtime_path, _, _, _ = synthetic_run(tmp_path, monkeypatch)
    result = runner.run(prepared, runtime_path, tmp_path / "disabled")
    assert result["status"] == "validated_network_disabled"
    assert not (tmp_path / "disabled").exists()
    runtime = __import__("json").loads(runtime_path.read_text())
    runtime["exclusive_device_available"] = False
    runtime_path.write_text(__import__("json").dumps(runtime))
    with pytest.raises(ValueError, match="exclusive"):
        runner.run(prepared, runtime_path, tmp_path / "blocked", True)


def test_evaluator_rejects_duplicate_completion_and_prepared_tamper(tmp_path, monkeypatch):
    reader, prepared, _, output, _, _ = synthetic_run(tmp_path, monkeypatch)
    ledger = output / "ledger.jsonl"
    ledger.write_text(ledger.read_text() + ledger.read_text().splitlines()[-1] + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        reader.evaluate(prepared, ledger, tmp_path / "evaluation")
    (prepared / "references.jsonl").write_text("{}\n")
    with pytest.raises(ValueError, match="digest"):
        reader.evaluate(prepared, ledger, tmp_path / "evaluation")


def test_runtime_bytes_are_frozen_and_checked_by_evaluator(tmp_path, monkeypatch):
    reader, prepared, runtime, output, _, _ = synthetic_run(tmp_path, monkeypatch)
    assert (output / "runtime.json").read_bytes() == runtime.read_bytes()
    (output / "runtime.json").write_text("{}")
    with pytest.raises(ValueError, match="runtime"):
        reader.evaluate(prepared, output / "ledger.jsonl", tmp_path / "evaluation")


def test_total_http_deadline_interrupts_nonreturning_transport(monkeypatch):
    import signal
    import time

    import httpx

    original = signal.setitimer
    monkeypatch.setattr(
        signal, "setitimer", lambda which, seconds: original(which, 0.02 if seconds else 0)
    )
    monkeypatch.setattr(httpx.Client, "post", lambda *args, **kwargs: time.sleep(2))
    transport = runner.HttpTransport({"reader": {"base_url": "http://invalid.test"}})
    start = time.monotonic()
    with pytest.raises(TimeoutError, match="deadline"):
        transport("reader", {})
    assert time.monotonic() - start < 1


def test_evaluation_separates_native_errors_abstention_invalid_and_attrition(tmp_path, monkeypatch):
    reader, prepared, _, output, _, _ = synthetic_run(tmp_path, monkeypatch)
    ledger = output / "ledger.jsonl"
    events = reader.read_jsonl(ledger)
    for event in events:
        if event["status"] == "completed" and event["arm"] == "full":
            event["response"]["choices"][0]["message"]["content"] = {
                "0": '{"label":"decreased"}',
                "1": '{"label":"increased"}',
                "2": '{"label":"insufficient_evidence"}',
                "3": "malformed",
            }[event["prompt_id"]]
    ledger.unlink()
    reader.write_jsonl(ledger, events)
    report = reader.evaluate(prepared, ledger, tmp_path / "evaluation")
    full = report["arms"]["full"]
    assert full["accuracy"] == 0.25
    assert full["abstentions"] == full["invalid"] == 1
    assert full["classes"]["decreased"]["false_negative"] == 3
    assert full["operational_completion_rate"] == 1
    assert report["complete_triplets"] == 4


@pytest.mark.parametrize("ceiling", [600, 5400])
def test_budget_checks_use_absolute_elapsed_run_time(tmp_path, ceiling):
    now = [0.0]
    coordinator = runner.Coordinator(tmp_path / "ledger.jsonl", lambda *args: {}, lambda: now[0])
    coordinator.started_at = 0
    now[0] = ceiling - 59.9
    with pytest.raises(RuntimeError, match="remaining"):
        coordinator.dispatch("reader", {}, "p", "a", "full", ceiling)


def test_report_exposes_preparation_selector_and_roundtrip_costs(tmp_path, monkeypatch):
    reader, prepared, _, output, _, _ = synthetic_run(tmp_path, monkeypatch)
    report = reader.evaluate(prepared, output / "ledger.jsonl", tmp_path / "evaluation")
    assert report["preparation_seconds"] >= 0
    assert report["selector_input_tokens"] > 0
    assert report["exact_byte_roundtrip_coverage"] == 1
    assert report["invalid_or_unknown_records"] == []


def test_evaluator_rejects_tampered_selected_coordinates(tmp_path, monkeypatch):
    reader, prepared, _, output, _, _ = synthetic_run(tmp_path, monkeypatch)
    ledger = output / "ledger.jsonl"
    events = reader.read_jsonl(ledger)
    for event in events:
        if event["arm"] == "selected":
            event["intervals"] = [[0, 1]]
    ledger.unlink()
    reader.write_jsonl(ledger, events)
    with pytest.raises(ValueError, match="selected"):
        reader.evaluate(prepared, ledger, tmp_path / "evaluation")


@pytest.mark.parametrize(
    "failure,reason",
    [("model", "reader_model_mismatch"), ("tokens", "reader_prompt_tokens_mismatch")],
)
def test_reader_identity_failure_on_third_arm_cannot_be_scored_as_triplet(
    tmp_path, monkeypatch, failure, reason
):
    reader, prepared, _, output, calls, result = synthetic_run(
        tmp_path, monkeypatch, reader_failure=failure
    )
    assert len(calls) == 4  # one selector and three reader calls; no second prompt
    assert result["status"] == "partial"
    events = reader.read_jsonl(output / "ledger.jsonl")
    assert events[-1]["status"] == "failed"
    assert events[-1]["failure_reason"] == reason
    assert events[-1]["response"]["choices"][0]["message"]["content"] == '{"label":"decreased"}'
    report = reader.evaluate(prepared, output / "ledger.jsonl", tmp_path / "evaluation")
    assert report["complete_triplets"] == 0
    assert report["arms"]["oracle"]["count"] == 1
    assert report["arms"]["oracle"]["failed"] == 1
    assert report["arms"]["oracle"]["classes"]["decreased"]["false_negative"] == 1
    assert report["arms"]["oracle"]["accuracy"] == 0


@pytest.mark.parametrize(
    "status,body,reason",
    [
        (503, b"synthetic service unavailable", "http_status"),
        (200, b"synthetic invalid JSON", "http_json_decode"),
    ],
)
def test_received_http_failure_is_retained_and_halts_without_retry(
    tmp_path, monkeypatch, status, body, reason
):
    import base64

    import httpx

    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        return httpx.Response(
            status, content=body, request=httpx.Request("POST", "http://invalid.test")
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    coordinator = runner.Coordinator(
        tmp_path / "ledger.jsonl",
        runner.HttpTransport({"reader": {"base_url": "http://invalid.test"}}),
    )
    event = coordinator.dispatch("reader", {}, "p", "a", "full", input_tokens=1)
    assert event["status"] == "failed"
    assert event["failure_reason"] == reason
    assert event["http_status"] == status
    assert base64.b64decode(event["raw_body_base64"]) == body
    assert runner.read_jsonl(tmp_path / "ledger.jsonl")[-1] == event
    with pytest.raises(RuntimeError, match="halted"):
        coordinator.dispatch("reader", {}, "q", "a", "full", input_tokens=1)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "shape",
    [
        "null_response",
        "list_response",
        "string_response",
        "null_usage",
        "list_usage",
        "string_usage",
    ],
)
def test_failed_response_shapes_do_not_break_optional_token_accounting(
    tmp_path, monkeypatch, shape
):
    def malformed(response):
        value = {"null": None, "list": [], "string": "synthetic"}[shape.split("_")[0]]
        return value if shape.endswith("response") else {**response, "usage": value}

    reader, prepared, _, output, calls, result = synthetic_run(
        tmp_path, monkeypatch, third_response=malformed
    )
    assert len(calls) == 4
    assert result["status"] == "partial"
    before = (output / "ledger.jsonl").read_bytes()
    event = reader.read_jsonl(output / "ledger.jsonl")[-1]
    assert event["status"] == "failed"
    report = reader.evaluate(prepared, output / "ledger.jsonl", tmp_path / "evaluation")
    assert (output / "ledger.jsonl").read_bytes() == before
    assert report["complete_triplets"] == 0
    oracle = report["arms"]["oracle"]
    assert oracle["count"] == oracle["failed"] == 1
    assert oracle["classes"]["decreased"]["false_negative"] == 1
    assert oracle["input_tokens"] == oracle["output_tokens"] == 0


@pytest.mark.parametrize(
    "prompt_tokens,completion_tokens,expected_output",
    [(True, 7, 7), (1.5, -1, 0), ("12", False, 0), (-1, "x", 0), (None, None, 0)],
)
def test_optional_token_counts_accept_only_nonnegative_integers(
    tmp_path, monkeypatch, prompt_tokens, completion_tokens, expected_output
):
    def malformed(response):
        return {
            **response,
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        }

    reader, prepared, _, output, _, _ = synthetic_run(
        tmp_path, monkeypatch, third_response=malformed
    )
    report = reader.evaluate(prepared, output / "ledger.jsonl", tmp_path / "evaluation")
    oracle = report["arms"]["oracle"]
    assert oracle["count"] == oracle["failed"] == 1
    assert oracle["input_tokens"] == 0
    assert oracle["output_tokens"] == expected_output
    assert report["complete_triplets"] == 0
