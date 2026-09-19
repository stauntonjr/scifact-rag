from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import cast

import httpx
import pytest
from mcp import Client
from typer.testing import CliRunner

from scifact_rag import cli as cli_module
from scifact_rag.application import RagApplication
from scifact_rag.cli import app as cli_app
from scifact_rag.domain import Answer, SearchHit
from scifact_rag.generation import GenerationContextStrategyName
from scifact_rag.http_api import create_http_app
from scifact_rag.mcp_server import create_mcp_server
from scifact_rag.strategies import RetrievalStrategyName

_ROOT = Path(__file__).resolve().parents[1]
_ADR_HEADING = re.compile(r"^# ADR-(?P<number>\d{4}):", re.MULTILINE)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_adr_identifiers_are_unique_and_match_filenames() -> None:
    identifiers: dict[str, list[str]] = {}
    mismatches: list[str] = []

    for path in sorted((_ROOT / "docs/adr").glob("[0-9][0-9][0-9][0-9]-*.md")):
        filename_number = path.name[:4]
        heading = _ADR_HEADING.search(path.read_text(encoding="utf-8"))
        assert heading is not None, f"{path.name}: missing ADR heading"
        heading_number = heading.group("number")
        identifiers.setdefault(heading_number, []).append(path.name)
        if filename_number != heading_number:
            mismatches.append(
                f"{path.name}: filename {filename_number} != heading {heading_number}"
            )

    duplicates = {
        number: paths for number, paths in identifiers.items() if len(paths) != 1
    }
    assert duplicates == {}
    assert mismatches == []

    exact_governing_links = {
        "0035-public-live-demo-edge.md": (
            "- Governing issue: [#27]"
            "(https://github.com/stauntonjr/scifact-rag/issues/27)"
        ),
        "0036-generation-fidelity-evaluation.md": (
            "- Governing issue: [#26]"
            "(https://github.com/stauntonjr/scifact-rag/issues/26)"
        ),
    }
    for filename, expected_link in exact_governing_links.items():
        text = (_ROOT / "docs/adr" / filename).read_text(encoding="utf-8")
        assert expected_link in text


class ParityApplication:
    def __init__(self) -> None:
        self.hit = SearchHit("17", "Trial", "Complete abstract.", 0.875)

    def search(self, query: str, *, limit: int = 5) -> list[SearchHit]:
        return [self.hit]

    def ask(self, query: str, *, limit: int = 5) -> Answer:
        return Answer(query, "Supported [17]", ("17",), "qwen", (self.hit,))


def _resolver(application: ParityApplication):
    def resolve(
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication:
        return cast(RagApplication, application)

    return resolve


def test_openapi_exposes_only_the_three_product_paths_and_versioned_models() -> None:
    application = create_http_app(_resolver(ParityApplication()))

    schema = application.openapi()

    assert set(schema["paths"]) == {"/healthz", "/v1/search", "/v1/ask"}
    components = set(schema["components"]["schemas"])
    assert {
        "HealthResponse",
        "SearchRequest",
        "SearchResponse",
        "AskRequest",
        "AnswerResponse",
        "SearchHitResponse",
        "ErrorResponse",
    } <= components


@pytest.mark.anyio
async def test_search_cli_and_http_have_normalized_result_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = ParityApplication()
    monkeypatch.setattr(
        cli_module,
        "build_application",
        lambda **kwargs: cast(RagApplication, application),
    )
    cli_result = CliRunner().invoke(
        cli_app,
        ["search", "claim", "--limit", "3", "--strategy", "bm25"],
    )
    transport = httpx.ASGITransport(app=create_http_app(_resolver(application)))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/search",
            json={
                "schema_version": "search-request/v1",
                "query": "claim",
                "limit": 3,
                "strategy": "bm25",
            },
        )

    assert cli_result.exit_code == 0
    assert response.status_code == 200
    assert response.json()["hits"] == json.loads(cli_result.stdout)


@pytest.mark.anyio
async def test_ask_cli_and_http_have_normalized_parent_citation_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = ParityApplication()
    monkeypatch.setattr(
        cli_module,
        "build_application",
        lambda **kwargs: cast(RagApplication, application),
    )
    cli_result = CliRunner().invoke(
        cli_app,
        [
            "ask",
            "claim",
            "--limit",
            "3",
            "--strategy",
            "bm25",
            "--context-strategy",
            "adaptive",
        ],
    )
    transport = httpx.ASGITransport(app=create_http_app(_resolver(application)))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/ask",
            json={
                "schema_version": "ask-request/v1",
                "query": "claim",
                "limit": 3,
                "strategy": "bm25",
                "context_strategy": "adaptive",
            },
        )

    assert cli_result.exit_code == 0
    assert response.status_code == 200
    normalized_http = response.json()
    normalized_http.pop("schema_version")
    assert normalized_http == json.loads(cli_result.stdout)
    assert normalized_http["citations"] == [normalized_http["evidence"][0]["doc_id"]]


@pytest.mark.anyio
async def test_search_cli_and_mcp_have_normalized_result_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = ParityApplication()
    monkeypatch.setattr(
        cli_module,
        "build_application",
        lambda **kwargs: cast(RagApplication, application),
    )
    cli_result = CliRunner().invoke(
        cli_app,
        ["search", "claim", "--limit", "3", "--strategy", "bm25"],
    )

    async with Client(create_mcp_server(_resolver(application))) as client:
        mcp_result = await client.call_tool(
            "search_scifact",
            {"query": "claim", "limit": 3, "strategy": "bm25"},
        )

    assert cli_result.exit_code == 0
    assert not mcp_result.is_error
    assert mcp_result.structured_content is not None
    assert mcp_result.structured_content["schema_version"] == "mcp-search-result/v1"
    assert mcp_result.structured_content["hits"] == json.loads(cli_result.stdout)


@pytest.mark.anyio
async def test_ask_cli_and_mcp_have_normalized_parent_citation_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = ParityApplication()
    monkeypatch.setattr(
        cli_module,
        "build_application",
        lambda **kwargs: cast(RagApplication, application),
    )
    cli_result = CliRunner().invoke(
        cli_app,
        [
            "ask",
            "claim",
            "--limit",
            "3",
            "--strategy",
            "bm25",
            "--context-strategy",
            "adaptive",
        ],
    )

    async with Client(create_mcp_server(_resolver(application))) as client:
        mcp_result = await client.call_tool(
            "answer_scifact",
            {
                "query": "claim",
                "limit": 3,
                "strategy": "bm25",
                "context_strategy": "adaptive",
            },
        )

    assert cli_result.exit_code == 0
    assert not mcp_result.is_error
    assert mcp_result.structured_content is not None
    normalized_mcp = dict(mcp_result.structured_content)
    assert normalized_mcp.pop("schema_version") == "mcp-answer-result/v1"
    assert normalized_mcp == json.loads(cli_result.stdout)
    assert normalized_mcp["citations"] == [normalized_mcp["evidence"][0]["doc_id"]]


def test_compose_exposes_only_the_loopback_api_factory() -> None:
    compose = (_ROOT / "compose.yaml").read_text(encoding="utf-8")
    match = re.search(
        r"^  api:\n(?P<body>.*?)(?=^  [a-z][a-z-]*:\n|^volumes:\n)",
        compose,
        re.MULTILINE | re.DOTALL,
    )

    assert match is not None
    service = match.group("body")
    assert 'entrypoint: ["uv", "run", "--no-dev", "uvicorn"]' in service
    assert "scifact_rag.http_api:build_http_app" in service
    assert "- --factory" in service
    assert "- --host\n      - 0.0.0.0" in service
    assert '- --workers\n      - "1"' in service
    assert '- "127.0.0.1:8090:80"' in service
    assert "postgres:" in service
    assert "condition: service_healthy" in service


def test_public_demo_is_opt_in_on_the_single_worker_api_only() -> None:
    completed = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    compose = json.loads(completed.stdout)
    api_environment = compose["services"]["api"]["environment"]

    assert api_environment["SCIFACT_PUBLIC_DEMO_ENABLED"] == "false"
    assert api_environment["SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN"] == "https://stauntonjr.github.io"
    assert "SCIFACT_PUBLIC_DEMO_ENABLED" not in compose["services"]["app"]["environment"]
    assert "SCIFACT_PUBLIC_DEMO_ENABLED" not in compose["services"]["mcp"]["environment"]
    assert compose["services"]["api"]["command"][-1] == "1"


def test_http_capability_is_active_with_exact_delivery_contract() -> None:
    catalog = json.loads((_ROOT / "harness/capabilities.json").read_text(encoding="utf-8"))
    capability = next(
        item for item in catalog["capabilities"] if item["id"] == "http-api-interface"
    )

    assert capability["status"] == "active"
    contract = capability["active_contract"]
    assert contract["runtime_dependencies"] == ["FastAPI", "Uvicorn"]
    assert (
        "uv run pytest tests/test_public_demo.py tests/test_health_adapters.py "
        "tests/test_http_api.py tests/test_interface_contracts.py"
        in contract["ci_checks"]
    )
    assert set(contract["implementation_paths"]) == {
        "src/scifact_rag/http_api.py",
        "src/scifact_rag/public_demo.py",
        "src/scifact_rag/adapters/health.py",
        "tests/test_public_demo.py",
        "tests/test_health_adapters.py",
        "tests/test_http_api.py",
        "tests/test_interface_contracts.py",
        "compose.yaml",
        "docs/research/scifact-rag-http-api.md",
        "docs/adr/0032-http-api-adapter.md",
        "docs/adr/0035-public-live-demo-edge.md",
        "docs/superpowers/specs/2026-09-17-http-api-adapter-design.md",
        "docs/superpowers/specs/2026-09-18-public-live-demo-design.md",
    }


def test_web_capability_is_active_with_exact_delivery_contract() -> None:
    catalog = json.loads((_ROOT / "harness/capabilities.json").read_text(encoding="utf-8"))
    capability = next(
        item for item in catalog["capabilities"] if item["id"] == "web-interface"
    )

    assert capability["status"] == "active"
    contract = capability["active_contract"]
    assert contract["runtime_dependencies"] == [
        "FastAPI",
        "native browser HTML/CSS/JavaScript",
    ]
    assert (
        "uv run pytest tests/test_web_ui.py tests/test_http_api.py "
        "tests/test_showcase.py tests/test_interface_contracts.py"
        in contract["ci_checks"]
    )
    assert set(contract["implementation_paths"]) == {
        "src/scifact_rag/web/__init__.py",
        "src/scifact_rag/web/index.html",
        "src/scifact_rag/web/scifact.css",
        "src/scifact_rag/web/scifact.js",
        "src/scifact_rag/http_api.py",
        "src/scifact_rag/public_demo.py",
        "tests/test_web_ui.py",
        "tests/test_http_api.py",
        "tests/test_showcase.py",
        "tests/test_interface_contracts.py",
        "docs/showcase/scifact-ui/",
        "docs/adr/0034-web-ui.md",
        "docs/adr/0035-public-live-demo-edge.md",
        "docs/superpowers/specs/2026-09-17-web-ui-design.md",
        "docs/superpowers/specs/2026-09-18-public-live-demo-design.md",
    }


def test_project_contract_bounds_the_public_demo() -> None:
    project = json.loads((_ROOT / "harness/project.yaml").read_text(encoding="utf-8"))

    assert "opt-in anonymous best-effort public live demo" in project["project"]["summary"]
    assert (
        "An opt-in anonymous best-effort public live demo with readiness, capability discovery, "
        "fixed public-demo errors, and a recorded GitHub Pages fallback"
        in project["intent"]["in_scope"]
    )
    assert {
        "Production deployment or multi-node operation",
        "A supported third-party public API or uptime objective",
        "Automated DGX or model-service lifecycle management",
    } <= set(project["intent"]["out_of_scope"])
    assert "application publication retained on host loopback" in project["constraints"][
        "deployment"
    ]
    assert "single-worker API" in project["constraints"]["deployment"]
    assert {
        "Opt-in public-demo readiness, capability-discovery, and fixed busy/unavailable error schemas",
        "SCIFACT_PUBLIC_DEMO_ENABLED and SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN environment-variable contract",
        "GitHub Pages one-shot live-status and recorded-fallback behavior",
    } <= set(project["engineering"]["versioning"]["public_contract"])


def test_public_demo_acceptance_ledger_has_twelve_pending_owned_rows() -> None:
    report = (_ROOT / "docs/reports/issue-27-public-live-demo.md").read_text(encoding="utf-8")
    rows = [line for line in report.splitlines() if line.startswith("| M")]

    assert len(rows) == 12
    assert all("| pending |" in row for row in rows)
    assert all(
        any(f"| {owner} |" in row for owner in ("scifact-rag", "vps-srv", "shared"))
        for row in rows
    )
    assert {"deterministic", "live non-inference", "live inference"} == {
        evidence_class
        for row in rows
        for evidence_class in ("deterministic", "live non-inference", "live inference")
        if f"| {evidence_class} |" in row
    }
    assert "Release-impact recommendation: `minor`" in report
    assert "## Rollback boundary" in report


def test_compose_exposes_only_the_loopback_mcp_module() -> None:
    completed = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    compose = json.loads(completed.stdout)
    service = compose["services"]["mcp"]

    assert service["entrypoint"] == ["uv", "run", "--no-dev", "python"]
    assert service["command"] == ["-m", "scifact_rag.mcp_server"]
    assert service["ports"] == [
        {
            "mode": "ingress",
            "host_ip": "127.0.0.1",
            "target": 80,
            "published": "8091",
            "protocol": "tcp",
        }
    ]
    assert service["depends_on"]["postgres"]["condition"] == "service_healthy"
    api_environment = dict(compose["services"]["api"]["environment"])
    api_environment.pop("SCIFACT_PUBLIC_DEMO_ENABLED")
    api_environment.pop("SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN")
    assert service["environment"] == api_environment
    assert service["extra_hosts"] == compose["services"]["api"]["extra_hosts"]
    assert [volume["target"] for volume in service["volumes"]] == [
        "/app/data",
        "/app/artifacts",
        "/models/huggingface",
    ]


def test_mcp_capability_is_active_with_exact_delivery_contract() -> None:
    catalog = json.loads((_ROOT / "harness/capabilities.json").read_text(encoding="utf-8"))
    capability = next(item for item in catalog["capabilities"] if item["id"] == "mcp-interface")

    assert capability["status"] == "active"
    contract = capability["active_contract"]
    assert contract["runtime_dependencies"] == ["mcp==2.2.0"]
    assert contract["ci_checks"] == [
        "uv run pytest tests/test_mcp_server.py tests/test_interface_contracts.py",
        "docker compose config --quiet",
        "make smoke",
    ]
    assert set(contract["implementation_paths"]) == {
        "src/scifact_rag/mcp_server.py",
        "tests/test_mcp_server.py",
        "tests/test_interface_contracts.py",
        "compose.yaml",
        "docs/research/scifact-rag-mcp.md",
        "docs/adr/0033-mcp-adapter.md",
        "docs/superpowers/specs/2026-09-17-mcp-adapter-design.md",
    }
