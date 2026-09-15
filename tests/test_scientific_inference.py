from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from scifact_rag.domain import EvidenceChunk, EvidenceDocument, SearchHit
from scifact_rag.scientific_inference import (
    EvidenceAssemblyError,
    EvidenceChunkRejection,
    InferenceLogits,
    InferenceRequest,
    InferenceResponse,
    ScientificEvidenceAssembler,
    ScientificInferenceLabel,
    bundle_identity,
    candidate_identity,
    request_identity,
)
from scifact_rag.strategies import COREF_NOMINAL_DP_MINILM


class FakeChunkStore:
    def __init__(self, chunks: Sequence[EvidenceChunk]) -> None:
        self.chunks = list(chunks)
        self.requests: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    def load_chunks(
        self,
        document_ids: Sequence[str],
        representations: Sequence[str],
    ) -> list[EvidenceChunk]:
        self.requests.append((tuple(document_ids), tuple(representations)))
        return list(self.chunks)


class FakeReranker:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.calls: list[tuple[str, list[SearchHit]]] = []

    def score(self, query: str, documents: Sequence[SearchHit]) -> list[float]:
        self.calls.append((query, list(documents)))
        return [self.scores[document.text] for document in documents]


class RecordingPairBudget:
    maximum_pair_tokens = 512

    def __init__(self, pair_tokens: int) -> None:
        self.pair_tokens = pair_tokens
        self.calls: list[tuple[str, str]] = []

    def pair_token_count(self, premise: str, hypothesis: str) -> int:
        self.calls.append((premise, hypothesis))
        return self.pair_tokens


class RejectTextPairBudget(RecordingPairBudget):
    def __init__(self, rejected_text: str) -> None:
        super().__init__(100)
        self.rejected_text = rejected_text

    def pair_token_count(self, premise: str, hypothesis: str) -> int:
        self.calls.append((premise, hypothesis))
        return 513 if self.rejected_text in premise else 100


def chunk(ordinal: int, text: str) -> EvidenceChunk:
    return EvidenceChunk(
        "10",
        ordinal,
        text,
        COREF_NOMINAL_DP_MINILM,
        embedding_required=False,
    )


def test_candidate_identity_precedes_bundle_and_binds_document_content() -> None:
    document = EvidenceDocument("10", "Title", "Abstract")
    identity = candidate_identity("run-1", "7", "A claim", document)

    assert identity == candidate_identity("run-1", "7", "A claim", document)
    assert identity != candidate_identity(
        "run-1", "7", "A claim", EvidenceDocument("10", "Title", "Changed")
    )
    assert len(identity) == 64


def test_bundle_and_request_identities_bind_their_separate_inputs() -> None:
    bundle = {"premise": "evidence", "chunk_ordinals": [0, 2]}
    bundle_digest = bundle_identity(bundle)
    payload = {"premise": "evidence", "hypothesis": "claim"}

    assert bundle_digest == bundle_identity(bundle)
    assert request_identity("a" * 64, bundle_digest, payload) == request_identity(
        "a" * 64, bundle_digest, payload
    )
    assert request_identity("a" * 64, bundle_digest, payload) != request_identity(
        "a" * 64, bundle_digest, {**payload, "hypothesis": "changed"}
    )


def test_logits_are_labeled_finite_and_use_a_fixed_tie_rule() -> None:
    logits = InferenceLogits(entailment=1.0, contradiction=1.0, neutral=0.0)

    assert logits.predicted_label is ScientificInferenceLabel.ENTAILMENT
    assert logits.evidence_margin == pytest.approx(1.0 + math.log(2.0))
    assert logits.polarity_margin == 0.0

    with pytest.raises(ValueError, match="finite"):
        InferenceLogits(float("nan"), 0.0, 0.0)


def test_request_and_response_validate_boundary_fields() -> None:
    request = InferenceRequest("a" * 64, "premise", "hypothesis", expected_pair_tokens=17)
    response = InferenceResponse(
        "a" * 64,
        "revision",
        17,
        InferenceLogits(entailment=2.0, contradiction=-1.0, neutral=0.5),
    )

    assert request.expected_pair_tokens == response.pair_token_count

    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        InferenceRequest("not-a-digest", "premise", "hypothesis", 17)
    with pytest.raises(ValueError, match="non-empty"):
        InferenceResponse("a" * 64, "", 17, response.logits)
    with pytest.raises(ValueError, match="positive"):
        InferenceRequest("a" * 64, "premise", "hypothesis", 0)


def test_assembler_admits_by_relevance_then_serializes_in_source_order() -> None:
    chunks = [chunk(0, "first"), chunk(1, "second"), chunk(2, "third")]
    assembler = ScientificEvidenceAssembler(
        FakeChunkStore(chunks),
        FakeReranker({"first": 0.1, "second": 0.9, "third": 0.8}),
        RejectTextPairBudget("first"),
    )

    bundle = assembler.assemble("claim", EvidenceDocument("10", "Title", "whole"))

    assert [item.ordinal for item in bundle.admitted] == [1, 2]
    assert bundle.premise.index("second") < bundle.premise.index("third")
    assert bundle.rejected == (EvidenceChunkRejection(0, "token_budget"),)


def test_assembler_continues_after_a_large_chunk_does_not_fit() -> None:
    chunks = [chunk(0, "small"), chunk(1, "oversized")]
    assembler = ScientificEvidenceAssembler(
        FakeChunkStore(chunks),
        FakeReranker({"small": 0.8, "oversized": 0.9}),
        RejectTextPairBudget("oversized"),
    )

    bundle = assembler.assemble("claim", EvidenceDocument("10", "Title", "whole"))

    assert [item.ordinal for item in bundle.admitted] == [0]
    assert bundle.rejected == (EvidenceChunkRejection(1, "token_budget"),)


def test_assembler_counts_title_claim_markers_separators_and_special_tokens() -> None:
    budget = RecordingPairBudget(pair_tokens=23)
    bundle = ScientificEvidenceAssembler(
        FakeChunkStore([chunk(0, "evidence")]),
        FakeReranker({"evidence": 1.0}),
        budget,
    ).assemble("raw claim", EvidenceDocument("10", "Document title", "whole"))

    assert budget.calls[-1] == (bundle.premise, "raw claim")
    assert bundle.premise == "[TITLE] Document title\n[EVIDENCE ordinal=0] evidence"
    assert bundle.pair_token_count == 23


@pytest.mark.parametrize(
    "chunks",
    (
        (),
        (EvidenceChunk("11", 0, "foreign", COREF_NOMINAL_DP_MINILM),),
        (chunk(0, "one"), chunk(0, "duplicate")),
        (EvidenceChunk("10", 0, "wrong", "token-window"),),
    ),
)
def test_assembler_rejects_invalid_store_results(chunks: Sequence[EvidenceChunk]) -> None:
    with pytest.raises(EvidenceAssemblyError, match="stored evidence"):
        ScientificEvidenceAssembler(
            FakeChunkStore(chunks), FakeReranker({}), RecordingPairBudget(10)
        ).assemble("claim", EvidenceDocument("10", "Title", "whole"))
