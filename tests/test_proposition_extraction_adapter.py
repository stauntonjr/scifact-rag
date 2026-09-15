from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from scifact_rag.adapters.proposition_extraction import (
    PROPOSITION_PROMPT_ID,
    PROPOSITION_PROMPT_SHA256,
    PROPOSITION_SCHEMA_SHA256,
    PROPOSITION_SEED,
    OpenAiCompatiblePropositionExtractor,
    PropositionExtractionError,
)
from scifact_rag.proposition import PropositionPolarity, QualifierRole, SourceKind, source_digest
from scifact_rag.proposition_evaluation import PropositionSource


class FakeResponse:
    def __init__(self, payload: object, *, status_error: bool = False) -> None:
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self) -> None:
        if self.status_error:
            raise httpx.HTTPStatusError(
                "failure",
                request=httpx.Request("POST", "http://qwen/v1/chat/completions"),
                response=httpx.Response(500),
            )

    def json(self) -> object:
        return self.payload


def _content(source: PropositionSource, **updates: Any) -> str:
    payload: dict[str, object] = {
        "source_kind": source.kind.value,
        "source_id": source.source_id,
        "source_sha256": source.sha256,
        "propositions": [
            {
                "sentence": {"start": 0, "end": len(source.text), "text": source.text},
                "subject": {"start": 0, "end": 7, "text": "Aspirin"},
                "predicate": {"start": 8, "end": 15, "text": "reduces"},
                "object": {"start": 16, "end": 21, "text": "fever"},
                "polarity": "positive",
                "qualifiers": [
                    {
                        "role": "population",
                        "span": {"start": 25, "end": 31, "text": "adults"},
                    }
                ],
            }
        ],
    }
    payload.update(updates)
    return json.dumps(payload)


def test_qwen_extractor_sends_frozen_schema_and_returns_grounded_propositions(monkeypatch) -> None:
    source_text = "Aspirin reduces fever in adults."
    source = PropositionSource(
        SourceKind.DOCUMENT,
        "d-1",
        source_text,
        source_digest(source_text),
    )
    calls: list[tuple[str, dict[str, object], float]] = []

    def fake_post(url, *, headers, json, timeout):
        calls.append((url, json, timeout))
        return FakeResponse(
            {
                "choices": [{"message": {"content": _content(source)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    extractor = OpenAiCompatiblePropositionExtractor(
        base_url="http://qwen/v1",
        model="qwen-test",
        api_key="token",
    )

    propositions = extractor.extract(source)

    assert len(calls) == 1
    url, request, timeout = calls[0]
    assert url == "http://qwen/v1/chat/completions"
    assert request["model"] == "qwen-test"
    assert request["temperature"] == 0
    assert request["seed"] == PROPOSITION_SEED == 1729
    assert request["chat_template_kwargs"] == {"enable_thinking": False}
    assert request["response_format"]["type"] == "json_schema"  # type: ignore[index]
    assert request["response_format"]["json_schema"]["strict"] is True  # type: ignore[index]
    assert PROPOSITION_PROMPT_ID in request["messages"][0]["content"]  # type: ignore[index]
    assert len(PROPOSITION_PROMPT_SHA256) == 64
    assert PROPOSITION_SCHEMA_SHA256 in request["messages"][0]["content"]  # type: ignore[index]
    assert source.sha256 in request["messages"][1]["content"]  # type: ignore[index]
    assert timeout == 120.0
    assert propositions[0].polarity is PropositionPolarity.POSITIVE
    assert propositions[0].qualifiers[0].role is QualifierRole.POPULATION
    assert propositions[0].qualifiers[0].span.text == "adults"


@pytest.mark.parametrize(
    ("content_update", "status_error", "expected_code"),
    (
        ({"source_id": "foreign"}, False, "source-mismatch"),
        ({"source_sha256": "0" * 64}, False, "source-mismatch"),
        ({"extra": "field"}, False, "schema"),
        ({"propositions": "not-a-list"}, False, "schema"),
        (
            {
                "propositions": [
                    {
                        "sentence": {
                            "start": 0,
                            "end": 31,
                            "text": "Aspirin reduces fever in adults.",
                        },
                        "subject": {"start": 0, "end": 7, "text": "Aspirin"},
                        "predicate": {"start": 8, "end": 15, "text": "reduces"},
                        "object": {"start": 16, "end": 21, "text": "fever"},
                        "polarity": "positive",
                        "qualifiers": [{"role": "population"}],
                    }
                ]
            },
            False,
            "schema",
        ),
        (
            {
                "propositions": [
                    {
                        "sentence": {
                            "start": 0,
                            "end": 31,
                            "text": "Aspirin reduces fever in adults.",
                        },
                        "subject": {"start": 0, "end": 7, "text": "Tylenol"},
                        "predicate": {"start": 8, "end": 15, "text": "reduces"},
                        "object": {"start": 16, "end": 21, "text": "fever"},
                        "polarity": "positive",
                        "qualifiers": [],
                    }
                ]
            },
            False,
            "grounding",
        ),
        ({}, True, "http"),
    ),
)
def test_qwen_extractor_rejects_invalid_or_ungrounded_output_without_retry(
    monkeypatch,
    content_update: dict[str, object],
    status_error: bool,
    expected_code: str,
) -> None:
    source_text = "Aspirin reduces fever in adults."
    source = PropositionSource(
        SourceKind.DOCUMENT,
        "d-1",
        source_text,
        source_digest(source_text),
    )
    calls = 0

    def fake_post(url, *, headers, json, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse(
            {"choices": [{"message": {"content": _content(source, **content_update)}}]},
            status_error=status_error,
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    extractor = OpenAiCompatiblePropositionExtractor(base_url="http://qwen/v1", model="qwen-test")

    with pytest.raises(PropositionExtractionError) as captured:
        extractor.extract(source)

    assert captured.value.code == expected_code
    assert calls == 1
