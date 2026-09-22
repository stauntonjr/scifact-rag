from __future__ import annotations

import json
from pathlib import Path

import pytest

from scifact_rag import generation_review_workflow as workflow


def case(number=1):
    return {
        "response_id": f"{number:032x}",
        "claim": "Fictional widgets improved.",
        "answer": "Fictional widgets improved.",
        "evidence": [
            {"document_id": str(number), "title": "Fiction", "text": "Fictional widgets improved."}
        ],
    }


def judgment(source):
    return {
        "schema_version": "generation-model-judgment/v2",
        "response_id": source["response_id"],
        "review_v2": {
            **{key: "not_applicable" for key in workflow.TRISTATE_FIELDS},
            "grounded": "yes",
            "material_overstatement": "none",
            "material_errors": [],
            "notes": "",
        },
        "adequacy": {
            "supplied_context_answerability": "answerable",
            "answer_adequacy": "adequate",
            "insufficiency_handling": "not_applicable",
            "rationale": "",
        },
        "rationale": {
            "summary": "Exact fictional support.",
            "answer_quotes": [source["answer"]],
            "evidence_quotes": [
                {
                    "document_id": source["evidence"][0]["document_id"],
                    "quote": source["evidence"][0]["text"],
                }
            ],
        },
    }


class FakeTransport:
    kind = "offline_fake"

    def __init__(self, failure=None):
        self.requests = []
        self.failure = failure

    def dispatch(self, request, timeout_seconds):
        self.requests.append(request)
        if self.failure:
            raise self.failure
        payload = judgment(request["case"])
        if request["stage"] == "adjudicator-final":
            payload = {
                "schema_version": "adjudicator-final/v2",
                "judgment": payload,
                "initial_sha256": request["initial_sha256"],
                "r1_sha256": request["r1_sha256"],
                "r2_sha256": request["r2_sha256"],
                "disposition": "resolved",
                "change_explanation": "Unchanged.",
            }
        return workflow.TransportResult(
            raw_output=json.dumps(payload),
            model=request["requested_model"],
            session_id=f"fake-{len(self.requests)}",
            provider="offline_fake",
            exit_status=0,
        )


def manifest():
    rows = [case(1), case(2)]
    return workflow.prepare_manifest(
        rows,
        {"clarification": [rows[0]["response_id"]], "assessment": [rows[1]["response_id"]]},
        {r["response_id"]: str(i) for i, r in enumerate(rows)},
        inventory_sha256="a" * 64,
        selection_sha256="b" * 64,
        rubric="Responsible substantive support defines answerable.",
        mode="fictional",
    )


def test_complete_offline_pipeline_freezes_initial_before_peers(tmp_path):
    transport = FakeTransport()
    result = workflow.run(tmp_path / "run", manifest(), transport)
    assert result["execution_status"] == "execution_complete"
    assert result["scheduled_turns"] == result["completed_turns"] == 8
    assert result["assessment_status"] == "insufficient_category_coverage"
    for request in transport.requests:
        if request["stage"] != "adjudicator-final":
            assert "peers" not in request and "initial" not in request
    assert [r["stage"] for r in transport.requests] == [
        "r1",
        "r2",
        "adjudicator-initial",
        "adjudicator-final",
    ] * 2
    with pytest.raises(workflow.WorkflowStop, match="fresh"):
        workflow.run(tmp_path / "run", manifest(), transport)


def test_timeout_preserves_attempt_and_all_denominators(tmp_path):
    result = workflow.run(tmp_path / "run", manifest(), FakeTransport(TimeoutError()))
    assert result["execution_status"] == "execution_failed"
    assert result["attempted_turns"] == result["failed_turns"] == 1
    assert result["scheduled_turns"] == 8
    assert result["assessment_status"] == "not_assessed"
    assert len(list((tmp_path / "run" / "attempts").glob("*.start.json"))) == 1


@pytest.mark.parametrize("mutation", ["enum", "quote", "extra", "adequacy"])
def test_invalid_judgments_fail(mutation):
    source = case()
    value = judgment(source)
    if mutation == "enum":
        value["review_v2"]["grounded"] = "maybe"
    if mutation == "quote":
        value["rationale"]["answer_quotes"] = ["altered"]
    if mutation == "extra":
        value["provenance"] = {}
    if mutation == "adequacy":
        value["adequacy"]["supplied_context_answerability"] = "not_answerable"
    with pytest.raises(workflow.WorkflowStop):
        workflow.validate_judgment(value, source)


def test_runtime_cannot_be_certified_by_boolean(tmp_path):
    report = workflow.qualify_runtime(tmp_path / "runtime", {"tools_disabled": True})
    assert report["status"] == "runtime_stopped"
    assert report["code"] == "unverified_runtime_enforcement"


def test_reordered_and_cross_family_split_rejected():
    rows = [case(2), case(1)]
    with pytest.raises(workflow.WorkflowStop):
        workflow.prepare_manifest(
            rows,
            {"clarification": [rows[0]["response_id"]], "assessment": [rows[1]["response_id"]]},
            {r["response_id"]: "same" for r in rows},
            inventory_sha256="a" * 64,
            selection_sha256="b" * 64,
            rubric="R",
            mode="fictional",
        )


def test_unknown_dispatch_cannot_resume(tmp_path):
    class Death(FakeTransport):
        def dispatch(self, request, timeout_seconds):
            raise KeyboardInterrupt()

    root = tmp_path / "run"
    with pytest.raises(KeyboardInterrupt):
        workflow.run(root, manifest(), Death())
    result = workflow.report(root)
    assert result["unknown_turns"] == 1
    assert result["not_attempted_turns"] == 7
    with pytest.raises(workflow.WorkflowStop, match="fresh"):
        workflow.run(root, manifest(), FakeTransport())


@pytest.mark.parametrize("problem", ["json", "session", "model", "exit", "final_digest"])
def test_transport_failures_are_attributable(tmp_path, problem):
    class BadTransport(FakeTransport):
        def dispatch(self, request, timeout_seconds):
            result = super().dispatch(request, timeout_seconds)
            from dataclasses import replace

            if problem == "json":
                return replace(result, raw_output="not json")
            if problem == "session":
                return replace(result, session_id=None)
            if problem == "model":
                return replace(result, model="substitute")
            if problem == "exit":
                return replace(result, exit_status=1)
            if problem == "final_digest" and request["stage"] == "adjudicator-final":
                value = json.loads(result.raw_output)
                value["initial_sha256"] = "f" * 64
                return replace(result, raw_output=json.dumps(value))
            return result

    root = tmp_path / "run"
    result = workflow.run(root, manifest(), BadTransport())
    assert result["execution_status"] == "execution_failed"
    assert result["failed_turns"] == 1
    results = sorted((root / "attempts").glob("*.result.json"))
    assert json.loads(results[-1].read_text())["transport"] is not None


def test_all_first_passes_precede_adjudication(tmp_path):
    rows = [case(i) for i in range(1, 5)]
    prepared = workflow.prepare_manifest(
        rows,
        {"clarification": [], "assessment": [r["response_id"] for r in rows]},
        {r["response_id"]: str(i) for i, r in enumerate(rows)},
        inventory_sha256="a" * 64,
        selection_sha256="b" * 64,
        rubric="Fictional",
        mode="fictional",
    )
    fake = FakeTransport()
    workflow.run(tmp_path / "run", prepared, fake)
    assert [r["stage"] for r in fake.requests] == (
        ["r1"] * 4 + ["r2"] * 4 + ["adjudicator-initial"] * 4 + ["adjudicator-final"] * 4
    )
    final = fake.requests[-1]
    assert final["initial"]["status"] == "completed"
    assert final["initial_sha256"] == workflow.canonical_json_sha256(final["initial"])


def test_public_report_contains_no_case_text(tmp_path):
    result = workflow.run(tmp_path / "run", manifest(), FakeTransport())
    rendered = json.dumps(result)
    for text in ["Fictional widgets", "Exact fictional support", "Unchanged."]:
        assert text not in rendered


def test_budget_and_live_admission(tmp_path):
    rows = [case(i) for i in range(1, 7)]
    with pytest.raises(workflow.WorkflowStop, match="budget"):
        workflow.prepare_manifest(
            rows,
            {"clarification": [], "assessment": [r["response_id"] for r in rows]},
            {r["response_id"]: str(i) for i, r in enumerate(rows)},
            inventory_sha256="a" * 64,
            selection_sha256="b" * 64,
            rubric="Fictional",
            mode="fictional",
        )
    fake = FakeTransport()
    fake.kind = "live"
    with pytest.raises(workflow.WorkflowStop, match="unverified_runtime"):
        workflow.run(tmp_path / "live", manifest(), fake)
    assert not (tmp_path / "live").exists()


def test_tampered_completed_artifact_fails_closed(tmp_path):
    root = tmp_path / "run"
    workflow.run(root, manifest(), FakeTransport())
    path = root / "attempts" / "001.result.json"
    value = json.loads(path.read_text())
    value["judgment"]["review_v2"]["grounded"] = "no"
    path.write_text(json.dumps(value))
    with pytest.raises(workflow.WorkflowStop, match="digest"):
        workflow.report(root)


def test_adjudicated_coverage_and_adequacy_drive_gate():
    rows = [case(i) for i in range(1, 11)]
    records = {}
    families = {r["response_id"]: str(i % 3) for i, r in enumerate(rows)}
    for i, row in enumerate(rows):
        value = judgment(row)
        for field, (section, positive, negative) in workflow.DIMENSIONS.items():
            value[section][field] = positive if i < 5 else negative
        for role in ("r1", "r2"):
            records[(row["response_id"], role)] = {"judgment": value}
        records[(row["response_id"], "adjudicator-final")] = {
            "judgment": {"judgment": value, "disposition": "resolved"}
        }
    metrics = workflow._agreement(rows, records)
    outcome, counts = workflow.qualification(rows, records, families, metrics)
    assert outcome == "qualified_development_screening"
    assert counts["answer_adequacy"]["adequate"] == {"cases": 5, "families": 3}
    records[(rows[0]["response_id"], "adjudicator-final")]["judgment"]["disposition"] = "unresolved"
    assert workflow.qualification(rows, records, families, metrics)[0] == "reliability_failed"


def test_absent_evidence_cannot_also_contain_spans():
    source = case()
    value = judgment(source)
    value["review_v2"]["grounded"] = "no"
    value["review_v2"]["material_overstatement"] = "present"
    value["review_v2"]["material_errors"] = [
        {
            "category": "unsupported_claim",
            "answer_span": {"start": 0, "end": 5},
            "evidence_absent": True,
            "evidence_spans": [{"evidence_index": 0, "start": 0, "end": 5}],
        }
    ]
    with pytest.raises(workflow.WorkflowStop, match="evidence spans"):
        workflow.validate_judgment(value, source)


def test_duplicate_session_is_not_a_fresh_request(tmp_path):
    from dataclasses import replace

    class Reused(FakeTransport):
        def dispatch(self, request, timeout_seconds):
            return replace(super().dispatch(request, timeout_seconds), session_id="same")

    result = workflow.run(tmp_path / "run", manifest(), Reused())
    assert result["completed_turns"] == 1
    assert result["failed_turns"] == 1
    assert result["attempted_turns"] == 2


def test_cli_runtime_stop_is_persisted(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    discovery = tmp_path / "discovery.json"
    discovery.write_text('{"tools_disabled":true}')
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[1] / "tools" / "generation_review_workflow.py"),
            "qualify-runtime",
            "--discovery",
            str(discovery),
            "--output",
            str(tmp_path / "admission"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["code"] == "unverified_runtime_enforcement"
    assert (tmp_path / "admission" / "runtime-admission.json").exists()


def test_development_cli_exposes_registered_rehearsal_reuse_option():
    import subprocess
    import sys
    from pathlib import Path

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[1] / "tools" / "generation_review_workflow.py"),
            "run-development",
            "--help",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--rehearsal-reuse" in result.stdout


def test_campaign_binds_prior_attempts_and_stops_unknown(tmp_path):
    prior = tmp_path / "prior"
    prior.mkdir()
    (prior / "attempt-start.json").write_text('{"sequence":1}')
    (prior / "terminal.json").write_text('{"status":"completed","seconds":29.417745875}')
    campaign = workflow.Campaign.create(tmp_path / "campaign", [prior])
    assert campaign.accounting()["engineering_turns"] == 1
    assert campaign.accounting()["elapsed_seconds"] == 29.417745875
    attempt = campaign.reserve("engineering", "a" * 64)
    assert attempt.name == "002.start.json"
    with pytest.raises(workflow.WorkflowStop, match="unknown"):
        campaign.reserve("engineering", "b" * 64)


def test_runtime_profile_requires_reviewed_pin(tmp_path):
    with pytest.raises(workflow.WorkflowStop, match="unreviewed"):
        workflow.CodexTransport("arbitrary-profile", workflow.Campaign.create(tmp_path / "c", []))


def test_candidate_cli_adapter_parses_only_allowlisted_metadata(tmp_path, monkeypatch):
    import sys

    monkeypatch.setenv("OPENAI_API_KEY", "fictional-do-not-use")
    monkeypatch.setenv("CODEX_MODEL_PROVIDER", "fictional-override")

    executable = tmp_path / "fake-codex"
    executable.write_text(
        "#!"
        + sys.executable
        + "\n"
        + """import json, sys, os
from pathlib import Path
assert "OPENAI_API_KEY" not in os.environ
assert "CODEX_MODEL_PROVIDER" not in os.environ
assert "CODEX_HOME" in os.environ
args = sys.argv
assert "--ephemeral" in args and "--strict-config" in args
assert Path(args[args.index("-C") + 1]).is_dir()
assert list(Path(args[args.index("-C") + 1]).iterdir()) == []
request = json.load(sys.stdin)
Path(args[args.index("--output-last-message") + 1]).write_text('{"ok": true}')
print(json.dumps({"type": "thread.started", "thread_id": "observed-session"}))
print(json.dumps({"type": "item.completed", "item": {"type": "reasoning", "text": "PRIVATE_REASONING"}}))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 3, "output_tokens": 2}}))
"""
    )
    executable.chmod(0o700)
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}")
    profile = {
        "executable": str(executable),
        "executable_sha256": workflow._file_digest(executable),
        "evidence_files": {str(evidence): workflow._file_digest(evidence)},
        "evidence_roles": {
            role: str(evidence)
            for role in [
                "capability_controls",
                "schema_probe",
                "prompt_inspection",
            ]
        },
        "config": {"agents.enabled": False},
        "configuration_sources": {},
        "codex_home": str(tmp_path),
        "model_identity_event": "turn.completed",
        "model_identity_field": "model",
    }
    monkeypatch.setitem(workflow.APPROVED_RUNTIME_PROFILES, "test-only", profile)
    campaign = workflow.Campaign.create(tmp_path / "campaign", [])
    transport = workflow.CodexTransport("test-only", campaign)
    result = transport.dispatch(
        {
            "schema": workflow.judgment_schema(),
            "requested_model": "gpt-5.6-sol",
            "case": case(),
            "prompt": "P",
            "rubric": "R",
        },
        2,
    )
    assert result.session_id == "observed-session"
    assert result.model is None
    assert result.usage == {"input_tokens": 3, "output_tokens": 2, "total_tokens": None}
    saved = (tmp_path / "campaign" / "attempts" / "001.result.json").read_text()
    assert "PRIVATE_REASONING" not in saved
    assert campaign.accounting()["engineering_turns"] == 1
    assert campaign.accounting()["unknown_turns"] == 0


def test_stderr_is_reduced_to_coarse_class_without_text():
    assert (
        workflow._classify_stderr("rate limit exceeded: secret-token", 1) == "rate_or_budget_limit"
    )
    assert workflow._classify_stderr("warning only", 0) == "stderr_without_failure"
    assert workflow._classify_stderr("", 0) is None


def test_campaign_counts_failed_dispatch_and_enforces_turn_boundary(tmp_path):
    campaign = workflow.Campaign.create(tmp_path / "campaign", [])
    for _ in range(20):
        start = campaign.reserve("engineering", "a" * 64)
        campaign.finish(start, 1, workflow.TransportResult("", None, None, None, -9))
    assert campaign.accounting()["engineering_turns"] == 20
    with pytest.raises(workflow.WorkflowStop, match="budget"):
        campaign.reserve("engineering", "b" * 64)
    assert campaign.accounting()["total_turns"] == 20


def test_campaign_development_requires_frozen_rehearsal(tmp_path):
    campaign = workflow.Campaign.create(tmp_path / "campaign", [])
    value = manifest()
    value["mode"] = "development"
    with pytest.raises(workflow.WorkflowStop, match="rehearsal"):
        campaign.begin_run(value)
    assert not (tmp_path / "campaign" / "active-run").exists()


def test_campaign_accepts_only_registered_digest_bound_rehearsal_reuse(tmp_path, monkeypatch):
    campaign = workflow.Campaign.create(tmp_path / "campaign", [])
    rehearsal = manifest()
    rehearsal_start = campaign.begin_run(rehearsal)
    campaign.end_run(rehearsal_start, {"execution_status": "execution_complete"})
    rehearsal_result = rehearsal_start.with_name("001.result.json")

    reuse = {
        "schema_version": "generation-review-rehearsal-reuse/v1",
        "source_run_start_sha256": workflow._file_digest(rehearsal_start),
        "source_run_result_sha256": workflow._file_digest(rehearsal_result),
        "rehearsal_implementation_sha256": rehearsal["implementation_sha256"],
        "rubric_sha256": rehearsal["rubric_sha256"],
        **workflow.rehearsal_contract_digests(),
        "evidence_origin": "reused",
        "applicability": "Only runtime-profile registration changed.",
        "independent_reviewer": "test/verifier",
    }
    descriptor = tmp_path / "reuse.json"
    descriptor.write_text(json.dumps(reuse))
    monkeypatch.setitem(
        workflow.APPROVED_REHEARSAL_REUSES,
        "test-reuse",
        {
            "descriptor_path": str(descriptor),
            "descriptor_sha256": workflow._file_digest(descriptor),
        },
    )
    development = {**rehearsal, "mode": "development", "implementation_sha256": "c" * 64}
    original = descriptor.read_text()
    descriptor.write_text(original + "\n")
    with pytest.raises(workflow.WorkflowStop, match="reuse_descriptor_digest"):
        workflow.Campaign(campaign.root, rehearsal_reuse_id="test-reuse").begin_run(development)

    descriptor.write_text(original)
    reused = workflow.Campaign(campaign.root, rehearsal_reuse_id="test-reuse")
    start = reused.begin_run(development)
    assert start.name == "002.start.json"


def test_rehearsal_contract_digest_closes_transitive_and_gate_surfaces():
    workflow_source = Path(workflow.__file__).read_text()
    pilot_source = Path(workflow.__file__.replace("workflow.py", "pilot.py")).read_text()
    cli_source = (
        Path(workflow.__file__).parents[2] / "tools/generation_review_workflow.py"
    ).read_text()
    baseline = workflow._contract_digests_from_sources(workflow_source, pilot_source, cli_source)

    validator_changed = pilot_source.replace(
        "def _validate_review(", "def _validate_review_changed("
    )
    assert (
        workflow._contract_digests_from_sources(workflow_source, validator_changed, cli_source)[
            "pilot_module_sha256"
        ]
        != baseline["pilot_module_sha256"]
    )

    dimensions_changed = workflow_source.replace(
        '"grounded": ("review_v2", "yes", "no")',
        '"grounded": ("review_v2", "no", "yes")',
    )
    assert (
        workflow._contract_digests_from_sources(dimensions_changed, pilot_source, cli_source)[
            "workflow_contract_sha256"
        ]
        != baseline["workflow_contract_sha256"]
    )

    campaign_changed = workflow_source.replace(
        'state["total_turns"] >= LIMITS["combined_turns"]',
        'state["total_turns"] >= LIMITS["combined_turns"] + 1',
    )
    assert (
        workflow._contract_digests_from_sources(campaign_changed, pilot_source, cli_source)[
            "execution_gate_sha256"
        ]
        != baseline["execution_gate_sha256"]
    )

    cli_changed = cli_source.replace(
        'command.add_argument("--rehearsal-reuse")', 'command.add_argument("--reuse")'
    )
    assert (
        workflow._contract_digests_from_sources(workflow_source, pilot_source, cli_changed)[
            "execution_gate_sha256"
        ]
        != baseline["execution_gate_sha256"]
    )


def development_fixture():
    rows = [case(i) for i in range(1, 43)]
    split = {
        "clarification": [r["response_id"] for r in rows[:11]],
        "assessment": [r["response_id"] for r in rows[11:]],
    }
    families = {
        r["response_id"]: ("c" + str(i % 3) if i < 11 else "a" + str(i % 17))
        for i, r in enumerate(rows)
    }
    return rows, split, families


def test_development_rejects_altered_source_with_original_hashes(monkeypatch):
    import copy

    rows, split, families = development_fixture()
    monkeypatch.setattr(
        workflow, "_frozen_development_projection", lambda: (copy.deepcopy(rows), split, families)
    )
    altered = copy.deepcopy(rows)
    altered[0]["answer"] = "Altered retained answer."
    with pytest.raises(workflow.WorkflowStop, match="frozen_source"):
        workflow.prepare_manifest(
            altered,
            split,
            families,
            inventory_sha256=workflow.FROZEN_SOURCE_DIGESTS["source-inventory.json"],
            selection_sha256=workflow.FROZEN_SOURCE_DIGESTS["selection.json"],
            rubric="R",
            mode="development",
        )


def test_evidence_projection_drops_historical_labels():
    value = manifest()
    value["cases"][0]["evidence"][0]["historical_label"] = "SECRET_OLD_LABEL"
    result = workflow.prepare_manifest(
        value["cases"],
        value["split"],
        value["families"],
        inventory_sha256="a" * 64,
        selection_sha256="b" * 64,
        rubric="R",
        mode="fictional",
    )
    assert "SECRET_OLD_LABEL" not in json.dumps(result)


def test_uncertain_answerability_remains_in_adequacy_denominator():
    rows = [case()]
    value = judgment(rows[0])
    value["adequacy"]["supplied_context_answerability"] = "uncertain"
    value["adequacy"]["answer_adequacy"] = "not_applicable"
    records = {(rows[0]["response_id"], role): {"judgment": value} for role in ("r1", "r2")}
    metric = workflow._agreement(rows, records)["answer_adequacy"]
    assert metric["scheduled"] == 1
    assert metric["uncertain_or_missing"] == 1
    assert metric["exact_agreements"] == 0
    value["adequacy"]["supplied_context_answerability"] = "not_answerable"
    assert workflow._agreement(rows, records)["answer_adequacy"]["scheduled"] == 0


def test_insufficiency_uncertainty_prevents_qualification():
    rows = [case(i) for i in range(1, 11)]
    records = {}
    families = {r["response_id"]: str(i % 3) for i, r in enumerate(rows)}
    for i, row in enumerate(rows):
        value = judgment(row)
        for field, (section, positive, negative) in workflow.DIMENSIONS.items():
            value[section][field] = positive if i < 5 else negative
        value["adequacy"]["insufficiency_handling"] = "uncertain"
        for role in ("r1", "r2"):
            records[(row["response_id"], role)] = {"judgment": value}
        records[(row["response_id"], "adjudicator-final")] = {
            "judgment": {"judgment": value, "disposition": "resolved"}
        }
    assert (
        workflow.qualification(rows, records, families, workflow._agreement(rows, records))[0]
        == "reliability_failed"
    )


def test_unavailable_observed_model_is_not_fabricated_or_rejected(tmp_path):
    from dataclasses import replace

    class Unavailable(FakeTransport):
        def dispatch(self, request, timeout_seconds):
            return replace(
                super().dispatch(request, timeout_seconds),
                model=None,
                runtime_selected_model=request["requested_model"],
            )

    result = workflow.run(tmp_path / "run", manifest(), Unavailable())
    assert result["execution_status"] == "execution_complete"
    saved = json.loads((tmp_path / "run" / "attempts" / "001.result.json").read_text())
    assert saved["transport"]["model"] is None
    assert saved["transport"]["runtime_selected_model"] == "gpt-5.6-sol"


def test_first_pass_payload_excludes_execution_labels_and_peers():
    request = {
        "case": case(),
        "prompt": "P",
        "rubric": "R",
        "stage": "r1",
        "cohort": "assessment",
        "requested_model": "model",
        "peers": {"bad": True},
    }
    assert set(workflow.model_payload(request)) == {"case", "prompt", "rubric"}


def test_runtime_rechecks_configuration_sources(tmp_path, monkeypatch):
    executable = tmp_path / "binary"
    executable.write_text("fake")
    config = tmp_path / "config.toml"
    evidence = tmp_path / "evidence"
    evidence.write_text("evidence")
    profile = {
        "executable": str(executable),
        "executable_sha256": workflow._file_digest(executable),
        "evidence_files": {str(evidence): workflow._file_digest(evidence)},
        "evidence_roles": {
            role: str(evidence)
            for role in ("capability_controls", "schema_probe", "prompt_inspection")
        },
        "configuration_sources": {str(config): None},
        "codex_home": str(tmp_path),
        "config": {},
    }
    monkeypatch.setitem(workflow.APPROVED_RUNTIME_PROFILES, "guard-test", profile)
    assert workflow.runtime_profile("guard-test") == profile
    config.write_text("changed=true")
    with pytest.raises(workflow.WorkflowStop, match="configuration"):
        workflow.runtime_profile("guard-test")


@pytest.mark.parametrize("exists", [False, True])
def test_registered_descriptor_missing_or_changed_fails_closed(tmp_path, monkeypatch, exists):
    monkeypatch.setattr(workflow, "__file__", str(tmp_path / "src/scifact_rag/workflow.py"))
    if exists:
        (tmp_path / "profile.json").write_text("{}")
    monkeypatch.setitem(
        workflow.APPROVED_RUNTIME_PROFILES,
        "descriptor-test",
        {"descriptor_path": "profile.json", "descriptor_sha256": "a" * 64},
    )
    with pytest.raises(workflow.WorkflowStop, match="descriptor_digest"):
        workflow.runtime_profile("descriptor-test")


def test_config_drift_requalification_preserves_original_profile():
    assert set(workflow.APPROVED_RUNTIME_PROFILES) >= {
        "mac-subscription-review-v2",
        "mac-subscription-review-v2-config2",
    }
    original = workflow.APPROVED_RUNTIME_PROFILES["mac-subscription-review-v2"]
    requalified = workflow.APPROVED_RUNTIME_PROFILES["mac-subscription-review-v2-config2"]
    assert original["descriptor_path"] != requalified["descriptor_path"]
    assert original["descriptor_sha256"] != requalified["descriptor_sha256"]


@pytest.mark.parametrize("field,category", sorted(workflow.MATERIAL_ERROR_CATEGORY_FIELDS.items()))
def test_schema_explains_every_yes_annotation_mapping(field, category):
    schema = workflow.judgment_schema()["properties"]["review_v2"]["properties"]
    assert f"category={category}" in schema[field]["description"]
    assert f"{field}=yes" in workflow.PROMPT
    value = judgment(case())
    value["review_v2"].update({field: "yes", "grounded": "no", "material_overstatement": "present"})
    value["review_v2"]["material_errors"] = [
        {
            "category": category,
            "answer_span": {"start": 0, "end": 9},
            "evidence_absent": False,
            "evidence_spans": [{"evidence_index": 0, "start": 0, "end": 9}],
        }
    ]
    workflow.validate_judgment(value, case())


def test_multi_yes_requires_each_category_but_allows_shared_valid_spans():
    value = judgment(case())
    review = value["review_v2"]
    review.update(
        {
            "causal_strengthening": "yes",
            "negation_omission": "yes",
            "qualifier_omission": "yes",
            "grounded": "no",
            "material_overstatement": "present",
        }
    )

    def annotation(category):
        return {
            "category": category,
            "answer_span": {"start": 0, "end": 9},
            "evidence_absent": False,
            "evidence_spans": [{"evidence_index": 0, "start": 0, "end": 9}],
        }

    review["material_errors"] = [annotation("causal_strengthening")]
    with pytest.raises(workflow.WorkflowStop, match="matching material error categories"):
        workflow.validate_judgment(value, case())
    review["material_errors"].extend([annotation("negation_loss"), annotation("qualifier_loss")])
    workflow.validate_judgment(value, case())


def test_many_fields_can_share_one_category_but_annotation_requires_matching_yes():
    value = judgment(case())
    review = value["review_v2"]
    review.update(
        {
            "population_generalization": "yes",
            "population_omission": "yes",
            "grounded": "no",
            "material_overstatement": "present",
        }
    )
    review["material_errors"] = [
        {
            "category": "population_generalization",
            "answer_span": {"start": 0, "end": 9},
            "evidence_absent": False,
            "evidence_spans": [{"evidence_index": 0, "start": 0, "end": 9}],
        }
    ]
    workflow.validate_judgment(value, case())
    review.update({"population_generalization": "no", "population_omission": "no"})
    with pytest.raises(workflow.WorkflowStop):
        workflow.validate_judgment(value, case())
    description = workflow.judgment_schema()["properties"]["review_v2"]["properties"][
        "material_errors"
    ]["description"]
    assert "population_generalization=yes or population_omission=yes" in description
    assert "unsupported_claim" in description
    assert "clean pass" in description
