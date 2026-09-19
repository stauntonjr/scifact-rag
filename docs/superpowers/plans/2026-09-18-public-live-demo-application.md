# SciFact public live-demo application implementation plan

> **For implementation:** Use `superpowers:executing-plans` and execute this plan in order. Do not
> delegate work unless the human owner explicitly asks for delegation. Keep the candidate on one
> issue branch/worktree until the application gate passes, and push after every task commit.

**Goal:** Add the application-owned half of the bounded anonymous SciFact live demo: dependency
readiness, per-strategy capabilities, one shared non-blocking inference slot, capability-aware UI
behavior, and a durable Pages entry point without changing retrieval, generation, evidence, or
citation semantics.

**Architecture:** Adapt the active FastAPI and native-browser adapters around the existing
application composition root. A public-demo runtime, enabled only by typed environment settings,
probes PostgreSQL and existing model health operations without inference, derives strategy
availability from the authoritative enums, and owns a process-local one-slot gate. The existing
FastAPI process continues to serve the UI and versioned application contracts. GitHub Pages remains
an independent recorded showcase and performs only an exact-origin readiness check before offering
the live link.

**Tech stack:** Python 3.12 dataclasses and protocols; FastAPI/Pydantic/httpx/SQLAlchemy; native
HTML/CSS/JavaScript; Docker Compose; pytest/Ruff/Pyright; GitHub Pages.

**Governing artifacts:**

- [Issue #27](https://github.com/stauntonjr/scifact-rag/issues/27)
- [Approved public-demo design](../specs/2026-09-18-public-live-demo-design.md)
- Coordinated edge work: [vps-srv Issue #4](https://github.com/stauntonjr/vps-srv/issues/4)
- Separate edge plan: `/home/jrs/vps-srv/docs/superpowers/plans/2026-09-18-scifact-public-edge.md`

## Frozen scope and capability disposition

- **Adapt**, do not rebuild: extend the active `http-api-interface` and `web-interface` contracts.
- `application-composition-root` is `use-active`; it remains the sole place that constructs RAG
  applications.
- `http-api-interface` and `web-interface` are `use-active`; update their active contracts only.
- `mcp-interface` and `cli-interface` are `use-active but unchanged`; their behavior and deployment
  remain local.
- Every inactive capability is `not-applicable`; do not activate deployment, memory, observability,
  graph, auth, queue, or policy substitutes.
- Do not change retrieval scores, candidate pools, generator prompts, evidence ordering, citation
  rules, exact `insufficient evidence`, PostgreSQL schema, or model lifecycle.
- Do not publish PostgreSQL, MCP, model, or application ports from Compose. Port 8090 remains bound
  to `127.0.0.1`.
- Do not add Redis, a job queue, accounts, browser storage, analytics, retries, or a second app.
- Public-demo mode requires the existing one-worker Uvicorn command. More than one worker is a
  design-revision trigger, not a scaling tweak.

## Public contracts to implement

### Environment

```text
SCIFACT_PUBLIC_DEMO_ENABLED=false
SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN=https://stauntonjr.github.io
```

Parse `SCIFACT_PUBLIC_DEMO_ENABLED` strictly as `true` or `false`. When disabled, retain the
accepted local UI behavior: do not install public readiness/capability routes, do not run probes,
do not add readiness CORS, and do not gate Search or Answer. When enabled, require an HTTPS origin
with no path, query, fragment, credentials, or wildcard. The deployed value is the exact origin
above.

### Readiness

```json
{"schema_version":"readiness/v1","status":"ready"}
```

Return HTTP 200 only when at least one Search strategy and at least one complete Answer combination
are available. Otherwise return HTTP 503 with the same schema and `status: "unavailable"`. Never
include dependency names, URLs, exceptions, or raw health responses.

### Capabilities

```json
{
  "schema_version": "capabilities/v1",
  "status": "ready",
  "search": {"available": true, "reason": null},
  "answer": {"available": true, "reason": null},
  "retrieval": {
    "configured_default": "pooled-coref-interval-content-max-colbert",
    "effective_default": "pooled-coref-interval-content-max-colbert",
    "strategies": [
      {"name": "bm25-token-window-rrf", "available": true, "reason": null}
    ]
  },
  "context": {
    "configured_default": "whole-document",
    "effective_default": "whole-document",
    "strategies": [
      {"name": "whole-document", "available": true, "reason": null}
    ]
  }
}
```

The arrays must contain every current enum member exactly once and in enum order. Allowed public
reason codes are `retrieval_store_unavailable`, `reranker_unavailable`,
`late_interaction_unavailable`, `rankllm_unavailable`, `generator_unavailable`, and
`no_available_strategy`. `status` is `ready` when configured defaults work, `degraded` when an
effective fallback exists, and `unavailable` when no complete Search or Answer path exists. The
existing fast fallback is `bm25-token-window-rrf`; never invent a new fallback.

### Errors and request ordering

- Keep request validation at HTTP 422 and ahead of all runtime work.
- For a valid public-demo request: acquire the shared gate, obtain one capability snapshot, reject
  an unavailable selection, resolve the application, execute it, then release in `finally`.
- If the gate is occupied, return the existing `error/v1` envelope with HTTP 429 and code `busy`;
  perform zero probes, resolution, retrieval, reranking, or generation for the rejected request.
- If the selected path is unavailable, return HTTP 503 with code `unavailable` and a fixed message.
- Retain HTTP 500 `internal_error`, but log only route, status, latency, selected public strategy
  names, and exception class. Never log claim text, request/response bodies, exception messages, or
  raw upstream output.

---

### Task 1: Add the typed public-demo policy and dependency map

**Files:**

- Create: `src/scifact_rag/public_demo.py`
- Create: `tests/test_public_demo.py`

**Interfaces:**

```python
class DependencyName(StrEnum):
    RETRIEVAL_STORE = "retrieval-store"
    GENERATOR = "generator"
    RERANKER = "reranker"
    LATE_INTERACTION = "late-interaction"
    RANKLLM = "rankllm"

@dataclass(frozen=True, slots=True)
class PublicDemoSettings:
    enabled: bool = False
    pages_origin: str | None = None

    @classmethod
    def from_environment(cls) -> "PublicDemoSettings": ...

def retrieval_dependencies(
    strategy: RetrievalStrategyName,
) -> frozenset[DependencyName]: ...

def context_dependencies(
    strategy: GenerationContextStrategyName,
) -> frozenset[DependencyName]: ...
```

- [ ] **Step 1: Write failing strict-environment tests**

  Cover absent values, explicit false, enabled exact Pages origin, invalid booleans, HTTP origins,
  origins with paths/query/fragment/credentials, and wildcards. Use `monkeypatch` and assert no
  environment value appears in the validation message.

  ```bash
  uv run pytest tests/test_public_demo.py -q
  ```

  Expected: fail because `scifact_rag.public_demo` does not exist.

- [ ] **Step 2: Write failing dependency-map tests**

  Assert all retrieval/context enum members are accepted. Assert the exact hosted-service groups:

  - MS MARCO: `rerank-msmarco`, `pooled-msmarco-rrf`, and
    `pooled-coref-interval-msmarco` require the store plus `reranker`.
  - ColBERT: `pooled-colbert`, `pooled-coref-interval-colbert`, and all four dual/interval ColBERT
    strategies require the store plus `late-interaction`.
  - RankZephyr: `pooled-coref-interval-rankzephyr` requires the store plus `rankllm`.
  - Every other retrieval strategy requires only the retrieval store.
  - `whole-document` requires no extra dependency; `top-dp-chunks` and `adaptive` require
    `late-interaction`.

  Build the map from the enum members themselves, not a copied string catalog. Add a regression
  assertion that changing either enum forces this test to account for the new dependency class.

- [ ] **Step 3: Implement the smallest policy module**

  Keep the module free of FastAPI, SQLAlchemy, and HTTP clients. Use frozen dataclasses and enums.
  The map may use enum-keyed groups and a single default rule; it must never supply UI labels or
  duplicate the strategy list.

- [ ] **Step 4: Verify and commit the policy slice**

  ```bash
  uv run pytest tests/test_public_demo.py -q
  uv run ruff check src/scifact_rag/public_demo.py tests/test_public_demo.py
  uv run pyright src/scifact_rag/public_demo.py tests/test_public_demo.py
  git diff --check
  git add src/scifact_rag/public_demo.py tests/test_public_demo.py
  git commit -m "feat: define public demo capability policy"
  git push
  ```

### Task 2: Add non-inference dependency probes and capability derivation

**Files:**

- Create: `src/scifact_rag/adapters/health.py`
- Modify: `src/scifact_rag/public_demo.py`
- Modify: `tests/test_public_demo.py`
- Create: `tests/test_health_adapters.py`

**Interfaces:**

```python
class DependencyProbe(Protocol):
    def available(self) -> bool: ...

@dataclass(frozen=True, slots=True)
class StrategyCapability:
    name: str
    available: bool
    reason: PublicReason | None

@dataclass(frozen=True, slots=True)
class CapabilitySnapshot:
    status: Literal["ready", "degraded", "unavailable"]
    search_available: bool
    answer_available: bool
    retrieval: tuple[StrategyCapability, ...]
    context: tuple[StrategyCapability, ...]
    effective_retrieval_default: RetrievalStrategyName | None
    effective_context_default: GenerationContextStrategyName | None

class CapabilityProvider(Protocol):
    def snapshot(self) -> CapabilitySnapshot: ...

class PublicDemoCapabilityService:
    def __init__(self, probes: Mapping[DependencyName, DependencyProbe]) -> None: ...
    def snapshot(self) -> CapabilitySnapshot: ...
```

- [ ] **Step 1: Write failing pure capability-service tests**

  Use recording fake probes and cover all-up, default-ColBERT-down with healthy BM25 fallback,
  store-down, generator-down, reranker-only-down, RankLLM-only-down, and adaptive-context-down.
  Assert each dependency is probed at most once per snapshot even though many strategies share it.
  Assert no probe payload or exception message enters the snapshot. Probe exceptions fail closed to
  the corresponding public reason code.

- [ ] **Step 2: Implement capability derivation**

  Search availability is any available retrieval strategy. Answer availability additionally
  requires the generator and an available context strategy. Prefer the configured defaults; use
  `BM25_TOKEN_WINDOW_RRF` only when the retrieval default is unavailable and that existing strategy
  is healthy. Prefer `WHOLE_DOCUMENT` as the only context fallback. Do not cache snapshots in this
  first version; one request executes one bounded probe set, avoiding invalidation state.

- [ ] **Step 3: Write failing adapter tests**

  For `PostgresHealthProbe`, inject an SQLAlchemy connection factory and assert exactly `SELECT 1`.
  For `HttpHealthProbe`, inject an `httpx.Client`/transport and assert one `GET`, a fixed sub-second
  timeout, `available=True` only for 2xx, and `False` for timeouts, transport errors, or non-2xx.
  Verify response bodies are never parsed or retained.

- [ ] **Step 4: Implement the health adapters**

  Use these existing non-inference operations:

  | Dependency | Operation |
  |---|---|
  | PostgreSQL | `SELECT 1` |
  | Generator | `GET {GENERATOR_BASE_URL}/models` |
  | MS MARCO TEI | `GET {RERANKER_BASE_URL}/health` |
  | ColBERT vLLM | `GET {LATE_INTERACTION_BASE_URL}/health` |
  | RankLLM | `GET {RANK_LLM_BASE_URL}/healthz` |

  Normalize the generator base URL so an existing trailing `/v1` produces `/v1/models`. Do not
  call embeddings, rerank, search, ask, or completions.

- [ ] **Step 5: Verify and commit the capability slice**

  ```bash
  uv run pytest tests/test_public_demo.py tests/test_health_adapters.py -q
  uv run ruff check src/scifact_rag/public_demo.py src/scifact_rag/adapters/health.py tests/test_public_demo.py tests/test_health_adapters.py
  uv run pyright src/scifact_rag/public_demo.py src/scifact_rag/adapters/health.py
  git diff --check
  git add src/scifact_rag/public_demo.py src/scifact_rag/adapters/health.py tests/test_public_demo.py tests/test_health_adapters.py
  git commit -m "feat: derive public demo readiness without inference"
  git push
  ```

### Task 3: Add HTTP readiness, capabilities, shared gating, and fixed failures

**Files:**

- Modify: `src/scifact_rag/http_api.py`
- Modify: `tests/test_http_api.py`

**Interfaces:**

```python
class InferenceGate(Protocol):
    @contextmanager
    def acquire(self) -> Iterator[bool]: ...

@dataclass(frozen=True, slots=True)
class PublicDemoRuntime:
    settings: PublicDemoSettings
    capabilities: CapabilityProvider
    gate: InferenceGate

def create_http_app(
    resolver: ApplicationResolver,
    *,
    public_demo: PublicDemoRuntime | None = None,
) -> FastAPI: ...
```

Use `threading.BoundedSemaphore(1)` behind a small gate class. Do not use `asyncio` locks, queues,
or middleware-global request state; the handlers are synchronous and Uvicorn has one worker.

- [ ] **Step 1: Write disabled-mode compatibility tests**

  Existing `create_http_app(resolver)` tests must remain unchanged and green. Add assertions that
  `/readyz` and `/v1/capabilities` are 404, no CORS header is present, and two ordinary local calls
  are not subject to the public gate when no runtime is supplied.

- [ ] **Step 2: Write failing readiness/capability contract tests**

  Inject a fake `CapabilityProvider`. Assert 200/503 readiness bodies, exact capability response
  shape and enum order, no resolver/application calls, and no arbitrary values. For CORS:

  - exact `Origin: https://stauntonjr.github.io` on `/readyz` receives that exact
    `Access-Control-Allow-Origin` plus `Vary: Origin`;
  - any other origin receives no allow-origin header;
  - `/v1/capabilities`, `/v1/search`, and `/v1/ask` never receive cross-origin allow headers.

- [ ] **Step 3: Write failing shared-slot tests**

  Block a first Search or Answer inside a recording application and submit the other operation.
  Assert the second response is exactly:

  ```json
  {
    "schema_version": "error/v1",
    "error": {"code": "busy", "message": "Another live request is in progress"}
  }
  ```

  Assert zero capability, resolver, and application calls attributable to the rejected request.
  Cover release after success, resolver failure, application failure, and cancellation of the
  client task. Validation failures must remain 422 and never acquire the gate.

- [ ] **Step 4: Write failing unavailable-selection and privacy tests**

  Ask/Search with a known unavailable strategy/context must return a fixed 503 `error/v1` envelope
  before resolution. Use a unique claim/error sentinel, capture logs, and assert it is absent from
  response details and log records. Assert only exception class, route, and selected enum names are
  emitted for an unexpected 500.

- [ ] **Step 5: Implement the public runtime in the composition factory**

  `build_http_app()` reads `Settings` and `PublicDemoSettings` once. When enabled it constructs the
  five probes, capability service, and one gate; the cached resolver passes the already-read
  `Settings` into `build_application`. This prevents environment drift and leaves application
  caching keyed only by the existing strategy pair.

- [ ] **Step 6: Implement routes and guarded handlers**

  Register readiness/capability routes only in enabled mode. Extend `ErrorBody.code` with `busy`
  and `unavailable`, document 429/503 in OpenAPI, and wrap both POST handlers in the same gate.
  Preserve all current result mapping and exact insufficiency behavior.

- [ ] **Step 7: Verify and commit the HTTP slice**

  ```bash
  uv run pytest tests/test_http_api.py tests/test_public_demo.py tests/test_health_adapters.py -q
  uv run ruff format --check src tests
  uv run ruff check src tests
  uv run pyright
  git diff --check
  git add src/scifact_rag/http_api.py src/scifact_rag/public_demo.py tests/test_http_api.py
  git commit -m "feat: bound the public HTTP demo runtime"
  git push
  ```

### Task 4: Make the existing browser UI capability-aware

**Files:**

- Modify: `src/scifact_rag/web/__init__.py`
- Modify: `src/scifact_rag/web/index.html`
- Modify: `src/scifact_rag/web/scifact.css`
- Modify: `src/scifact_rag/web/scifact.js`
- Modify: `tests/test_web_ui.py`

**Behavior:** All current retrieval and context controls remain visible. In local mode, behavior is
unchanged. In public-demo mode, the UI fetches `/v1/capabilities` once on load, disables only
unavailable options, attaches the stable reason as visible helper text and an accessible label,
selects the effective defaults, and disables submission only when the requested operation has no
valid path.

- [ ] **Step 1: Write failing packaged-configuration tests**

  Extend the injected JSON contract with only `public_demo_enabled`. Assert enum/default data still
  comes from the authoritative Python enums and that disabled mode exposes `false`. Assert the
  packaged page includes a capability status region, a recorded-showcase link, and no internal
  hostname or dependency URL.

- [ ] **Step 2: Write failing JavaScript contract assertions**

  Assert the shipped script:

  - fetches same-origin `/v1/capabilities` only when enabled;
  - validates `capabilities/v1` before mutation;
  - disables `<option>` elements instead of removing them;
  - uses `effective_default` values;
  - preserves `queryInput.value` during all failures;
  - recognizes structured application `429 busy` separately from an unstructured edge 429;
  - maps 503, 502/504/network, validation, and malformed responses to fixed messages;
  - never inserts a response body with `innerHTML`.

  Keep these as packaged-asset contract checks; live browser behavior is accepted later.

- [ ] **Step 3: Implement capability loading and control state**

  Split `setBusy` so it disables submit/select/number controls but not the claim textarea. After a
  request, restore each option to the availability state from the last valid snapshot rather than
  blindly enabling every control. Add visible messages:

  - busy: `Another live request is running. Try again shortly.`
  - edge limit: `The anonymous request allowance is exhausted. Try again later.`
  - dependency 503: `A required service is temporarily unavailable.`
  - network/502/504: `The live demo is offline. View the recorded showcase instead.`

  Do not display raw server text. Use `textContent` for every dynamic value.

- [ ] **Step 4: Preserve existing rendering contracts**

  Run the current supported-answer, exact insufficiency, citation-target, grouped-evidence, and
  contract-mismatch tests unchanged. Do not alter evidence cards, answer validation, or citations.

- [ ] **Step 5: Verify and commit the UI slice**

  ```bash
  uv run pytest tests/test_web_ui.py tests/test_http_api.py -q
  uv run ruff check src/scifact_rag/web tests/test_web_ui.py
  python3 tools/python_package_smoke.py
  git diff --check
  git add src/scifact_rag/web tests/test_web_ui.py
  git commit -m "feat: expose public demo availability in the UI"
  git push
  ```

### Task 5: Upgrade the GitHub Pages showcase into the durable entry point

**Files:**

- Modify: `docs/showcase/scifact-ui/index.html`
- Modify: `docs/showcase/scifact-ui/showcase.css`
- Create: `docs/showcase/scifact-ui/showcase.js`
- Create: `docs/showcase/scifact-ui/offline.html`
- Create: `tests/test_showcase.py`

**Interfaces:**

- Readiness URL: `https://scifact.ediacarian.dedyn.io/readyz`
- Live UI URL: `https://scifact.ediacarian.dedyn.io/`
- Durable recording: existing MP4/poster/VTT/GIF assets

- [ ] **Step 1: Write failing static-showcase tests**

  Parse the HTML without network access. Require the existing recording, captions, provenance, and
  research-only boundary; a disabled-by-default **Open live demo** link; a status region; an
  explicit Retry button; local `showcase.js`; and `offline.html`. Assert there is no automatic
  polling, analytics, storage, cookie, or claim field.

- [ ] **Step 2: Implement the one-shot readiness check**

  On `DOMContentLoaded`, call readiness once with `GET`, `Accept: application/json`, no credentials,
  and a short `AbortController` timeout. Enable the live link only for HTTP 200 with the exact
  `readiness/v1` ready body. On any other result, keep the recording fully usable and show a concise
  offline message. Retry only on an explicit button click.

- [ ] **Step 3: Add the edge fallback page**

  `offline.html` must be small, self-contained, and free of JavaScript. State that the live demo is
  temporarily unavailable, link to the recorded showcase and repository, and preserve the
  research-only boundary. It must not claim that the failed Search/Answer succeeded.

- [ ] **Step 4: Verify static publication locally**

  ```bash
  uv run pytest tests/test_showcase.py -q
  python3 -m http.server 8765 --directory docs
  ```

  In a second terminal, require HTTP 200 for the showcase, script, stylesheet, offline page, MP4,
  poster, and captions. Stop the server after the checks. Verify both narrow and desktop layouts
  and reduced-motion behavior in a browser.

- [ ] **Step 5: Commit and push the Pages slice**

  ```bash
  git diff --check
  git add docs/showcase/scifact-ui tests/test_showcase.py
  git commit -m "feat: add live readiness to the Pages showcase"
  git push
  ```

### Task 6: Wire explicit deployment configuration and reconcile durable contracts

**Files:**

- Modify: `compose.yaml`
- Modify: `tests/test_interface_contracts.py`
- Create: `docs/adr/0035-public-live-demo-edge.md`
- Create: `docs/reports/issue-27-public-live-demo.md`
- Modify: `harness/capabilities.json`
- Modify: `harness/project.yaml`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/project/technical-reference.md`
- Modify: `docs/project/roadmap.md`
- Modify: `docs/project/handoff.md`

- [ ] **Step 1: Write failing Compose/interface tests**

  Assert only the `api` service receives the two public-demo variables, both have safe disabled
  defaults, port 8090 remains `127.0.0.1:8090:80`, the command has exactly one worker, MCP and model
  ports remain loopback, and no new service/volume/network/dependency is added.

- [ ] **Step 2: Add the explicit Compose settings**

  ```yaml
  SCIFACT_PUBLIC_DEMO_ENABLED: ${SCIFACT_PUBLIC_DEMO_ENABLED:-false}
  SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN: ${SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN:-https://stauntonjr.github.io}
  ```

  Do not enable the mode in the committed default. The DGX operator opts in through deployment
  environment after the application checks pass.

- [ ] **Step 3: Record ADR-0035**

  Accept the two-variable configuration, non-inference capability service, shared process-local
  slot, exact readiness CORS, Pages-first public presentation, and separate VPS edge. Explicitly
  supersede only ADR-0032's and ADR-0034's non-public/loopback presentation statements when public
  mode is enabled. Preserve their framework, composition, validation, result, and same-origin UI
  decisions. Record the one-worker revisit trigger.

- [ ] **Step 4: Reconcile active capability and project contracts**

  Extend only the active HTTP/web implementation paths and focused checks in
  `harness/capabilities.json`. Update `harness/project.yaml` to include the bounded best-effort live
  demo while retaining production/multi-node operation, a supported third-party API, and automated
  lifecycle as out of scope. Do not activate an inactive capability.

- [ ] **Step 5: Update operator and hiring-manager documentation**

  Keep README concise: recorded showcase first, live-demo link second, honest best-effort status,
  no uptime or clinical claims. Put environment variables, endpoint schemas, startup sequence,
  failure semantics, Pages fallback, and cross-repository ownership in the technical reference and
  handoff. Add an acceptance matrix to the Issue #27 report with `pending` status for live evidence.

- [ ] **Step 6: Verify and commit the contract slice**

  ```bash
  uv run pytest tests/test_interface_contracts.py tests/test_showcase.py -q
  docker compose config --quiet
  python3 -m json.tool harness/capabilities.json >/dev/null
  python3 tools/github_planning.py audit --offline
  python3 tools/product_version.py
  git diff --check
  git add compose.yaml tests/test_interface_contracts.py docs/adr/0035-public-live-demo-edge.md docs/reports/issue-27-public-live-demo.md harness/capabilities.json harness/project.yaml README.md CHANGELOG.md docs/project
  git commit -m "docs: define the bounded public demo contract"
  git push
  ```

### Task 7: Verify the DGX application boundary before any public routing

**Files:**

- Modify: `docs/reports/issue-27-public-live-demo.md`

- [ ] **Step 1: Run the complete focused application suite**

  ```bash
  uv run pytest tests/test_public_demo.py tests/test_health_adapters.py tests/test_http_api.py tests/test_web_ui.py tests/test_showcase.py tests/test_interface_contracts.py -q
  ```

- [ ] **Step 2: Record the release-impact recommendation before the full gate**

  Record `minor` because public-demo readiness/capability/error and deployment environment
  contracts are added without breaking existing request/result schemas. Do not tag, publish a
  release, or change the version without separate release authority.

- [ ] **Step 3: Run exactly one full repository gate on the final candidate**

  ```bash
  make smoke
  python3 tools/product_version.py
  git diff --check
  git status --short
  ```

  A failed full gate ends the attempt. Repair in one new attempt, rerun affected checks, and then
  run one new final full gate; do not repeatedly run the full gate against a moving candidate.

- [ ] **Step 4: Obtain independent application review**

  Review exact contract shapes, dependency classification, no-inference proof, semaphore ordering
  and release paths, CORS scope, log privacy, disabled-mode compatibility, one-worker enforcement,
  UI failure mapping, Pages accessibility, and non-duplication of strategy/application logic.

- [ ] **Step 5: Rebuild and enable only the DGX API service**

  With explicit deployment authorization and after inspecting current workload state:

  ```bash
  SCIFACT_PUBLIC_DEMO_ENABLED=true SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN=https://stauntonjr.github.io docker compose up -d --build api
  ```

  Do not restart PostgreSQL or model services merely to deploy the API. Verify loopback
  `/healthz`, `/readyz`, `/v1/capabilities`, supported Search, supported Answer, exact
  insufficiency, unavailable strategy, overlapping busy response, and recovery after one
  dependency loss. Search API/Uvicorn logs for unique claim sentinels and require zero matches.

- [ ] **Step 6: Commit retained DGX evidence and push**

  Update the report with exact application revision, image digest, settings (without secrets),
  timestamps, commands, redacted responses, and evidence status. Do not mark public deployment
  accepted yet.

  ```bash
  git add docs/reports/issue-27-public-live-demo.md
  git commit -m "docs: record public demo application acceptance"
  git push
  ```

### Task 8: Run the shared public acceptance gate and close only after the edge plan passes

**Files:**

- Modify: `docs/reports/issue-27-public-live-demo.md`
- Modify: `docs/project/handoff.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Require the VPS plan's private-path gate**

  Do not enable the Pages live link or claim public availability until the VPS report identifies
  the deployed vps-srv revision, Tailscale Serve status, Traefik config digest, DNS record, and TLS
  certificate.

- [ ] **Step 2: Execute the twelve-case public matrix from the design**

  Cover DNS/TLS; supported answer/citations; exact insufficiency; Search; disabled optional
  strategy; overlapping busy response; separate rate limits; dependency loss/restoration; DGX
  outage/Pages fallback; kill switch/restoration; external-port isolation; and log privacy. Use
  unique harmless sentinels for privacy checks. Distinguish deterministic fixtures from bounded
  live inference.

- [ ] **Step 3: Enable the Pages live link only after acceptance**

  The page's readiness logic already fails closed; update only any `pending` presentation text
  required by the accepted public URL. Recheck both the live and recorded paths from a public
  browser.

- [ ] **Step 4: Reconcile and close**

  Record final URLs, revisions, digests, timestamps, residual best-effort risks, and rollback
  instructions. Close Issue #27 and move its Project item to Done only after exact-SHA CI and the
  coordinated VPS acceptance are green. Keep VPS Issue #4 independently owned and close it from
  its repository.

- [ ] **Step 5: Push the final reconciliation commit**

  ```bash
  git add docs/reports/issue-27-public-live-demo.md docs/project/handoff.md CHANGELOG.md
  git commit -m "docs: accept the bounded public live demo"
  git push
  ```

## Stop conditions

Stop and return to design review if implementation requires multiple Uvicorn workers, a second
public hostname, a public DGX listener, broad CORS, automatic model lifecycle, a durable quota
store, a supported third-party API, a new runtime dependency, changes to scientific results, or
VPS-hosted SciFact compute. Stop deployment without changing the accepted application if the
tailnet path, DNS authority, TLS resolver, or clean-vs-live VPS file boundary cannot be verified.
