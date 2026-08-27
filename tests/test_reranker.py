from __future__ import annotations

from typing import Any

import httpx
import pytest

from scifact_rag.adapters.reranker import RankLlmReranker, TeiReranker, VllmColbertReranker
from scifact_rag.domain import SearchHit


def test_tei_adapter_scores_raw_query_document_pairs_in_input_order(
    monkeypatch: Any,
) -> None:
    observed: dict[str, Any] = {}

    def fake_post(url: str, *, json: dict[str, Any], timeout: float) -> httpx.Response:
        observed.update({"url": url, "json": json, "timeout": timeout})
        return httpx.Response(
            200,
            json=[{"index": 1, "score": 0.9}, {"index": 0, "score": 0.2}],
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    reranker = TeiReranker("http://reranker.test/", timeout_seconds=30.0)

    scores = reranker.score(
        "raw query",
        [
            SearchHit("1", "First title", "First abstract", 0.2),
            SearchHit("2", "Second title", "Second abstract", 0.1),
        ],
    )

    assert scores == [0.2, 0.9]
    assert observed == {
        "url": "http://reranker.test/rerank",
        "json": {
            "query": "raw query",
            "texts": ["First title\nFirst abstract", "Second title\nSecond abstract"],
            "return_text": False,
            "truncate": True,
        },
        "timeout": 30.0,
    }


def test_vllm_colbert_adapter_scores_raw_query_document_pairs_in_input_order(
    monkeypatch: Any,
) -> None:
    observed: dict[str, Any] = {}

    def fake_post(url: str, *, json: dict[str, Any], timeout: float) -> httpx.Response:
        observed.update({"url": url, "json": json, "timeout": timeout})
        return httpx.Response(
            200,
            json={
                "model": "answerdotai/answerai-colbert-small-v1",
                "results": [
                    {"index": 1, "relevance_score": 19.5},
                    {"index": 0, "relevance_score": 11.25},
                ],
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    reranker = VllmColbertReranker(
        "http://late-interaction.test/",
        "answerdotai/answerai-colbert-small-v1",
        timeout_seconds=45.0,
    )

    scores = reranker.score(
        "raw query",
        [
            SearchHit("1", "First title", "First abstract", 0.2),
            SearchHit("2", "Second title", "Second abstract", 0.1),
        ],
    )

    assert scores == [11.25, 19.5]
    assert observed == {
        "url": "http://late-interaction.test/rerank",
        "json": {
            "model": "answerdotai/answerai-colbert-small-v1",
            "query": "raw query",
            "documents": ["First title\nFirst abstract", "Second title\nSecond abstract"],
            "return_documents": False,
            "truncate_prompt_tokens": 512,
            "truncation_side": "right",
        },
        "timeout": 45.0,
    }


@pytest.mark.parametrize(
    "payload, message",
    (
        ({"results": [{"index": 0, "relevance_score": 1.0}]}, "wrong number"),
        (
            {
                "results": [
                    {"index": 0, "relevance_score": 1.0},
                    {"index": 0, "relevance_score": 2.0},
                ]
            },
            "duplicate",
        ),
        ({"results": [{}, {}]}, "invalid response"),
    ),
)
def test_vllm_colbert_adapter_rejects_incomplete_or_invalid_results(
    monkeypatch: Any,
    payload: dict[str, Any],
    message: str,
) -> None:
    def fake_post(url: str, *, json: dict[str, Any], timeout: float) -> httpx.Response:
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    reranker = VllmColbertReranker("http://late-interaction.test", "model")

    with pytest.raises(ValueError, match=message):
        reranker.score(
            "query",
            [SearchHit("1", "one", "first", 0.0), SearchHit("2", "two", "second", 0.0)],
        )


def rankllm_envelope(candidates: object) -> dict[str, Any]:
    return {
        "schema_version": "castorini.cli.v1",
        "repo": "rank_llm",
        "command": "rerank",
        "status": "success",
        "exit_code": 0,
        "artifacts": [
            {
                "name": "rerank-results",
                "kind": "data",
                "value": [{"query": {"text": "raw query"}, "candidates": candidates}],
            }
        ],
    }


def test_rankllm_adapter_preserves_authoritative_listwise_order(
    monkeypatch: Any,
) -> None:
    observed: dict[str, Any] = {}

    def fake_post(url: str, *, json: dict[str, Any], timeout: float) -> httpx.Response:
        observed.update({"url": url, "json": json, "timeout": timeout})
        return httpx.Response(
            200,
            json=rankllm_envelope(
                [
                    {"docid": "2", "score": 1.0, "doc": {"contents": "second"}},
                    {"docid": "1", "score": 0.5, "doc": {"contents": "first"}},
                ]
            ),
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    reranker = RankLlmReranker("http://rankllm.test/", timeout_seconds=45.0)

    scores = reranker.score(
        "raw query",
        [
            SearchHit("1", "First title", "First abstract", 0.2),
            SearchHit("2", "Second title", "Second abstract", 0.1),
        ],
    )

    assert scores == [1.0, 2.0]
    assert observed == {
        "url": "http://rankllm.test/v1/rerank",
        "json": {
            "query": "raw query",
            "candidates": [
                {
                    "docid": "1",
                    "score": 0.0,
                    "text": "First title\nFirst abstract",
                },
                {
                    "docid": "2",
                    "score": 0.0,
                    "text": "Second title\nSecond abstract",
                },
            ],
        },
        "timeout": 45.0,
    }


@pytest.mark.parametrize(
    "payload, message",
    (
        ({}, "envelope"),
        (rankllm_envelope([{"docid": "1"}]), "wrong number"),
        (rankllm_envelope([{"docid": "1"}, {"docid": "1"}]), "duplicate"),
        (rankllm_envelope([{"docid": "1"}, {"docid": "3"}]), "unknown"),
    ),
)
def test_rankllm_adapter_rejects_invalid_or_incomplete_rankings(
    monkeypatch: Any,
    payload: dict[str, Any],
    message: str,
) -> None:
    def fake_post(url: str, *, json: dict[str, Any], timeout: float) -> httpx.Response:
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    reranker = RankLlmReranker("http://rankllm.test")

    with pytest.raises(ValueError, match=message):
        reranker.score(
            "query",
            [SearchHit("1", "one", "first", 0.0), SearchHit("2", "two", "second", 0.0)],
        )
