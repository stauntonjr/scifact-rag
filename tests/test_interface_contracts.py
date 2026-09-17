from __future__ import annotations

import json
from typing import cast

import httpx
import pytest
from typer.testing import CliRunner

from scifact_rag import cli as cli_module
from scifact_rag.application import RagApplication
from scifact_rag.cli import app as cli_app
from scifact_rag.domain import Answer, SearchHit
from scifact_rag.generation import GenerationContextStrategyName
from scifact_rag.http_api import create_http_app
from scifact_rag.strategies import RetrievalStrategyName


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class ParityApplication:
    def __init__(self) -> None:
        self.hit = SearchHit("17", "Trial", "Complete abstract.", 0.875)

    def search(self, query: str, *, limit: int = 5) -> list[SearchHit]:
        return [self.hit]

    def ask(self, query: str, *, limit: int = 5) -> Answer:
        return Answer(query, "Supported [17]", ("17",), "qwen", (self.hit,))


def _resolver(application: ParityApplication):
    def resolve(
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication:
        return cast(RagApplication, application)

    return resolve


def test_openapi_exposes_only_the_three_product_paths_and_versioned_models() -> None:
    application = create_http_app(_resolver(ParityApplication()))

    schema = application.openapi()

    assert set(schema["paths"]) == {"/healthz", "/v1/search", "/v1/ask"}
    components = set(schema["components"]["schemas"])
    assert {
        "HealthResponse",
        "SearchRequest",
        "SearchResponse",
        "AskRequest",
        "AnswerResponse",
        "SearchHitResponse",
        "ErrorResponse",
    } <= components


@pytest.mark.anyio
async def test_search_cli_and_http_have_normalized_result_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = ParityApplication()
    monkeypatch.setattr(
        cli_module,
        "build_application",
        lambda **kwargs: cast(RagApplication, application),
    )
    cli_result = CliRunner().invoke(
        cli_app,
        ["search", "claim", "--limit", "3", "--strategy", "bm25"],
    )
    transport = httpx.ASGITransport(app=create_http_app(_resolver(application)))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/search",
            json={
                "schema_version": "search-request/v1",
                "query": "claim",
                "limit": 3,
                "strategy": "bm25",
            },
        )

    assert cli_result.exit_code == 0
    assert response.status_code == 200
    assert response.json()["hits"] == json.loads(cli_result.stdout)


@pytest.mark.anyio
async def test_ask_cli_and_http_have_normalized_parent_citation_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = ParityApplication()
    monkeypatch.setattr(
        cli_module,
        "build_application",
        lambda **kwargs: cast(RagApplication, application),
    )
    cli_result = CliRunner().invoke(
        cli_app,
        [
            "ask",
            "claim",
            "--limit",
            "3",
            "--strategy",
            "bm25",
            "--context-strategy",
            "adaptive",
        ],
    )
    transport = httpx.ASGITransport(app=create_http_app(_resolver(application)))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/ask",
            json={
                "schema_version": "ask-request/v1",
                "query": "claim",
                "limit": 3,
                "strategy": "bm25",
                "context_strategy": "adaptive",
            },
        )

    assert cli_result.exit_code == 0
    assert response.status_code == 200
    normalized_http = response.json()
    normalized_http.pop("schema_version")
    assert normalized_http == json.loads(cli_result.stdout)
    assert normalized_http["citations"] == [normalized_http["evidence"][0]["doc_id"]]
