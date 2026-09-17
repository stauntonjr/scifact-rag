# Thin HTTP API Adapter Design

Date: 2026-09-17

Governing issue: [#11](https://github.com/stauntonjr/scifact-rag/issues/11)

Status: owner-approved design pending written-spec review

## Objective

Activate the existing `http-api-interface` capability with one thin, read-only JSON adapter over
the accepted SciFact `RagApplication`. The adapter gives local consumers typed, versioned access to
liveness, retrieval, and grounded generation while keeping all scientific and product behavior in
the existing application layer.

The HTTP and CLI paths must produce the same normalized search hits and answers for the same query,
limit, retrieval strategy, generation-context strategy, application dependencies, and stored data.

## Non-goals

This phase does not add ingest, evaluation, diagnostics, administration, authentication, TLS,
CORS, public ingress, rate limiting, streaming, asynchronous jobs, model lifecycle management,
MCP, a web UI, new retrieval or generation behavior, graph features, or production-readiness
claims. It does not convert domain dataclasses to Pydantic or introduce a general service layer.

## Capability disposition

- `http-api-interface`: activate under owner-approved Issue #11 with the exact implementation,
  dependency, documentation, and acceptance paths defined here.
- `application-composition-root`: use active; it remains the only place that wires concrete stores,
  models, retrievers, generators, and context assemblers.
- `cli-interface`: use active as the parity reference; its behavior is not moved into HTTP code.
- every other inactive capability: not applicable. This work does not independently recreate MCP,
  web, memory, security, graph, or architecture-analysis responsibilities.

## Selected solution

Adopt FastAPI and Uvicorn following the bounded comparison in
`docs/research/scifact-rag-http-api.md`. FastAPI owns only the transport boundary: parsing, schema
validation, response serialization, OpenAPI, and HTTP status codes. Uvicorn owns the local ASGI
process. Existing dataclasses remain the canonical application results.

```text
local HTTP client
       |
       v
FastAPI request model and route
       |
       v
injected application resolver --------> existing composition root
       |                                      |
       v                                      v
RagApplication.search/ask             existing ports and adapters
       |
       v
explicit response-model conversion
       |
       v
versioned JSON response
```

No route handler imports or instantiates a store, embedder, retriever, reranker, generator, or
context assembler.

## Construction and application lifetime

The HTTP module exposes two constructors:

```python
def create_http_app(resolver: ApplicationResolver) -> FastAPI: ...
def build_http_app() -> FastAPI: ...
```

`ApplicationResolver` is a callable transport dependency that accepts a retrieval strategy and a
generation-context strategy and returns a `RagApplication`. `create_http_app` receives it
explicitly, allowing unit and parity tests to inject deterministic applications without model,
database, or network construction.

`build_http_app` is the runtime factory. It supplies a bounded, process-local cached resolver whose
cache key is `(retrieval_strategy, generation_context_strategy)`. Cache misses delegate to the
existing `composition.build_application`; endpoint handlers never assemble adapters themselves.
Search requests resolve with `whole-document` as the unused context key so equivalent searches
share one application. The cache is bounded by the finite enum combinations and exposes no cache
control over HTTP.

Compose starts the service with Uvicorn's application-factory form:

```text
uvicorn scifact_rag.http_api:build_http_app --factory --host 0.0.0.0 --port 80 --workers 1
```

The service deliberately runs one process. Synchronous route functions call the synchronous
application API; no asynchronous wrapper, job system, or concurrency promise is introduced.

## HTTP contract

The FastAPI document version is `1.0.0`; public operation paths are under `/v1`. Every successful
response and every project-owned error response includes a literal `schema_version`. Unknown JSON
fields are rejected. Request bodies use JSON only.

Queries are stripped only for emptiness validation; the original query string is passed unchanged
to the application. A query must contain at least one non-whitespace character and may contain at
most 4,096 Unicode code points. The boundary rejects invalid input before resolving or invoking an
application.

### `GET /healthz`

Returns HTTP 200:

```json
{"schema_version": "health/v1", "status": "ok"}
```

This is process liveness only. It does not load a model, resolve an application, query PostgreSQL,
or probe downstream model services. Readiness and dependency diagnosis remain operational checks,
not part of this slice.

### `POST /v1/search`

Request model:

```json
{
  "schema_version": "search-request/v1",
  "query": "scientific claim",
  "limit": 5,
  "strategy": "pooled-coref-interval-content-max-colbert"
}
```

- `schema_version` is required and must be exactly `search-request/v1`.
- `limit` defaults to 5 and is bounded to 1 through 100, matching the CLI.
- `strategy` defaults to the existing `DEFAULT_RETRIEVAL_STRATEGY` and accepts exactly the existing
  `RetrievalStrategyName` values.

Response model:

```json
{
  "schema_version": "search-response/v1",
  "hits": [
    {"doc_id": "123", "title": "Title", "text": "Abstract", "score": 0.75}
  ]
}
```

Hit order is preserved. `doc_id`, `title`, `text`, and finite `score` map directly from each
`SearchHit`; HTTP performs no ranking, normalization, filtering, or citation logic.

### `POST /v1/ask`

Request model:

```json
{
  "schema_version": "ask-request/v1",
  "query": "scientific claim",
  "limit": 5,
  "strategy": "pooled-coref-interval-content-max-colbert",
  "context_strategy": "whole-document"
}
```

- `schema_version` is required and must be exactly `ask-request/v1`.
- `limit` defaults to 5 and is bounded to 1 through 20, matching the CLI.
- `strategy` and `context_strategy` default to the existing CLI defaults and accept exactly the
  existing enum values.

Response model:

```json
{
  "schema_version": "answer/v1",
  "query": "scientific claim",
  "text": "insufficient evidence",
  "citations": [],
  "model": "model-id",
  "evidence": []
}
```

Evidence entries use the same shape as search hits. Evidence order, parent document identifiers,
answer text, citations, and model identifier map directly from `Answer`. The HTTP layer must not
reinterpret the application's exact `insufficient evidence` result or reconstruct citations.

## Errors and information boundary

Transport validation failures return HTTP 422 with:

```json
{
  "schema_version": "error/v1",
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [{"location": ["body", "query"], "message": "...", "type": "..."}]
  }
}
```

Details may identify fields and validation rules but must not echo the rejected request value.
Invalid schema versions, enum values, limits, unknown fields, malformed JSON, blank queries, and
overlong queries are rejected before the resolver or application is called.

Unexpected resolver or application exceptions return HTTP 500 with the fixed public envelope:

```json
{
  "schema_version": "error/v1",
  "error": {"code": "internal_error", "message": "The request could not be completed"}
}
```

The server logs the exception through the module logger, but the response contains no exception
text, stack trace, configuration, or raw request body. The adapter performs no retries. Framework
404 and 405 responses may retain FastAPI's standard shape because they expose no application
failure; only the three documented operations form the versioned product contract.

## OpenAPI and response integrity

FastAPI generates OpenAPI from explicit request and response models. Route decorators declare a
response model; handlers never return `dataclasses.asdict` directly. Boundary conversion functions
copy every field explicitly, preventing newly added dataclass fields from leaking automatically.
Response models reject non-finite scores and are validated during tests.

Pydantic types stay in `scifact_rag.http_api`. Domain, port, application, composition, CLI, and
adapter modules remain framework-neutral.

## Compose boundary

Add an `api` service using the existing application image, environment, data/artifact mounts,
model cache, host gateway, and PostgreSQL health dependency. Override only the command with the
Uvicorn factory invocation. Publish `127.0.0.1:8090:80`; no wildcard host binding is exposed from
Docker to the workstation network.

The container's internal `0.0.0.0` bind is required for Docker port forwarding and does not alter
the loopback-only host publication. No CORS middleware is installed. Downstream reranker,
late-interaction, ranker, and generator addresses retain the existing composition settings.

## Test and acceptance design

The implementation adds focused tests proportional to the three-operation adapter:

1. construct the app with a deterministic resolver and assert `/healthz` does not resolve it;
2. assert valid search and ask requests map all request fields and result fields exactly;
3. assert exact `insufficient evidence`, empty citations, and parent evidence survive unchanged;
4. parameterize invalid schema version, JSON shape, unknown field, query, limit, strategy, and
   context strategy, asserting 422 and zero resolver/application calls;
5. assert a raised resolver/application exception produces only the fixed 500 envelope;
6. assert OpenAPI exposes exactly the documented product operations and versioned schemas;
7. drive CLI and HTTP through equivalent fakes and compare normalized JSON results for search and
   ask, including parent-document citations.

The live loopback Compose acceptance starts the API with the existing data and services and records:

- liveness;
- one supported answer with citations constrained to returned parent evidence;
- one exact `insufficient evidence` answer;
- the strategy and context strategy used;
- HTTP status and response-schema validation.

The live smoke is acceptance evidence, not a new model-quality evaluation. It must not tune
retrieval, prompts, thresholds, or models.

## Documentation and capability activation

Implementation updates:

- `harness/capabilities.json` with an active contract naming owner approval, FastAPI/Uvicorn,
  implementation paths, and focused checks;
- an accepted ADR for the HTTP boundary and framework decision;
- README usage for a hiring-manager-readable local demonstration;
- the technical reference, roadmap, handoff, and changelog;
- canonical live acceptance evidence if the existing artifact policy requires a report.

MCP and web UI remain visibly inactive next capabilities. Their later adapters should call the
same application layer, not proxy through HTTP unless a separately approved deployment boundary
requires it.

## Verification gate

Before merge:

- lock and package metadata agree on FastAPI and Uvicorn;
- formatting, lint, static typing, unit tests, package smoke, and Compose validation pass;
- focused HTTP contract and CLI parity tests pass;
- affected database/model integration checks pass;
- the live loopback smoke produces retained evidence;
- an independent review finds no application policy moved into the HTTP adapter;
- Issue #11 acceptance criteria, capability status, ADR status, handoff, and changelog agree.

## Revisit triggers

Return to design rather than expanding this slice if implementation requires authentication,
non-loopback exposure, streaming, asynchronous jobs, another process, a new domain use case, model
lifecycle ownership, or changes to retrieval/generation semantics. Measured resource lifetime or
thread-safety failures may justify explicit startup/shutdown management, but not an unbounded web
platform refactor.
