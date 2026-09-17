# SciFact evidence-inspection web UI design

Date: 2026-09-17  
Status: accepted by the human owner  
Governing issue: [#13](https://github.com/stauntonjr/scifact-rag/issues/13)  
Human decider: repository owner

## Objective

Complete Phase 6 with the smallest useful browser interface for inspecting SciFact search and
answer results. The interface must reuse the accepted HTTP and application contracts and must not
become a second retrieval, ranking, generation, or citation implementation.

The primary user is a developer, researcher, or hiring manager who wants to submit one claim and
inspect the answer and the exact parent-document evidence supplied by the system.

## Solution assessment

Disposition: **adapt**.

The existing FastAPI process already owns the loopback HTTP boundary and exposes stable,
versioned search and answer operations. The UI will adapt that process by adding packaged static
assets and same-origin browser calls. Native HTML, CSS, DOM, and `fetch` APIs are sufficient. No
new runtime dependency, frontend build system, service, protocol, or license is justified.

## Scope

### Included

- One responsive page served at `GET /` by the existing FastAPI `api` service.
- Packaged CSS and JavaScript served at fixed `/assets/` paths by the same service.
- Search and Answer actions calling only `POST /v1/search` and `POST /v1/ask`.
- Existing query, limit, retrieval-strategy, and generation-context-strategy values.
- Answer, model, active strategies, ordered citations, evidence titles, document IDs, scores, and
  complete supplied parent-document text.
- Distinct exact-insufficient-evidence, validation-error, network/unavailable, loading, search,
  and answered states.
- Deterministic HTTP/static-contract tests, installed-wheel resource verification, one bounded live
  browser acceptance, capability activation, ADR, documentation, and retained evidence.

### Excluded

- React, Vue, another component framework, Node, a bundler, or external browser assets.
- A separate web container, reverse proxy, new port, or new Compose dependency.
- New HTTP endpoints, CORS, authentication, authorization, TLS, or non-loopback exposure.
- Browser persistence, accounts, saved searches, analytics, telemetry, or URL query state.
- Ingest, evaluation, administration, model-management, or configuration mutation controls.
- Retrieval, ranking, context-selection, generation, prompt, model, evidence, or citation changes.
- Graph work, LangGraph, streaming generation, or production deployment.

Discovery of any excluded requirement stops implementation and requires a scope revision.

## Architecture

```text
Browser at DGX loopback URL
        |
        | GET / and /assets/*
        v
FastAPI web presentation router ---- packaged HTML/CSS/JavaScript
        |
        | same-origin POST /v1/search or /v1/ask
        v
existing FastAPI transport models
        |
        v
existing RagApplication composition root
```

The browser never calls PostgreSQL, a model endpoint, or an application adapter directly. It does
not reconstruct application results. It renders the versioned HTTP response fields verbatim and
adds presentation-only labels and state.

## Components and ownership

### `src/scifact_rag/web/__init__.py`

This module owns only presentation delivery:

- load the three packaged assets with `importlib.resources`;
- create an `APIRouter` for `/`, `/assets/scifact.css`, and `/assets/scifact.js`;
- insert a small JSON configuration into the index containing the current retrieval enum values,
  current context enum values, and their accepted defaults;
- return explicit HTML, CSS, and JavaScript media types.

The configuration comes from `RetrievalStrategyName`, `DEFAULT_RETRIEVAL_STRATEGY`, and
`GenerationContextStrategyName`. This prevents a hand-maintained second list of strategies in
JavaScript. The JSON is encoded by Python and characters significant inside HTML are escaped
before insertion.

The router accepts no `RagApplication` or resolver and owns no search or answer route.

### `src/scifact_rag/web/index.html`

The document contains:

- a concise product header and limitation statement;
- one claim textarea (`required`, `maxlength=4096`);
- an advanced-controls region with retrieval strategy, context strategy, and result limit;
- separate Search and Answer submit buttons;
- a polite live-status region;
- a result summary region;
- an ordered evidence region.

The document uses landmarks, labels, fieldsets, headings, and buttons rather than clickable generic
containers. A no-script message explains that interaction requires JavaScript.

### `src/scifact_rag/web/scifact.js`

The script owns browser interaction and presentation state only.

At startup it parses the server-inserted configuration and populates the strategy controls. On a
Search action it sends:

```json
{
  "schema_version": "search-request/v1",
  "query": "...",
  "limit": 5,
  "strategy": "pooled-coref-interval-content-max-colbert"
}
```

On an Answer action it sends the corresponding `ask-request/v1` payload and adds the selected
`context_strategy`. Search constrains the limit to 1-100; Answer constrains it to 1-20. The form
uses the browser's constraint validation before a request. Buttons and controls are disabled only
while one request is active.

Response data is inserted with DOM text properties, never interpreted as HTML. Search results and
answer evidence preserve server order. Answer citations are rendered only when their document IDs
occur in supplied evidence. If the server ever returns a citation outside that evidence, the UI
shows a bounded response-contract error rather than inventing or linking evidence.

Exact `text == "insufficient evidence"` with empty citations and evidence produces the dedicated
insufficient state. Any contradictory shape produces the same bounded response-contract error.

HTTP validation errors show the fixed server message. HTTP 500, non-JSON responses, network
failures, and malformed response shapes show a fixed unavailable/error state without exception
text or response-body echoing.

### `src/scifact_rag/web/scifact.css`

The page uses a restrained evidence-oriented visual system: readable measure, strong typographic
hierarchy, neutral document cards, clear status colors, and no decorative animation. It supports
narrow mobile viewports, visible keyboard focus, system color preferences, and
`prefers-reduced-motion`. Evidence text remains selectable and is not truncated.

### `src/scifact_rag/http_api.py`

`create_http_app()` includes the web router. Existing `/healthz`, `/v1/search`, `/v1/ask`, request
models, response models, exception handlers, composition caching, and defaults remain unchanged.

## Interaction states

| State | Summary | Evidence area |
|---|---|---|
| Idle | Invitation to enter a scientific claim | Empty |
| Loading | Names Search or Answer operation | Previous result cleared |
| Search success | Result count and active retrieval strategy | Ordered hit cards |
| Supported/contradicted answer | Answer text, model, citations, active strategies | Ordered evidence cards |
| Insufficient evidence | Exact insufficiency message and active strategies | Explicitly empty |
| Validation error | Fixed request-validation explanation | Empty |
| Unavailable/error | Fixed retryable failure explanation | Empty |
| Contract mismatch | Fixed response-contract explanation | Empty |

The UI does not infer SciFact support/refutation labels from generated prose. It displays the model
answer exactly and preserves its evidence boundary.

## Packaging and deployment

The web assets live inside the `scifact_rag` Python package and must be present in the wheel. The
Hatch wheel configuration will explicitly include the web directory if the default package
selection does not retain it. Acceptance inspects and installs the built wheel, imports the package
resource path, and confirms all three assets exist.

The current Compose `api` service and `127.0.0.1:8090:80` publication remain unchanged. Rebuilding
that service is sufficient to deploy the UI. No other service is restarted except where Compose
must replace the `api` container with its newly built image.

## Error and trust boundaries

- All corpus and model text is untrusted display data and is inserted as text, not markup.
- The API remains the authority for request validation and bounded error envelopes.
- Browser-side validation improves usability but is not an authority boundary.
- The UI sends no credentials and stores no query or result data after page lifetime.
- A browser failure does not prove an application or model failure; acceptance distinguishes UI,
  API, and dependency observations.
- Read-only means no corpus, database, model, or configuration mutation. Answer still consumes
  model compute.

## Verification

### Deterministic checks

One focused `tests/test_web_ui.py` module will verify:

- `/` and every asset return the expected media type and stable identifying content;
- no application resolver is invoked while serving UI resources;
- configuration contains the exact current retrieval/context enum values and defaults;
- the HTML contains the required semantic controls, landmarks, live region, and no external asset
  reference;
- JavaScript contains the two versioned endpoint/request contracts, text-only rendering boundary,
  citation-to-evidence check, insufficiency condition, and fixed failure messages;
- CSS contains responsive, focus-visible, and reduced-motion rules.

Existing HTTP and interface-contract tests continue to prove the application behavior behind the
UI. A wheel build/install/resource probe proves packaged operation. Compose validation proves that
no topology expansion occurred.

### Live browser acceptance

Against the rebuilt loopback `api` service, retain four observations:

1. one supported claim renders an answer whose citations all resolve to displayed evidence;
2. one known unsupported claim renders exact insufficient evidence with no citations or evidence;
3. an invalid client value is rejected and rendered as a bounded validation state;
4. after the loaded page loses its API connection in a controlled reversible probe, a request
   renders the fixed unavailable state, and the service is restored and rechecked.

The acceptance report records the commit, image, host, browser path, queries, output boundaries,
latency, and restoration evidence. These observations prove local UI operation only.

## Documentation and capability activation

The implementation will:

- change `web-interface` from inactive to active with exact paths and focused checks;
- move the small UI into project scope in `harness/project.yaml`;
- add ADR-0034 recording same-process static delivery and same-origin API reuse;
- update the charter, roadmap, technical reference, handoff, README, and changelog;
- retain the Issue #13 browser acceptance report.

## Alternatives considered

| Alternative | Advantage | Reason not selected |
|---|---|---|
| Separate static container | Independent deployment lifecycle | Adds a service, port, CORS/reverse-proxy decision, and operational surface without product benefit |
| Server-render every result | Works without browser JavaScript | Duplicates the existing JSON application flow and couples presentation to backend request handling |
| React or another SPA framework | Rich component ecosystem | Adds Node/build/dependency machinery far beyond one evidence-inspection page |
| Keep CLI/API only | No implementation cost | Does not satisfy the approved interactive evidence-inspection workflow or complete Phase 6 |

## Release impact and revisit triggers

Recommended release impact is **minor** because this adds a new public browser interface while
preserving all existing CLI, HTTP JSON, MCP, and Compose environment contracts.

Revisit this design only if a measured user workflow requires multiple pages, persistent state,
streaming, non-loopback users, authentication, a separate deployment cadence, or a frontend build
system. Any such change requires a new Issue and ADR rather than incremental expansion of Issue
#13.
