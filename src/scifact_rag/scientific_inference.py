from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, is_dataclass
from enum import StrEnum
from typing import Any

from .domain import EvidenceDocument

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ScientificInferenceLabel(StrEnum):
    ENTAILMENT = "entailment"
    CONTRADICTION = "contradiction"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class InferenceLogits:
    entailment: float
    contradiction: float
    neutral: float

    def __post_init__(self) -> None:
        if not all(
            math.isfinite(value)
            for value in (self.entailment, self.contradiction, self.neutral)
        ):
            raise ValueError("inference logits must be finite")

    @property
    def predicted_label(self) -> ScientificInferenceLabel:
        ordered = (
            (ScientificInferenceLabel.ENTAILMENT, self.entailment),
            (ScientificInferenceLabel.CONTRADICTION, self.contradiction),
            (ScientificInferenceLabel.NEUTRAL, self.neutral),
        )
        return max(ordered, key=lambda item: item[1])[0]

    @property
    def evidence_margin(self) -> float:
        largest = max(self.entailment, self.contradiction)
        evidence_logit = largest + math.log(
            math.exp(self.entailment - largest) + math.exp(self.contradiction - largest)
        )
        return evidence_logit - self.neutral

    @property
    def polarity_margin(self) -> float:
        return self.entailment - self.contradiction


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    attempt_id: str
    premise: str
    hypothesis: str
    expected_pair_tokens: int

    def __post_init__(self) -> None:
        _validate_digest("attempt_id", self.attempt_id)
        _validate_text("premise", self.premise)
        _validate_text("hypothesis", self.hypothesis)
        _validate_positive_count("expected_pair_tokens", self.expected_pair_tokens)


@dataclass(frozen=True, slots=True)
class InferenceResponse:
    attempt_id: str
    model_revision: str
    pair_token_count: int
    logits: InferenceLogits

    def __post_init__(self) -> None:
        _validate_digest("attempt_id", self.attempt_id)
        _validate_text("model_revision", self.model_revision)
        _validate_positive_count("pair_token_count", self.pair_token_count)


def candidate_identity(
    run_id: str,
    query_id: str,
    claim: str,
    document: EvidenceDocument,
) -> str:
    """Identify a run candidate before evidence assembly can succeed or fail."""
    _validate_text("run_id", run_id)
    _validate_text("query_id", query_id)
    _validate_text("claim", claim)
    _validate_text("document_id", document.doc_id)
    document_digest = _sha256_json({"text": document.text, "title": document.title})
    return _sha256_json(
        {
            "claim_sha256": hashlib.sha256(claim.encode("utf-8")).hexdigest(),
            "document_digest": document_digest,
            "document_id": document.doc_id,
            "query_id": query_id,
            "run_id": run_id,
        }
    )


def bundle_identity(bundle: object) -> str:
    """Digest a completed evidence bundle independently of candidate identity."""
    return _sha256_json(bundle)


def request_identity(
    candidate_id: str,
    bundle_digest: str,
    payload: object,
    attempt_ordinal: int = 1,
) -> str:
    """Bind the single allowed attempt to its candidate, bundle, and exact payload."""
    _validate_digest("candidate_id", candidate_id)
    _validate_digest("bundle_digest", bundle_digest)
    _validate_positive_count("attempt_ordinal", attempt_ordinal)
    return _sha256_json(
        {
            "attempt_ordinal": attempt_ordinal,
            "bundle_digest": bundle_digest,
            "candidate_id": candidate_id,
            "payload_digest": _sha256_json(payload),
        }
    )


def _validate_digest(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a 64-character lowercase hexadecimal digest")


def _validate_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")


def _validate_positive_count(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    serializable: Any = asdict(value) if is_dataclass(value) and not isinstance(value, type) else value
    return json.dumps(
        serializable,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
