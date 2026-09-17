# Thin HTTP API Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a loopback-only FastAPI adapter whose health, search, and ask operations preserve the accepted `RagApplication` and CLI contracts.

**Architecture:** `scifact_rag.http_api` owns strict Pydantic transport models, explicit dataclass conversion, route handlers, safe error envelopes, and an injected application resolver. The runtime resolver caches applications built by the existing composition root; Docker Compose launches the same image under a Uvicorn entrypoint.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, Uvicorn, HTTPX ASGI transport, Typer, Docker Compose, pytest, Ruff, Pyright

**Spec:** `docs/superpowers/specs/2026-09-17-http-api-adapter-design.md`

## Global Constraints

- Public operations are exactly `GET /healthz`, `POST /v1/search`, and `POST /v1/ask`.
- Query length is 1 through 4,096 Unicode code points after requiring non-whitespace content; pass the original query unchanged.
- Search limits are 1 through 100; ask limits are 1 through 20; both default to 5.
- Strategy values and defaults come from `RetrievalStrategyName`, `DEFAULT_RETRIEVAL_STRATEGY`, and `GenerationContextStrategyName`.
- Every request requires its exact literal `schema_version`; unknown fields are rejected.
- Validation failures do not resolve or invoke an application and do not echo rejected values.
- Unexpected failures expose only the fixed `error/v1` internal-error envelope and perform no retries.
- Domain and application contracts remain dataclasses and contain no FastAPI or Pydantic types.
- The host publication is exactly `127.0.0.1:8090:80`; no CORS, authentication, TLS, streaming, jobs, ingest, evaluation, MCP, web UI, or product-semantic change enters this phase.
- Use test-driven development for every production behavior and push every commit.

---

### Task 1: Dependency and liveness boundary

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/scifact_rag/http_api.py`
- Create: `tests/test_http_api.py`

**Interfaces:**
- Consumes: `RagApplication`, `RetrievalStrategyName`, and `GenerationContextStrategyName`.
- Produces: `ApplicationResolver`, `create_http_app(resolver: ApplicationResolver) -> FastAPI`, and a dependency-free `/healthz` operation.

- [ ] **Step 1: Write the failing liveness test**

```python
@pytest.mark.anyio
async def test_health_is_liveness_only() -> None:
    def fail_if_resolved(
        retrieval_strategy: RetrievalStrategyName,
        generation_context_strategy: GenerationContextStrategyName,
    ) -> RagApplication:
        raise AssertionError("health must not resolve an application")

    transport = httpx.ASGITransport(app=create_http_app(fail_if_resolved))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"schema_version": "health/v1", "status": "ok"}
```

- [ ] **Step 2: Run the test and verify RED**

Run: `uv run pytest tests/test_http_api.py::test_health_is_liveness_only -v`

Expected: collection fails because `scifact_rag.http_api` does not exist.

- [ ] **Step 3: Add the framework dependencies and lock them**

Add direct runtime constraints:

```toml
"fastapi>=0.116,<1",
"uvicorn>=0.35,<1",
```

Run: `uv lock && uv sync --dev`

- [ ] **Step 4: Implement the minimal constructor and health response**

```python
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
```

- [ ] **Step 5: Run the focused test and static checks**

Run: `uv run pytest tests/test_http_api.py::test_health_is_liveness_only -v && uv run ruff check src/scifact_rag/http_api.py tests/test_http_api.py && uv run pyright src/scifact_rag/http_api.py tests/test_http_api.py`

Expected: all pass.

- [ ] **Step 6: Commit and push**

```bash
git add pyproject.toml uv.lock src/scifact_rag/http_api.py tests/test_http_api.py
git commit -m "feat: add HTTP liveness boundary"
git push
```

### Task 2: Strict search and ask contracts

**Files:**
- Modify: `src/scifact_rag/http_api.py`
- Modify: `tests/test_http_api.py`

**Interfaces:**
- Consumes: the Task 1 application resolver plus `SearchHit` and `Answer` dataclasses.
- Produces: `SearchRequest`, `SearchResponse`, `AskRequest`, `AnswerResponse`, explicit response converters, and the two `/v1` routes.

- [ ] **Step 1: Write failing success-path tests**

Use a recording resolver whose application returns:

```python
SearchHit("17", "Trial", "Complete abstract.", 0.875)
Answer(
    query="claim",
    text="Supported [17]",
    citations=("17",),
    model="qwen",
    evidence=(SearchHit("17", "Trial", "Complete abstract.", 0.875),),
)
```

Assert request enums, unchanged query, and limit reach the resolver/application exactly; assert the
complete `search-response/v1` and `answer/v1` JSON structures and evidence order.

- [ ] **Step 2: Run the success-path tests and verify RED**

Run: `uv run pytest tests/test_http_api.py -k 'search_maps or ask_maps' -v`

Expected: 404 for the missing operations.

- [ ] **Step 3: Implement strict request and response models**

Define one strict base model using `ConfigDict(extra="forbid")`. Define `query` with maximum length
4,096 and a validator that rejects whitespace-only strings without altering the returned value.
Use `Literal` schema versions, existing enum fields, and bounded integer fields. Define explicit
`SearchHitResponse.from_domain` and `AnswerResponse.from_domain` constructors; require finite
scores with `Field(allow_inf_nan=False)`.

- [ ] **Step 4: Implement the two synchronous routes**

```python
@app.post("/v1/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    application = resolver(request.strategy, GenerationContextStrategyName.WHOLE_DOCUMENT)
    return SearchResponse(
        hits=tuple(SearchHitResponse.from_domain(hit) for hit in application.search(request.query, limit=request.limit))
    )


@app.post("/v1/ask", response_model=AnswerResponse)
def ask(request: AskRequest) -> AnswerResponse:
    application = resolver(request.strategy, request.context_strategy)
    return AnswerResponse.from_domain(application.ask(request.query, limit=request.limit))
```

- [ ] **Step 5: Verify GREEN**

Run: `uv run pytest tests/test_http_api.py -k 'search_maps or ask_maps' -v`

Expected: all selected tests pass.

- [ ] **Step 6: Add and verify the exact insufficient-evidence test**

Return `Answer("claim", "insufficient evidence", (), "qwen", ())` and assert HTTP preserves the
exact text, empty citations, and empty evidence. Run that test first against the current response
mapping; it must pass only through the real application-result converter.

- [ ] **Step 7: Commit and push**

```bash
git add src/scifact_rag/http_api.py tests/test_http_api.py
git commit -m "feat: expose search and ask over HTTP"
git push
```

### Task 3: Validation, failure isolation, runtime composition, and CLI parity

**Files:**
- Modify: `src/scifact_rag/http_api.py`
- Modify: `tests/test_http_api.py`
- Create: `tests/test_interface_contracts.py`

**Interfaces:**
- Consumes: Task 2 schemas and routes plus `composition.build_application` and the existing Typer commands.
- Produces: safe `error/v1` responses, `build_http_app() -> FastAPI`, cached strategy resolution, OpenAPI assertions, and normalized CLI/HTTP parity evidence.

- [ ] **Step 1: Write failing validation-isolation tests**

Parameterize malformed JSON, missing/wrong schema version, unknown fields, blank and 4,097-character
queries, limits outside each route's range, and invalid strategy values. For every case assert 422,
`error/v1`, absence of the rejected value in serialized output, and zero resolver/application calls.

- [ ] **Step 2: Run validation tests and verify RED**

Run: `uv run pytest tests/test_http_api.py -k validation -v`

Expected: FastAPI's default validation body does not match the required envelope.

- [ ] **Step 3: Implement the validation and internal-error handlers**

Convert `RequestValidationError.errors()` to details containing only `location`, `message`, and
`type`. Register a general exception handler that logs the exception and returns status 500 with:

```python
{"schema_version": "error/v1", "error": {"code": "internal_error", "message": "The request could not be completed"}}
```

- [ ] **Step 4: Verify validation GREEN and write the failing internal-error test**

Run validation tests, then configure `httpx.ASGITransport(..., raise_app_exceptions=False)` with a
resolver that raises `RuntimeError("secret configuration")`. Assert status 500 and that neither
`secret` nor the exception type appears in the response.

- [ ] **Step 5: Write the failing runtime-cache test**

Monkeypatch `http_api.build_application`, call the runtime resolver twice for one strategy pair and
once for a different pair, and assert exactly two composition calls. Verify RED because
`build_http_app` is absent.

- [ ] **Step 6: Implement the runtime factory**

Define `build_http_app()` with a local `@lru_cache` resolver keyed by both existing enums. Delegate
cache misses to `build_application(retrieval_strategy=..., generation_context_strategy=...)`, then
return `create_http_app(resolver)`.

- [ ] **Step 7: Add OpenAPI and CLI/API parity tests**

Assert OpenAPI contains exactly the three product paths and schema components for all request,
success, and error models. Monkeypatch `cli.build_application` and inject the equivalent HTTP
resolver; invoke Typer `search` and `ask`, invoke HTTP with the same options, remove only the HTTP
top-level `schema_version`/wrapper, and assert identical normalized dataclass fields including
parent citations and evidence.

- [ ] **Step 8: Run the complete focused suite and static checks**

Run: `uv run pytest tests/test_http_api.py tests/test_interface_contracts.py -v && uv run ruff format --check src tests && uv run ruff check src tests && uv run pyright`

Expected: all pass with no warnings or type errors.

- [ ] **Step 9: Commit and push**

```bash
git add src/scifact_rag/http_api.py tests/test_http_api.py tests/test_interface_contracts.py
git commit -m "test: enforce HTTP interface parity"
git push
```

### Task 4: Compose delivery, capability activation, and durable documentation

**Files:**
- Modify: `compose.yaml`
- Modify: `harness/capabilities.json`
- Create: `docs/adr/0032-http-api-adapter.md`
- Modify: `README.md`
- Modify: `docs/project/technical-reference.md`
- Modify: `docs/project/roadmap.md`
- Modify: `docs/project/handoff.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/superpowers/specs/2026-09-17-http-api-adapter-design.md`

**Interfaces:**
- Consumes: `build_http_app` and the accepted Issue #11 design.
- Produces: loopback Compose service, active capability contract, accepted ADR, and operator-facing usage/provenance.

- [ ] **Step 1: Write the failing static interface-contract checks**

Extend `tests/test_interface_contracts.py` to parse Compose and the capability catalog. Assert the
API service publishes `127.0.0.1:8090:80`, starts `scifact_rag.http_api:build_http_app --factory`,
depends on healthy PostgreSQL, and the capability is active with FastAPI/Uvicorn, focused checks,
and exact implementation paths. Run the tests and verify RED.

- [ ] **Step 2: Add the Compose API service**

Mirror the existing app service environment, volumes, host gateway, and PostgreSQL dependency.
Override entrypoint with `["uv", "run", "--no-dev", "uvicorn"]`; pass
`scifact_rag.http_api:build_http_app`, `--factory`, `--host`, `0.0.0.0`, `--port`, and `80` as the
command. Publish only `127.0.0.1:8090:80`.

- [ ] **Step 3: Activate the capability exactly**

Set `http-api-interface.status` to `active` and add an `active_contract` naming the owner's
2026-09-17 Issue #11 approval, FastAPI/Uvicorn runtime dependencies, focused unit/parity/Compose
checks, and only `src/scifact_rag/http_api.py`, `tests/test_http_api.py`,
`tests/test_interface_contracts.py`, `compose.yaml`, and the HTTP documentation paths.

- [ ] **Step 4: Record the architecture decision**

ADR-0032 records FastAPI/Uvicorn, boundary-only Pydantic, the injected/cached resolver, synchronous
one-worker service, safe error boundary, loopback non-production status, rejected alternatives,
and revisit triggers from the accepted spec. Status is accepted with the human owner as decider.

- [ ] **Step 5: Update product and operator documents**

Keep README concise: add one API demonstration with health/search/ask and link to the technical
reference. Put complete request schemas, strategy options, Compose startup, curl examples, error
contract, OpenAPI location, and non-production boundary in the technical reference. Mark HTTP as
the active Phase 6 slice in the roadmap; make MCP the next adapter. Update handoff with exact state,
verification, and remaining live acceptance. Add one changelog item. Preserve all removed detail in
the technical reference.

- [ ] **Step 6: Run static contracts and Compose validation**

Run: `uv run pytest tests/test_interface_contracts.py -v && docker compose config --quiet && python3 tools/harness_check.py && git diff --check`

Expected: all pass.

- [ ] **Step 7: Commit and push**

```bash
git add compose.yaml harness/capabilities.json docs/adr/0032-http-api-adapter.md README.md docs/project/technical-reference.md docs/project/roadmap.md docs/project/handoff.md CHANGELOG.md docs/superpowers/specs/2026-09-17-http-api-adapter-design.md tests/test_interface_contracts.py
git commit -m "docs: activate the HTTP adapter"
git push
```

### Task 5: Full verification, live acceptance, review, and integration

**Files:**
- Create when the live run succeeds: `docs/reports/issue-11-http-api-acceptance.md`
- Modify: `docs/project/handoff.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: the complete HTTP adapter and existing accepted corpus/model services.
- Produces: retained acceptance evidence, independently reviewed implementation, merged main, closed Issue #11, and the next bounded roadmap state.

- [ ] **Step 1: Run the complete local engineering gate**

Run: `make smoke`

Expected: harness, formatting, Ruff, Pyright, non-integration tests, package smoke, and Compose
configuration all pass.

- [ ] **Step 2: Run affected integration checks**

Run: `uv run pytest -m integration -v`

Expected: all database/retrieval integration tests pass against the accepted Compose data state.

- [ ] **Step 3: Run the live loopback acceptance**

Start the required Compose services without rebuilding model behavior. Call `/healthz`, then call
`/v1/ask` for one accepted supported CLI case and one accepted exact-insufficiency CLI case using
the same strategy/context settings as their retained CLI rows. Validate status, response schema,
exact insufficiency text, and that every supported citation names returned parent evidence. Do not
tune or substitute cases after seeing outputs.

- [ ] **Step 4: Retain the acceptance report**

Record commit, timestamp, host, image/config provenance, request strategy settings, status codes,
schema validation, normalized CLI/API equality, citation-parent result, insufficiency result,
latency, and any operational limitation in `docs/reports/issue-11-http-api-acceptance.md`. Do not
store secrets or unrestricted model text.

- [ ] **Step 5: Perform independent review and resolve findings**

Use the requesting-code-review skill against the Issue #11 acceptance criteria and diff from
`c000159`. Fix only verified findings through new failing tests, rerun affected checks, and push
each corrective commit.

- [ ] **Step 6: Re-run fresh verification**

Run: `make smoke && uv run pytest -m integration -v`

Expected: all pass after the final change.

- [ ] **Step 7: Commit and push acceptance evidence**

```bash
git add docs/reports/issue-11-http-api-acceptance.md docs/project/handoff.md CHANGELOG.md
git commit -m "docs: record HTTP adapter acceptance"
git push
```

- [ ] **Step 8: Finish the development branch**

Use `superpowers:finishing-a-development-branch`. The owner's standing choice is local merge to
`main`; merge only after clean fresh verification, push `main`, remove the feature worktree/branch,
comment evidence on Issue #11, close it, and move its Project #17 item to Done.

- [ ] **Step 9: Advance without another prompt**

Re-read Phase 6 and active capability state. Report the next bounded product action; do not activate
MCP, web UI, memory, or another capability without the explicit owner boundary required by the
catalog.
