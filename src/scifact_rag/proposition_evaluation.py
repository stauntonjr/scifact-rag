from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from .domain import EvidenceDocument
from .proposition import (
    GroundedProposition,
    GroundedSpan,
    PropositionPolarity,
    PropositionQualifier,
    QualifierRole,
    SourceKind,
    proposition_identity,
    source_digest,
    validate_propositions,
)
from .scientific_inference import canonical_payload_digest

_SOURCE_MANIFEST_SCHEMA = "proposition-source-manifest/v1"
_AUDIT_SCHEMA = "proposition-error-audit/v1"
_EXTRACTION_SCHEMA = "proposition-extraction-result/v1"
_LABELS = {"entailment", "contradiction", "neutral"}


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
    sources: tuple[PropositionSource, ...]

    def __post_init__(self) -> None:
        if self.schema_version != _SOURCE_MANIFEST_SCHEMA:
            raise ValueError(f"schema_version must be {_SOURCE_MANIFEST_SCHEMA}")
        _validate_text("run_id", self.run_id)
        _validate_digest("evaluation_sha256", self.evaluation_sha256)
        _validate_digest("phase3_sha256", self.phase3_sha256)
        _validate_digest("source_set_sha256", self.source_set_sha256)
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
        qualifiers=tuple(
            PropositionQualifier(QualifierRole(value["role"]), _parse_span(value["span"]))
            for value in raw["qualifiers"]
        ),
    )
    proposition_identity(proposition)
    return proposition


def _parse_span(raw: object) -> GroundedSpan:
    if not isinstance(raw, dict) or set(raw) != {"start", "end", "text"}:
        raise ValueError("span fields do not match schema")
    return GroundedSpan(raw["start"], raw["end"], raw["text"])


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
