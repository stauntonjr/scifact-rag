from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Sequence
from dataclasses import replace

import pytest

from scifact_rag.domain import (
    EvidenceChunk,
    EvidenceDocument,
    RetrievalCandidate,
    RetrievalSignal,
    SearchHit,
)
from scifact_rag.evaluation import (
    ComponentRevision,
    GenerationEvaluationCase,
    GenerationEvaluationSet,
    GoldRationale,
    ScientificStance,
)
from scifact_rag.metrics import evaluate_rankings
from scifact_rag.scientific_inference import (
    DEBERTA_MODEL,
    DEBERTA_REVISION,
    EvidenceAssemblyError,
    EvidenceBundle,
    EvidenceChunkSelection,
    InferenceLogits,
    InferenceRequest,
    InferenceResponse,
    ScientificInferenceLabel,
    bundle_identity,
    candidate_identity,
    canonical_payload_digest,
    inference_request_payload,
    request_identity,
)
from scifact_rag.scientific_inference_evaluation import (
    ScientificInferenceAttemptStarted,
    ScientificInferenceEvaluationExecutor,
    ScientificInferenceEvaluator,
    ScientificInferenceJournal,
    ScientificInferenceResult,
    ScientificInferenceRunManifest,
    build_scientific_inference_report,
    write_scientific_inference_failures,
    write_scientific_inference_report,
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
    result = successful_inference_result_fixture()
    assert result.bundle_digest is not None
    return ScientificInferenceAttemptStarted(
        schema_version="scientific-inference-attempt-started/v1",
        run_id="run-1",
        candidate_id="c" * 64,
        bundle_digest=result.bundle_digest,
        attempt_id="a" * 64,
        request_digest="d" * 64,
        started_at="2026-09-15T14:01:00Z",
    )


def successful_inference_result_fixture() -> ScientificInferenceResult:
    logits = InferenceLogits(2.0, -1.0, 0.5)
    evidence = EvidenceChunkSelection(
        "10",
        COREF_NOMINAL_DP_MINILM,
        0,
        "evidence-10",
        hashlib.sha256(b"evidence-10").hexdigest(),
        0.8,
    )
    premise = "[TITLE] Study\n[EVIDENCE ordinal=0] evidence-10"
    bundle = EvidenceBundle(
        document_id="10",
        title="Study",
        premise=premise,
        pair_token_count=17,
        admitted=(evidence,),
        rejected=(),
        omitted_ranges=(),
    )
    return ScientificInferenceResult(
        schema_version="scientific-inference-result/v1",
        run_id="run-1",
        candidate_id="c" * 64,
        query_id="1",
        document_id="10",
        claim="Aspirin helps.",
        claim_sha256=hashlib.sha256(b"Aspirin helps.").hexdigest(),
        document_title="Study",
        document_sha256="2" * 64,
        bundle_digest=bundle_identity(bundle),
        attempt_id="a" * 64,
        request_digest="d" * 64,
        premise_sha256=hashlib.sha256(premise.encode("utf-8")).hexdigest(),
        baseline_rank=1,
        colbert_score=0.9,
        gold_label=ScientificInferenceLabel.ENTAILMENT,
        admitted=(evidence,),
        rejected=(),
        pair_token_count=17,
        model=DEBERTA_MODEL,
        model_revision=DEBERTA_REVISION,
        tokenizer=DEBERTA_MODEL,
        tokenizer_revision=DEBERTA_REVISION,
        tokenizer_maximum_length=512,
        scorer="colbert-content",
        scorer_revision="c72aa89bc61afdd85373643f3a1a75b2aad6e0fe",
        evidence_assembly_version="scientific-evidence-bundle/v1",
        omitted_ranges=(),
        source_order_restored=True,
        title_included=True,
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
        admitted=(),
        rejected=(),
        model_revision=None,
        omitted_ranges=(),
        source_order_restored=False,
        title_included=False,
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
    successful = successful_inference_result_fixture()
    postassembly = replace(
        preassembly_failure_fixture(),
        candidate_id="f" * 64,
        bundle_digest=successful.bundle_digest,
        premise_sha256=successful.premise_sha256,
        pair_token_count=17,
        admitted=(
            EvidenceChunkSelection(
                "10",
                COREF_NOMINAL_DP_MINILM,
                0,
                "evidence-10",
                hashlib.sha256(b"evidence-10").hexdigest(),
                0.8,
            ),
        ),
        source_order_restored=True,
        title_included=True,
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


class FixedPoolSource:
    def __init__(self, candidates: Sequence[RetrievalCandidate]) -> None:
        self.candidates = list(candidates)
        self.calls: list[tuple[str, int]] = []

    def retrieve_pool(
        self, query: str, *, limit: int
    ) -> tuple[list[SearchHit], list[RetrievalCandidate]]:
        self.calls.append((query, limit))
        ranked = [
            SearchHit(
                candidate.document.doc_id, candidate.document.title, candidate.document.text, 1.0
            )
            for candidate in self.candidates[:limit]
        ]
        return ranked, list(self.candidates)


class FixedStoredChunkSource:
    def __init__(self, overrides: dict[str, str] | None = None) -> None:
        self.overrides = overrides or {}

    def load_chunks(
        self,
        document_ids: Sequence[str],
        representations: Sequence[str],
    ) -> list[EvidenceChunk]:
        assert tuple(representations) == (COREF_NOMINAL_DP_MINILM,)
        return [
            EvidenceChunk(
                document_id,
                0,
                self.overrides.get(document_id, f"evidence-{document_id}"),
                COREF_NOMINAL_DP_MINILM,
            )
            for document_id in document_ids
        ]


class FixedAssembler:
    def __init__(self, *, fail_document_id: str | None = None) -> None:
        self.fail_document_id = fail_document_id

    def assemble(self, claim: str, document: EvidenceDocument) -> EvidenceBundle:
        if document.doc_id == self.fail_document_id:
            raise EvidenceAssemblyError("missing_chunks", "stored evidence is missing")
        text = f"evidence-{document.doc_id}"
        admitted = EvidenceChunkSelection(
            document.doc_id,
            COREF_NOMINAL_DP_MINILM,
            0,
            text,
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
            0.8,
        )
        return EvidenceBundle(
            document_id=document.doc_id,
            title=document.title,
            premise=f"[TITLE] {document.title}\n[EVIDENCE ordinal=0] {text}",
            pair_token_count=17,
            admitted=(admitted,),
            rejected=(),
            omitted_ranges=(),
        )


class RecordingClient:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls: list[InferenceRequest] = []

    def classify(self, request: InferenceRequest) -> InferenceResponse:
        self.events.append("http-request")
        self.calls.append(request)
        return InferenceResponse(
            request.attempt_id,
            DEBERTA_REVISION,
            request.expected_pair_tokens,
            InferenceLogits(2.0, -1.0, 0.5),
        )


class FailingClient(RecordingClient):
    def classify(self, request: InferenceRequest) -> InferenceResponse:
        self.events.append("http-request")
        self.calls.append(request)
        raise TimeoutError("endpoint detail must not leak")


def single_case_fixture() -> GenerationEvaluationSet:
    return GenerationEvaluationSet(
        (
            GenerationEvaluationCase(
                schema_version="generation-evaluation-case/v1",
                query_id="1",
                claim="Aspirin helps.",
                source_split="train-validation",
                expected_stance=ScientificStance.SUPPORT,
                cited_document_ids=("10",),
                rationales=(GoldRationale("10", ScientificStance.SUPPORT, (0,), ("evidence-10",)),),
            ),
        )
    )


def candidate_fixture(doc_id: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        EvidenceDocument(doc_id, f"Title {doc_id}", f"Abstract {doc_id}"),
        (RetrievalSignal("colbert-content", COREF_NOMINAL_DP_MINILM, 0.8, 1, False),),
    )


def test_executor_persists_start_before_one_request_and_processes_the_full_pool(tmp_path) -> None:
    events: list[str] = []
    client = RecordingClient(events)
    executor = ScientificInferenceEvaluationExecutor(
        FixedPoolSource([candidate_fixture("11"), candidate_fixture("10")]),
        ScientificInferenceEvaluator(FixedAssembler(), client),
        FixedStoredChunkSource(),
        event_observer=lambda event: events.append(
            "attempt-started"
            if isinstance(event, ScientificInferenceAttemptStarted)
            else "terminal-result"
        ),
    )

    summary = executor.run(
        run_id="run-1",
        evaluation_set=single_case_fixture(),
        retrieval_limit=10,
        output=tmp_path / "results.jsonl",
    )

    assert events == [
        "attempt-started",
        "http-request",
        "terminal-result",
        "attempt-started",
        "http-request",
        "terminal-result",
    ]
    assert [request.premise.splitlines()[0] for request in client.calls] == [
        "[TITLE] Title 10",
        "[TITLE] Title 11",
    ]
    assert summary.expected_candidates == 2
    assert summary.scored_candidates == 2


def test_resume_does_not_resend_an_unmatched_start(tmp_path) -> None:
    output = tmp_path / "results.jsonl"
    case = single_case_fixture().cases[0]
    candidate = candidate_fixture("10")
    bundle = FixedAssembler().assemble(case.claim, candidate.document)
    candidate_id = candidate_identity("run-1", case.query_id, case.claim, candidate.document)
    bundle_digest = bundle_identity(bundle)
    intent = {
        "schema_version": "scientific-inference-request/v1",
        "premise": bundle.premise,
        "hypothesis": case.claim,
        "expected_pair_tokens": bundle.pair_token_count,
    }
    attempt_id = request_identity(candidate_id, bundle_digest, intent)
    request = InferenceRequest(attempt_id, bundle.premise, case.claim, bundle.pair_token_count)
    ScientificInferenceJournal.open(output, run_id="run-1").append(
        ScientificInferenceAttemptStarted(
            _STARTED_SCHEMA_FOR_TEST,
            "run-1",
            candidate_id,
            bundle_digest,
            attempt_id,
            canonical_payload_digest(inference_request_payload(request)),
            "2026-09-15T14:01:00Z",
        )
    )
    client = RecordingClient([])

    summary = ScientificInferenceEvaluationExecutor(
        FixedPoolSource([candidate]),
        ScientificInferenceEvaluator(FixedAssembler(), client),
        FixedStoredChunkSource(),
    ).run(
        run_id="run-1",
        evaluation_set=single_case_fixture(),
        retrieval_limit=10,
        output=output,
    )

    assert client.calls == []
    assert summary.outcome_unknown == 1
    assert summary.complete is False


def test_assembly_failure_is_terminal_without_an_attempt(tmp_path) -> None:
    output = tmp_path / "results.jsonl"
    client = RecordingClient([])
    executor = ScientificInferenceEvaluationExecutor(
        FixedPoolSource([candidate_fixture("10")]),
        ScientificInferenceEvaluator(FixedAssembler(fail_document_id="10"), client),
        FixedStoredChunkSource(),
    )

    summary = executor.run(
        run_id="run-1",
        evaluation_set=single_case_fixture(),
        retrieval_limit=10,
        output=output,
    )
    result = next(iter(ScientificInferenceJournal.open(output, "run-1").state.results.values()))

    assert client.calls == []
    assert summary.failed_candidates == 1
    assert result.bundle_digest is None
    assert result.attempt_id is None
    assert result.attempt_count == 0


def test_request_failure_is_terminal_after_exactly_one_attempt(tmp_path) -> None:
    output = tmp_path / "results.jsonl"
    client = FailingClient([])
    executor = ScientificInferenceEvaluationExecutor(
        FixedPoolSource([candidate_fixture("10")]),
        ScientificInferenceEvaluator(FixedAssembler(), client),
        FixedStoredChunkSource(),
    )

    summary = executor.run(
        run_id="run-1",
        evaluation_set=single_case_fixture(),
        retrieval_limit=10,
        output=output,
    )
    result = next(iter(ScientificInferenceJournal.open(output, "run-1").state.results.values()))

    assert len(client.calls) == 1
    assert summary.failed_candidates == 1
    assert result.attempt_id is not None
    assert result.attempt_count == 1
    assert result.error_stage == "request"
    assert result.error_message == "TimeoutError: request failed"


def test_resume_rejects_a_semantically_corrupted_terminal_row(tmp_path) -> None:
    output = tmp_path / "results.jsonl"
    executor = ScientificInferenceEvaluationExecutor(
        FixedPoolSource([candidate_fixture("10")]),
        ScientificInferenceEvaluator(FixedAssembler(), RecordingClient([])),
        FixedStoredChunkSource(),
    )
    executor.run(
        run_id="run-1",
        evaluation_set=single_case_fixture(),
        retrieval_limit=10,
        output=output,
    )
    original_rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

    for field, value in (("gold_label", "neutral"), ("evidence_coverage", "not-annotated")):
        rows = [dict(row) for row in original_rows]
        rows[-1][field] = value
        output.write_text(
            "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="retained result"):
            executor.run(
                run_id="run-1",
                evaluation_set=single_case_fixture(),
                retrieval_limit=10,
                output=output,
            )

    rows = [dict(row) for row in original_rows]
    rows[-1] = dict(rows[-1])
    rows[-1]["admitted"] = [dict(item) for item in rows[-1]["admitted"]]
    rows[-1]["admitted"][0]["text"] = "altered evidence"
    rows[-1]["admitted"][0]["text_sha256"] = hashlib.sha256(b"altered evidence").hexdigest()
    output.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="premise_sha256"):
        executor.run(
            run_id="run-1",
            evaluation_set=single_case_fixture(),
            retrieval_limit=10,
            output=output,
        )

    output.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in original_rows
        ),
        encoding="utf-8",
    )
    drifted = ScientificInferenceEvaluationExecutor(
        FixedPoolSource([candidate_fixture("10")]),
        ScientificInferenceEvaluator(FixedAssembler(), RecordingClient([])),
        FixedStoredChunkSource({"10": "different stored evidence"}),
    )
    with pytest.raises(ValueError, match="stored DP evidence"):
        drifted.run(
            run_id="run-1",
            evaluation_set=single_case_fixture(),
            retrieval_limit=10,
            output=output,
        )


_STARTED_SCHEMA_FOR_TEST = "scientific-inference-attempt-started/v1"


def scored_result(
    candidate_id: str,
    document_id: str,
    gold: ScientificInferenceLabel,
    logits: InferenceLogits,
    *,
    baseline_rank: int,
) -> ScientificInferenceResult:
    text = f"evidence-{document_id}"
    admitted = (
        EvidenceChunkSelection(
            document_id,
            COREF_NOMINAL_DP_MINILM,
            0,
            text,
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
            0.8,
        ),
    )
    premise = f"[TITLE] Study\n[EVIDENCE ordinal=0] {text}"
    bundle = EvidenceBundle(
        document_id=document_id,
        title="Study",
        premise=premise,
        pair_token_count=17,
        admitted=admitted,
        rejected=(),
        omitted_ranges=(),
    )
    return replace(
        successful_inference_result_fixture(),
        candidate_id=candidate_id,
        document_id=document_id,
        document_sha256=candidate_id,
        baseline_rank=baseline_rank,
        gold_label=gold,
        admitted=admitted,
        premise_sha256=hashlib.sha256(premise.encode("utf-8")).hexdigest(),
        bundle_digest=bundle_identity(bundle),
        logits=logits,
        predicted_label=logits.predicted_label,
        evidence_margin=logits.evidence_margin,
        polarity_margin=logits.polarity_margin,
        evidence_coverage=(
            "annotated-evidence-present" if document_id == "10" else "not-annotated"
        ),
    )


def test_report_derives_metrics_controls_and_ranking_from_raw_records() -> None:
    records = (
        scored_result(
            "1" * 64,
            "10",
            ScientificInferenceLabel.ENTAILMENT,
            InferenceLogits(3.0, 0.0, -1.0),
            baseline_rank=1,
        ),
        scored_result(
            "2" * 64,
            "11",
            ScientificInferenceLabel.NEUTRAL,
            InferenceLogits(0.0, 1.0, 2.0),
            baseline_rank=2,
        ),
        scored_result(
            "3" * 64,
            "12",
            ScientificInferenceLabel.NEUTRAL,
            InferenceLogits(0.0, 0.0, 2.0),
            baseline_rank=3,
        ),
        scored_result(
            "4" * 64,
            "13",
            ScientificInferenceLabel.NEUTRAL,
            InferenceLogits(-1.0, 0.0, 2.0),
            baseline_rank=4,
        ),
        replace(
            preassembly_failure_fixture(),
            candidate_id="5" * 64,
            document_id="14",
            document_sha256="5" * 64,
            baseline_rank=5,
            gold_label=ScientificInferenceLabel.NEUTRAL,
            evidence_coverage="not-annotated",
        ),
    )

    report = build_scientific_inference_report(
        records,
        evaluation_set=single_case_fixture(),
        run_id="run-1",
        expected_candidates=6,
        outcome_unknown_candidates=1,
    )

    assert report.complete is False
    assert report.scored_candidates == 4
    assert report.failed_candidates == 1
    assert report.outcome_unknown_candidates == 1
    assert report.three_way.confusion["entailment"]["entailment"] == 1
    assert report.label_prior.predicted_label == "neutral"
    assert report.evidence_partitions.annotated_evidence_present == 1
    assert report.ranking == evaluate_rankings(
        {"1": {"10": 1}}, {"1": ["10", "11", "12", "13", "14"]}, 10
    )


def test_report_and_failure_outputs_are_atomic_and_failure_tags_start_empty(tmp_path) -> None:
    failure = preassembly_failure_fixture()
    report = build_scientific_inference_report(
        (failure,),
        evaluation_set=single_case_fixture(),
        run_id="run-1",
        expected_candidates=1,
        outcome_unknown_candidates=0,
    )
    report_path = tmp_path / "report.json"
    failure_path = tmp_path / "failures.jsonl"

    write_scientific_inference_report(report, report_path)
    write_scientific_inference_failures((failure,), failure_path)

    assert json.loads(report_path.read_text(encoding="utf-8"))["failed_candidates"] == 1
    failure_row = json.loads(failure_path.read_text(encoding="utf-8"))
    assert failure_row["error_stage"] == "assembly"
    assert failure_row["phenomenon_tags"] == []
