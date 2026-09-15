from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .domain import RetrievalCandidate
from .evaluation import (
    ComponentRevision,
    GenerationEvaluationCase,
    GenerationEvaluationSet,
    ScientificStance,
)
from .ports import CandidatePoolSource, EvidenceBundleAssembler, ScientificInferenceClient
from .scientific_inference import (
    DEBERTA_MODEL,
    DEBERTA_REVISION,
    EvidenceAssemblyError,
    EvidenceChunkRejection,
    EvidenceChunkSelection,
    InferenceLogits,
    InferenceRequest,
    ScientificInferenceLabel,
    bundle_identity,
    candidate_identity,
    canonical_payload_digest,
    inference_request_payload,
    request_identity,
)
from .strategies import COREF_NOMINAL_DP_MINILM, DEFAULT_RETRIEVAL_STRATEGY

_MANIFEST_SCHEMA = "scientific-inference-run-manifest/v1"
_STARTED_SCHEMA = "scientific-inference-attempt-started/v1"
_RESULT_SCHEMA = "scientific-inference-result/v1"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COLBERT_MODEL = "answerdotai/answerai-colbert-small-v1"
_COLBERT_REVISION = "c72aa89bc61afdd85373643f3a1a75b2aad6e0fe"
_EVIDENCE_COVERAGE = {
    "not-annotated",
    "gold-document-absent",
    "annotated-evidence-absent",
    "annotated-evidence-present",
}


@dataclass(frozen=True, slots=True)
class ScientificInferenceRunManifest:
    schema_version: str
    run_id: str
    repository_commit: str
    evaluation_manifest_sha256: str
    source_split: str
    evidence_class: str
    candidate_pool_strategy: str
    candidate_limit_per_generator: int
    ranking_cutoff: int
    dp_representation: str
    colbert_model: str
    colbert_revision: str
    model: str
    model_revision: str
    tokenizer: str
    tokenizer_revision: str
    transformers_version: str
    container_image: str
    endpoint: str
    context_limit: int
    request_attempt_policy: str
    components: tuple[ComponentRevision, ...]
    started_at: str
    completed_at: str | None
    host: str
    results_path: str
    test_qrels_inspected: bool

    def __post_init__(self) -> None:
        if self.schema_version != _MANIFEST_SCHEMA:
            raise ValueError(f"schema_version must be {_MANIFEST_SCHEMA}")
        _validate_safe_name("run_id", self.run_id)
        if not _HEX_40.fullmatch(self.repository_commit):
            raise ValueError("repository_commit must be a lowercase 40-character Git commit")
        _validate_digest("evaluation_manifest_sha256", self.evaluation_manifest_sha256)
        fixed_values = {
            "source_split": (self.source_split, "train-validation"),
            "evidence_class": (self.evidence_class, "internal-diagnostic"),
            "candidate_pool_strategy": (
                self.candidate_pool_strategy,
                DEFAULT_RETRIEVAL_STRATEGY.value,
            ),
            "dp_representation": (self.dp_representation, COREF_NOMINAL_DP_MINILM),
            "colbert_model": (self.colbert_model, _COLBERT_MODEL),
            "colbert_revision": (self.colbert_revision, _COLBERT_REVISION),
            "model": (self.model, DEBERTA_MODEL),
            "model_revision": (self.model_revision, DEBERTA_REVISION),
            "tokenizer": (self.tokenizer, DEBERTA_MODEL),
            "tokenizer_revision": (self.tokenizer_revision, DEBERTA_REVISION),
            "request_attempt_policy": (
                self.request_attempt_policy,
                "at-most-once-per-run",
            ),
        }
        for field_name, (actual, expected) in fixed_values.items():
            if actual != expected:
                raise ValueError(f"{field_name} must be {expected}")
        if self.candidate_limit_per_generator != 50:
            raise ValueError("candidate_limit_per_generator must be 50")
        if self.ranking_cutoff != 10:
            raise ValueError("ranking_cutoff must be 10")
        if self.context_limit != 512:
            raise ValueError("context_limit must be 512")
        for field_name in ("transformers_version", "container_image", "endpoint", "host"):
            _validate_text(field_name, getattr(self, field_name))
        if not self.components or any(
            not isinstance(component, ComponentRevision) for component in self.components
        ):
            raise ValueError("components must be a non-empty ComponentRevision tuple")
        names = [component.component for component in self.components]
        if len(names) != len(set(names)):
            raise ValueError("component names must be unique")
        object.__setattr__(
            self,
            "components",
            tuple(sorted(self.components, key=lambda component: component.component)),
        )
        started = _parse_utc("started_at", self.started_at)
        if (
            self.completed_at is not None
            and _parse_utc("completed_at", self.completed_at) < started
        ):
            raise ValueError("completed_at must not precede started_at")
        _validate_results_path(self.results_path)
        if self.test_qrels_inspected is not True:
            raise ValueError("test_qrels_inspected must record the existing inspection as true")

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, serialized: str) -> ScientificInferenceRunManifest:
        raw = _json_object(serialized, "manifest")
        if set(raw) != {field.name for field in fields(cls)}:
            raise ValueError("manifest fields do not match scientific-inference-run-manifest/v1")
        raw_components = raw["components"]
        if not isinstance(raw_components, list):
            raise TypeError("manifest components must be a JSON array")
        component_fields = {field.name for field in fields(ComponentRevision)}
        components: list[ComponentRevision] = []
        for value in raw_components:
            if not isinstance(value, dict) or set(value) != component_fields:
                raise ValueError("manifest component fields do not match ComponentRevision")
            components.append(ComponentRevision(**value))
        values: dict[str, Any] = dict(raw)
        values["components"] = tuple(components)
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ScientificInferenceAttemptStarted:
    schema_version: str
    run_id: str
    candidate_id: str
    bundle_digest: str
    attempt_id: str
    request_digest: str
    started_at: str

    def __post_init__(self) -> None:
        if self.schema_version != _STARTED_SCHEMA:
            raise ValueError(f"schema_version must be {_STARTED_SCHEMA}")
        _validate_safe_name("run_id", self.run_id)
        for field_name in ("candidate_id", "bundle_digest", "attempt_id", "request_digest"):
            _validate_digest(field_name, getattr(self, field_name))
        _parse_utc("started_at", self.started_at)

    def to_json(self) -> str:
        return _canonical_json(asdict(self))


@dataclass(frozen=True, slots=True)
class ScientificInferenceResult:
    schema_version: str
    run_id: str
    candidate_id: str
    query_id: str
    document_id: str
    claim: str
    claim_sha256: str
    document_title: str
    document_sha256: str
    bundle_digest: str | None
    attempt_id: str | None
    request_digest: str | None
    premise_sha256: str | None
    baseline_rank: int | None
    colbert_score: float | None
    gold_label: ScientificInferenceLabel
    admitted: tuple[EvidenceChunkSelection, ...]
    rejected: tuple[EvidenceChunkRejection, ...]
    pair_token_count: int | None
    model_revision: str | None
    logits: InferenceLogits | None
    predicted_label: ScientificInferenceLabel | None
    evidence_margin: float | None
    polarity_margin: float | None
    evidence_coverage: str
    latency_ms: float | None
    attempt_count: int
    error_stage: str | None
    error_code: str | None
    error_message: str | None
    completed_at: str

    def __post_init__(self) -> None:
        if self.schema_version != _RESULT_SCHEMA:
            raise ValueError(f"schema_version must be {_RESULT_SCHEMA}")
        _validate_safe_name("run_id", self.run_id)
        _validate_digest("candidate_id", self.candidate_id)
        for field_name in ("query_id", "document_id", "claim"):
            _validate_text(field_name, getattr(self, field_name))
        for field_name in ("claim_sha256", "document_sha256"):
            _validate_digest(field_name, getattr(self, field_name))
        for field_name in ("bundle_digest", "attempt_id", "request_digest", "premise_sha256"):
            value = getattr(self, field_name)
            if value is not None:
                _validate_digest(field_name, value)
        _validate_optional_positive("baseline_rank", self.baseline_rank)
        _validate_optional_finite("colbert_score", self.colbert_score)
        if not isinstance(self.gold_label, ScientificInferenceLabel):
            raise TypeError("gold_label must be a ScientificInferenceLabel")
        if any(not isinstance(item, EvidenceChunkSelection) for item in self.admitted):
            raise TypeError("admitted must contain EvidenceChunkSelection values")
        if any(not isinstance(item, EvidenceChunkRejection) for item in self.rejected):
            raise TypeError("rejected must contain EvidenceChunkRejection values")
        _validate_optional_positive("pair_token_count", self.pair_token_count)
        if self.evidence_coverage not in _EVIDENCE_COVERAGE:
            raise ValueError("evidence_coverage is unsupported")
        _validate_optional_nonnegative("latency_ms", self.latency_ms)
        if self.attempt_count not in (0, 1):
            raise ValueError("attempt_count must be zero or one")
        _parse_utc("completed_at", self.completed_at)
        self._validate_outcome()

    def _validate_outcome(self) -> None:
        error_fields = (self.error_stage, self.error_code, self.error_message)
        has_error = any(value is not None for value in error_fields)
        if has_error and not all(
            isinstance(value, str) and value.strip() for value in error_fields
        ):
            raise ValueError("error fields must all be non-empty or all be null")
        if self.attempt_count != (1 if self.attempt_id is not None else 0):
            raise ValueError("attempt_count must match attempt identity presence")
        if self.attempt_id is not None and (
            self.bundle_digest is None or self.request_digest is None
        ):
            raise ValueError("an attempted result requires bundle and request digests")
        if self.bundle_digest is None and any(
            value is not None
            for value in (self.premise_sha256, self.pair_token_count, self.request_digest)
        ):
            raise ValueError("pre-assembly results cannot contain bundle provenance")
        if self.bundle_digest is not None and (
            self.premise_sha256 is None or self.pair_token_count is None
        ):
            raise ValueError("a completed bundle requires premise and token provenance")
        scoring = (
            self.model_revision,
            self.logits,
            self.predicted_label,
            self.evidence_margin,
            self.polarity_margin,
        )
        if has_error:
            if any(value is not None for value in scoring):
                raise ValueError("failed results cannot contain inference outputs")
            return
        if any(value is None for value in scoring):
            raise ValueError("successful results require complete inference outputs")
        if self.attempt_count != 1 or self.bundle_digest is None:
            raise ValueError("successful results require one durably started attempt")
        assert self.logits is not None
        assert self.evidence_margin is not None
        assert self.polarity_margin is not None
        if self.model_revision != DEBERTA_REVISION:
            raise ValueError("successful result model revision does not match")
        if self.predicted_label is not self.logits.predicted_label:
            raise ValueError("predicted label does not match logits")
        if not math.isclose(self.evidence_margin, self.logits.evidence_margin):
            raise ValueError("evidence margin does not match logits")
        if not math.isclose(self.polarity_margin, self.logits.polarity_margin):
            raise ValueError("polarity margin does not match logits")

    def to_json(self) -> str:
        return _canonical_json(asdict(self))


type ScientificInferenceEvent = ScientificInferenceAttemptStarted | ScientificInferenceResult


@dataclass(slots=True)
class ScientificInferenceJournalState:
    starts: dict[str, ScientificInferenceAttemptStarted]
    results: dict[str, ScientificInferenceResult]

    @property
    def completed(self) -> set[str]:
        return set(self.results)

    @property
    def outcome_unknown(self) -> set[str]:
        return set(self.starts).difference(self.results)


class ScientificInferenceJournal:
    def __init__(
        self,
        path: Path,
        run_id: str,
        state: ScientificInferenceJournalState,
        event_observer: Callable[[ScientificInferenceEvent], None] | None,
    ) -> None:
        self.path = path
        self.run_id = run_id
        self.state = state
        self._event_observer = event_observer

    @classmethod
    def open(
        cls,
        path: Path,
        run_id: str,
        *,
        event_observer: Callable[[ScientificInferenceEvent], None] | None = None,
    ) -> ScientificInferenceJournal:
        _validate_safe_name("run_id", run_id)
        journal = cls(path, run_id, ScientificInferenceJournalState({}, {}), event_observer)
        if not path.exists():
            return journal
        lines = path.read_text(encoding="utf-8").splitlines()
        if any(not line.strip() for line in lines):
            raise ValueError("scientific inference journal must not contain blank rows")
        for line_number, line in enumerate(lines, start=1):
            try:
                event = _parse_event(line)
                journal._validate_transition(event)
                journal._commit_transition(event)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"scientific inference journal row {line_number} is invalid: {error}"
                ) from error
        return journal

    def append(self, event: ScientificInferenceEvent) -> None:
        self._validate_transition(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as output:
            output.write(event.to_json() + "\n")
            output.flush()
            os.fsync(output.fileno())
        self._commit_transition(event)
        if self._event_observer is not None:
            self._event_observer(event)

    def _validate_transition(self, event: ScientificInferenceEvent) -> None:
        if event.run_id != self.run_id:
            raise ValueError("event belongs to a foreign run")
        candidate_id = event.candidate_id
        if candidate_id in self.state.results:
            raise ValueError("invalid event transition after terminal result")
        prior_start = self.state.starts.get(candidate_id)
        if isinstance(event, ScientificInferenceAttemptStarted):
            if prior_start is not None:
                raise ValueError("invalid duplicate attempt-start transition")
            return
        if prior_start is None:
            if event.attempt_id is not None:
                raise ValueError("invalid terminal transition without attempt-start")
            return
        if event.attempt_id != prior_start.attempt_id:
            raise ValueError("terminal attempt identifier does not match attempt-start")
        if event.bundle_digest != prior_start.bundle_digest:
            raise ValueError("terminal bundle digest does not match attempt-start")
        if event.request_digest != prior_start.request_digest:
            raise ValueError("terminal request digest does not match attempt-start")

    def _commit_transition(self, event: ScientificInferenceEvent) -> None:
        if isinstance(event, ScientificInferenceAttemptStarted):
            self.state.starts[event.candidate_id] = event
        else:
            self.state.results[event.candidate_id] = event


@dataclass(frozen=True, slots=True)
class ScientificInferenceExecutionSummary:
    expected_candidates: int
    preexisting_terminal: int
    scored_candidates: int
    failed_candidates: int
    outcome_unknown: int
    complete: bool


@dataclass(frozen=True, slots=True)
class _PlannedCandidate:
    case: GenerationEvaluationCase
    candidate: RetrievalCandidate
    candidate_id: str
    baseline_rank: int | None


class ScientificInferenceEvaluator:
    def __init__(
        self,
        assembler: EvidenceBundleAssembler,
        client: ScientificInferenceClient,
        *,
        now: Callable[[], str] | None = None,
        timer: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._assembler = assembler
        self._client = client
        self._now = now or _utc_now
        self._timer = timer

    def evaluate_candidate(
        self,
        plan: _PlannedCandidate,
        journal: ScientificInferenceJournal,
    ) -> None:
        case = plan.case
        document = plan.candidate.document
        common = self._common_result_values(plan, journal.run_id)
        colbert_score: float | None = None
        try:
            colbert_score = _colbert_content_score(plan.candidate)
            bundle = self._assembler.assemble(case.claim, document)
        except Exception as error:  # noqa: BLE001 - each pool candidate needs a terminal row
            journal.append(
                ScientificInferenceResult(
                    **common,
                    bundle_digest=None,
                    attempt_id=None,
                    request_digest=None,
                    premise_sha256=None,
                    colbert_score=colbert_score,
                    admitted=(),
                    rejected=(),
                    pair_token_count=None,
                    model_revision=None,
                    logits=None,
                    predicted_label=None,
                    evidence_margin=None,
                    polarity_margin=None,
                    evidence_coverage=_evidence_coverage(case, document.doc_id, ()),
                    latency_ms=None,
                    attempt_count=0,
                    error_stage=(
                        "assembly" if isinstance(error, EvidenceAssemblyError) else "candidate"
                    ),
                    error_code=(
                        error.code
                        if isinstance(error, EvidenceAssemblyError)
                        else type(error).__name__
                    ),
                    error_message=_sanitized_error(error),
                    completed_at=self._now(),
                )
            )
            return

        digest = bundle_identity(bundle)
        request_intent = {
            "schema_version": "scientific-inference-request/v1",
            "premise": bundle.premise,
            "hypothesis": case.claim,
            "expected_pair_tokens": bundle.pair_token_count,
        }
        attempt_id = request_identity(plan.candidate_id, digest, request_intent)
        request = InferenceRequest(
            attempt_id,
            bundle.premise,
            case.claim,
            bundle.pair_token_count,
        )
        request_digest = canonical_payload_digest(inference_request_payload(request))
        started = ScientificInferenceAttemptStarted(
            schema_version=_STARTED_SCHEMA,
            run_id=journal.run_id,
            candidate_id=plan.candidate_id,
            bundle_digest=digest,
            attempt_id=attempt_id,
            request_digest=request_digest,
            started_at=self._now(),
        )
        journal.append(started)
        started_timer = self._timer()
        try:
            response = self._client.classify(request)
            latency_ms = max(0.0, (self._timer() - started_timer) * 1000.0)
            if (
                response.attempt_id != attempt_id
                or response.model_revision != DEBERTA_REVISION
                or response.pair_token_count != bundle.pair_token_count
            ):
                raise ValueError("inference response provenance does not match the request")
        except Exception as error:  # noqa: BLE001 - request failures are terminal evidence
            latency_ms = max(0.0, (self._timer() - started_timer) * 1000.0)
            journal.append(
                ScientificInferenceResult(
                    **common,
                    bundle_digest=digest,
                    attempt_id=attempt_id,
                    request_digest=request_digest,
                    premise_sha256=_text_digest(bundle.premise),
                    colbert_score=colbert_score,
                    admitted=bundle.admitted,
                    rejected=bundle.rejected,
                    pair_token_count=bundle.pair_token_count,
                    model_revision=None,
                    logits=None,
                    predicted_label=None,
                    evidence_margin=None,
                    polarity_margin=None,
                    evidence_coverage=_evidence_coverage(case, document.doc_id, bundle.admitted),
                    latency_ms=latency_ms,
                    attempt_count=1,
                    error_stage="request",
                    error_code=type(error).__name__,
                    error_message=_sanitized_error(error, include_message=False),
                    completed_at=self._now(),
                )
            )
            return
        journal.append(
            ScientificInferenceResult(
                **common,
                bundle_digest=digest,
                attempt_id=attempt_id,
                request_digest=request_digest,
                premise_sha256=_text_digest(bundle.premise),
                colbert_score=colbert_score,
                admitted=bundle.admitted,
                rejected=bundle.rejected,
                pair_token_count=bundle.pair_token_count,
                model_revision=response.model_revision,
                logits=response.logits,
                predicted_label=response.logits.predicted_label,
                evidence_margin=response.logits.evidence_margin,
                polarity_margin=response.logits.polarity_margin,
                evidence_coverage=_evidence_coverage(case, document.doc_id, bundle.admitted),
                latency_ms=latency_ms,
                attempt_count=1,
                error_stage=None,
                error_code=None,
                error_message=None,
                completed_at=self._now(),
            )
        )

    def _common_result_values(self, plan: _PlannedCandidate, run_id: str) -> dict[str, Any]:
        case = plan.case
        document = plan.candidate.document
        return {
            "schema_version": _RESULT_SCHEMA,
            "run_id": run_id,
            "candidate_id": plan.candidate_id,
            "query_id": case.query_id,
            "document_id": document.doc_id,
            "claim": case.claim,
            "claim_sha256": _text_digest(case.claim),
            "document_title": document.title,
            "document_sha256": canonical_payload_digest(
                {"text": document.text, "title": document.title}
            ),
            "baseline_rank": plan.baseline_rank,
            "gold_label": _gold_label(case, document.doc_id),
        }


class ScientificInferenceEvaluationExecutor:
    def __init__(
        self,
        pool_source: CandidatePoolSource,
        evaluator: ScientificInferenceEvaluator,
        *,
        event_observer: Callable[[ScientificInferenceEvent], None] | None = None,
    ) -> None:
        self._pool_source = pool_source
        self._evaluator = evaluator
        self._event_observer = event_observer

    def run(
        self,
        *,
        run_id: str,
        evaluation_set: GenerationEvaluationSet,
        retrieval_limit: int,
        output: Path,
    ) -> ScientificInferenceExecutionSummary:
        if retrieval_limit != 10:
            raise ValueError("scientific inference retrieval_limit must be 10")
        if any(case.source_split != "train-validation" for case in evaluation_set.cases):
            raise ValueError("scientific inference requires the train-validation split")
        journal = ScientificInferenceJournal.open(
            output,
            run_id,
            event_observer=self._event_observer,
        )
        preexisting_terminal = len(journal.state.results)
        planned = self._planned_candidates(run_id, evaluation_set, retrieval_limit)
        planned_ids = {item.candidate_id for item in planned}
        journal_ids = set(journal.state.starts).union(journal.state.results)
        foreign = journal_ids.difference(planned_ids)
        if foreign:
            raise ValueError("journal contains candidates outside the regenerated pool")
        for plan in planned:
            if plan.candidate_id in journal.state.completed:
                continue
            if plan.candidate_id in journal.state.outcome_unknown:
                continue
            self._evaluator.evaluate_candidate(plan, journal)
        results = [
            result
            for candidate_id, result in journal.state.results.items()
            if candidate_id in planned_ids
        ]
        outcome_unknown = len(journal.state.outcome_unknown.intersection(planned_ids))
        failed = sum(result.error_stage is not None for result in results)
        scored = len(results) - failed
        return ScientificInferenceExecutionSummary(
            expected_candidates=len(planned),
            preexisting_terminal=preexisting_terminal,
            scored_candidates=scored,
            failed_candidates=failed,
            outcome_unknown=outcome_unknown,
            complete=len(results) == len(planned) and failed == 0 and outcome_unknown == 0,
        )

    def _planned_candidates(
        self,
        run_id: str,
        evaluation_set: GenerationEvaluationSet,
        retrieval_limit: int,
    ) -> list[_PlannedCandidate]:
        planned: list[_PlannedCandidate] = []
        for case in evaluation_set.cases:
            ranked, candidates = self._pool_source.retrieve_pool(
                case.claim,
                limit=retrieval_limit,
            )
            baseline_ranks = {hit.doc_id: rank for rank, hit in enumerate(ranked, start=1)}
            document_ids = [candidate.document.doc_id for candidate in candidates]
            if len(document_ids) != len(set(document_ids)):
                raise ValueError("candidate pool contains duplicate documents")
            for candidate in sorted(candidates, key=lambda item: int(item.document.doc_id)):
                planned.append(
                    _PlannedCandidate(
                        case=case,
                        candidate=candidate,
                        candidate_id=candidate_identity(
                            run_id,
                            case.query_id,
                            case.claim,
                            candidate.document,
                        ),
                        baseline_rank=baseline_ranks.get(candidate.document.doc_id),
                    )
                )
        return planned


def _colbert_content_score(candidate: RetrievalCandidate) -> float:
    scores = [signal.score for signal in candidate.signals if signal.channel == "colbert-content"]
    if len(scores) != 1 or not math.isfinite(scores[0]):
        raise ValueError("candidate must contain exactly one finite colbert-content score")
    return scores[0]


def _gold_label(
    case: GenerationEvaluationCase,
    document_id: str,
) -> ScientificInferenceLabel:
    if document_id not in case.cited_document_ids:
        return ScientificInferenceLabel.NEUTRAL
    if case.expected_stance is ScientificStance.SUPPORT:
        return ScientificInferenceLabel.ENTAILMENT
    if case.expected_stance is ScientificStance.CONTRADICT:
        return ScientificInferenceLabel.CONTRADICTION
    return ScientificInferenceLabel.NEUTRAL


def _evidence_coverage(
    case: GenerationEvaluationCase,
    document_id: str,
    admitted: tuple[EvidenceChunkSelection, ...],
) -> str:
    rationales = [rationale for rationale in case.rationales if rationale.doc_id == document_id]
    if not rationales:
        return "not-annotated"
    evidence = [_normalize_text(chunk.text) for chunk in admitted]
    if any(
        _normalize_text(sentence) in chunk
        for rationale in rationales
        for sentence in rationale.sentences
        for chunk in evidence
    ):
        return "annotated-evidence-present"
    return "annotated-evidence-absent"


def _normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sanitized_error(error: Exception, *, include_message: bool = True) -> str:
    name = type(error).__name__
    if not include_message:
        return f"{name}: request failed"
    message = " ".join(str(error).split())
    message = re.sub(r"https?://\S+", "<redacted-url>", message)
    return f"{name}: {message[:240]}"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_event(serialized: str) -> ScientificInferenceEvent:
    raw = _json_object(serialized, "journal event")
    schema_version = raw.get("schema_version")
    if schema_version == _STARTED_SCHEMA:
        if set(raw) != {field.name for field in fields(ScientificInferenceAttemptStarted)}:
            raise ValueError("attempt-started fields do not match the schema")
        return ScientificInferenceAttemptStarted(**raw)
    if schema_version == _RESULT_SCHEMA:
        return _parse_result(raw)
    raise ValueError("journal event schema version is unsupported")


def _parse_result(raw: dict[str, Any]) -> ScientificInferenceResult:
    if set(raw) != {field.name for field in fields(ScientificInferenceResult)}:
        raise ValueError("result fields do not match the schema")
    values = dict(raw)
    values["gold_label"] = ScientificInferenceLabel(values["gold_label"])
    predicted = values["predicted_label"]
    values["predicted_label"] = (
        ScientificInferenceLabel(predicted) if predicted is not None else None
    )
    logits = values["logits"]
    if logits is not None:
        values["logits"] = _parse_nested(logits, InferenceLogits, "logits")
    admitted = values["admitted"]
    rejected = values["rejected"]
    if not isinstance(admitted, list) or not isinstance(rejected, list):
        raise TypeError("admitted and rejected provenance must be arrays")
    values["admitted"] = tuple(
        _parse_nested(item, EvidenceChunkSelection, "admitted chunk") for item in admitted
    )
    values["rejected"] = tuple(
        _parse_nested(item, EvidenceChunkRejection, "rejected chunk") for item in rejected
    )
    return ScientificInferenceResult(**values)


def _parse_nested(value: object, kind: type[Any], name: str) -> Any:
    if not isinstance(value, dict) or set(value) != {field.name for field in fields(kind)}:
        raise ValueError(f"{name} fields do not match the schema")
    return kind(**value)


def _json_object(serialized: str, name: str) -> dict[str, Any]:
    try:
        raw = json.loads(serialized)
    except json.JSONDecodeError as error:
        raise ValueError(f"{name} must be valid JSON") from error
    if not isinstance(raw, dict):
        raise TypeError(f"{name} must be a JSON object")
    return raw


def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )


def _validate_safe_name(name: str, value: str) -> None:
    if not isinstance(value, str) or _SAFE_NAME.fullmatch(value) is None:
        raise ValueError(f"{name} must be a safe non-empty name")


def _validate_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _validate_digest(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _validate_optional_positive(name: str, value: int | None) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
        raise ValueError(f"{name} must be a positive integer or null")


def _validate_optional_finite(name: str, value: float | None) -> None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
    ):
        raise ValueError(f"{name} must be finite or null")


def _validate_optional_nonnegative(name: str, value: float | None) -> None:
    _validate_optional_finite(name, value)
    if value is not None and value < 0:
        raise ValueError(f"{name} must be non-negative or null")


def _parse_utc(name: str, value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{name} must be an ISO-8601 UTC timestamp ending in Z")
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise ValueError(f"{name} must be a valid ISO-8601 UTC timestamp") from error


def _validate_results_path(value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError("results_path must be a safe repository-relative JSONL path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.suffix != ".jsonl"
        or "\\" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("results_path must be a safe repository-relative JSONL path")
