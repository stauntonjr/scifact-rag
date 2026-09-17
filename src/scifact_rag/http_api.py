from __future__ import annotations

from typing import Annotated, Literal, Protocol, Self

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .application import RagApplication
from .domain import Answer, SearchHit
from .generation import GenerationContextStrategyName
from .strategies import DEFAULT_RETRIEVAL_STRATEGY, RetrievalStrategyName


class ApplicationResolver(Protocol):
    def __call__(
        self,
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication: ...


class StrictTransportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictTransportModel):
    schema_version: Literal["health/v1"] = "health/v1"
    status: Literal["ok"] = "ok"


class QueryRequest(StrictTransportModel):
    query: Annotated[str, Field(min_length=1, max_length=4096)]

    @field_validator("query")
    @classmethod
    def require_non_whitespace_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value


class SearchRequest(QueryRequest):
    schema_version: Literal["search-request/v1"]
    limit: Annotated[int, Field(ge=1, le=100)] = 5
    strategy: RetrievalStrategyName = DEFAULT_RETRIEVAL_STRATEGY


class AskRequest(QueryRequest):
    schema_version: Literal["ask-request/v1"]
    limit: Annotated[int, Field(ge=1, le=20)] = 5
    strategy: RetrievalStrategyName = DEFAULT_RETRIEVAL_STRATEGY
    context_strategy: GenerationContextStrategyName = GenerationContextStrategyName.WHOLE_DOCUMENT


class SearchHitResponse(StrictTransportModel):
    doc_id: str
    title: str
    text: str
    score: Annotated[float, Field(allow_inf_nan=False)]

    @classmethod
    def from_domain(cls, hit: SearchHit) -> Self:
        return cls(doc_id=hit.doc_id, title=hit.title, text=hit.text, score=hit.score)


class SearchResponse(StrictTransportModel):
    schema_version: Literal["search-response/v1"] = "search-response/v1"
    hits: tuple[SearchHitResponse, ...]


class AnswerResponse(StrictTransportModel):
    schema_version: Literal["answer/v1"] = "answer/v1"
    query: str
    text: str
    citations: tuple[str, ...]
    model: str
    evidence: tuple[SearchHitResponse, ...]

    @classmethod
    def from_domain(cls, answer: Answer) -> Self:
        return cls(
            query=answer.query,
            text=answer.text,
            citations=answer.citations,
            model=answer.model,
            evidence=tuple(SearchHitResponse.from_domain(hit) for hit in answer.evidence),
        )


def create_http_app(resolver: ApplicationResolver) -> FastAPI:
    app = FastAPI(title="SciFact RAG API", version="1.0.0")

    @app.get("/healthz", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @app.post("/v1/search", response_model=SearchResponse)
    def search(request: SearchRequest) -> SearchResponse:
        application = resolver(
            request.strategy,
            GenerationContextStrategyName.WHOLE_DOCUMENT,
        )
        return SearchResponse(
            hits=tuple(
                SearchHitResponse.from_domain(hit)
                for hit in application.search(request.query, limit=request.limit)
            )
        )

    @app.post("/v1/ask", response_model=AnswerResponse)
    def ask(request: AskRequest) -> AnswerResponse:
        application = resolver(request.strategy, request.context_strategy)
        return AnswerResponse.from_domain(application.ask(request.query, limit=request.limit))

    return app
