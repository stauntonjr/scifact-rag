from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, is_dataclass
from enum import StrEnum
from typing import Any

from .domain import EvidenceChunk, EvidenceDocument, SearchHit
from .ports import PairTokenBudget, Reranker, StoredChunkSource
from .strategies import COREF_NOMINAL_DP_MINILM

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TITLE_PREFIX = "[TITLE] "
_CHUNK_PREFIX = "[EVIDENCE ordinal={ordinal}] "
_GAP = "[OMITTED ordinals={start}-{end}]"


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


@dataclass(frozen=True, slots=True)
class EvidenceChunkSelection:
    doc_id: str
    representation: str
    ordinal: int
    text: str
    text_sha256: str
    colbert_score: float

    def __post_init__(self) -> None:
        _validate_text("doc_id", self.doc_id)
        _validate_text("representation", self.representation)
        if self.ordinal < 0:
            raise ValueError("chunk ordinal must be non-negative")
        _validate_text("chunk text", self.text)
        _validate_digest("text_sha256", self.text_sha256)
        if not math.isfinite(self.colbert_score):
            raise ValueError("ColBERT score must be finite")


@dataclass(frozen=True, slots=True)
class EvidenceChunkRejection:
    ordinal: int
    reason: str

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("rejected chunk ordinal must be non-negative")
        _validate_text("rejection reason", self.reason)


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    document_id: str
    title: str
    premise: str
    pair_token_count: int
    admitted: tuple[EvidenceChunkSelection, ...]
    rejected: tuple[EvidenceChunkRejection, ...]
    omitted_ranges: tuple[tuple[int, int], ...]
    source_order_restored: bool = True
    title_included: bool = True

    def __post_init__(self) -> None:
        _validate_text("document_id", self.document_id)
        _validate_text("premise", self.premise)
        _validate_positive_count("pair_token_count", self.pair_token_count)
        if not self.admitted:
            raise ValueError("evidence bundle must contain admitted evidence")


class EvidenceAssemblyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class ScientificEvidenceAssembler:
    """Select complete stored DP chunks under the classifier's exact pair budget."""

    def __init__(
        self,
        chunk_source: StoredChunkSource,
        reranker: Reranker,
        token_budget: PairTokenBudget,
    ) -> None:
        self._chunk_source = chunk_source
        self._reranker = reranker
        self._token_budget = token_budget

    def assemble(self, claim: str, document: EvidenceDocument) -> EvidenceBundle:
        _validate_text("claim", claim)
        chunks = self._chunk_source.load_chunks(
            [document.doc_id],
            [COREF_NOMINAL_DP_MINILM],
        )
        self._validate_chunks(document.doc_id, chunks)
        scores = self._reranker.score(
            claim,
            [SearchHit(chunk.doc_id, "", chunk.text, 0.0) for chunk in chunks],
        )
        if len(scores) != len(chunks) or not all(math.isfinite(score) for score in scores):
            raise EvidenceAssemblyError(
                "invalid_chunk_scores",
                "chunk scoring returned a non-finite or incorrectly sized result",
            )

        selections = [self._selection(chunk, score) for chunk, score in zip(chunks, scores)]
        admission_order = sorted(selections, key=lambda item: (-item.colbert_score, item.ordinal))
        admitted: list[EvidenceChunkSelection] = []
        rejected: list[EvidenceChunkRejection] = []
        for selection in admission_order:
            tentative = sorted((*admitted, selection), key=lambda item: item.ordinal)
            premise, _ = _serialize_premise(document.title, tentative)
            pair_tokens = self._token_budget.pair_token_count(premise, claim)
            if pair_tokens <= self._token_budget.maximum_pair_tokens:
                admitted = tentative
            else:
                rejected.append(EvidenceChunkRejection(selection.ordinal, "token_budget"))

        if not admitted:
            raise EvidenceAssemblyError(
                "no_evidence_fit",
                "no complete evidence chunk fits the pair token budget",
            )
        premise, omitted_ranges = _serialize_premise(document.title, admitted)
        pair_tokens = self._token_budget.pair_token_count(premise, claim)
        return EvidenceBundle(
            document_id=document.doc_id,
            title=document.title,
            premise=premise,
            pair_token_count=pair_tokens,
            admitted=tuple(admitted),
            rejected=tuple(sorted(rejected, key=lambda item: item.ordinal)),
            omitted_ranges=omitted_ranges,
        )

    @staticmethod
    def _validate_chunks(document_id: str, chunks: Sequence[EvidenceChunk]) -> None:
        if not chunks:
            raise EvidenceAssemblyError(
                "invalid_stored_evidence", "stored evidence is missing"
            )
        ordinals: set[int] = set()
        for chunk in chunks:
            if (
                chunk.doc_id != document_id
                or chunk.representation != COREF_NOMINAL_DP_MINILM
                or not chunk.text.strip()
                or chunk.ordinal < 0
                or chunk.ordinal in ordinals
            ):
                raise EvidenceAssemblyError(
                    "invalid_stored_evidence",
                    "stored evidence has a foreign, malformed, or duplicate chunk",
                )
            ordinals.add(chunk.ordinal)

    @staticmethod
    def _selection(chunk: EvidenceChunk, score: float) -> EvidenceChunkSelection:
        return EvidenceChunkSelection(
            doc_id=chunk.doc_id,
            representation=chunk.representation,
            ordinal=chunk.ordinal,
            text=chunk.text,
            text_sha256=hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
            colbert_score=score,
        )


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


def _serialize_premise(
    title: str,
    admitted: Sequence[EvidenceChunkSelection],
) -> tuple[str, tuple[tuple[int, int], ...]]:
    ordered = sorted(admitted, key=lambda item: item.ordinal)
    lines = [f"{_TITLE_PREFIX}{title}"]
    omitted_ranges: list[tuple[int, int]] = []
    previous: EvidenceChunkSelection | None = None
    for selection in ordered:
        if previous is not None and selection.ordinal > previous.ordinal + 1:
            gap = (previous.ordinal + 1, selection.ordinal - 1)
            omitted_ranges.append(gap)
            lines.append(_GAP.format(start=gap[0], end=gap[1]))
        lines.append(_CHUNK_PREFIX.format(ordinal=selection.ordinal) + selection.text)
        previous = selection
    return "\n".join(lines), tuple(omitted_ranges)


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
