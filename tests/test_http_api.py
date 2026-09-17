from __future__ import annotations

import httpx
import pytest

from scifact_rag.application import RagApplication
from scifact_rag.generation import GenerationContextStrategyName
from scifact_rag.http_api import create_http_app
from scifact_rag.strategies import RetrievalStrategyName


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
