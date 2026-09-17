from __future__ import annotations

from typing import cast

import pytest
from mcp import Client, MCPError
from mcp_types import INVALID_PARAMS

from scifact_rag.application import RagApplication
from scifact_rag.domain import Answer, SearchHit
from scifact_rag.generation import GenerationContextStrategyName
from scifact_rag.mcp_server import create_mcp_server
from scifact_rag.strategies import RetrievalStrategyName

_REJECTED_VALUE = "REJECTED_VALUE_SENTINEL"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class RecordingApplication:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def search(self, query: str, *, limit: int = 5) -> list[SearchHit]:
        self.calls.append(("search", query, limit))
        return []

    def ask(self, query: str, *, limit: int = 5) -> Answer:
        self.calls.append(("ask", query, limit))
        return Answer(query, "insufficient evidence", (), "qwen", ())


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
