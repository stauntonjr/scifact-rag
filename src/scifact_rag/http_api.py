from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated, Any, Literal, Protocol, Self

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import create_engine

from .adapters.health import HttpHealthProbe, PostgresHealthProbe
from .application import RagApplication
from .composition import Settings, build_application
from .domain import Answer, SearchHit
from .generation import GenerationContextStrategyName
from .public_demo import (
    CapabilitySnapshot,
    DependencyName,
    InferenceGate,
    PublicDemoCapabilityService,
    PublicDemoRuntime,
    PublicDemoSettings,
    StrategyCapability,
)
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


class ReadinessResponse(StrictTransportModel):
    schema_version: Literal["readiness/v1"] = "readiness/v1"
    status: Literal["ready", "unavailable"]


class OperationCapabilityResponse(StrictTransportModel):
    available: bool
    reason: str | None = None


class StrategyCapabilityResponse(StrictTransportModel):
    name: str
    available: bool
    reason: str | None = None


class CapabilityGroupResponse(StrictTransportModel):
    configured_default: str
    effective_default: str | None
    strategies: tuple[StrategyCapabilityResponse, ...]


class CapabilitiesResponse(StrictTransportModel):
    schema_version: Literal["capabilities/v1"] = "capabilities/v1"
    status: Literal["ready", "degraded", "unavailable"]
    search: OperationCapabilityResponse
    answer: OperationCapabilityResponse
    retrieval: CapabilityGroupResponse
    context: CapabilityGroupResponse


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
    code: Literal["validation_error", "busy", "unavailable", "internal_error"]
    message: str
    details: tuple[ErrorDetail, ...] | None = None


class ErrorResponse(StrictTransportModel):
    schema_version: Literal["error/v1"] = "error/v1"
    error: ErrorBody


_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Request validation failed"},
    429: {"model": ErrorResponse, "description": "Another live request is in progress"},
    503: {"model": ErrorResponse, "description": "Selected capability is unavailable"},
    500: {"model": ErrorResponse, "description": "Request processing failed"},
}


def _error_json(response: ErrorResponse) -> dict[str, object]:
    return response.model_dump(mode="json", exclude_none=True)


def _capabilities_response(snapshot: CapabilitySnapshot) -> CapabilitiesResponse:
    return CapabilitiesResponse(
        status=snapshot.status,
        search=OperationCapabilityResponse(
            available=snapshot.search.available,
            reason=snapshot.search.reason.value if snapshot.search.reason else None,
        ),
        answer=OperationCapabilityResponse(
            available=snapshot.answer.available,
            reason=snapshot.answer.reason.value if snapshot.answer.reason else None,
        ),
        retrieval=CapabilityGroupResponse(
            configured_default=DEFAULT_RETRIEVAL_STRATEGY.value,
            effective_default=(
                snapshot.effective_retrieval_default.value
                if snapshot.effective_retrieval_default
                else None
            ),
            strategies=tuple(_strategy_response(item) for item in snapshot.retrieval),
        ),
        context=CapabilityGroupResponse(
            configured_default=GenerationContextStrategyName.WHOLE_DOCUMENT.value,
            effective_default=(
                snapshot.effective_context_default.value
                if snapshot.effective_context_default
                else None
            ),
            strategies=tuple(_strategy_response(item) for item in snapshot.context),
        ),
    )


def _strategy_response(item: StrategyCapability) -> StrategyCapabilityResponse:
    return StrategyCapabilityResponse(
        name=item.name,
        available=item.available,
        reason=item.reason.value if item.reason else None,
    )


def _fixed_error(code: Literal["busy", "unavailable"], message: str) -> JSONResponse:
    return JSONResponse(
        status_code=429 if code == "busy" else 503,
        content=_error_json(ErrorResponse(error=ErrorBody(code=code, message=message))),
    )


def _selected_capability(
    snapshot: CapabilitySnapshot,
    strategy: RetrievalStrategyName,
) -> StrategyCapabilityResponse | None:
    item = next((item for item in snapshot.retrieval if item.name == strategy.value), None)
    return _strategy_response(item) if item else None


def _selected_context_capability(
    snapshot: CapabilitySnapshot,
    strategy: GenerationContextStrategyName,
) -> StrategyCapabilityResponse | None:
    item = next((item for item in snapshot.context if item.name == strategy.value), None)
    return _strategy_response(item) if item else None


def create_http_app(
    resolver: ApplicationResolver,
    *,
    public_demo: PublicDemoRuntime | None = None,
) -> FastAPI:
    app = FastAPI(title="SciFact RAG API", version="1.0.0")
    runtime = public_demo if public_demo and public_demo.settings.enabled else None
    app.include_router(create_web_router(public_demo_enabled=runtime is not None))

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
        _LOGGER.error(
            "Unhandled HTTP request failure",
            extra={
                "request_path": request.url.path,
                "exception_type": type(exception).__name__,
            },
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

    if runtime is not None:

        def readiness_headers(request: Request) -> dict[str, str]:
            headers = {"Vary": "Origin"}
            pages_origin = runtime.settings.pages_origin
            if pages_origin is not None and request.headers.get("origin") == pages_origin:
                headers["Access-Control-Allow-Origin"] = pages_origin
            return headers

        @app.get(
            "/readyz",
            response_model=ReadinessResponse,
            responses={503: {"model": ReadinessResponse}},
        )
        def ready(request: Request) -> JSONResponse:
            snapshot = runtime.capabilities.snapshot()
            response = ReadinessResponse(
                status="ready"
                if snapshot.search.available and snapshot.answer.available
                else "unavailable"
            )
            return JSONResponse(
                status_code=200 if response.status == "ready" else 503,
                content=response.model_dump(mode="json"),
                headers=readiness_headers(request),
            )

        @app.get("/v1/capabilities", response_model=CapabilitiesResponse)
        def capabilities() -> CapabilitiesResponse:
            return _capabilities_response(runtime.capabilities.snapshot())

    @app.post("/v1/search", response_model=SearchResponse, responses=_ERROR_RESPONSES)
    def search(request: SearchRequest) -> SearchResponse | JSONResponse:
        if runtime is not None:
            with runtime.gate.acquire() as acquired:
                if not acquired:
                    return _fixed_error("busy", "Another live request is in progress")
                snapshot = runtime.capabilities.snapshot()
                selected = _selected_capability(snapshot, request.strategy)
                if selected is None or not selected.available:
                    return _fixed_error(
                        "unavailable", "The selected live capability is unavailable"
                    )
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
    def ask(request: AskRequest) -> AnswerResponse | JSONResponse:
        if runtime is not None:
            with runtime.gate.acquire() as acquired:
                if not acquired:
                    return _fixed_error("busy", "Another live request is in progress")
                snapshot = runtime.capabilities.snapshot()
                selected = _selected_capability(snapshot, request.strategy)
                selected_context = _selected_context_capability(snapshot, request.context_strategy)
                if (
                    selected is None
                    or not selected.available
                    or selected_context is None
                    or not selected_context.available
                    or not snapshot.answer.available
                ):
                    return _fixed_error(
                        "unavailable", "The selected live capability is unavailable"
                    )
                application = resolver(request.strategy, request.context_strategy)
                return AnswerResponse.from_domain(
                    application.ask(request.query, limit=request.limit)
                )
        application = resolver(request.strategy, request.context_strategy)
        return AnswerResponse.from_domain(application.ask(request.query, limit=request.limit))

    return app


def build_http_app() -> FastAPI:
    settings = Settings.from_environment()
    public_settings = PublicDemoSettings.from_environment()
    runtime: PublicDemoRuntime | None = None
    if public_settings.enabled:
        engine = create_engine(settings.database_url)
        runtime = PublicDemoRuntime(
            settings=public_settings,
            capabilities=PublicDemoCapabilityService(
                {
                    DependencyName.RETRIEVAL_STORE: PostgresHealthProbe(engine),
                    DependencyName.GENERATOR: HttpHealthProbe(
                        f"{settings.generator_base_url.rstrip('/')}/models"
                    ),
                    DependencyName.RERANKER: HttpHealthProbe(
                        f"{settings.reranker_base_url.rstrip('/')}/health"
                    ),
                    DependencyName.LATE_INTERACTION: HttpHealthProbe(
                        f"{settings.late_interaction_base_url.rstrip('/')}/health"
                    ),
                    DependencyName.RANKLLM: HttpHealthProbe(
                        f"{settings.rank_llm_base_url.rstrip('/')}/healthz"
                    ),
                }
            ),
            gate=InferenceGate(),
        )
    cache_size = len(RetrievalStrategyName) * len(GenerationContextStrategyName)

    @lru_cache(maxsize=cache_size)
    def resolve(
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication:
        if runtime is None:
            return build_application(
                retrieval_strategy=retrieval_strategy,
                generation_context_strategy=generation_context_strategy,
            )
        return build_application(
            settings=settings,
            retrieval_strategy=retrieval_strategy,
            generation_context_strategy=generation_context_strategy,
        )

    return create_http_app(resolve, public_demo=runtime)
