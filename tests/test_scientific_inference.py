from __future__ import annotations

import math

import pytest

from scifact_rag.domain import EvidenceDocument
from scifact_rag.scientific_inference import (
    InferenceLogits,
    InferenceRequest,
    InferenceResponse,
    ScientificInferenceLabel,
    bundle_identity,
    candidate_identity,
    request_identity,
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
