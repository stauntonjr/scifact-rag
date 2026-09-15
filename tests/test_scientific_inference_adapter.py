from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
import pytest

from scifact_rag.adapters.scientific_inference import (
    ScientificInferenceProtocolError,
    TransformersScientificInferenceClient,
)
from scifact_rag.scientific_inference import (
    DEBERTA_REVISION,
    InferenceRequest,
    ScientificInferenceLabel,
)


class FakeResponse:
    def __init__(self, payload: object, *, status_error: bool = False) -> None:
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self) -> None:
        if self.status_error:
            raise httpx.HTTPStatusError(
                "failure",
                request=httpx.Request("POST", "http://nli/v1/classify"),
                response=httpx.Response(500),
            )

    def json(self) -> object:
        return self.payload


def response_payload(**updates: Any) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "scientific-inference-response/v1",
        "attempt_id": "a" * 64,
        "model_revision": DEBERTA_REVISION,
        "pair_token_count": 17,
        "logits": {
            "entailment": 2.0,
            "contradiction": -1.0,
            "neutral": 0.5,
        },
    }
    payload.update(updates)
    return payload


def test_client_sends_one_pair_and_preserves_labeled_logits(monkeypatch) -> None:
    calls: list[tuple[str, Mapping[str, object], float]] = []

    def fake_post(url: str, *, json: Mapping[str, object], timeout: float) -> FakeResponse:
        calls.append((url, json, timeout))
        return FakeResponse(response_payload())

    monkeypatch.setattr(httpx, "post", fake_post)
    response = TransformersScientificInferenceClient("http://nli:80", DEBERTA_REVISION).classify(
        InferenceRequest("a" * 64, "premise", "hypothesis", 17)
    )

    assert calls == [
        (
            "http://nli:80/v1/classify",
            {
                "schema_version": "scientific-inference-request/v1",
                "attempt_id": "a" * 64,
                "premise": "premise",
                "hypothesis": "hypothesis",
                "expected_pair_tokens": 17,
            },
            30.0,
        )
    ]
    assert response.logits.predicted_label is ScientificInferenceLabel.ENTAILMENT


@pytest.mark.parametrize(
    "payload",
    (
        response_payload(attempt_id="b" * 64),
        response_payload(model_revision="wrong"),
        response_payload(pair_token_count=18),
        response_payload(schema_version="unknown/v1"),
        response_payload(extra="field"),
        response_payload(logits={"entailment": 1.0, "contradiction": 0.0}),
        response_payload(logits={"entailment": 1.0, "contradiction": 0.0, "neutral": float("inf")}),
        ["not", "an", "object"],
    ),
)
def test_client_rejects_invalid_responses_after_one_call(monkeypatch, payload: object) -> None:
    calls = 0

    def fake_post(url: str, *, json: object, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse(payload)

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises((ScientificInferenceProtocolError, ValueError)):
        TransformersScientificInferenceClient("http://nli", DEBERTA_REVISION).classify(
            InferenceRequest("a" * 64, "premise", "hypothesis", 17)
        )

    assert calls == 1


def test_client_propagates_http_error_without_retry(monkeypatch) -> None:
    calls = 0

    def fake_post(url: str, *, json: object, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse({}, status_error=True)

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(httpx.HTTPStatusError):
        TransformersScientificInferenceClient("http://nli", DEBERTA_REVISION).classify(
            InferenceRequest("a" * 64, "premise", "hypothesis", 17)
        )

    assert calls == 1
