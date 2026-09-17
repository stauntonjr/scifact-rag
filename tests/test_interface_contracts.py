from __future__ import annotations

import json
import re
from pathlib import Path
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

_ROOT = Path(__file__).resolve().parents[1]


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


def test_compose_exposes_only_the_loopback_api_factory() -> None:
    compose = (_ROOT / "compose.yaml").read_text(encoding="utf-8")
    match = re.search(
        r"^  api:\n(?P<body>.*?)(?=^  [a-z][a-z-]*:\n|^volumes:\n)",
        compose,
        re.MULTILINE | re.DOTALL,
    )

    assert match is not None
    service = match.group("body")
    assert 'entrypoint: ["uv", "run", "--no-dev", "uvicorn"]' in service
    assert "scifact_rag.http_api:build_http_app" in service
    assert "- --factory" in service
    assert '- "127.0.0.1:8090:80"' in service
    assert "postgres:" in service
    assert "condition: service_healthy" in service


def test_http_capability_is_active_with_exact_delivery_contract() -> None:
    catalog = json.loads((_ROOT / "harness/capabilities.json").read_text(encoding="utf-8"))
    capability = next(
        item for item in catalog["capabilities"] if item["id"] == "http-api-interface"
    )

    assert capability["status"] == "active"
    contract = capability["active_contract"]
    assert contract["runtime_dependencies"] == ["FastAPI", "Uvicorn"]
    assert (
        "uv run pytest tests/test_http_api.py tests/test_interface_contracts.py"
        in contract["ci_checks"]
    )
    assert set(contract["implementation_paths"]) == {
        "src/scifact_rag/http_api.py",
        "tests/test_http_api.py",
        "tests/test_interface_contracts.py",
        "compose.yaml",
        "docs/research/scifact-rag-http-api.md",
        "docs/adr/0032-http-api-adapter.md",
        "docs/superpowers/specs/2026-09-17-http-api-adapter-design.md",
    }
