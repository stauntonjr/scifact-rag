from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from statistics import fmean


class SourceKind(StrEnum):
    CLAIM = "claim"
    DOCUMENT = "document"


class PropositionPolarity(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class QualifierRole(StrEnum):
    POPULATION = "population"
    SPECIES = "species"
    INTERVENTION = "intervention"
    COMPARATOR = "comparator"
    OUTCOME = "outcome"
    MEASUREMENT = "measurement"
    TIME = "time"
    STUDY_CONTEXT = "study-context"


@dataclass(frozen=True, slots=True)
class GroundedSpan:
    start: int
    end: int
    text: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.start, bool)
            or not isinstance(self.start, int)
            or isinstance(self.end, bool)
            or not isinstance(self.end, int)
        ):
            raise TypeError("span offsets must be integers")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("span offsets must define a non-empty half-open interval")
        if not isinstance(self.text, str) or not self.text:
            raise ValueError("span text must be non-empty")

    @property
    def canonical_key(self) -> str:
        normalized = " ".join(unicodedata.normalize("NFKC", self.text).lower().split())
        return normalized.strip("".join(chr(code) for code in range(128) if _is_punctuation(code)))

    def validate(self, source: str, *, within: GroundedSpan | None = None) -> None:
        if self.end > len(source) or source[self.start : self.end] != self.text:
            raise ValueError("span text does not match the exact source interval")
        if within is not None and (self.start < within.start or self.end > within.end):
            raise ValueError("proposition span is outside its sentence interval")


@dataclass(frozen=True, slots=True)
class PropositionQualifier:
    role: QualifierRole
    span: GroundedSpan


@dataclass(frozen=True, slots=True)
class GroundedProposition:
    source_kind: SourceKind
    source_id: str
    source_sha256: str
    sentence: GroundedSpan
    subject: GroundedSpan
    predicate: GroundedSpan
    object: GroundedSpan
    polarity: PropositionPolarity
    qualifiers: tuple[PropositionQualifier, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.qualifiers, tuple):
            raise TypeError("proposition qualifiers must be a tuple")


@dataclass(frozen=True, slots=True)
class PropositionPairFeatures:
    claim_proposition_id: str
    document_proposition_id: str
    entity: float
    predicate: float
    argument_direction: float
    polarity: float
    qualifier: float
    proposition_pair_mean: float


@dataclass(frozen=True, slots=True)
class ExtractionCoverage:
    total_sources: int
    schema_valid_sources: int
    total_claims: int
    usable_claims: int
    total_candidate_documents: int
    usable_candidate_documents: int
    decisive_documents: int
    usable_decisive_documents: int
    audit_documents: int
    usable_audit_documents: int


@dataclass(frozen=True, slots=True)
class ExtractionCoverageGate:
    passed: bool
    failed_conditions: tuple[str, ...]
    coverage: ExtractionCoverage


def source_digest(source: str) -> str:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source text must be non-empty")
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def proposition_identity(proposition: GroundedProposition) -> str:
    payload = asdict(proposition)
    payload["source_kind"] = proposition.source_kind.value
    payload["polarity"] = proposition.polarity.value
    payload["qualifiers"] = [
        {"role": qualifier.role.value, "span": asdict(qualifier.span)}
        for qualifier in proposition.qualifiers
    ]
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_propositions(
    source: str,
    propositions: Sequence[GroundedProposition],
) -> None:
    digest = source_digest(source)
    identities: set[str] = set()
    for proposition in propositions:
        if not isinstance(proposition, GroundedProposition):
            raise TypeError("propositions must contain GroundedProposition values")
        if not isinstance(proposition.source_kind, SourceKind):
            raise TypeError("source_kind must be a SourceKind")
        if not isinstance(proposition.source_id, str) or not proposition.source_id.strip():
            raise ValueError("source_id must be non-empty")
        if proposition.source_sha256 != digest:
            raise ValueError("source_sha256 does not match source text")
        if not isinstance(proposition.polarity, PropositionPolarity):
            raise TypeError("polarity must be a PropositionPolarity")
        proposition.sentence.validate(source)
        for span in (proposition.subject, proposition.predicate, proposition.object):
            span.validate(source, within=proposition.sentence)
        for qualifier in proposition.qualifiers:
            if not isinstance(qualifier, PropositionQualifier):
                raise TypeError("qualifiers must contain PropositionQualifier values")
            if not isinstance(qualifier.role, QualifierRole):
                raise TypeError("qualifier role must be a QualifierRole")
            qualifier.span.validate(source, within=proposition.sentence)
        identity = proposition_identity(proposition)
        if identity in identities:
            raise ValueError("duplicate proposition identity")
        identities.add(identity)


def score_proposition_pairs(
    claim_propositions: Sequence[GroundedProposition],
    document_propositions: Sequence[GroundedProposition],
    cosine_similarity: Callable[[str, str], float],
) -> PropositionPairFeatures:
    if not claim_propositions or not document_propositions:
        raise ValueError("at least one claim and document proposition is required")
    candidates: list[tuple[float, str, str, PropositionPairFeatures]] = []
    for claim in claim_propositions:
        if claim.source_kind is not SourceKind.CLAIM:
            raise ValueError("claim propositions must use claim source kind")
        for document in document_propositions:
            if document.source_kind is not SourceKind.DOCUMENT:
                raise ValueError("document propositions must use document source kind")
            features, structural = _score_pair(claim, document, cosine_similarity)
            candidates.append(
                (
                    -structural,
                    features.claim_proposition_id,
                    features.document_proposition_id,
                    features,
                )
            )
    return min(candidates)[3]


def evaluate_extraction_coverage(coverage: ExtractionCoverage) -> ExtractionCoverageGate:
    pairs = (
        ("schema_valid_sources", coverage.schema_valid_sources, coverage.total_sources),
        ("usable_claims", coverage.usable_claims, coverage.total_claims),
        (
            "usable_candidate_documents",
            coverage.usable_candidate_documents,
            coverage.total_candidate_documents,
        ),
        (
            "usable_decisive_documents",
            coverage.usable_decisive_documents,
            coverage.decisive_documents,
        ),
        ("usable_audit_documents", coverage.usable_audit_documents, coverage.audit_documents),
    )
    for name, value, total in pairs:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
        if isinstance(total, bool) or not isinstance(total, int) or total < 1 or value > total:
            raise ValueError(f"{name} total must be positive and contain the covered count")
    failed: list[str] = []
    if coverage.schema_valid_sources / coverage.total_sources < 0.99:
        failed.append("schema-valid-sources")
    if coverage.usable_claims != coverage.total_claims:
        failed.append("usable-claims")
    if coverage.usable_candidate_documents / coverage.total_candidate_documents < 0.95:
        failed.append("usable-candidate-documents")
    if coverage.usable_decisive_documents != coverage.decisive_documents:
        failed.append("usable-decisive-documents")
    if coverage.usable_audit_documents != coverage.audit_documents:
        failed.append("usable-audit-documents")
    return ExtractionCoverageGate(not failed, tuple(failed), coverage)


def _score_pair(
    claim: GroundedProposition,
    document: GroundedProposition,
    cosine_similarity: Callable[[str, str], float],
) -> tuple[PropositionPairFeatures, float]:
    ss = _mapped_similarity(claim.subject.text, document.subject.text, cosine_similarity)
    so = _mapped_similarity(claim.subject.text, document.object.text, cosine_similarity)
    os = _mapped_similarity(claim.object.text, document.subject.text, cosine_similarity)
    oo = _mapped_similarity(claim.object.text, document.object.text, cosine_similarity)
    predicate = _mapped_similarity(
        claim.predicate.text,
        document.predicate.text,
        cosine_similarity,
    )
    entity = max(ss, so, os, oo)
    argument_direction = ((ss + oo) - (so + os)) / 2.0
    polarity = 1.0 if claim.polarity is document.polarity else -1.0
    qualifier = _qualifier_similarity(claim, document, cosine_similarity)
    structural = fmean((entity, predicate, (argument_direction + 1.0) / 2.0))
    pair_mean = fmean(
        (
            entity,
            predicate,
            (argument_direction + 1.0) / 2.0,
            (polarity + 1.0) / 2.0,
            qualifier,
        )
    )
    return (
        PropositionPairFeatures(
            claim_proposition_id=proposition_identity(claim),
            document_proposition_id=proposition_identity(document),
            entity=entity,
            predicate=predicate,
            argument_direction=argument_direction,
            polarity=polarity,
            qualifier=qualifier,
            proposition_pair_mean=pair_mean,
        ),
        structural,
    )


def _qualifier_similarity(
    claim: GroundedProposition,
    document: GroundedProposition,
    cosine_similarity: Callable[[str, str], float],
) -> float:
    if not claim.qualifiers:
        return 0.0
    values: list[float] = []
    for claim_qualifier in claim.qualifiers:
        same_role = [
            qualifier for qualifier in document.qualifiers if qualifier.role is claim_qualifier.role
        ]
        values.append(
            max(
                (
                    _mapped_similarity(
                        claim_qualifier.span.text,
                        qualifier.span.text,
                        cosine_similarity,
                    )
                    for qualifier in same_role
                ),
                default=0.0,
            )
        )
    return fmean(values)


def _mapped_similarity(
    left: str,
    right: str,
    cosine_similarity: Callable[[str, str], float],
) -> float:
    value = cosine_similarity(left, right)
    if not isinstance(value, float | int) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError("similarity must be a finite cosine value")
    if value < -1.0 or value > 1.0:
        raise ValueError("similarity must be a finite cosine value in [-1, 1]")
    return (float(value) + 1.0) / 2.0


def _is_punctuation(code: int) -> bool:
    return unicodedata.category(chr(code)).startswith("P")
