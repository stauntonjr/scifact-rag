from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Literal, Protocol, Self

from mcp import MCPError
from mcp.server import ServerRequestContext
from mcp.server.context import CallNext, HandlerResult
from mcp.server.mcpserver import MCPServer
from mcp_types import INVALID_PARAMS, ToolAnnotations
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError

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


class StrictToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")


class McpSearchHit(StrictToolResult):
    doc_id: str
    title: str
    text: str
    score: Annotated[float, Field(allow_inf_nan=False)]

    @classmethod
    def from_domain(cls, hit: SearchHit) -> Self:
        return cls(doc_id=hit.doc_id, title=hit.title, text=hit.text, score=hit.score)


class McpSearchResult(StrictToolResult):
    schema_version: Literal["mcp-search-result/v1"]
    hits: tuple[McpSearchHit, ...]


class McpAnswerResult(StrictToolResult):
    schema_version: Literal["mcp-answer-result/v1"]
    query: str
    text: str
    citations: tuple[str, ...]
    model: str
    evidence: tuple[McpSearchHit, ...]

    @classmethod
    def from_domain(cls, answer: Answer) -> Self:
        return cls(
            schema_version="mcp-answer-result/v1",
            query=answer.query,
            text=answer.text,
            citations=answer.citations,
            model=answer.model,
            evidence=tuple(McpSearchHit.from_domain(hit) for hit in answer.evidence),
        )


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
    ) -> McpSearchResult:
        application = resolver(strategy, GenerationContextStrategyName.WHOLE_DOCUMENT)
        return McpSearchResult(
            schema_version="mcp-search-result/v1",
            hits=tuple(
                McpSearchHit.from_domain(hit) for hit in application.search(query, limit=limit)
            ),
        )

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
    ) -> McpAnswerResult:
        application = resolver(strategy, context_strategy)
        return McpAnswerResult.from_domain(application.ask(query, limit=limit))

    return server
