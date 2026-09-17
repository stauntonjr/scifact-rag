# ADR-0033: Expose the application through a thin MCP adapter

- Status: proposed after bounded review correction; awaiting owner confirmation
- Date: 2026-09-17
- Decider: Jack Rory Staunton, human owner
- Governing issue: [#12](https://github.com/stauntonjr/scifact-rag/issues/12)

## Context

Issues #10 and #11 accepted the CLI and loopback HTTP interfaces over one common
`RagApplication` composition boundary. Phase 6 next calls for an MCP interface so an external agent
can use the proven search and answer operations without direct database, model, or storage access.
The capability catalog assigns this responsibility to the inactive `mcp-interface`; the owner
approved its activation with a named client and deployment path.

MCP is a standardized protocol with an official Python SDK. The current v2 line supplies typed
tool schemas, structured output, an official client, in-memory protocol tests, and Streamable HTTP.
Implementing protocol framing locally or routing MCP through the HTTP adapter would add machinery
without changing the SciFact use case.

## Decision

Adopt and pin the official MCP Python SDK v2.2.0 as a direct runtime dependency. Keep MCP models and
SDK types inside `scifact_rag.mcp_server`; domain and application contracts remain frozen
dataclasses.

Expose exactly two tools:

- `search_scifact`: retrieve ordered SciFact parent documents for a claim or question;
- `answer_scifact`: retrieve evidence and invoke the existing grounded generator, returning a
  cited answer or exact `insufficient evidence`.

Both tools accept the existing query, limit, retrieval-strategy, and—where applicable—generation-
context-strategy choices and defaults. Queries are validated for non-blank content and a 4,096-
character maximum without rewriting the value passed to the application. Limits retain the CLI
bounds: 1–100 for search and 1–20 for answer. Returned Pydantic models include literal MCP schema
versions and explicitly map every existing result field.

`create_mcp_server` accepts an application resolver for deterministic tests. The runtime
`build_mcp_server` factory supplies a finite process-local resolver cached by retrieval/context
strategy pair; misses delegate to `composition.build_application`. Tool handlers never instantiate
stores, embedders, retrievers, rerankers, generators, or context assemblers.

Tool annotations identify both tools as read-only and closed-corpus. This means they do not mutate
the corpus, configuration, or database. It does not mean calls are cost-free: `answer_scifact`
invokes the configured generator and its description says so. No idempotence claim is made about
generated text.

The SDK-generated v2.2.0 argument model does not reject unknown fields, and its native Pydantic
validation-error rendering can expose rejected values. Therefore, define project-owned Pydantic
argument models for both tools with `extra="forbid"`, strict constraints, and
`hide_input_in_errors=True`. Install one SDK-supported, refusal-only server middleware. For a
recognized `tools/call`, it validates raw `arguments` before SDK dispatch, passes valid requests
through unchanged, and converts any `ValidationError` into a fixed `INVALID_PARAMS` MCP error with
no error data. It neither rewrites nor answers requests. Thus unknown or invalid arguments cause
zero resolver/application calls and expose neither rejected values nor Pydantic error details.

The middleware API is provisional in v2.2.0; the exact dependency pin and focused in-memory probe
make any upgrade an explicit revisit point. Mutating SDK-generated models, custom protocol framing,
and using an advertised extension for local validation policy are prohibited. Unexpected resolver
or application failures remain on the SDK's separate sanitized tool-error boundary. The adapter
adds no retries.

Run one MCP server process in Docker Compose using Streamable HTTP at `/mcp`. Bind internally to
`0.0.0.0:80` for Docker forwarding and publish only `127.0.0.1:8091:80` on the DGX. Configure the
server as stateless for legacy HTTP clients and use JSON responses because these tools never call
back into the client. The official SDK v2 `Client` on the same DGX is the first accepted consumer.

Resources, prompts, stdio acceptance, Mac connectivity, SSH tunnels, authentication, TLS,
non-loopback publication, multiple workers, administration, ingest, evaluation, and web UI remain
outside this decision.

## Consequences

### Positive

- CLI, HTTP, and MCP reuse one application and composition boundary.
- The maintained SDK owns protocol framing, discovery, validation, negotiation, and client
  compatibility.
- Structured results preserve evidence and citation fields for agent consumers.
- In-memory client tests exercise discovery and tool calls without model or network construction.
- The service exposes no direct database or model-management capability.

### Negative

- MCP v2 becomes a direct runtime dependency and expands the versioned public interface.
- A separate MCP process may compose its own application resources when run beside the HTTP
  service; this phase makes no multi-process resource-sharing claim.
- A DGX-local client does not prove that a Mac-hosted client can connect.
- Tool calls are synchronous from the application perspective; no throughput guarantee is made.

### Risks and mitigations

- **Transport/application drift:** parity tests compare complete normalized search and answer
  results through an injected application.
- **Invalid calls doing expensive work:** tests assert malformed arguments cause zero resolver and
  application calls.
- **Information leakage:** middleware tests assert fixed `INVALID_PARAMS` errors contain neither
  raw Pydantic details nor rejected values; separate failure tests cover unexpected exceptions.
- **Schema/policy drift:** tests compare the registered tool fields, defaults, enums, and constraints
  with the strict project-owned validation models.
- **Tool-surface growth:** discovery tests require exactly two tools and empty resources/prompts.
- **Misleading read-only claims:** tool descriptions disclose inference work and avoid an
  idempotence claim.
- **Network-boundary drift:** Compose tests require exact host-loopback publication.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| MCP SDK v1 | Maintenance line with older client and session APIs; new work should use v2 |
| Low-level official server | Makes the project own validation and result/error conversion unnecessarily |
| Bespoke MCP/JSON-RPC implementation | Duplicates a maintained standardized capability |
| Proxy MCP tools through HTTP | Adds a transport-to-transport dependency without a deployment need |
| Stdio-first acceptance | Does not match the approved Compose-hosted service and named DGX client |
| Mac client in this phase | Requires a separately accepted connection path and deployment boundary |

## Verification and revisit trigger

Focused tests cover exact discovery, input schemas, annotations, strict validation, structured
mapping, exact insufficiency, fixed non-disclosing invalid-parameter errors, zero downstream calls,
bounded unexpected failures, finite resolver caching, empty resources/prompts,
Compose publication, capability declarations, and CLI/application parity. The complete gate,
affected PostgreSQL/ColBERT integrations, and a retained official-client live run complete Issue
#12.

Revisit before upgrading the MCP SDK, or before accepting a Mac client, SSH tunnel, stdio host,
non-loopback listener, authentication, another tool or MCP primitive, more than one server process,
server-to-client callbacks, or application-semantic changes. A measured resource-lifetime failure
may justify explicit lifecycle management but does not authorize a general agent gateway.
