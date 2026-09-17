from __future__ import annotations

from typing import cast

import pytest
from mcp import Client, MCPError
from mcp_types import INVALID_PARAMS, TextContent
from pydantic import BaseModel, ValidationError

from scifact_rag import mcp_server as mcp_server_module
from scifact_rag.application import RagApplication
from scifact_rag.domain import Answer, SearchHit
from scifact_rag.generation import GenerationContextStrategyName
from scifact_rag.mcp_server import (
    AnswerToolArguments,
    SearchToolArguments,
    create_mcp_server,
)
from scifact_rag.strategies import RetrievalStrategyName

_REJECTED_VALUE = "REJECTED_VALUE_SENTINEL"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class RecordingApplication:
    def __init__(
        self,
        *,
        hits: list[SearchHit] | None = None,
        answer: Answer | None = None,
    ) -> None:
        self.calls: list[tuple[str, str, int]] = []
        self.hits = hits or []
        self.answer = answer or Answer("claim", "insufficient evidence", (), "qwen", ())

    def search(self, query: str, *, limit: int = 5) -> list[SearchHit]:
        self.calls.append(("search", query, limit))
        return self.hits

    def ask(self, query: str, *, limit: int = 5) -> Answer:
        self.calls.append(("ask", query, limit))
        return self.answer


def recording_resolver(
    application: RecordingApplication,
    resolutions: list[tuple[RetrievalStrategyName, GenerationContextStrategyName]],
):
    def resolve(
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication:
        resolutions.append((retrieval_strategy, generation_context_strategy))
        return cast(RagApplication, application)

    return resolve


@pytest.mark.anyio
async def test_discovery_exposes_only_two_tools_and_no_other_mcp_primitives() -> None:
    application = RecordingApplication()
    server = create_mcp_server(recording_resolver(application, []))

    async with Client(server) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        resource_templates = await client.list_resource_templates()
        prompts = await client.list_prompts()

    assert {tool.name for tool in tools.tools} == {"search_scifact", "answer_scifact"}
    assert resources.resources == []
    assert resource_templates.resource_templates == []
    assert prompts.prompts == []
    assert application.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize("tool_name", ("search_scifact", "answer_scifact"))
@pytest.mark.parametrize(
    "invalid_arguments",
    (
        {"query": "claim", "unexpected": _REJECTED_VALUE},
        {"query": "claim", "limit": _REJECTED_VALUE},
    ),
)
async def test_invalid_arguments_are_rejected_without_disclosure_or_downstream_calls(
    tool_name: str,
    invalid_arguments: dict[str, object],
) -> None:
    application = RecordingApplication()
    resolutions: list[tuple[RetrievalStrategyName, GenerationContextStrategyName]] = []
    server = create_mcp_server(recording_resolver(application, resolutions))

    async with Client(server) as client:
        with pytest.raises(MCPError) as exc_info:
            await client.call_tool(tool_name, invalid_arguments)

    assert exc_info.value.code == INVALID_PARAMS
    assert exc_info.value.message == f"Invalid arguments for tool {tool_name}"
    assert exc_info.value.data is None
    assert _REJECTED_VALUE not in str(exc_info.value)
    assert _REJECTED_VALUE not in repr(exc_info.value.error)
    assert resolutions == []
    assert application.calls == []


def test_argument_models_reject_every_bounded_contract_violation() -> None:
    invalid_cases: tuple[tuple[type[BaseModel], dict[str, object]], ...] = (
        (SearchToolArguments, {}),
        (SearchToolArguments, {"query": "   "}),
        (SearchToolArguments, {"query": "x" * 4097}),
        (SearchToolArguments, {"query": "claim", "limit": 0}),
        (SearchToolArguments, {"query": "claim", "limit": 101}),
        (SearchToolArguments, {"query": "claim", "limit": True}),
        (SearchToolArguments, {"query": "claim", "limit": "5"}),
        (SearchToolArguments, {"query": "claim", "limit": 5.0}),
        (SearchToolArguments, {"query": "claim", "strategy": "unknown"}),
        (AnswerToolArguments, {"query": "claim", "limit": 21}),
        (AnswerToolArguments, {"query": "claim", "context_strategy": "unknown"}),
    )

    for model, arguments in invalid_cases:
        with pytest.raises(ValidationError):
            model.model_validate(arguments)


@pytest.mark.anyio
async def test_search_maps_inputs_and_complete_structured_result() -> None:
    hit = SearchHit("17", "Trial", "Complete abstract.", 0.875)
    application = RecordingApplication(hits=[hit])
    resolutions: list[tuple[RetrievalStrategyName, GenerationContextStrategyName]] = []
    server = create_mcp_server(recording_resolver(application, resolutions))

    async with Client(server) as client:
        result = await client.call_tool(
            "search_scifact",
            {"query": "  claim  ", "limit": 7, "strategy": "bm25"},
        )

    assert not result.is_error
    assert result.structured_content == {
        "schema_version": "mcp-search-result/v1",
        "hits": [
            {
                "doc_id": "17",
                "title": "Trial",
                "text": "Complete abstract.",
                "score": 0.875,
            }
        ],
    }
    assert resolutions == [
        (RetrievalStrategyName.BM25, GenerationContextStrategyName.WHOLE_DOCUMENT)
    ]
    assert application.calls == [("search", "  claim  ", 7)]


@pytest.mark.anyio
async def test_answer_maps_inputs_and_complete_structured_result() -> None:
    hit = SearchHit("17", "Trial", "Complete abstract.", 0.875)
    answer = Answer("claim", "Supported [17]", ("17",), "qwen", (hit,))
    application = RecordingApplication(answer=answer)
    resolutions: list[tuple[RetrievalStrategyName, GenerationContextStrategyName]] = []
    server = create_mcp_server(recording_resolver(application, resolutions))

    async with Client(server) as client:
        result = await client.call_tool(
            "answer_scifact",
            {
                "query": "claim",
                "limit": 3,
                "strategy": "bm25",
                "context_strategy": "adaptive",
            },
        )

    assert not result.is_error
    assert result.structured_content == {
        "schema_version": "mcp-answer-result/v1",
        "query": "claim",
        "text": "Supported [17]",
        "citations": ["17"],
        "model": "qwen",
        "evidence": [
            {
                "doc_id": "17",
                "title": "Trial",
                "text": "Complete abstract.",
                "score": 0.875,
            }
        ],
    }
    assert resolutions == [(RetrievalStrategyName.BM25, GenerationContextStrategyName.ADAPTIVE)]
    assert application.calls == [("ask", "claim", 3)]


@pytest.mark.anyio
async def test_answer_preserves_exact_insufficient_evidence() -> None:
    answer = Answer("unresolved claim", "insufficient evidence", (), "qwen", ())
    application = RecordingApplication(answer=answer)
    server = create_mcp_server(recording_resolver(application, []))

    async with Client(server) as client:
        result = await client.call_tool("answer_scifact", {"query": "unresolved claim"})

    assert not result.is_error
    assert result.structured_content == {
        "schema_version": "mcp-answer-result/v1",
        "query": "unresolved claim",
        "text": "insufficient evidence",
        "citations": [],
        "model": "qwen",
        "evidence": [],
    }
    assert application.calls == [("ask", "unresolved claim", 5)]


@pytest.mark.anyio
async def test_discovery_publishes_bounded_schemas_and_read_only_annotations() -> None:
    server = create_mcp_server(recording_resolver(RecordingApplication(), []))

    async with Client(server) as client:
        discovered = {tool.name: tool for tool in (await client.list_tools()).tools}

    search = discovered["search_scifact"]
    answer = discovered["answer_scifact"]
    assert search.input_schema["required"] == ["query"]
    assert set(search.input_schema["properties"]) == {"query", "limit", "strategy"}
    assert search.input_schema["properties"]["query"] == {
        "maxLength": 4096,
        "minLength": 1,
        "title": "Query",
        "type": "string",
    }
    assert search.input_schema["properties"]["limit"] == {
        "default": 5,
        "maximum": 100,
        "minimum": 1,
        "title": "Limit",
        "type": "integer",
    }
    assert set(answer.input_schema["properties"]) == {
        "query",
        "limit",
        "strategy",
        "context_strategy",
    }
    assert answer.input_schema["properties"]["limit"]["maximum"] == 20
    assert answer.input_schema["properties"]["context_strategy"]["default"] == "whole-document"
    assert search.output_schema is not None
    assert answer.output_schema is not None
    assert set(search.output_schema["required"]) == {"schema_version", "hits"}
    assert set(answer.output_schema["required"]) == {
        "schema_version",
        "query",
        "text",
        "citations",
        "model",
        "evidence",
    }
    for tool in (search, answer):
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is False
        assert tool.annotations.idempotent_hint is None


@pytest.mark.anyio
async def test_runtime_factory_caches_applications_by_strategy_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = RecordingApplication()
    compositions: list[tuple[RetrievalStrategyName, GenerationContextStrategyName]] = []

    def fake_build_application(
        *,
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication:
        compositions.append((retrieval_strategy, generation_context_strategy))
        return cast(RagApplication, application)

    monkeypatch.setattr(
        mcp_server_module,
        "build_application",
        fake_build_application,
        raising=False,
    )
    server = mcp_server_module.build_mcp_server()

    async with Client(server) as client:
        search_arguments = {"query": "claim", "strategy": "bm25"}
        assert not (await client.call_tool("search_scifact", search_arguments)).is_error
        assert not (await client.call_tool("search_scifact", search_arguments)).is_error
        assert not (
            await client.call_tool(
                "answer_scifact",
                {
                    "query": "claim",
                    "strategy": "bm25",
                    "context_strategy": "adaptive",
                },
            )
        ).is_error

    assert compositions == [
        (RetrievalStrategyName.BM25, GenerationContextStrategyName.WHOLE_DOCUMENT),
        (RetrievalStrategyName.BM25, GenerationContextStrategyName.ADAPTIVE),
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("failure_site", ("resolver", "application"))
async def test_unexpected_failures_use_sanitized_sdk_boundary_without_retry(
    failure_site: str,
) -> None:
    secret = "SECRET_FAILURE_SENTINEL"
    attempts = 0

    class FailingApplication(RecordingApplication):
        def search(self, query: str, *, limit: int = 5) -> list[SearchHit]:
            nonlocal attempts
            attempts += 1
            raise RuntimeError(secret)

    application = FailingApplication()

    def failing_resolver(
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication:
        nonlocal attempts
        if failure_site == "resolver":
            attempts += 1
            raise RuntimeError(secret)
        return cast(RagApplication, application)

    server = create_mcp_server(failing_resolver)
    async with Client(server) as client:
        result = await client.call_tool("search_scifact", {"query": "claim"})

    assert result.is_error
    assert result.structured_content is None
    public_text = " ".join(block.text for block in result.content if isinstance(block, TextContent))
    assert public_text == "Error executing tool search_scifact"
    assert secret not in public_text
    assert "RuntimeError" not in public_text
    assert attempts == 1


def test_main_runs_exact_streamable_http_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeServer:
        def run(self, transport: str, **kwargs: object) -> None:
            calls.append((transport, kwargs))

    monkeypatch.setattr(mcp_server_module, "build_mcp_server", FakeServer)

    mcp_server_module.main()

    assert calls == [
        (
            "streamable-http",
            {
                "host": "0.0.0.0",
                "port": 80,
                "streamable_http_path": "/mcp",
                "stateless_http": True,
                "json_response": True,
            },
        )
    ]
