# ADR-0032: Expose the application through a thin FastAPI adapter

- Status: accepted
- Date: 2026-09-17
- Decider: Jack Rory Staunton, human owner
- Governing issue: [#11](https://github.com/stauntonjr/scifact-rag/issues/11)

## Context

Issue #10 accepted the CLI vertical slice and its common `RagApplication` composition boundary.
Phase 6 next requires a network interface without creating a second retrieval, ranking, context,
generation, or citation architecture. The capability catalog already assigns that responsibility
to the inactive `http-api-interface`; the owner approved activating it for one bounded slice.

The existing application is synchronous and selects retrieval and generation-context strategies
when it is composed. A useful HTTP contract must preserve the CLI's selectable enums and defaults,
reject invalid transport input before constructing expensive model clients, and expose no raw
exception details. The existing application image also has a CLI entrypoint, so an API Compose
service must explicitly launch an ASGI server.

## Decision

Adopt FastAPI and Uvicorn as direct runtime dependencies. Keep Pydantic request and response models
inside `scifact_rag.http_api`; domain and application contracts remain frozen dataclasses.

Expose exactly:

- `GET /healthz` for process liveness without dependency probes;
- `POST /v1/search` for the existing retrieval use case;
- `POST /v1/ask` for the existing grounded-generation use case.

Every request requires a literal version, rejects unknown fields, and uses the existing strategy
enums. Search and ask retain their CLI defaults and limit bounds. Explicit conversion maps every
dataclass field into a response model; framework serialization never automatically publishes new
domain fields.

`create_http_app` accepts an application resolver for deterministic tests. The runtime
`build_http_app` factory supplies a process-local resolver cached by the finite retrieval/context
strategy pair. Cache misses call the existing composition root; route handlers never instantiate
stores, embedders, retrievers, rerankers, generators, or context assemblers.

Validation failures return a versioned 422 envelope without rejected values. Unexpected failures
are logged and return one fixed 500 envelope without exception text. The adapter retries nothing.

Run one synchronous Uvicorn worker in Compose and publish only `127.0.0.1:8090:80`. The container
binds internally to `0.0.0.0` only for Docker forwarding. No CORS, authentication, TLS, rate
limiting, public ingress, streaming, or asynchronous job behavior is added or implied.

## Consequences

### Positive

- CLI and HTTP exercise one application layer and produce normalized result parity.
- Generated OpenAPI documents the three typed product operations.
- Invalid requests cannot trigger model, database, or application composition work.
- Framework types remain replaceable because they do not cross the transport boundary.
- MCP and a small web UI can later reuse the application layer without copying HTTP policy.

### Negative

- The first request for a strategy pair pays its existing composition cost.
- A process-local cache does not coordinate resources across multiple workers; the service is
  deliberately fixed to one worker.
- Liveness does not prove PostgreSQL or model readiness.
- The loopback prototype is not suitable for untrusted or public traffic.

### Risks and mitigations

- **Semantic drift:** parity tests drive CLI and HTTP through equivalent applications and compare
  complete normalized hits, answers, evidence, and parent citations.
- **Accidental work on invalid input:** validation tests assert zero resolver and application calls.
- **Information leakage:** custom errors omit input values and unexpected exception details.
- **Resource duplication:** the finite resolver cache reuses one application per strategy pair.
- **Framework spread:** tests enforce framework ownership in the single HTTP module and capability
  paths remain explicit.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Starlette plus Uvicorn | Requires project-owned validation, serialization, and OpenAPI machinery without product value |
| Python `http.server` | Lacks the typed contract and is explicitly not recommended for production-style serving |
| One fixed application per API process | Cannot preserve the existing CLI strategy contract |
| Construct an application inside each route | Repeats expensive model wiring and moves composition into the transport |
| Proxy later adapters through HTTP | Adds a network dependency where direct application composition is sufficient |

## Verification and revisit trigger

Focused tests cover liveness isolation, strict request validation, mapping, exact insufficiency,
error isolation, resolver caching, OpenAPI, Compose/capability declarations, and CLI parity. The
repository gate, affected integrations, and one retained loopback acceptance run complete Issue
#11.

Revisit this decision before non-loopback exposure, multiple workers, authentication, TLS,
streaming, background jobs, or model-lifetime ownership. A measured thread-safety or resource-
lifetime failure may justify explicit startup/shutdown management; it does not authorize a general
web-platform refactor.
