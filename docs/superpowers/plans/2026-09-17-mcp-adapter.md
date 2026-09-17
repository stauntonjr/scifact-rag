# Thin MCP Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a DGX-local, loopback-only MCP service exposing the accepted SciFact search and grounded-answer operations as exactly two typed tools.

**Architecture:** `scifact_rag.mcp_server` owns strict transport models, one refusal-only pre-dispatch validator, explicit domain conversion, two tool handlers, and a cached application resolver. Official MCP Python SDK v2.2.0 owns protocol negotiation, discovery, structured results, Streamable HTTP, and unexpected-exception sanitization; Docker Compose runs the same project image as one MCP process.

**Tech Stack:** Python 3.12, MCP Python SDK 2.2.0, Pydantic, Docker Compose, pytest, Ruff, Pyright

**Spec:** `docs/superpowers/specs/2026-09-17-mcp-adapter-design.md`

## Global Constraints

- The server exposes exactly `search_scifact` and `answer_scifact`; no resources, prompts, or additional tools.
- The first accepted client is the official MCP Python SDK v2 `Client` running on the DGX.
- The deployed endpoint is exactly `http://127.0.0.1:8091/mcp` over Streamable HTTP.
- Pin the runtime dependency to exactly `mcp==2.2.0`; any SDK upgrade reopens ADR-0033.
- Queries contain 1 through 4,096 code points, must not be whitespace-only, and reach the application unchanged.
- Search limits are strict integers from 1 through 100; answer limits are strict integers from 1 through 20; both default to 5.
- Strict project-owned argument models reject unknown arguments before resolver or application invocation.
- Invalid recognized calls return fixed `INVALID_PARAMS` errors without error data, Pydantic details, or rejected values.
- Unexpected resolver/application failures use the SDK sanitized tool-error path; the adapter performs no retries.
- Result schemas are `mcp-search-result/v1` and `mcp-answer-result/v1`; all application fields and ordering are preserved.
- Both tools are read-only and closed-corpus client hints. `answer_scifact` still invokes model inference and consumes compute.
- Domain and application contracts remain dataclasses and import no MCP or Pydantic types.
- Do not add stdio acceptance, Mac connectivity, tunnels, auth, TLS, non-loopback exposure, resources, prompts, administration, ingest, evaluation, web UI, or application-semantic changes.
- Use test-driven development for every production behavior and push every commit.

---

### Task 1: Strict discovery and input-refusal boundary

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/scifact_rag/mcp_server.py`
- Create: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `RagApplication`, `RetrievalStrategyName`, `DEFAULT_RETRIEVAL_STRATEGY`, and `GenerationContextStrategyName`.
- Produces: `ApplicationResolver`, `SearchToolArguments`, `AnswerToolArguments`, `enforce_tool_arguments`, and `create_mcp_server(resolver: ApplicationResolver) -> MCPServer`.

- [ ] **Step 1: Add the failing discovery and invalid-input tests**

Use the official in-memory `Client(server)`. Assert discovery returns exactly
`{"search_scifact", "answer_scifact"}`, while resources, resource templates, and prompts are
empty. Parameterize both tool names with an unknown argument containing
`REJECTED_VALUE_SENTINEL`, and with the sentinel supplied as `limit`. Catch `MCPError` and assert:

```python
assert exc_info.value.code == INVALID_PARAMS
assert exc_info.value.message == f"Invalid arguments for tool {tool_name}"
assert exc_info.value.data is None
assert "REJECTED_VALUE_SENTINEL" not in str(exc_info.value)
assert "REJECTED_VALUE_SENTINEL" not in repr(exc_info.value.error)
assert resolutions == []
assert application.calls == []
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `uv run pytest tests/test_mcp_server.py -k 'discovery or invalid' -v`

Expected: collection fails because `scifact_rag.mcp_server` does not exist and the SDK dependency
is not installed.

- [ ] **Step 3: Pin the SDK dependency and refresh the lock**

Add `"mcp==2.2.0"` to project runtime dependencies. Run `uv lock && uv sync --dev` and verify the
resolved `mcp` distribution is exactly 2.2.0.

- [ ] **Step 4: Implement strict input types and refusal-only middleware**

Define reusable annotated query and strict bounded integer aliases. Define `SearchToolArguments`
and `AnswerToolArguments` as Pydantic models with:

```python
model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
```

Map the two public tool names to those models. For `ctx.method == "tools/call"`, identify only a
recognized tool and call `model.model_validate(raw_arguments)`. On `ValidationError`, raise:

```python
raise MCPError(
    code=INVALID_PARAMS,
    message=f"Invalid arguments for tool {tool_name}",
) from None
```

Pass all valid and unrelated requests to `call_next(ctx)` unchanged. Do not log, attach, rewrite,
or return the rejected payload.

- [ ] **Step 5: Register the minimal server surface**

Construct `MCPServer("SciFact RAG", version="0.1.0", instructions=..., middleware=[enforce_tool_arguments])`.
Register exactly the two named handlers with `ToolAnnotations(read_only_hint=True,
open_world_hint=False)`. Use the accepted flat handler signatures and strict annotated aliases;
return a minimal typed result temporarily so discovery and validation can execute.

- [ ] **Step 6: Verify GREEN and static quality**

Run: `uv run pytest tests/test_mcp_server.py -k 'discovery or invalid' -v && uv run ruff check src/scifact_rag/mcp_server.py tests/test_mcp_server.py && uv run pyright src/scifact_rag/mcp_server.py tests/test_mcp_server.py`

Expected: all selected tests pass with no warnings or type errors.

- [ ] **Step 7: Commit and push**

```bash
git add pyproject.toml uv.lock src/scifact_rag/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: add strict MCP tool boundary"
git push
```

### Task 2: Search and answer structured-result parity

**Files:**
- Modify: `src/scifact_rag/mcp_server.py`
- Modify: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: Task 1 resolver and argument contracts plus `SearchHit` and `Answer` dataclasses.
- Produces: `McpSearchHit`, `McpSearchResult`, `McpAnswerResult`, and complete tool mappings.

- [ ] **Step 1: Write failing success-path tests**

Use a recording resolver returning `SearchHit("17", "Trial", "Complete abstract.", 0.875)` and an
`Answer` with citation `("17",)`. Call both tools through the official client. Assert the resolver
receives the exact enum pair, the application receives the unchanged query and limit once, and
`structured_content` equals these hand-derived literals:

```python
{"schema_version": "mcp-search-result/v1", "hits": [{"doc_id": "17", "title": "Trial", "text": "Complete abstract.", "score": 0.875}]}
```

and the equivalent complete answer object with query, text, citations, model, and evidence.

- [ ] **Step 2: Run the success tests and verify RED**

Run: `uv run pytest tests/test_mcp_server.py -k 'maps_search or maps_answer' -v`

Expected: the temporary Task 1 results do not match the required schemas or mappings.

- [ ] **Step 3: Implement explicit structured result models**

Use `ConfigDict(extra="forbid")`, literal schema versions, tuple ordering, and finite scores.
Implement explicit `from_domain` constructors. `search_scifact` resolves the supplied retrieval
strategy with `WHOLE_DOCUMENT` and calls `application.search(query, limit=limit)` once.
`answer_scifact` resolves the exact supplied strategy pair and calls
`application.ask(query, limit=limit)` once.

- [ ] **Step 4: Verify GREEN and add exact-insufficiency coverage**

Run the success tests. Then add a test returning
`Answer("unresolved claim", "insufficient evidence", (), "qwen", ())` and assert the exact text,
empty citations, and empty evidence survive the official client path.

- [ ] **Step 5: Add schema/annotation contract assertions**

Inspect discovered tools by name. Assert both input schemas publish the exact properties, defaults,
enum values, and numeric/string bounds represented by the strict validation models. Assert output
schemas require the versioned structures and tool annotations serialize to `readOnlyHint=true` and
`openWorldHint=false`. This comparison deliberately excludes `additionalProperties`, which the SDK
does not copy from the strict policy models; runtime unknown-field behavior is covered in Task 1.

- [ ] **Step 6: Run the focused suite and static checks**

Run: `uv run pytest tests/test_mcp_server.py -v && uv run ruff format --check src tests && uv run ruff check src tests && uv run pyright`

Expected: all pass.

- [ ] **Step 7: Commit and push**

```bash
git add src/scifact_rag/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: map MCP search and answer results"
git push
```

### Task 3: Runtime composition, failure isolation, and interface parity

**Files:**
- Modify: `src/scifact_rag/mcp_server.py`
- Modify: `tests/test_mcp_server.py`
- Modify: `tests/test_interface_contracts.py`

**Interfaces:**
- Consumes: Task 2 server plus `composition.build_application` and existing CLI behavior.
- Produces: `build_mcp_server() -> MCPServer`, finite resolver caching, `main()`, and normalized CLI/MCP parity evidence.

- [ ] **Step 1: Write the failing runtime-cache and unexpected-failure tests**

Monkeypatch `mcp_server.build_application`, call a built server twice for one strategy pair and once
for another, and assert two composition calls. Separately inject resolver and application failures
containing `SECRET_FAILURE_SENTINEL`; assert the SDK returns an error result, no structured content,
and no sentinel or exception type in any public content. Verify RED because `build_mcp_server` is
absent.

- [ ] **Step 2: Implement the bounded runtime factory**

Define a local `@lru_cache` keyed by both enum types with maximum size
`len(RetrievalStrategyName) * len(GenerationContextStrategyName)`. Delegate misses to
`build_application(retrieval_strategy=..., generation_context_strategy=...)`, then return
`create_mcp_server(resolve)`.

- [ ] **Step 3: Implement the exact Streamable HTTP entry point**

`main()` calls `build_mcp_server().run(transport="streamable-http", host="0.0.0.0", port=80,
streamable_http_path="/mcp", stateless_http=True, json_response=True)`. Keep it under a module guard
so imports have no runtime side effects.

- [ ] **Step 4: Add normalized CLI/MCP parity tests**

Reuse one deterministic application underneath the Typer CLI and injected MCP resolver. Compare
all normalized search and answer fields after removing only the MCP schema-version wrapper. Assert
parent citations refer to returned evidence and exact insufficiency remains unchanged.

- [ ] **Step 5: Verify GREEN**

Run: `uv run pytest tests/test_mcp_server.py tests/test_interface_contracts.py -v && uv run ruff format --check src tests && uv run ruff check src tests && uv run pyright`

Expected: all pass.

- [ ] **Step 6: Commit and push**

```bash
git add src/scifact_rag/mcp_server.py tests/test_mcp_server.py tests/test_interface_contracts.py
git commit -m "test: enforce MCP runtime and interface parity"
git push
```

### Task 4: Compose delivery, capability activation, and durable documentation

**Files:**
- Modify: `compose.yaml`
- Modify: `harness/capabilities.json`
- Modify: `harness/project.yaml`
- Modify: `README.md`
- Modify: `docs/project/charter.md`
- Modify: `docs/project/capability-matrix.md`
- Modify: `docs/project/technical-reference.md`
- Modify: `docs/project/roadmap.md`
- Modify: `docs/project/handoff.md`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_interface_contracts.py`

**Interfaces:**
- Consumes: `python -m scifact_rag.mcp_server` and accepted ADR-0033.
- Produces: exact loopback Compose publication, active capability contract, public contract documentation, and operator guidance.

- [ ] **Step 1: Write failing Compose and capability behavior tests**

Parse `docker compose config --format json` in the test rather than grepping source. Assert service
`mcp` uses the application image/build, starts `uv run --no-dev python -m scifact_rag.mcp_server`,
publishes only host `127.0.0.1`, port `8091`, target `80`, depends on healthy PostgreSQL, and carries
the existing application environment/mount boundary. Parse the capability catalog and assert
`mcp-interface` is active with dependency `mcp==2.2.0`, the focused test command, and only actual
implementation/documentation paths. Verify RED.

- [ ] **Step 2: Add the Compose service and activate the capability**

Mirror the accepted `api` service environment, mounts, host gateway, and PostgreSQL dependency.
Override the image entrypoint with `entrypoint: ["uv", "run", "--no-dev", "python"]`, command
`["-m", "scifact_rag.mcp_server"]`, and exact loopback publication `127.0.0.1:8091:80`. Set the
catalog capability active with the owner approval, dependency, checks, and exact paths.

- [ ] **Step 3: Update product contracts and operator documentation**

Add MCP to project scope, summary, and public compatibility contracts while keeping web UI and all
other deferred capabilities out of scope. Keep README concise: show the two tool names, Compose
startup, and endpoint, then link to the technical reference. Put the complete argument/result/error
contracts, inference-cost warning, official-client example, topology, and loopback limitation in
the technical reference. Mark MCP implemented pending live acceptance in roadmap/handoff, update
the capability matrix and charter, and add one changelog entry.

- [ ] **Step 4: Verify static delivery contracts**

Run: `uv run pytest tests/test_interface_contracts.py tests/test_mcp_server.py -v && docker compose config --quiet && python3 tools/harness_check.py && git diff --check`

Expected: all pass.

- [ ] **Step 5: Commit and push**

```bash
git add compose.yaml harness/capabilities.json harness/project.yaml README.md CHANGELOG.md docs/project tests/test_interface_contracts.py
git commit -m "docs: activate the MCP adapter"
git push
```

### Task 5: Full verification, live acceptance, review, and integration

**Files:**
- Create after successful live run: `docs/reports/issue-12-mcp-acceptance.md`
- Modify: `docs/project/handoff.md`
- Modify: `docs/project/roadmap.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: the complete MCP adapter and current accepted corpus/model services.
- Produces: retained official-client evidence, independent review, locally merged `main`, closed Issue #12, and the next explicit roadmap state.

- [ ] **Step 1: Run the complete local engineering gate**

Run: `make smoke`

Expected: harness, formatting, Ruff, Pyright, all non-integration tests, package smoke, and Compose
configuration pass.

- [ ] **Step 2: Run affected integrations**

Run the existing PostgreSQL and retrieval integrations selected by Issue #12 without starting or
tuning unrelated GPU services. Expected: application search/ask dependencies used by the adapter
pass against the accepted Compose data state.

- [ ] **Step 3: Run bounded live DGX acceptance**

Start `postgres` and `mcp` with Docker Compose, spinning down conflicting services only if required
for the already-authorized DGX memory boundary. Use the official SDK v2.2.0 URL client against
`http://127.0.0.1:8091/mcp`. Record server identity, exactly two discovered tools, one successful
search, one supported answer whose citations are contained in returned evidence, one exact
`insufficient evidence` answer with empty citations, active strategies, schema versions, model,
timings, image identity, host, and commit. This is operational acceptance, not model-quality tuning.

- [ ] **Step 4: Retain acceptance evidence and reconcile documents**

Create `docs/reports/issue-12-mcp-acceptance.md` from the observed commands/results. Mark roadmap,
handoff, and changelog accepted only for checks that actually passed. Commit and push the report.

- [ ] **Step 5: Request and address independent review**

Review the exact Issue #12 diff for application-boundary drift, invalid-input disclosure, unknown
argument handling, public schemas, Compose exposure, and documentation truthfulness. Any defect is
reproduced with a failing test before correction; each correction is committed and pushed.

- [ ] **Step 6: Finish according to the standing owner choice**

Use `superpowers:finishing-a-development-branch`. Re-run the full gate after the final diff, merge
the feature branch locally to `main`, push `main`, verify the remote commit and CI, close Issue #12,
and update its Project status. Do not create a release or tag.
