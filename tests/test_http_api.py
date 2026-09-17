from __future__ import annotations

from typing import cast

import httpx
import pytest

from scifact_rag import http_api as http_api_module
from scifact_rag.application import RagApplication
from scifact_rag.domain import Answer, SearchHit
from scifact_rag.generation import GenerationContextStrategyName
from scifact_rag.http_api import create_http_app
from scifact_rag.strategies import DEFAULT_RETRIEVAL_STRATEGY, RetrievalStrategyName


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_health_is_liveness_only() -> None:
    def fail_if_resolved(
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication:
        raise AssertionError("health must not resolve an application")

    transport = httpx.ASGITransport(app=create_http_app(fail_if_resolved))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"schema_version": "health/v1", "status": "ok"}


class RecordingApplication:
    def __init__(self, *, answer: Answer | None = None) -> None:
        self.hit = SearchHit("17", "Trial", "Complete abstract.", 0.875)
        self.answer = answer or Answer(
            query="claim",
            text="Supported [17]",
            citations=("17",),
            model="qwen",
            evidence=(self.hit,),
        )
        self.calls: list[tuple[str, str, int]] = []

    def search(self, query: str, *, limit: int = 5) -> list[SearchHit]:
        self.calls.append(("search", query, limit))
        return [self.hit]

    def ask(self, query: str, *, limit: int = 5) -> Answer:
        self.calls.append(("ask", query, limit))
        return self.answer


def recording_resolver(
    application: RecordingApplication,
    resolutions: list[tuple[RetrievalStrategyName, GenerationContextStrategyName]],
):
    def resolve(
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication:
        resolutions.append((retrieval_strategy, generation_context_strategy))
        return cast(RagApplication, application)

    return resolve


@pytest.mark.anyio
async def test_search_maps_request_and_result_without_changing_values() -> None:
    application = RecordingApplication()
    resolutions: list[tuple[RetrievalStrategyName, GenerationContextStrategyName]] = []
    transport = httpx.ASGITransport(
        app=create_http_app(recording_resolver(application, resolutions))
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/search",
            json={
                "schema_version": "search-request/v1",
                "query": "  claim  ",
                "limit": 7,
                "strategy": RetrievalStrategyName.BM25.value,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "search-response/v1",
        "hits": [
            {
                "doc_id": "17",
                "title": "Trial",
                "text": "Complete abstract.",
                "score": 0.875,
            }
        ],
    }
    assert resolutions == [
        (RetrievalStrategyName.BM25, GenerationContextStrategyName.WHOLE_DOCUMENT)
    ]
    assert application.calls == [("search", "  claim  ", 7)]


@pytest.mark.anyio
async def test_ask_maps_request_and_result_without_changing_values() -> None:
    application = RecordingApplication()
    resolutions: list[tuple[RetrievalStrategyName, GenerationContextStrategyName]] = []
    transport = httpx.ASGITransport(
        app=create_http_app(recording_resolver(application, resolutions))
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/ask",
            json={
                "schema_version": "ask-request/v1",
                "query": "claim",
                "limit": 3,
                "strategy": DEFAULT_RETRIEVAL_STRATEGY.value,
                "context_strategy": GenerationContextStrategyName.ADAPTIVE.value,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "answer/v1",
        "query": "claim",
        "text": "Supported [17]",
        "citations": ["17"],
        "model": "qwen",
        "evidence": [
            {
                "doc_id": "17",
                "title": "Trial",
                "text": "Complete abstract.",
                "score": 0.875,
            }
        ],
    }
    assert resolutions == [(DEFAULT_RETRIEVAL_STRATEGY, GenerationContextStrategyName.ADAPTIVE)]
    assert application.calls == [("ask", "claim", 3)]


@pytest.mark.anyio
async def test_ask_preserves_exact_insufficient_evidence_result() -> None:
    application = RecordingApplication(
        answer=Answer(
            query="unresolved claim",
            text="insufficient evidence",
            citations=(),
            model="qwen",
            evidence=(),
        )
    )
    resolutions: list[tuple[RetrievalStrategyName, GenerationContextStrategyName]] = []
    transport = httpx.ASGITransport(
        app=create_http_app(recording_resolver(application, resolutions))
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/ask",
            json={
                "schema_version": "ask-request/v1",
                "query": "unresolved claim",
            },
        )

    assert response.status_code == 200
    assert response.json()["text"] == "insufficient evidence"
    assert response.json()["citations"] == []
    assert response.json()["evidence"] == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path", "payload"),
    (
        ("/v1/search", {"query": "claim"}),
        (
            "/v1/search",
            {"schema_version": "search-request/v2", "query": "claim"},
        ),
        (
            "/v1/search",
            {"schema_version": "search-request/v1", "query": "claim", "extra": True},
        ),
        (
            "/v1/search",
            {"schema_version": "search-request/v1", "query": "   "},
        ),
        (
            "/v1/search",
            {"schema_version": "search-request/v1", "query": "x" * 4097},
        ),
        (
            "/v1/search",
            {"schema_version": "search-request/v1", "query": "claim", "limit": 0},
        ),
        (
            "/v1/search",
            {"schema_version": "search-request/v1", "query": "claim", "limit": 101},
        ),
        (
            "/v1/search",
            {"schema_version": "search-request/v1", "query": "claim", "limit": True},
        ),
        (
            "/v1/search",
            {"schema_version": "search-request/v1", "query": "claim", "limit": "5"},
        ),
        (
            "/v1/search",
            {"schema_version": "search-request/v1", "query": "claim", "limit": 5.0},
        ),
        (
            "/v1/search",
            {"schema_version": "search-request/v1", "query": "claim", "strategy": "bad"},
        ),
        (
            "/v1/ask",
            {"schema_version": "ask-request/v1", "query": "claim", "limit": 21},
        ),
        (
            "/v1/ask",
            {"schema_version": "ask-request/v1", "query": "claim", "limit": True},
        ),
        (
            "/v1/ask",
            {"schema_version": "ask-request/v1", "query": "claim", "limit": "5"},
        ),
        (
            "/v1/ask",
            {"schema_version": "ask-request/v1", "query": "claim", "limit": 5.0},
        ),
        (
            "/v1/ask",
            {
                "schema_version": "ask-request/v1",
                "query": "claim",
                "context_strategy": "bad",
            },
        ),
    ),
)
async def test_validation_failure_is_structured_and_never_resolves_application(
    path: str,
    payload: dict[str, object],
) -> None:
    application = RecordingApplication()
    resolutions: list[tuple[RetrievalStrategyName, GenerationContextStrategyName]] = []
    transport = httpx.ASGITransport(
        app=create_http_app(recording_resolver(application, resolutions))
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(path, json=payload)

    assert response.status_code == 422
    assert response.json()["schema_version"] == "error/v1"
    assert response.json()["error"]["code"] == "validation_error"
    assert "x" * 256 not in response.text
    assert resolutions == []
    assert application.calls == []


@pytest.mark.anyio
async def test_malformed_json_uses_validation_envelope_without_resolving_application() -> None:
    application = RecordingApplication()
    resolutions: list[tuple[RetrievalStrategyName, GenerationContextStrategyName]] = []
    transport = httpx.ASGITransport(
        app=create_http_app(recording_resolver(application, resolutions))
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/search",
            content=b'{"schema_version":',
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 422
    assert response.json()["schema_version"] == "error/v1"
    assert response.json()["error"]["code"] == "validation_error"
    assert resolutions == []
    assert application.calls == []


@pytest.mark.anyio
async def test_unexpected_failure_returns_only_fixed_internal_error() -> None:
    def failing_resolver(
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication:
        raise RuntimeError("secret configuration")

    transport = httpx.ASGITransport(
        app=create_http_app(failing_resolver),
        raise_app_exceptions=False,
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/search",
            json={"schema_version": "search-request/v1", "query": "claim"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "schema_version": "error/v1",
        "error": {
            "code": "internal_error",
            "message": "The request could not be completed",
        },
    }
    assert "secret" not in response.text
    assert "RuntimeError" not in response.text


@pytest.mark.anyio
async def test_runtime_factory_caches_composed_applications_by_strategy_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = RecordingApplication()
    compositions: list[tuple[RetrievalStrategyName, GenerationContextStrategyName]] = []

    def fake_build_application(
        *,
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication:
        compositions.append((retrieval_strategy, generation_context_strategy))
        return cast(RagApplication, application)

    monkeypatch.setattr(
        http_api_module,
        "build_application",
        fake_build_application,
        raising=False,
    )
    transport = httpx.ASGITransport(app=http_api_module.build_http_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        search_payload = {
            "schema_version": "search-request/v1",
            "query": "claim",
            "strategy": RetrievalStrategyName.BM25.value,
        }
        assert (await client.post("/v1/search", json=search_payload)).status_code == 200
        assert (await client.post("/v1/search", json=search_payload)).status_code == 200
        assert (
            await client.post(
                "/v1/ask",
                json={
                    "schema_version": "ask-request/v1",
                    "query": "claim",
                    "strategy": RetrievalStrategyName.BM25.value,
                    "context_strategy": GenerationContextStrategyName.ADAPTIVE.value,
                },
            )
        ).status_code == 200

    assert compositions == [
        (RetrievalStrategyName.BM25, GenerationContextStrategyName.WHOLE_DOCUMENT),
        (RetrievalStrategyName.BM25, GenerationContextStrategyName.ADAPTIVE),
    ]
