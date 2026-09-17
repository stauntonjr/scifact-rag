from __future__ import annotations

from typing import Literal, Protocol

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from .application import RagApplication
from .generation import GenerationContextStrategyName
from .strategies import RetrievalStrategyName


class ApplicationResolver(Protocol):
    def __call__(
        self,
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication: ...


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["health/v1"] = "health/v1"
    status: Literal["ok"] = "ok"


def create_http_app(resolver: ApplicationResolver) -> FastAPI:
    app = FastAPI(title="SciFact RAG API", version="1.0.0")

    @app.get("/healthz", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    return app
