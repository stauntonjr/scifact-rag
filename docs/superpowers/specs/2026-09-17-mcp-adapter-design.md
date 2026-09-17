# Thin MCP Adapter Design

Date: 2026-09-17

Governing issue: [#12](https://github.com/stauntonjr/scifact-rag/issues/12)

Status: revised after bounded written review; awaiting owner confirmation

## Objective

Activate the existing `mcp-interface` capability with one thin, read-only MCP server over the
accepted SciFact `RagApplication`. The adapter gives one named agent client typed access to the
proven search and grounded-answer use cases while keeping all scientific and product behavior in
the application layer.

The first accepted consumer is the official MCP Python SDK v2 `Client` running on the DGX. It
connects over Streamable HTTP to `http://127.0.0.1:8091/mcp`.

## Non-goals

This phase does not add resources, prompts, stdio acceptance, a Mac connection path, SSH tunnels,
authentication, TLS, public or tailnet exposure, multiple workers, administration, ingest,
evaluation, model management, server-to-client callbacks, tracing exporters, web UI, new retrieval
or generation behavior, or a general agent gateway.

## Capability disposition

- `mcp-interface`: activate under owner-approved Issue #12 with the exact dependency,
  implementation, documentation, and acceptance paths defined here.
- `application-composition-root`: use active; it remains the only place that wires stores, models,
  retrievers, generators, and context assemblers.
- `cli-interface` and `http-api-interface`: use active as parity references. MCP does not proxy
  through either interface or move their behavior.
- `product-validation-challenges`: use active only through the existing affected integration gate;
  no new challenge cases are created unless implementation exposes a deterministic defect.
- every other inactive capability: not applicable. This work does not independently recreate web,
  memory, graph, architecture-analysis, complexity, provenance, or role-parallelism responsibilities.

## Selected solution

Adopt plain `mcp==2.2.0` following `docs/research/scifact-rag-mcp.md`. The high-level `MCPServer`
owns protocol negotiation, discovery, input/output schemas, structured results, Streamable HTTP,
and the unexpected-exception boundary. The project owns only the typed transport models, one
refusal-only input-validation middleware, two tool handlers, domain-result mapping, application
resolver, Compose process, and acceptance evidence.

```text
official MCP Python SDK v2 Client on DGX
                    |
                    v
       Streamable HTTP 127.0.0.1:8091/mcp
                    |
                    v
      strict refusal middleware, then MCPServer discovery/dispatch
                    |
                    v
           search_scifact / answer_scifact
                    |
                    v
         injected application resolver --------> existing composition root
                    |                                      |
                    v                                      v
        RagApplication.search/ask                 existing ports/adapters
                    |
                    v
       explicit versioned result conversion
```

No tool handler imports or instantiates a store, embedder, retriever, reranker, generator, or
context assembler. MCP does not call the HTTP API.

## Module and construction boundary

Create `src/scifact_rag/mcp_server.py` containing:

- transport-only Pydantic result models;
- strict project-owned Pydantic argument models, reusable annotated input types, and a
  non-whitespace validator;
- one refusal-only `tools/call` middleware;
- an `ApplicationResolver` protocol matching the HTTP adapter's conceptual dependency without
  importing the HTTP module;
- explicit `SearchHit` and `Answer` conversion functions;
- `create_mcp_server(resolver) -> MCPServer` for deterministic tests;
- `build_mcp_server() -> MCPServer` for runtime composition;
- `main()` and a module guard that run Streamable HTTP.

The runtime resolver is bounded with `lru_cache` across the finite retrieval-strategy and
generation-context-strategy product. Search resolves with `whole-document` as its unused context
strategy so equivalent search calls share one application. Cache misses call the existing
`composition.build_application` function.

The module must remain import-safe: importing it registers no live service, opens no socket,
connects to no database, and loads no model.

## MCP server identity and discovery

The server name is `SciFact RAG` and its instructions state that it searches the public SciFact
corpus and answers only from supplied evidence. It registers exactly two tools in this order:

1. `search_scifact`;
2. `answer_scifact`.

No resources, resource templates, or prompts are registered. Acceptance checks the set of tool
names rather than depending on list order, while schema snapshots inspect each named tool.

Both tool definitions carry `readOnlyHint=true` and `openWorldHint=false`. They do not claim
idempotence. `answer_scifact` documentation says that a call invokes configured retrieval and model
inference and may consume significant compute even though it mutates no project data.

Annotations are client hints, not enforcement. The actual no-mutation property follows from the
tool surface: handlers can only call the existing `search` and `ask` application methods.

## Input contract

MCP already versions and discovers tool schemas, so callers do not send a redundant
`schema_version` argument. This Issue defines the initial tool contract as v1; any incompatible
argument change requires a new public-contract decision.

Define one reusable query type:

```python
QueryText = Annotated[
    str,
    Field(min_length=1, max_length=4096),
    AfterValidator(require_non_whitespace_query),
]
```

The validator checks `value.strip()` only for emptiness and returns the original string unchanged.
The application receives exactly what the client supplied.

Define strict bounded integer aliases so JSON booleans, strings, and floats do not coerce:

```python
SearchLimit = Annotated[int, Field(strict=True, ge=1, le=100)]
AnswerLimit = Annotated[int, Field(strict=True, ge=1, le=20)]
```

### `search_scifact`

Arguments:

```text
query: QueryText
limit: SearchLimit = 5
strategy: RetrievalStrategyName = DEFAULT_RETRIEVAL_STRATEGY
```

The handler resolves an application with the supplied retrieval strategy and
`GenerationContextStrategyName.WHOLE_DOCUMENT`, then calls `application.search(query, limit)` once.

### `answer_scifact`

Arguments:

```text
query: QueryText
limit: AnswerLimit = 5
strategy: RetrievalStrategyName = DEFAULT_RETRIEVAL_STRATEGY
context_strategy: GenerationContextStrategyName = WHOLE_DOCUMENT
```

The handler resolves the exact strategy pair and calls `application.ask(query, limit)` once.

Define one Pydantic argument model per tool using these exact fields and defaults. Both use
`ConfigDict(extra="forbid", hide_input_in_errors=True)`. These models are the runtime source of the
strict input policy; focused tests compare their fields, defaults, enums, and constraints with the
SDK-published schemas so the policy and discovery contracts cannot drift silently.

SDK v2.2.0's generated top-level argument model ignores unknown fields, and its native validation
error includes Pydantic details that can contain the rejected value. One server middleware corrects
both behaviors before tool dispatch:

```python
async def enforce_tool_arguments(ctx, call_next):
    if ctx.method != "tools/call":
        return await call_next(ctx)
    model = argument_model_for_recognized_tool(ctx.params)
    if model is None:
        return await call_next(ctx)
    try:
        model.model_validate(raw_arguments(ctx.params))
    except ValidationError:
        raise MCPError(
            code=INVALID_PARAMS,
            message=f"Invalid arguments for tool {tool_name(ctx.params)}",
        ) from None
    return await call_next(ctx)
```

The middleware uses the public `MCPServer(middleware=[...])` API only to refuse invalid recognized
calls. It does not rewrite parameters, return successful results, intercept unknown tool names, or
implement protocol framing. The Pydantic exception is neither logged nor attached as error data.
Consequently unknown arguments, invalid enums, blank or overlong queries, and invalid limits yield
a fixed protocol `INVALID_PARAMS` error before resolver or application invocation. The exact
v2.2.0 pin bounds this provisional SDK hook; any SDK upgrade reopens the decision.

## Structured output contract

Return Pydantic objects so the SDK publishes and validates an `outputSchema` and emits
`structuredContent`. Models use `extra="forbid"`; finite scores are required.

### Search

`search_scifact` returns:

```json
{
  "schema_version": "mcp-search-result/v1",
  "hits": [
    {"doc_id": "123", "title": "Title", "text": "Abstract", "score": 0.75}
  ]
}
```

Hit order and all four `SearchHit` fields map directly. MCP performs no ranking, normalization,
filtering, truncation, or citation logic.

### Answer

`answer_scifact` returns:

```json
{
  "schema_version": "mcp-answer-result/v1",
  "query": "scientific claim",
  "text": "insufficient evidence",
  "citations": [],
  "model": "model-id",
  "evidence": []
}
```

Evidence entries use the search-hit shape. Query, answer text, citation order, model identifier,
and evidence order map directly from `Answer`. The tool does not reinterpret exact
`insufficient evidence` or reconstruct citations.

The MCP schema-version literals are transport contract identifiers. Parity tests remove only that
transport wrapper and compare all application fields with the CLI/HTTP-normalized form.

## Failure boundary

Input-policy failures are protocol `MCPError`s with code `INVALID_PARAMS` produced by the refusal
middleware before SDK tool dispatch. Tests assert the fixed message, absent error data, absence of
the rejected value from both string and structured public error representations, and zero
resolver/application calls. They separately cover unknown fields and invalid values for both
tools. Public errors name only the tool, never the invalid field, constraint, or value.

Unexpected resolver or application exceptions are not caught and reworded by project code. MCP
SDK v2.2 logs the traceback server-side and returns a sanitized tool failure containing the tool
name but not exception text. Tests inject a distinctive secret-like exception message and prove it
is absent from all public content and structured output.

The adapter performs no retries. A client may choose whether to retry, but retry policy is not part
of this server contract.

## Runtime and Compose boundary

`main()` builds the server and runs:

```text
transport=streamable-http
host=0.0.0.0
port=80
streamable_http_path=/mcp
stateless_http=true
json_response=true
```

JSON responses are sufficient because neither tool uses progress, elicitation, sampling, or any
server-to-client callback. Stateless mode avoids legacy HTTP session storage; the official v2
client uses the current sessionless protocol automatically.

Add an `mcp` Compose service using the existing application image, environment, data/artifact
mounts, model cache, host gateway, and PostgreSQL health dependency. Override the image CLI
entrypoint with:

```text
uv run --no-dev python -m scifact_rag.mcp_server
```

Publish exactly `127.0.0.1:8091:80`. The internal wildcard bind exists only for Docker forwarding.
The service has one Python process and no replica or multi-worker configuration. It defines no
authentication, CORS, TLS, public ingress, or additional health endpoint.

## Test design

Focused tests use the official in-memory `Client(server)` path and deterministic fake applications:

1. discover exactly the two named tools and no resources or prompts;
2. inspect input/output schemas, descriptions, and read-only/closed-world annotations;
3. call search and answer and verify every argument passed to the resolver/application exactly;
4. verify every result field, order, schema version, parent citation, and exact insufficiency;
5. parameterize unknown fields, invalid schema shapes, queries, limits, and enums for both tools;
   assert fixed `INVALID_PARAMS`, no error data, no rejected-value disclosure, and zero calls;
6. prove the registered schemas and strict validation models agree on fields, defaults, enums, and
   constraints;
7. inject resolver and application failures and assert the SDK's separate bounded public tool
   errors without raw text;
8. exercise the runtime resolver cache without constructing real dependencies;
9. compare normalized deterministic CLI/application and MCP results;
10. assert Compose command, path, internal bind, one-process shape, and exact loopback publication;
11. assert the capability catalog names only actual dependency, implementation, and check paths.

The live Compose acceptance uses the official SDK v2 `Client` over the published URL and records:

- negotiated protocol/server identity and discovery of exactly two tools;
- one supported `answer_scifact` call with citations constrained to returned parent evidence;
- one exact `insufficient evidence` call with an empty citation list;
- the active strategies, response schema versions, model identifier, timing, image identity, host,
  and repository commit.

Live generated prose is not required to be byte-identical to CLI or HTTP calls. Deterministic fakes
prove exact parity; live cases prove only protocol, topology, citations, and insufficiency
invariants. No model-quality comparison or tuning occurs.

## Documentation and capability activation

Implementation updates:

- `harness/capabilities.json` with an active `mcp-interface` contract naming owner approval,
  official SDK dependency, exact paths, and focused checks;
- `harness/project.yaml` and the charter to place this bounded MCP service in scope and add MCP tool
  schemas to the public compatibility contract;
- capability matrix, roadmap, handoff, README, technical reference, and changelog;
- a retained acceptance report containing engineering, integration, protocol, and live evidence.

Web UI, durable memory, architecture analysis, complexity review, graph work, and role parallelism
remain inactive.

## Verification gate

Before merge:

- package metadata and lock resolve exactly MCP v2.2.0;
- the focused in-memory client, interface parity, capability, and Compose tests pass;
- formatting, lint, Pyright, unit tests, package smoke, and Compose validation pass;
- affected PostgreSQL/ColBERT integrations pass;
- the official DGX-local URL client completes discovery and both bounded live calls;
- exact-range diff hygiene is clean;
- independent review finds no transport policy or application semantics outside the accepted
  boundary;
- Issue #12, capability state, ADR, project contract, handoff, and acceptance report agree.

## Revisit triggers

Return to design rather than expanding this slice before any MCP SDK upgrade, or if implementation
requires a Mac client, tunnel, stdio acceptance, authentication, a non-loopback listener, another
tool or primitive, another service, project-owned protocol framing, server-to-client callbacks,
new domain semantics, application-layer changes, or retrieval/generation changes. A measured
resource lifetime or concurrency failure may justify explicit lifecycle management but not an
unbounded agent gateway.
