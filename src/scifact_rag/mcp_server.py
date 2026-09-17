from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Protocol

from mcp import MCPError
from mcp.server import ServerRequestContext
from mcp.server.context import CallNext, HandlerResult
from mcp.server.mcpserver import MCPServer
from mcp_types import INVALID_PARAMS, ToolAnnotations
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError

from .application import RagApplication
from .generation import GenerationContextStrategyName
from .strategies import DEFAULT_RETRIEVAL_STRATEGY, RetrievalStrategyName


class ApplicationResolver(Protocol):
    def __call__(
        self,
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication: ...


def _require_non_whitespace_query(value: str) -> str:
    if not value.strip():
        raise ValueError("query must not be blank")
    return value


QueryText = Annotated[
    str,
    Field(min_length=1, max_length=4096),
    AfterValidator(_require_non_whitespace_query),
]
SearchLimit = Annotated[int, Field(strict=True, ge=1, le=100)]
AnswerLimit = Annotated[int, Field(strict=True, ge=1, le=20)]


class StrictToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class SearchToolArguments(StrictToolArguments):
    query: QueryText
    limit: SearchLimit = 5
    strategy: RetrievalStrategyName = DEFAULT_RETRIEVAL_STRATEGY


class AnswerToolArguments(StrictToolArguments):
    query: QueryText
    limit: AnswerLimit = 5
    strategy: RetrievalStrategyName = DEFAULT_RETRIEVAL_STRATEGY
    context_strategy: GenerationContextStrategyName = GenerationContextStrategyName.WHOLE_DOCUMENT


_ARGUMENT_MODELS: dict[str, type[StrictToolArguments]] = {
    "search_scifact": SearchToolArguments,
    "answer_scifact": AnswerToolArguments,
}


async def enforce_tool_arguments(
    ctx: ServerRequestContext[Any, Any],
    call_next: CallNext,
) -> HandlerResult:
    if ctx.method != "tools/call":
        return await call_next(ctx)

    params = ctx.params
    if not isinstance(params, Mapping):
        return await call_next(ctx)
    tool_name = params.get("name")
    model = _ARGUMENT_MODELS.get(tool_name) if isinstance(tool_name, str) else None
    if model is None:
        return await call_next(ctx)
    arguments = params.get("arguments") or {}
    try:
        model.model_validate(arguments)
    except ValidationError:
        raise MCPError(
            code=INVALID_PARAMS,
            message=f"Invalid arguments for tool {tool_name}",
        ) from None
    return await call_next(ctx)


def create_mcp_server(resolver: ApplicationResolver) -> MCPServer:
    server = MCPServer(
        "SciFact RAG",
        version="0.1.0",
        instructions=(
            "Search the public SciFact corpus and answer only from retrieved evidence. "
            "An answer may report exact insufficient evidence."
        ),
        middleware=[enforce_tool_arguments],
    )
    read_only_closed_corpus = ToolAnnotations(read_only_hint=True, open_world_hint=False)

    @server.tool(
        name="search_scifact",
        description="Retrieve ranked parent documents from the public SciFact corpus.",
        annotations=read_only_closed_corpus,
        structured_output=True,
    )
    def search_scifact(
        query: QueryText,
        limit: SearchLimit = 5,
        strategy: RetrievalStrategyName = DEFAULT_RETRIEVAL_STRATEGY,
    ) -> dict[str, object]:
        raise NotImplementedError("search result mapping is implemented in the next plan task")

    @server.tool(
        name="answer_scifact",
        description=(
            "Retrieve evidence and invoke configured model inference to answer from the public "
            "SciFact corpus; this read-only call may consume significant compute."
        ),
        annotations=read_only_closed_corpus,
        structured_output=True,
    )
    def answer_scifact(
        query: QueryText,
        limit: AnswerLimit = 5,
        strategy: RetrievalStrategyName = DEFAULT_RETRIEVAL_STRATEGY,
        context_strategy: GenerationContextStrategyName = (
            GenerationContextStrategyName.WHOLE_DOCUMENT
        ),
    ) -> dict[str, object]:
        raise NotImplementedError("answer result mapping is implemented in the next plan task")

    return server
