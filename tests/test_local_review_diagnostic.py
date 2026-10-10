from __future__ import annotations

import json
import subprocess
import sys

import pytest

from scifact_rag import local_review_diagnostic as diagnostic


def test_fixture_has_frozen_coverage_and_model_payload_hides_references(tmp_path):
    fixture = tmp_path / "diagnostic.json"
    fixture.write_text(json.dumps(diagnostic.example_fixture()))

    loaded = diagnostic.load_fixture(fixture)
    assert len(loaded["cases"]) == 24
    assert loaded["rubric_sha256"]
    mixed = next(item for item in loaded["cases"] if item["case"]["response_id"] == f"{19:032x}")
    assert mixed["reference"]["expected"]["review_v2"]["grounded"] == "yes"
    assert mixed["reference"]["expected"]["review_v2"]["comparison_omission"] == "no"
    assert mixed["reference"]["expected"]["adequacy"]["answer_adequacy"] == "adequate"
    for field in diagnostic.workflow.TRISTATE_FIELDS:
        error = next(
            item
            for item in loaded["cases"]
            if item["reference"]["target"] == field and item["reference"]["variant"] == "error"
        )
        faithful = next(
            item
            for item in loaded["cases"]
            if item["reference"]["target"] == field and item["reference"]["variant"] == "faithful"
        )
        assert error["reference"]["expected"]["review_v2"][field] == "yes"
        assert faithful["reference"]["expected"]["review_v2"][field] == "no"
    assert diagnostic.model_payload(loaded["cases"][0], "rubric") == {
        "case": loaded["cases"][0]["case"],
        "rubric": "rubric",
        "schema": diagnostic.judgment_schema(final=False),
    }


def test_run_persists_attempts_and_separates_semantic_failure(tmp_path):
    fixture = tmp_path / "diagnostic.json"
    fixture.write_text(json.dumps(diagnostic.example_fixture()))
    preflight = {"services": [{"endpoint": "http://127.0.0.1:8000", "model": "existing"}]}

    result = diagnostic.run(
        tmp_path / "run",
        diagnostic.load_fixture(fixture),
        FakeTransport(),
        preflight,
        rubric="rubric",
    )

    assert result["execution_status"] == "execution_complete"
    assert result["attempted"] == result["completed"] == 24
    assert result["semantic_disagreements"] == 0
    assert len(list((tmp_path / "run" / "attempts").glob("*.start.json"))) == 24


def test_runner_never_passes_reference_data_to_the_transport(tmp_path):
    fixture = tmp_path / "diagnostic.json"
    fixture.write_text(json.dumps(diagnostic.example_fixture()))
    transport = CapturingTransport()
    diagnostic.run(
        tmp_path / "run",
        diagnostic.load_fixture(fixture),
        transport,
        {"services": [{"endpoint": "http://127.0.0.1:8000", "model": "existing"}]},
        rubric="rubric",
    )
    assert all("reference" not in payload for payload in transport.payloads)


def test_run_refuses_missing_preflight_and_unknown_dispatch(tmp_path):
    fixture = tmp_path / "diagnostic.json"
    fixture.write_text(json.dumps(diagnostic.example_fixture()))
    loaded = diagnostic.load_fixture(fixture)

    with pytest.raises(diagnostic.DiagnosticStop, match="preflight"):
        diagnostic.run(tmp_path / "missing", loaded, FakeTransport(), None, rubric="rubric")

    with pytest.raises(KeyboardInterrupt):
        diagnostic.run(
            tmp_path / "unknown",
            loaded,
            InterruptingTransport(),
            {"services": [{"endpoint": "http://127.0.0.1:8000", "model": "existing"}]},
            rubric="rubric",
        )
    report = diagnostic.report(tmp_path / "unknown", loaded)
    assert report["unknown"] == 1
    assert report["not_attempted"] == 23


def test_unknown_transport_stops_without_turning_a_maybe_dispatched_call_into_failure(tmp_path):
    fixture = tmp_path / "diagnostic.json"
    fixture.write_text(json.dumps(diagnostic.example_fixture()))
    loaded = diagnostic.load_fixture(fixture)
    result = diagnostic.run(
        tmp_path / "unknown-transport",
        loaded,
        UnknownTransport(),
        {"services": [{"endpoint": "http://127.0.0.1:8000", "model": "existing"}]},
        rubric="rubric",
    )
    assert result["unknown"] == 1
    assert result["failed"] == 0
    assert result["not_attempted"] == 23


def test_unattributable_transport_exception_stops_as_unknown(tmp_path):
    fixture = tmp_path / "diagnostic.json"
    fixture.write_text(json.dumps(diagnostic.example_fixture()))
    result = diagnostic.run(
        tmp_path / "generic-transport",
        diagnostic.load_fixture(fixture),
        GenericFailTransport(),
        {"services": [{"endpoint": "http://127.0.0.1:8000", "model": "existing"}]},
        rubric="rubric",
    )
    assert result["unknown"] == 1
    assert result["failed"] == 0
    assert result["not_attempted"] == 23


def test_observed_model_mismatch_persists_failure_and_stops_arm(tmp_path):
    fixture = tmp_path / "diagnostic.json"
    fixture.write_text(json.dumps(diagnostic.example_fixture()))
    result = diagnostic.run(
        tmp_path / "wrong-model",
        diagnostic.load_fixture(fixture),
        WrongModelTransport(),
        {"services": [{"endpoint": "http://127.0.0.1:8000", "model": "existing"}]},
        rubric="rubric",
    )
    assert result["attempted"] == 1
    assert result["failed"] == 1
    assert result["unknown"] == 0
    assert result["not_attempted"] == 23
    assert json.loads((tmp_path / "wrong-model" / "terminal.json").read_text())["status"] == (
        "runtime_identity_mismatch"
    )


class FakeTransport:
    kind = "offline_fake"
    model_id = "existing"

    def dispatch(self, payload, timeout_seconds):
        source = payload["case"]
        expected = diagnostic.expected_for_case(source["response_id"])
        return diagnostic.LocalTransportResult(
            raw_output=json.dumps(diagnostic.judgment_from_expected(source, expected)),
            model="existing",
            request_id="request-" + source["response_id"],
            status_code=200,
        )


class InterruptingTransport(FakeTransport):
    def dispatch(self, payload, timeout_seconds):
        raise KeyboardInterrupt()


class UnknownTransport(FakeTransport):
    def dispatch(self, payload, timeout_seconds):
        raise diagnostic.UnknownDispatch("request may have reached server")


class GenericFailTransport(FakeTransport):
    def dispatch(self, payload, timeout_seconds):
        raise RuntimeError("unknown whether request was received")


class WrongModelTransport(FakeTransport):
    def dispatch(self, payload, timeout_seconds):
        result = super().dispatch(payload, timeout_seconds)
        return diagnostic.LocalTransportResult(
            raw_output=result.raw_output,
            model="unexpected-model",
            request_id=result.request_id,
            status_code=result.status_code,
        )


class CapturingTransport(FakeTransport):
    def __init__(self):
        self.payloads = []

    def dispatch(self, payload, timeout_seconds):
        self.payloads.append(payload)
        return super().dispatch(payload, timeout_seconds)


def test_prepare_command_writes_frozen_fixture_without_model_dispatch(tmp_path):
    fixture = tmp_path / "local_review_diagnostic_v1.json"
    command = [
        sys.executable,
        "tools/local_review_diagnostic.py",
        "prepare",
        "--fixture",
        str(fixture),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    assert fixture.exists()
    assert json.loads(completed.stdout)["case_count"] == 24
    assert diagnostic.load_fixture(fixture)["fixture_sha256"]


def test_execute_command_reports_missing_preflight_without_dispatch(tmp_path):
    fixture = tmp_path / "local_review_diagnostic_v1.json"
    fixture.write_text(json.dumps(diagnostic.example_fixture()))
    completed = subprocess.run(
        [
            sys.executable,
            "tools/local_review_diagnostic.py",
            "execute",
            "--fixture",
            str(fixture),
            "--preflight",
            str(tmp_path / "missing.json"),
            "--rubric",
            "docs/project/generation-review-rubric-v3-draft.md",
            "--endpoint",
            "http://127.0.0.1:1",
            "--model",
            "test",
            "--output",
            str(tmp_path / "output"),
            "--execute",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "missing_preflight" in completed.stderr
    assert not (tmp_path / "output").exists()
