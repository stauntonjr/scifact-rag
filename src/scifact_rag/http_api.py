from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated, Any, Literal, Protocol, Self

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .application import RagApplication
from .composition import build_application
from .domain import Answer, SearchHit
from .generation import GenerationContextStrategyName
from .strategies import DEFAULT_RETRIEVAL_STRATEGY, RetrievalStrategyName
from .web import create_web_router

_LOGGER = logging.getLogger(__name__)


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
    limit: Annotated[int, Field(strict=True, ge=1, le=100)] = 5
    strategy: RetrievalStrategyName = DEFAULT_RETRIEVAL_STRATEGY


class AskRequest(QueryRequest):
    schema_version: Literal["ask-request/v1"]
    limit: Annotated[int, Field(strict=True, ge=1, le=20)] = 5
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


class ErrorDetail(StrictTransportModel):
    location: tuple[str | int, ...]
    message: str
    type: str


class ErrorBody(StrictTransportModel):
    code: Literal["validation_error", "internal_error"]
    message: str
    details: tuple[ErrorDetail, ...] | None = None


class ErrorResponse(StrictTransportModel):
    schema_version: Literal["error/v1"] = "error/v1"
    error: ErrorBody


_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Request validation failed"},
    500: {"model": ErrorResponse, "description": "Request processing failed"},
}


def _error_json(response: ErrorResponse) -> dict[str, object]:
    return response.model_dump(mode="json", exclude_none=True)


def create_http_app(resolver: ApplicationResolver) -> FastAPI:
    app = FastAPI(title="SciFact RAG API", version="1.0.0")
    app.include_router(create_web_router())

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request,
        exception: RequestValidationError,
    ) -> JSONResponse:
        details = tuple(
            ErrorDetail(
                location=tuple(error["loc"]),
                message=str(error["msg"]),
                type=str(error["type"]),
            )
            for error in exception.errors()
        )
        return JSONResponse(
            status_code=422,
            content=_error_json(
                ErrorResponse(
                    error=ErrorBody(
                        code="validation_error",
                        message="Request validation failed",
                        details=details,
                    )
                )
            ),
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exception: Exception) -> JSONResponse:
        _LOGGER.exception(
            "Unhandled HTTP request failure",
            exc_info=exception,
            extra={"request_path": request.url.path},
        )
        return JSONResponse(
            status_code=500,
            content=_error_json(
                ErrorResponse(
                    error=ErrorBody(
                        code="internal_error",
                        message="The request could not be completed",
                    )
                )
            ),
        )

    @app.get(
        "/healthz",
        response_model=HealthResponse,
        responses={500: _ERROR_RESPONSES[500]},
    )
    def health() -> HealthResponse:
        return HealthResponse()

    @app.post("/v1/search", response_model=SearchResponse, responses=_ERROR_RESPONSES)
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

    @app.post("/v1/ask", response_model=AnswerResponse, responses=_ERROR_RESPONSES)
    def ask(request: AskRequest) -> AnswerResponse:
        application = resolver(request.strategy, request.context_strategy)
        return AnswerResponse.from_domain(application.ask(request.query, limit=request.limit))

    return app


def build_http_app() -> FastAPI:
    cache_size = len(RetrievalStrategyName) * len(GenerationContextStrategyName)

    @lru_cache(maxsize=cache_size)
    def resolve(
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication:
        return build_application(
            retrieval_strategy=retrieval_strategy,
            generation_context_strategy=generation_context_strategy,
        )

    return create_http_app(resolve)
