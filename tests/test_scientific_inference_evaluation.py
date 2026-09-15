from __future__ import annotations

import json
import os
from dataclasses import replace

import pytest

from scifact_rag.evaluation import ComponentRevision
from scifact_rag.scientific_inference import (
    DEBERTA_MODEL,
    DEBERTA_REVISION,
    InferenceLogits,
    ScientificInferenceLabel,
)
from scifact_rag.scientific_inference_evaluation import (
    ScientificInferenceAttemptStarted,
    ScientificInferenceJournal,
    ScientificInferenceResult,
    ScientificInferenceRunManifest,
)
from scifact_rag.strategies import (
    COREF_NOMINAL_DP_MINILM,
    DEFAULT_RETRIEVAL_STRATEGY,
)


def inference_manifest() -> ScientificInferenceRunManifest:
    return ScientificInferenceRunManifest(
        schema_version="scientific-inference-run-manifest/v1",
        run_id="run-1",
        repository_commit="a" * 40,
        evaluation_manifest_sha256="e" * 64,
        source_split="train-validation",
        evidence_class="internal-diagnostic",
        candidate_pool_strategy=DEFAULT_RETRIEVAL_STRATEGY.value,
        candidate_limit_per_generator=50,
        ranking_cutoff=10,
        dp_representation=COREF_NOMINAL_DP_MINILM,
        colbert_model="answerdotai/answerai-colbert-small-v1",
        colbert_revision="c72aa89bc61afdd85373643f3a1a75b2aad6e0fe",
        model=DEBERTA_MODEL,
        model_revision=DEBERTA_REVISION,
        tokenizer=DEBERTA_MODEL,
        tokenizer_revision=DEBERTA_REVISION,
        transformers_version="4.55.0",
        container_image="scifact-rag-scientific-inference@sha256:123",
        endpoint="http://scientific-inference:80",
        context_limit=512,
        request_attempt_policy="at-most-once-per-run",
        components=(ComponentRevision("application-image", "scifact-rag", "sha256:123"),),
        started_at="2026-09-15T14:00:00Z",
        completed_at=None,
        host="spark-3a8f",
        results_path="artifacts/scientific-inference-run-1/results.jsonl",
        test_qrels_inspected=True,
    )


def inference_attempt_started_fixture() -> ScientificInferenceAttemptStarted:
    return ScientificInferenceAttemptStarted(
        schema_version="scientific-inference-attempt-started/v1",
        run_id="run-1",
        candidate_id="c" * 64,
        bundle_digest="b" * 64,
        attempt_id="a" * 64,
        request_digest="d" * 64,
        started_at="2026-09-15T14:01:00Z",
    )


def successful_inference_result_fixture() -> ScientificInferenceResult:
    logits = InferenceLogits(2.0, -1.0, 0.5)
    return ScientificInferenceResult(
        schema_version="scientific-inference-result/v1",
        run_id="run-1",
        candidate_id="c" * 64,
        query_id="1",
        document_id="10",
        claim="Aspirin helps.",
        claim_sha256="1" * 64,
        document_title="Study",
        document_sha256="2" * 64,
        bundle_digest="b" * 64,
        attempt_id="a" * 64,
        request_digest="d" * 64,
        premise_sha256="3" * 64,
        baseline_rank=1,
        colbert_score=0.9,
        gold_label=ScientificInferenceLabel.ENTAILMENT,
        admitted=(),
        rejected=(),
        pair_token_count=17,
        model_revision=DEBERTA_REVISION,
        logits=logits,
        predicted_label=ScientificInferenceLabel.ENTAILMENT,
        evidence_margin=logits.evidence_margin,
        polarity_margin=logits.polarity_margin,
        evidence_coverage="annotated-evidence-present",
        latency_ms=5.0,
        attempt_count=1,
        error_stage=None,
        error_code=None,
        error_message=None,
        completed_at="2026-09-15T14:01:01Z",
    )


def preassembly_failure_fixture() -> ScientificInferenceResult:
    return replace(
        successful_inference_result_fixture(),
        bundle_digest=None,
        attempt_id=None,
        request_digest=None,
        premise_sha256=None,
        pair_token_count=None,
        model_revision=None,
        logits=None,
        predicted_label=None,
        evidence_margin=None,
        polarity_margin=None,
        evidence_coverage="annotated-evidence-absent",
        latency_ms=None,
        attempt_count=0,
        error_stage="assembly",
        error_code="missing_chunks",
        error_message="EvidenceAssemblyError: stored evidence is missing",
    )


def test_manifest_freezes_the_diagnostic_boundary() -> None:
    manifest = inference_manifest()

    assert manifest.source_split == "train-validation"
    assert manifest.candidate_pool_strategy == DEFAULT_RETRIEVAL_STRATEGY.value
    assert manifest.dp_representation == COREF_NOMINAL_DP_MINILM
    assert manifest.context_limit == 512
    assert manifest.request_attempt_policy == "at-most-once-per-run"
    assert ScientificInferenceRunManifest.from_json(manifest.to_json()) == manifest


def test_journal_accepts_started_then_terminal_but_rejects_impossible_transitions(
    tmp_path,
) -> None:
    path = tmp_path / "results.jsonl"
    started = inference_attempt_started_fixture()
    terminal = successful_inference_result_fixture()
    journal = ScientificInferenceJournal.open(path, run_id="run-1")
    journal.append(started)
    journal.append(terminal)

    state = ScientificInferenceJournal.open(path, run_id="run-1").state
    assert state.completed == {"c" * 64}
    assert not state.outcome_unknown

    with pytest.raises(ValueError, match="transition"):
        journal.append(started)


def test_journal_accepts_terminal_failures_before_an_attempt_or_after_assembly(tmp_path) -> None:
    path = tmp_path / "results.jsonl"
    journal = ScientificInferenceJournal.open(path, run_id="run-1")
    journal.append(preassembly_failure_fixture())
    postassembly = replace(
        preassembly_failure_fixture(),
        candidate_id="f" * 64,
        bundle_digest="b" * 64,
        premise_sha256="3" * 64,
        pair_token_count=17,
        error_stage="request-preparation",
        error_code="payload_failure",
    )
    journal.append(postassembly)

    assert journal.state.completed == {"c" * 64, "f" * 64}


def test_unmatched_start_is_outcome_unknown_on_resume(tmp_path) -> None:
    path = tmp_path / "results.jsonl"
    ScientificInferenceJournal.open(path, run_id="run-1").append(
        inference_attempt_started_fixture()
    )

    resumed = ScientificInferenceJournal.open(path, run_id="run-1")

    assert resumed.state.completed == set()
    assert resumed.state.outcome_unknown == {"c" * 64}


def test_journal_rejects_foreign_malformed_and_unknown_events(tmp_path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="row 1"):
        ScientificInferenceJournal.open(path, run_id="run-1")

    path.write_text(json.dumps({"schema_version": "unknown/v1"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        ScientificInferenceJournal.open(path, run_id="run-1")

    path.write_text(
        replace(inference_attempt_started_fixture(), run_id="foreign").to_json() + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="foreign run"):
        ScientificInferenceJournal.open(path, run_id="run-1")


def test_journal_fsyncs_before_observing_the_event(tmp_path, monkeypatch) -> None:
    observed: list[str] = []

    def fake_fsync(file_descriptor: int) -> None:
        assert file_descriptor >= 0
        observed.append("fsync")

    monkeypatch.setattr(os, "fsync", fake_fsync)
    journal = ScientificInferenceJournal.open(
        tmp_path / "results.jsonl",
        run_id="run-1",
        event_observer=lambda event: observed.append(event.schema_version),
    )

    journal.append(inference_attempt_started_fixture())

    assert observed == ["fsync", "scientific-inference-attempt-started/v1"]
