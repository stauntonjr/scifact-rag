from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from enum import StrEnum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .domain import EvidenceDocument
from .ports import Embedder, PropositionExtractor
from .proposition import (
    ExtractionCoverage,
    ExtractionCoverageGate,
    GroundedProposition,
    GroundedSpan,
    PropositionPairFeatures,
    PropositionPolarity,
    PropositionQualifier,
    QualifierRole,
    SourceKind,
    evaluate_extraction_coverage,
    proposition_identity,
    score_proposition_pairs,
    source_digest,
    validate_propositions,
)
from .scientific_inference import canonical_payload_digest
from .scientific_inference_evaluation import ScientificInferenceResult

_SOURCE_MANIFEST_SCHEMA = "proposition-source-manifest/v1"
_AUDIT_SCHEMA = "proposition-error-audit/v1"
_EXTRACTION_SCHEMA = "proposition-extraction-result/v1"
_LABELS = {"entailment", "contradiction", "neutral"}
_REVIEW_SCHEMA = "proposition-audit-review/v1"
_DISPOSITIONS = {
    "likely_annotation_gap",
    "related_insufficient",
    "model_reasoning_error",
    "evidence_selection_error",
    "indeterminate",
}
_PHENOMENA = {
    "synonymy",
    "argument-direction",
    "polarity",
    "negation",
    "population-qualifier",
    "intervention-qualifier",
    "comparator-qualifier",
    "outcome-qualifier",
    "association-versus-causation",
    "species-evidence-boundary",
    "cross-sentence-reasoning",
}
_QUALIFICATION_PROBES = (
    ("positive-relation", "Aspirin reduces fever.", "positive"),
    ("explicit-negation", "Aspirin does not reduce fever.", "negative"),
    ("scientific-qualifier", "In adults, aspirin reduces fever.", "qualifier"),
    ("no-relation", "Aspirin. Fever.", "empty"),
)


@dataclass(frozen=True, slots=True)
class Phase3CandidateRecord:
    candidate_id: str
    query_id: str
    document_id: str
    claim: str
    document_sha256: str
    gold_label: str
    predicted_label: str
    evidence_margin: float
    polarity_margin: float
    colbert_score: float
    evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("candidate_id", "document_sha256"):
            _validate_digest(name, getattr(self, name))
        for name in ("query_id", "document_id", "claim"):
            _validate_text(name, getattr(self, name))
        if self.gold_label not in _LABELS or self.predicted_label not in _LABELS:
            raise ValueError("candidate labels must be entailment, contradiction, or neutral")
        for name in ("evidence_margin", "polarity_margin", "colbert_score"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(value)
            ):
                raise ValueError(f"{name} must be finite")
        if not isinstance(self.evidence, tuple) or any(
            not isinstance(value, str) or not value.strip() for value in self.evidence
        ):
            raise ValueError("candidate evidence must be a tuple of non-empty text")


@dataclass(frozen=True, slots=True)
class PropositionSource:
    kind: SourceKind
    source_id: str
    text: str
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SourceKind):
            raise TypeError("source kind must be SourceKind")
        _validate_text("source_id", self.source_id)
        if self.sha256 != source_digest(self.text):
            raise ValueError("source SHA-256 does not match source text")


@dataclass(frozen=True, slots=True)
class PropositionSourceManifest:
    schema_version: str
    run_id: str
    evaluation_sha256: str
    phase3_sha256: str
    source_set_sha256: str
    extractor_model: str
    prompt_id: str
    prompt_sha256: str
    schema_sha256: str
    seed: int
    embedding_model: str
    sources: tuple[PropositionSource, ...]

    def __post_init__(self) -> None:
        if self.schema_version != _SOURCE_MANIFEST_SCHEMA:
            raise ValueError(f"schema_version must be {_SOURCE_MANIFEST_SCHEMA}")
        _validate_text("run_id", self.run_id)
        _validate_digest("evaluation_sha256", self.evaluation_sha256)
        _validate_digest("phase3_sha256", self.phase3_sha256)
        _validate_digest("source_set_sha256", self.source_set_sha256)
        for name in ("extractor_model", "prompt_id", "embedding_model"):
            _validate_text(name, getattr(self, name))
        _validate_digest("prompt_sha256", self.prompt_sha256)
        _validate_digest("schema_sha256", self.schema_sha256)
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer")
        expected = tuple(sorted(self.sources, key=lambda item: (item.kind.value, item.source_id)))
        if not self.sources or self.sources != expected:
            raise ValueError("manifest sources must be non-empty and sorted")
        identities = [(source.kind, source.source_id) for source in self.sources]
        if len(identities) != len(set(identities)):
            raise ValueError("manifest sources must have unique identities")
        if self.source_set_sha256 != _source_set_digest(self.sources):
            raise ValueError("source_set_sha256 does not match sources")

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    @classmethod
    def from_json(cls, serialized: str) -> PropositionSourceManifest:
        raw = _json_object(serialized, "source manifest")
        _require_fields(raw, cls, "source manifest")
        if not isinstance(raw["sources"], list):
            raise TypeError("source manifest sources must be an array")
        sources = tuple(_parse_source(item) for item in raw["sources"])
        return cls(**{**raw, "sources": sources})


@dataclass(frozen=True, slots=True)
class PropositionAuditRow:
    schema_version: str
    candidate_id: str
    query_id: str
    document_id: str
    claim: str
    gold_label: str
    predicted_label: str
    evidence_margin: float
    polarity_margin: float
    colbert_score: float
    evidence: tuple[str, ...]
    stratum: str
    margin_band: int

    def __post_init__(self) -> None:
        if self.schema_version != _AUDIT_SCHEMA:
            raise ValueError(f"schema_version must be {_AUDIT_SCHEMA}")
        _validate_digest("candidate_id", self.candidate_id)
        for name in ("query_id", "document_id", "claim", "stratum"):
            _validate_text(name, getattr(self, name))
        if self.gold_label not in _LABELS or self.predicted_label not in _LABELS:
            raise ValueError("audit labels are unsupported")
        for name in ("evidence_margin", "polarity_margin", "colbert_score"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(value)
            ):
                raise ValueError(f"{name} must be finite")
        if not isinstance(self.evidence, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.evidence
        ):
            raise ValueError("audit evidence must be a tuple of non-empty text")
        if self.margin_band not in range(6):
            raise ValueError("audit margin band must be between zero and five")

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class PropositionAuditReview:
    schema_version: str
    candidate_id: str
    reviewer: str
    disposition: str
    phenomena: tuple[str, ...]
    rationale: str

    def __post_init__(self) -> None:
        if self.schema_version != _REVIEW_SCHEMA:
            raise ValueError(f"schema_version must be {_REVIEW_SCHEMA}")
        _validate_digest("candidate_id", self.candidate_id)
        _validate_text("reviewer", self.reviewer)
        _validate_text("rationale", self.rationale)
        if self.disposition not in _DISPOSITIONS:
            raise ValueError("audit disposition is unsupported")
        if len(self.phenomena) != len(set(self.phenomena)) or any(
            item not in _PHENOMENA for item in self.phenomena
        ):
            raise ValueError("audit phenomena are invalid")


class ExtractionStatus(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class PropositionExtractionResult:
    schema_version: str
    run_id: str
    source_kind: SourceKind
    source_id: str
    source_text: str
    source_sha256: str
    status: ExtractionStatus
    propositions: tuple[GroundedProposition, ...]
    error_code: str | None
    error_message: str | None
    latency_ms: float

    def __post_init__(self) -> None:
        if self.schema_version != _EXTRACTION_SCHEMA:
            raise ValueError(f"schema_version must be {_EXTRACTION_SCHEMA}")
        _validate_text("run_id", self.run_id)
        if not isinstance(self.source_kind, SourceKind):
            raise TypeError("source_kind must be SourceKind")
        _validate_text("source_id", self.source_id)
        if self.source_sha256 != source_digest(self.source_text):
            raise ValueError("extraction source digest does not match text")
        if not isinstance(self.status, ExtractionStatus):
            raise TypeError("status must be ExtractionStatus")
        if (
            isinstance(self.latency_ms, bool)
            or not isinstance(self.latency_ms, int | float)
            or not math.isfinite(self.latency_ms)
            or self.latency_ms < 0
        ):
            raise ValueError("latency_ms must be finite and non-negative")
        validate_propositions(self.source_text, self.propositions)
        if any(
            proposition.source_kind is not self.source_kind
            or proposition.source_id != self.source_id
            for proposition in self.propositions
        ):
            raise ValueError("proposition belongs to a foreign source")
        if self.status is ExtractionStatus.SUCCESS:
            if (
                not self.propositions
                or self.error_code is not None
                or self.error_message is not None
            ):
                raise ValueError("successful extraction requires propositions and no error")
        elif self.status is ExtractionStatus.EMPTY:
            if self.propositions or self.error_code is not None or self.error_message is not None:
                raise ValueError("empty extraction requires no propositions or error")
        elif self.propositions or not self.error_code or not self.error_message:
            raise ValueError("failed extraction requires an error and no propositions")

    @classmethod
    def create(
        cls,
        run_id: str,
        source_kind: SourceKind,
        source_id: str,
        source_text: str,
        propositions: Sequence[GroundedProposition],
        latency_ms: float,
        *,
        error: tuple[str, str] | None = None,
    ) -> PropositionExtractionResult:
        values = tuple(propositions)
        status = (
            ExtractionStatus.FAILURE
            if error is not None
            else ExtractionStatus.SUCCESS
            if values
            else ExtractionStatus.EMPTY
        )
        return cls(
            _EXTRACTION_SCHEMA,
            run_id,
            source_kind,
            source_id,
            source_text,
            source_digest(source_text),
            status,
            values,
            error[0] if error else None,
            error[1] if error else None,
            latency_ms,
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class BinarySeparationMetrics:
    roc_auc: float
    average_precision: float
    prevalence: float


@dataclass(frozen=True, slots=True)
class PropositionExtractionSummary:
    total_sources: int
    preexisting_sources: int
    extracted_sources: int
    successful_sources: int
    empty_sources: int
    failed_sources: int


@dataclass(frozen=True, slots=True)
class PropositionQualificationProbe:
    name: str
    source_sha256: str
    passed: bool
    proposition_count: int
    latency_ms: float
    error_code: str | None
    error_message: str | None

    def __post_init__(self) -> None:
        _validate_text("probe name", self.name)
        _validate_digest("probe source_sha256", self.source_sha256)
        if not isinstance(self.passed, bool):
            raise TypeError("probe passed must be boolean")
        if self.proposition_count < 0 or self.latency_ms < 0 or not math.isfinite(self.latency_ms):
            raise ValueError("probe counts and latency must be non-negative")
        errors = (self.error_code, self.error_message)
        if self.passed != all(value is None for value in errors):
            raise ValueError("probe pass state does not match error fields")
        if not self.passed and not all(
            isinstance(value, str) and value.strip() for value in errors
        ):
            raise ValueError("failed probe requires code and message")


@dataclass(frozen=True, slots=True)
class PropositionQualificationReport:
    schema_version: str
    run_id: str
    extractor_model: str
    prompt_id: str
    prompt_sha256: str
    schema_sha256: str
    seed: int
    probes: tuple[PropositionQualificationProbe, ...]
    passed: bool

    def __post_init__(self) -> None:
        if self.schema_version != "proposition-qualification-report/v1":
            raise ValueError("qualification report schema is unsupported")
        for name in ("run_id", "extractor_model", "prompt_id"):
            _validate_text(name, getattr(self, name))
        for name in ("prompt_sha256", "schema_sha256"):
            _validate_digest(name, getattr(self, name))
        if len(self.probes) != 4 or self.passed != all(probe.passed for probe in self.probes):
            raise ValueError("qualification pass state must summarize four probes")

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, serialized: str) -> PropositionQualificationReport:
        raw = _json_object(serialized, "qualification report")
        _require_fields(raw, cls, "qualification report")
        if not isinstance(raw["probes"], list):
            raise TypeError("qualification probes must be an array")
        probes = tuple(_parse_qualification_probe(item) for item in raw["probes"])
        return cls(**{**raw, "probes": probes})


@dataclass(frozen=True, slots=True)
class PropositionPairRecord:
    candidate_id: str
    query_id: str
    document_id: str
    gold_label: str
    predicted_label: str
    evidence_margin: float
    polarity_margin: float
    colbert_score: float
    features: PropositionPairFeatures

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class NumericDistribution:
    count: int
    minimum: float
    median: float
    mean: float
    maximum: float


@dataclass(frozen=True, slots=True)
class PropositionExtractionDiagnostics:
    total_sources: int
    successful_sources: int
    empty_sources: int
    failed_sources: int
    span_validated_propositions: int
    failures_by_code: Mapping[str, int]
    latency_ms: NumericDistribution


@dataclass(frozen=True, slots=True)
class PropositionEvaluationReport:
    schema_version: str
    run_id: str
    decisive_candidates: int
    false_positive_candidates: int
    extraction_coverage: ExtractionCoverageGate
    metrics: Mapping[str, BinarySeparationMetrics]
    correlations: Mapping[str, float | None]
    distributions: Mapping[str, Mapping[str, Mapping[str, NumericDistribution]]]
    extraction: PropositionExtractionDiagnostics
    artifact_sha256: Mapping[str, str]
    decision: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


class PropositionEvaluationExecutor:
    def __init__(
        self,
        extractor: PropositionExtractor,
        *,
        timer: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._extractor = extractor
        self._timer = timer

    def extract(
        self,
        manifest: PropositionSourceManifest,
        output: Path,
    ) -> PropositionExtractionSummary:
        journal = PropositionExtractionJournal.open(output, manifest.run_id)
        sources = {(source.kind, source.source_id): source for source in manifest.sources}
        foreign = set(journal.results).difference(sources)
        if foreign:
            raise ValueError("extraction journal contains sources outside the manifest")
        for identity, result in journal.results.items():
            source = sources[identity]
            if result.source_sha256 != source.sha256 or result.source_text != source.text:
                raise ValueError("retained extraction does not match the source manifest")
        preexisting = len(journal.completed)
        for source in manifest.sources:
            if (source.kind, source.source_id) in journal.completed:
                continue
            started = self._timer()
            try:
                propositions = self._extractor.extract(source)
                result = PropositionExtractionResult.create(
                    manifest.run_id,
                    source.kind,
                    source.source_id,
                    source.text,
                    propositions,
                    max(0.0, (self._timer() - started) * 1000.0),
                )
            except Exception as error:  # noqa: BLE001 - every source needs a terminal row
                code = getattr(error, "code", type(error).__name__)
                result = PropositionExtractionResult.create(
                    manifest.run_id,
                    source.kind,
                    source.source_id,
                    source.text,
                    (),
                    max(0.0, (self._timer() - started) * 1000.0),
                    error=(str(code), _sanitized_error(error)),
                )
            journal.append(result)
        values = tuple(journal.results.values())
        return PropositionExtractionSummary(
            total_sources=len(manifest.sources),
            preexisting_sources=preexisting,
            extracted_sources=len(values) - preexisting,
            successful_sources=sum(item.status is ExtractionStatus.SUCCESS for item in values),
            empty_sources=sum(item.status is ExtractionStatus.EMPTY for item in values),
            failed_sources=sum(item.status is ExtractionStatus.FAILURE for item in values),
        )


def qualify_proposition_extractor(
    extractor: PropositionExtractor,
    manifest: PropositionSourceManifest,
    *,
    timer: Callable[[], float] = time.perf_counter,
) -> PropositionQualificationReport:
    results: list[PropositionQualificationProbe] = []
    for name, text, expectation in _QUALIFICATION_PROBES:
        source = PropositionSource(
            SourceKind.DOCUMENT,
            f"qualification-{name}",
            text,
            source_digest(text),
        )
        started = timer()
        error: tuple[str, str] | None = None
        propositions: tuple[GroundedProposition, ...] = ()
        try:
            propositions = extractor.extract(source)
            passed = (
                (
                    expectation == "positive"
                    and any(p.polarity.value == "positive" for p in propositions)
                )
                or (
                    expectation == "negative"
                    and any(p.polarity.value == "negative" for p in propositions)
                )
                or (expectation == "qualifier" and any(p.qualifiers for p in propositions))
                or (expectation == "empty" and not propositions)
            )
            if not passed:
                error = ("expectation", f"{name} did not satisfy {expectation}")
        except Exception as caught:  # noqa: BLE001 - all four probe outcomes are retained
            passed = False
            error = (str(getattr(caught, "code", type(caught).__name__)), _sanitized_error(caught))
        results.append(
            PropositionQualificationProbe(
                name,
                source.sha256,
                passed,
                len(propositions),
                max(0.0, (timer() - started) * 1000.0),
                error[0] if error else None,
                error[1] if error else None,
            )
        )
    probes = tuple(results)
    return PropositionQualificationReport(
        "proposition-qualification-report/v1",
        manifest.run_id,
        manifest.extractor_model,
        manifest.prompt_id,
        manifest.prompt_sha256,
        manifest.schema_sha256,
        manifest.seed,
        probes,
        all(item.passed for item in probes),
    )


def validate_qualification_report(
    report: PropositionQualificationReport,
    manifest: PropositionSourceManifest,
) -> None:
    expected = {
        "run_id": manifest.run_id,
        "extractor_model": manifest.extractor_model,
        "prompt_id": manifest.prompt_id,
        "prompt_sha256": manifest.prompt_sha256,
        "schema_sha256": manifest.schema_sha256,
        "seed": manifest.seed,
    }
    if any(getattr(report, name) != value for name, value in expected.items()):
        raise ValueError("qualification report does not match the source manifest")
    expected_probes = {
        name: source_digest(text) for name, text, _expectation in _QUALIFICATION_PROBES
    }
    observed = {probe.name: probe.source_sha256 for probe in report.probes}
    if observed != expected_probes or len(report.probes) != len(expected_probes):
        raise ValueError("qualification report does not match the four frozen probes")
    if not report.passed or not all(probe.passed for probe in report.probes):
        raise ValueError("proposition extraction qualification did not pass")


def build_pair_records(
    manifest: PropositionSourceManifest,
    records: Sequence[Phase3CandidateRecord],
    journal: PropositionExtractionJournal,
    embedder: Embedder,
    *,
    decisive_document_ids: set[str],
    audit_document_ids: set[str],
) -> tuple[tuple[PropositionPairRecord, ...], ExtractionCoverageGate]:
    if journal.run_id != manifest.run_id:
        raise ValueError("extraction journal belongs to a foreign run")
    identities = {(source.kind, source.source_id): source for source in manifest.sources}
    if set(journal.results) != set(identities):
        raise ValueError("extraction journal is incomplete or contains foreign sources")
    successful = {
        identity: result
        for identity, result in journal.results.items()
        if result.status is ExtractionStatus.SUCCESS
    }
    candidate_document_ids = {record.document_id for record in records}
    claim_ids = {record.query_id for record in records}
    target = tuple(
        sorted(
            (
                record
                for record in records
                if record.gold_label in {"entailment", "contradiction"}
                or (
                    record.gold_label == "neutral"
                    and record.predicted_label in {"entailment", "contradiction"}
                )
            ),
            key=lambda item: item.candidate_id,
        )
    )
    target_document_ids = {record.document_id for record in target}
    coverage = ExtractionCoverage(
        total_sources=len(manifest.sources),
        schema_valid_sources=sum(
            result.status is not ExtractionStatus.FAILURE for result in journal.results.values()
        ),
        total_claims=len(claim_ids),
        usable_claims=sum((SourceKind.CLAIM, value) in successful for value in claim_ids),
        total_candidate_documents=len(candidate_document_ids),
        usable_candidate_documents=sum(
            (SourceKind.DOCUMENT, value) in successful for value in candidate_document_ids
        ),
        decisive_documents=len(decisive_document_ids),
        usable_decisive_documents=sum(
            (SourceKind.DOCUMENT, value) in successful for value in decisive_document_ids
        ),
        audit_documents=len(audit_document_ids),
        usable_audit_documents=sum(
            (SourceKind.DOCUMENT, value) in successful for value in audit_document_ids
        ),
        target_documents=len(target_document_ids),
        usable_target_documents=sum(
            (SourceKind.DOCUMENT, value) in successful for value in target_document_ids
        ),
    )
    gate = evaluate_extraction_coverage(coverage)
    if not gate.passed:
        return (), gate

    scorable = [
        record
        for record in target
        if (SourceKind.CLAIM, record.query_id) in successful
        and (SourceKind.DOCUMENT, record.document_id) in successful
    ]
    surfaces = sorted(
        {
            surface
            for record in scorable
            for result in (
                successful[(SourceKind.CLAIM, record.query_id)],
                successful[(SourceKind.DOCUMENT, record.document_id)],
            )
            for proposition in result.propositions
            for surface in _proposition_surfaces(proposition)
        }
    )
    vectors = embedder.embed(surfaces)
    if len(vectors) != len(surfaces):
        raise ValueError("embedder returned the wrong number of vectors")
    vector_by_surface = dict(zip(surfaces, vectors, strict=True))

    def similarity(left: str, right: str) -> float:
        return _cosine(vector_by_surface[left], vector_by_surface[right])

    pairs = tuple(
        PropositionPairRecord(
            record.candidate_id,
            record.query_id,
            record.document_id,
            record.gold_label,
            record.predicted_label,
            record.evidence_margin,
            record.polarity_margin,
            record.colbert_score,
            score_proposition_pairs(
                successful[(SourceKind.CLAIM, record.query_id)].propositions,
                successful[(SourceKind.DOCUMENT, record.document_id)].propositions,
                similarity,
            ),
        )
        for record in scorable
    )
    return pairs, gate


def build_proposition_report(
    run_id: str,
    pairs: Sequence[PropositionPairRecord],
    coverage: ExtractionCoverageGate,
    *,
    artifact_sha256: Mapping[str, str],
    audit_complete: bool,
    audit: Sequence[PropositionAuditRow] = (),
    reviews: Sequence[PropositionAuditReview] = (),
    extractions: Sequence[PropositionExtractionResult] = (),
    expected_decisive: int = 120,
    expected_false_positives: int = 4316,
) -> PropositionEvaluationReport:
    if not audit_complete:
        raise ValueError("audit review must be complete before report interpretation")
    if not coverage.passed:
        raise ValueError("extraction coverage gate must pass before report derivation")
    required_digests = {"manifest", "audit", "audit_review", "qualification", "extraction", "pairs"}
    if set(artifact_sha256) != required_digests:
        raise ValueError("report requires every frozen artifact digest")
    for name, digest in artifact_sha256.items():
        _validate_digest(name, digest)
    decisive = sum(item.gold_label in {"entailment", "contradiction"} for item in pairs)
    false_positives = sum(
        item.gold_label == "neutral" and item.predicted_label in {"entailment", "contradiction"}
        for item in pairs
    )
    if decisive != expected_decisive or false_positives != expected_false_positives:
        raise ValueError("pair artifact does not match the fixed comparison boundary")
    labels = tuple(item.gold_label in {"entailment", "contradiction"} for item in pairs)
    feature_names = (
        "entity",
        "predicate",
        "argument_direction",
        "polarity",
        "qualifier",
        "proposition_pair_mean",
    )
    metrics = {
        name: score_binary_separation(
            labels,
            tuple(float(getattr(item.features, name)) for item in pairs),
        )
        for name in feature_names
    }
    pair_mean = tuple(item.features.proposition_pair_mean for item in pairs)
    correlations = {
        "colbert": _pearson(pair_mean, tuple(item.colbert_score for item in pairs)),
        "evidence_margin": _pearson(pair_mean, tuple(item.evidence_margin for item in pairs)),
        "polarity_margin": _pearson(pair_mean, tuple(item.polarity_margin for item in pairs)),
    }
    audit_strata = {row.candidate_id: row.stratum for row in audit}
    dispositions = {review.candidate_id: review.disposition for review in reviews}
    distributions = _score_distributions(pairs, audit_strata, dispositions, feature_names)
    extraction_diagnostics = _extraction_diagnostics(extractions)
    control = metrics["proposition_pair_mean"]
    decision = (
        "graph-next"
        if control.roc_auc >= 0.65 and control.average_precision >= 2.0 * control.prevalence
        else "stop"
    )
    return PropositionEvaluationReport(
        "proposition-pair-report/v1",
        run_id,
        decisive,
        false_positives,
        coverage,
        metrics,
        correlations,
        distributions,
        extraction_diagnostics,
        dict(artifact_sha256),
        decision,
    )


class PropositionExtractionJournal:
    def __init__(
        self,
        path: Path,
        run_id: str,
        results: dict[tuple[SourceKind, str], PropositionExtractionResult],
    ) -> None:
        self.path = path
        self.run_id = run_id
        self.results = results

    @property
    def completed(self) -> set[tuple[SourceKind, str]]:
        return set(self.results)

    @classmethod
    def open(cls, path: Path, run_id: str) -> PropositionExtractionJournal:
        results: dict[tuple[SourceKind, str], PropositionExtractionResult] = {}
        journal = cls(path, run_id, results)
        if not path.exists():
            return journal
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                result = _parse_extraction(line)
                journal._validate(result)
                results[(result.source_kind, result.source_id)] = result
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"proposition extraction journal row {line_number} is invalid: {error}"
                ) from error
        return journal

    def append(self, result: PropositionExtractionResult) -> None:
        self._validate(result)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as output:
            output.write(result.to_json() + "\n")
            output.flush()
            os.fsync(output.fileno())
        self.results[(result.source_kind, result.source_id)] = result

    def _validate(self, result: PropositionExtractionResult) -> None:
        if result.run_id != self.run_id:
            raise ValueError("result belongs to a foreign run")
        identity = (result.source_kind, result.source_id)
        if identity in self.results:
            raise ValueError("terminal source already exists")


def document_digest(title: str, text: str) -> str:
    return canonical_payload_digest({"text": text, "title": title})


def build_source_manifest(
    *,
    run_id: str,
    evaluation_sha256: str,
    phase3_sha256: str,
    records: Sequence[Phase3CandidateRecord],
    documents: Mapping[str, EvidenceDocument],
    extractor_model: str,
    prompt_id: str,
    prompt_sha256: str,
    schema_sha256: str,
    seed: int,
    embedding_model: str,
    expected_claims: int = 160,
) -> PropositionSourceManifest:
    _unique_candidates(records)
    claims: dict[str, str] = {}
    document_ids: set[str] = set()
    for record in records:
        existing = claims.setdefault(record.query_id, record.claim)
        if existing != record.claim:
            raise ValueError("conflicting claim text for one query")
        document = documents.get(record.document_id)
        if document is None:
            raise ValueError("candidate document is missing from the corpus")
        if record.document_sha256 != document_digest(document.title, document.text):
            raise ValueError("candidate document digest does not match corpus")
        document_ids.add(record.document_id)
    if len(claims) != expected_claims:
        raise ValueError(f"source manifest requires exactly {expected_claims} claims")
    sources = [
        PropositionSource(SourceKind.CLAIM, query_id, claim, source_digest(claim))
        for query_id, claim in claims.items()
    ]
    for document_id in document_ids:
        document = documents[document_id]
        text = f"{document.title}\n{document.text}" if document.title else document.text
        sources.append(
            PropositionSource(SourceKind.DOCUMENT, document_id, text, source_digest(text))
        )
    ordered = tuple(sorted(sources, key=lambda item: (item.kind.value, item.source_id)))
    return PropositionSourceManifest(
        _SOURCE_MANIFEST_SCHEMA,
        run_id,
        evaluation_sha256,
        phase3_sha256,
        _source_set_digest(ordered),
        extractor_model,
        prompt_id,
        prompt_sha256,
        schema_sha256,
        seed,
        embedding_model,
        ordered,
    )


def build_error_audit(
    records: Sequence[Phase3CandidateRecord],
) -> tuple[PropositionAuditRow, ...]:
    _unique_candidates(records)
    decisive = [
        record
        for record in records
        if record.gold_label in {"entailment", "contradiction"}
        and record.predicted_label != record.gold_label
    ]
    if len(decisive) != 50:
        raise ValueError("audit requires exactly 50 decisive-label errors")
    selected: list[PropositionAuditRow] = [
        _audit_row(
            record,
            f"{record.gold_label}-to-{record.predicted_label}",
            0,
        )
        for record in decisive
    ]
    for prediction in ("entailment", "contradiction"):
        false_positives = sorted(
            (
                record
                for record in records
                if record.gold_label == "neutral" and record.predicted_label == prediction
            ),
            key=lambda item: (item.evidence_margin, item.candidate_id),
        )
        if len(false_positives) < 25:
            raise ValueError(f"audit requires at least 25 neutral-to-{prediction} errors")
        bands: dict[int, list[Phase3CandidateRecord]] = {index: [] for index in range(1, 6)}
        for index, record in enumerate(false_positives):
            band = min(5, index * 5 // len(false_positives) + 1)
            bands[band].append(record)
        for band, candidates in bands.items():
            if len(candidates) < 5:
                raise ValueError("audit margin band contains fewer than five candidates")
            selected.extend(
                _audit_row(record, f"neutral-to-{prediction}", band)
                for record in sorted(candidates, key=lambda item: item.candidate_id)[:5]
            )
    return tuple(sorted(selected, key=lambda row: (row.stratum, row.candidate_id)))


def phase3_candidate_records(
    results: Sequence[ScientificInferenceResult],
) -> tuple[Phase3CandidateRecord, ...]:
    records: list[Phase3CandidateRecord] = []
    for result in results:
        if (
            any(
                value is None
                for value in (
                    result.predicted_label,
                    result.evidence_margin,
                    result.polarity_margin,
                    result.colbert_score,
                )
            )
            or result.error_stage is not None
        ):
            raise ValueError("Phase 3 result is not completely scored")
        assert result.predicted_label is not None
        assert result.evidence_margin is not None
        assert result.polarity_margin is not None
        assert result.colbert_score is not None
        records.append(
            Phase3CandidateRecord(
                result.candidate_id,
                result.query_id,
                result.document_id,
                result.claim,
                result.document_sha256,
                result.gold_label.value,
                result.predicted_label.value,
                result.evidence_margin,
                result.polarity_margin,
                result.colbert_score,
                tuple(item.text for item in result.admitted),
            )
        )
    ordered = tuple(sorted(records, key=lambda item: item.candidate_id))
    _unique_candidates(ordered)
    return ordered


def read_audit(serialized: str) -> tuple[PropositionAuditRow, ...]:
    rows: list[PropositionAuditRow] = []
    for number, line in enumerate(serialized.splitlines(), 1):
        try:
            raw = _json_object(line, "audit row")
            _require_fields(raw, PropositionAuditRow, "audit row")
            raw["evidence"] = tuple(raw["evidence"])
            rows.append(PropositionAuditRow(**raw))
        except (TypeError, ValueError) as error:
            raise ValueError(f"audit row {number} is invalid: {error}") from error
    if len(rows) != 100 or len({row.candidate_id for row in rows}) != 100:
        raise ValueError("audit must contain 100 unique rows")
    return tuple(rows)


def read_audit_reviews(
    serialized: str,
    audit: Sequence[PropositionAuditRow],
) -> tuple[PropositionAuditReview, ...]:
    reviews: list[PropositionAuditReview] = []
    for number, line in enumerate(serialized.splitlines(), 1):
        try:
            raw = _json_object(line, "audit review")
            _require_fields(raw, PropositionAuditReview, "audit review")
            raw["phenomena"] = tuple(raw["phenomena"])
            reviews.append(PropositionAuditReview(**raw))
        except (TypeError, ValueError) as error:
            raise ValueError(f"audit review row {number} is invalid: {error}") from error
    expected = {row.candidate_id for row in audit}
    observed = [review.candidate_id for review in reviews]
    if len(observed) != len(set(observed)) or set(observed) != expected:
        raise ValueError("audit review must contain exactly one row per frozen candidate")
    return tuple(sorted(reviews, key=lambda item: item.candidate_id))


def write_immutable(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") == content:
            return
        raise FileExistsError(f"refusing to replace conflicting artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    staged: Path | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
            staged = Path(output.name)
        os.replace(staged, path)
        staged = None
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def score_binary_separation(
    labels: Sequence[bool],
    scores: Sequence[float],
) -> BinarySeparationMetrics:
    if len(labels) != len(scores) or not labels:
        raise ValueError("binary labels and scores must have equal non-zero length")
    if any(not isinstance(label, bool) for label in labels):
        raise TypeError("binary labels must be booleans")
    if any(
        isinstance(score, bool) or not isinstance(score, int | float) or not math.isfinite(score)
        for score in scores
    ):
        raise ValueError("binary scores must be finite")
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("binary separation requires both classes")
    wins = 0.0
    positive_scores = [score for label, score in zip(labels, scores, strict=True) if label]
    negative_scores = [score for label, score in zip(labels, scores, strict=True) if not label]
    for positive in positive_scores:
        for negative in negative_scores:
            wins += 1.0 if positive > negative else 0.5 if positive == negative else 0.0
    ranked = sorted(
        enumerate(zip(labels, scores, strict=True)), key=lambda item: (-item[1][1], item[0])
    )
    hits = 0
    precision_total = 0.0
    for rank, (_index, (label, _score)) in enumerate(ranked, 1):
        if label:
            hits += 1
            precision_total += hits / rank
    return BinarySeparationMetrics(
        roc_auc=wins / (positives * negatives),
        average_precision=precision_total / positives,
        prevalence=positives / len(labels),
    )


def _audit_row(record: Phase3CandidateRecord, stratum: str, band: int) -> PropositionAuditRow:
    return PropositionAuditRow(
        _AUDIT_SCHEMA,
        record.candidate_id,
        record.query_id,
        record.document_id,
        record.claim,
        record.gold_label,
        record.predicted_label,
        float(record.evidence_margin),
        float(record.polarity_margin),
        float(record.colbert_score),
        record.evidence,
        stratum,
        band,
    )


def _unique_candidates(records: Sequence[Phase3CandidateRecord]) -> None:
    identities = [record.candidate_id for record in records]
    if not records:
        raise ValueError("candidate records must be non-empty")
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate candidate identity")


def _source_set_digest(sources: Sequence[PropositionSource]) -> str:
    payload = [asdict(source) for source in sources]
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _parse_extraction(serialized: str) -> PropositionExtractionResult:
    raw = json.loads(serialized)
    expected = {
        "schema_version",
        "run_id",
        "source_kind",
        "source_id",
        "source_text",
        "source_sha256",
        "status",
        "propositions",
        "error_code",
        "error_message",
        "latency_ms",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError("extraction fields do not match proposition-extraction-result/v1")
    propositions = tuple(_parse_proposition(value) for value in raw["propositions"])
    return PropositionExtractionResult(
        schema_version=raw["schema_version"],
        run_id=raw["run_id"],
        source_kind=SourceKind(raw["source_kind"]),
        source_id=raw["source_id"],
        source_text=raw["source_text"],
        source_sha256=raw["source_sha256"],
        status=ExtractionStatus(raw["status"]),
        propositions=propositions,
        error_code=raw["error_code"],
        error_message=raw["error_message"],
        latency_ms=raw["latency_ms"],
    )


def _parse_proposition(raw: object) -> GroundedProposition:
    if not isinstance(raw, dict):
        raise TypeError("proposition must be an object")
    expected = {
        "source_kind",
        "source_id",
        "source_sha256",
        "sentence",
        "subject",
        "predicate",
        "object",
        "polarity",
        "qualifiers",
    }
    if set(raw) != expected or not isinstance(raw["qualifiers"], list):
        raise ValueError("proposition fields do not match schema")
    proposition = GroundedProposition(
        source_kind=SourceKind(raw["source_kind"]),
        source_id=raw["source_id"],
        source_sha256=raw["source_sha256"],
        sentence=_parse_span(raw["sentence"]),
        subject=_parse_span(raw["subject"]),
        predicate=_parse_span(raw["predicate"]),
        object=_parse_span(raw["object"]),
        polarity=PropositionPolarity(raw["polarity"]),
        qualifiers=tuple(_parse_qualifier(value) for value in raw["qualifiers"]),
    )
    proposition_identity(proposition)
    return proposition


def _parse_span(raw: object) -> GroundedSpan:
    if not isinstance(raw, dict) or set(raw) != {"start", "end", "text"}:
        raise ValueError("span fields do not match schema")
    return GroundedSpan(raw["start"], raw["end"], raw["text"])


def _parse_qualifier(raw: object) -> PropositionQualifier:
    if not isinstance(raw, dict) or set(raw) != {"role", "span"}:
        raise ValueError("qualifier fields do not match schema")
    return PropositionQualifier(QualifierRole(raw["role"]), _parse_span(raw["span"]))


def _validate_digest(name: str, value: object) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256")


def _validate_text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")


def _proposition_surfaces(proposition: GroundedProposition) -> tuple[str, ...]:
    return (
        proposition.subject.text,
        proposition.predicate.text,
        proposition.object.text,
        *(qualifier.span.text for qualifier in proposition.qualifiers),
    )


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or len(left) != len(right):
        raise ValueError("embedding vectors must have the same non-zero dimension")
    if any(
        isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value)
        for value in (*left, *right)
    ):
        raise ValueError("embedding vectors must contain finite numeric values")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise ValueError("embedding vectors must be non-zero")
    return max(
        -1.0,
        min(1.0, sum(a * b for a, b in zip(left, right, strict=True)) / left_norm / right_norm),
    )


def _pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or not left:
        raise ValueError("correlation vectors must have equal non-zero length")
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    centered_left = tuple(value - left_mean for value in left)
    centered_right = tuple(value - right_mean for value in right)
    denominator = math.sqrt(
        sum(value * value for value in centered_left)
        * sum(value * value for value in centered_right)
    )
    if denominator == 0:
        return None
    return sum(a * b for a, b in zip(centered_left, centered_right, strict=True)) / denominator


def _score_distributions(
    pairs: Sequence[PropositionPairRecord],
    audit_strata: Mapping[str, str],
    dispositions: Mapping[str, str],
    feature_names: Sequence[str],
) -> dict[str, dict[str, dict[str, NumericDistribution]]]:
    dimensions = {
        "gold_label": {item.candidate_id: item.gold_label for item in pairs},
        "predicted_label": {item.candidate_id: item.predicted_label for item in pairs},
        "audit_stratum": audit_strata,
        "audit_disposition": dispositions,
    }
    output: dict[str, dict[str, dict[str, NumericDistribution]]] = {}
    for dimension, assignments in dimensions.items():
        groups: dict[str, list[PropositionPairRecord]] = {}
        for pair in pairs:
            group = assignments.get(pair.candidate_id)
            if group is not None:
                groups.setdefault(group, []).append(pair)
        output[dimension] = {
            group: {
                feature: _distribution(
                    tuple(float(getattr(pair.features, feature)) for pair in members)
                )
                for feature in feature_names
            }
            for group, members in sorted(groups.items())
        }
    return output


def _extraction_diagnostics(
    results: Sequence[PropositionExtractionResult],
) -> PropositionExtractionDiagnostics:
    if not results:
        raise ValueError("report requires extraction results")
    failures: dict[str, int] = {}
    for result in results:
        if result.error_code is not None:
            failures[result.error_code] = failures.get(result.error_code, 0) + 1
    return PropositionExtractionDiagnostics(
        total_sources=len(results),
        successful_sources=sum(item.status is ExtractionStatus.SUCCESS for item in results),
        empty_sources=sum(item.status is ExtractionStatus.EMPTY for item in results),
        failed_sources=sum(item.status is ExtractionStatus.FAILURE for item in results),
        span_validated_propositions=sum(len(item.propositions) for item in results),
        failures_by_code=dict(sorted(failures.items())),
        latency_ms=_distribution(tuple(float(item.latency_ms) for item in results)),
    )


def _distribution(values: Sequence[float]) -> NumericDistribution:
    if not values:
        raise ValueError("distribution requires values")
    return NumericDistribution(
        len(values),
        min(values),
        statistics.median(values),
        statistics.fmean(values),
        max(values),
    )


def _sanitized_error(error: Exception) -> str:
    message = " ".join(str(error).split())
    return f"{type(error).__name__}: {message[:240]}"


def _json_object(serialized: str, name: str) -> dict[str, Any]:
    try:
        value = json.loads(serialized)
    except json.JSONDecodeError as error:
        raise ValueError(f"{name} must be valid JSON") from error
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    return value


def _require_fields(value: Mapping[str, object], kind: type[Any], name: str) -> None:
    if set(value) != {field.name for field in fields(kind)}:
        raise ValueError(f"{name} fields do not match the schema")


def _parse_source(value: object) -> PropositionSource:
    if not isinstance(value, dict):
        raise TypeError("source must be an object")
    _require_fields(value, PropositionSource, "source")
    return PropositionSource(
        SourceKind(value["kind"]), value["source_id"], value["text"], value["sha256"]
    )


def _parse_qualification_probe(value: object) -> PropositionQualificationProbe:
    if not isinstance(value, dict):
        raise TypeError("qualification probe must be an object")
    _require_fields(value, PropositionQualificationProbe, "qualification probe")
    return PropositionQualificationProbe(**value)
