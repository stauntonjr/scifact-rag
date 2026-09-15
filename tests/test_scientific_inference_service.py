from __future__ import annotations

from collections.abc import Mapping

import pytest

from scifact_rag.scientific_inference import DEBERTA_REVISION
from scifact_rag.scientific_inference_service import classify_payload


class RecordingBackend:
    def __init__(
        self,
        *,
        id2label: Mapping[int, str],
        logits: tuple[float, ...],
        pair_tokens: int,
        model_revision: str = DEBERTA_REVISION,
    ) -> None:
        self.id2label = dict(id2label)
        self.logits = logits
        self.pair_tokens = pair_tokens
        self.model_revision = model_revision
        self.pairs: list[tuple[str, str]] = []

    def classify_pair(self, premise: str, hypothesis: str) -> tuple[tuple[float, ...], int]:
        self.pairs.append((premise, hypothesis))
        return self.logits, self.pair_tokens


def request_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "scientific-inference-request/v1",
        "attempt_id": "a" * 64,
        "premise": "premise",
        "hypothesis": "hypothesis",
        "expected_pair_tokens": 17,
    }
    payload.update(updates)
    return payload


def valid_backend(**updates: object) -> RecordingBackend:
    values: dict[str, object] = {
        "id2label": {0: "contradiction", 1: "entailment", 2: "neutral"},
        "logits": (-2.0, 3.0, 0.5),
        "pair_tokens": 17,
        "model_revision": DEBERTA_REVISION,
    }
    values.update(updates)
    return RecordingBackend(**values)  # type: ignore[arg-type]


def test_classify_payload_preserves_pair_order_and_maps_checkpoint_labels() -> None:
    backend = valid_backend()

    response = classify_payload(request_payload(), backend, maximum_pair_tokens=512)

    assert backend.pairs == [("premise", "hypothesis")]
    assert response["logits"] == {
        "entailment": 3.0,
        "contradiction": -2.0,
        "neutral": 0.5,
    }
    assert response["pair_token_count"] == 17
    assert response["model_revision"] == DEBERTA_REVISION


@pytest.mark.parametrize(
    ("payload", "backend"),
    (
        (request_payload(extra="field"), valid_backend()),
        (request_payload(schema_version="wrong"), valid_backend()),
        (request_payload(expected_pair_tokens=18), valid_backend()),
        (request_payload(), valid_backend(pair_tokens=513)),
        (request_payload(), valid_backend(model_revision="wrong")),
        (request_payload(), valid_backend(id2label={0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"})),
        (request_payload(), valid_backend(logits=(-2.0, float("nan"), 0.5))),
    ),
)
def test_classify_payload_rejects_contract_violations(
    payload: dict[str, object], backend: RecordingBackend
) -> None:
    with pytest.raises(ValueError):
        classify_payload(payload, backend, maximum_pair_tokens=512)
