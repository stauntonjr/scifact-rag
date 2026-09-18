from __future__ import annotations

import json
import re

import httpx
import pytest

from scifact_rag.application import RagApplication
from scifact_rag.generation import GenerationContextStrategyName
from scifact_rag.http_api import create_http_app
from scifact_rag.strategies import DEFAULT_RETRIEVAL_STRATEGY, RetrievalStrategyName


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def fail_if_resolved(
    retrieval_strategy: RetrievalStrategyName,
    generation_context_strategy: GenerationContextStrategyName,
) -> RagApplication:
    raise AssertionError("web resources must not resolve the application")


@pytest.mark.anyio
async def test_web_resources_are_served_without_application_resolution() -> None:
    transport = httpx.ASGITransport(app=create_http_app(fail_if_resolved))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        index = await client.get("/")
        stylesheet = await client.get("/assets/scifact.css")
        script = await client.get("/assets/scifact.js")

    assert index.status_code == 200
    assert index.headers["content-type"].startswith("text/html")
    assert index.headers["cache-control"] == "no-store"
    for marker in (
        "<main",
        'id="claim-form"',
        'id="claim-input"',
        'maxlength="4096"',
        'id="strategy-select"',
        'id="context-strategy-select"',
        'id="result-limit"',
        'id="search-button"',
        'id="answer-button"',
        'id="request-status"',
        'id="capability-status"',
        'id="showcase-link"',
        'aria-live="polite"',
        'id="result-summary"',
        'id="evidence-list"',
    ):
        assert marker in index.text
    assert "https://" not in index.text
    assert "http://" not in index.text

    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert stylesheet.headers["cache-control"] == "no-store"
    assert stylesheet.text.strip()
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert script.headers["cache-control"] == "no-store"
    assert script.text.strip()


@pytest.mark.anyio
async def test_web_configuration_matches_existing_strategy_contracts() -> None:
    transport = httpx.ASGITransport(app=create_http_app(fail_if_resolved))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        html = (await client.get("/")).text

    match = re.search(
        r'<script id="scifact-config" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    config = json.loads(match.group(1))
    assert config == {
        "retrieval_strategies": [strategy.value for strategy in RetrievalStrategyName],
        "default_retrieval_strategy": DEFAULT_RETRIEVAL_STRATEGY.value,
        "context_strategies": [strategy.value for strategy in GenerationContextStrategyName],
        "default_context_strategy": GenerationContextStrategyName.WHOLE_DOCUMENT.value,
        "public_demo_enabled": False,
    }


def test_web_script_contains_public_failure_and_capability_boundaries() -> None:
    transport = httpx.ASGITransport(app=create_http_app(fail_if_resolved))

    async def read_script() -> str:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return (await client.get("/assets/scifact.js")).text

    import asyncio

    script = asyncio.run(read_script())
    for marker in (
        'fetch("/v1/capabilities"',
        'payload.schema_version !== "capabilities/v1"',
        "option.disabled = !available",
        "effective_default",
        'error.code === "busy"',
        "status === 429",
        "status === 503",
        "status === 502",
        "status === 504",
        "textContent",
    ):
        assert marker in script
    assert "innerHTML" not in script
