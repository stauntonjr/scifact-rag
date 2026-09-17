# SciFact RAG MCP adapter existing-solution review

- Date inspected: 2026-09-17
- Governing issue: [#12](https://github.com/stauntonjr/scifact-rag/issues/12)
- Decision: select the smallest maintained MCP implementation that can expose the existing
  application layer to one named local client with typed, inspectable contracts.
- Disposition: adopt and pin the official MCP Python SDK v2.2.0, add one refusal-only validation
  middleware, and adapt the existing application composition root.
- Stop condition: current primary sources and a v2.2.0 in-memory probe establish the supported
  release, license, tool schemas, structured results, Streamable HTTP serving, client behavior,
  unexpected-error boundary, and the bounded correction needed for strict, non-disclosing input
  rejection. A general agent-framework survey is not needed.

## Decision boundary

The project needs two read-only MCP tools for the already accepted `search` and `ask` use cases.
The server must not own retrieval, ranking, context assembly, generation, citations, persistence,
or model lifecycle. The first named consumer is the official MCP Python SDK v2 `Client` running on
the DGX and connecting to `http://127.0.0.1:8091/mcp`.

The first deployment is Docker Compose on one DGX Spark with host-loopback publication. Resources,
prompts, stdio acceptance, Mac connectivity, SSH tunnels, authentication, TLS, non-loopback
publication, administration, ingest, evaluation, and web UI are outside this decision.

## Search method and comparison dimensions

Primary sources were inspected on 2026-09-17 in the canonical
`modelcontextprotocol/python-sdk` repository and its published SDK documentation. Search focused on
the current stable release, transport selection, tool schemas, structured output, testing, error
handling, license, and supported-version policy.

The important dimensions are:

- protocol conformance and current maintenance status;
- generated schemas plus an explicit strict-input policy;
- a first-party client for end-to-end acceptance;
- Streamable HTTP and in-memory testing through the same observable protocol behavior;
- safe failure behavior without project-owned JSON-RPC framing;
- Python 3.12 compatibility and synchronous-handler support;
- license compatibility, dependency cost, and replacement cost;
- preservation of the existing application and composition boundaries.

## Primary-source findings

- The official SDK's current stable line is v2. The latest release inspected is
  [v2.2.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0); v1 is a
  maintenance line. The repository supports Python 3.10 and later.
- The SDK documentation directs deployed services to
  [Streamable HTTP](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/index.md)
  and treats stdio as the local-subprocess transport. SSE is superseded and is not suitable for new
  work.
- [`MCPServer` tools](https://github.com/modelcontextprotocol/python-sdk/blob/v2.2.0/docs/servers/tools.md)
  derive input schemas from type annotations and Pydantic constraints, validate known arguments
  before the handler runs, generate structured content from typed returns, and accept
  read-only/open-world annotations as client hints.
- The v2.2.0 high-level server does **not** supply the complete input policy required here. Its
  [generated argument model](https://github.com/modelcontextprotocol/python-sdk/blob/v2.2.0/src/mcp/server/mcpserver/utilities/func_metadata.py#L87-L101)
  inherits a configuration that does not forbid extras, so an unknown tool argument is ignored and
  the handler runs. Its
  [tool validation-error path](https://github.com/modelcontextprotocol/python-sdk/blob/v2.2.0/src/mcp/server/mcpserver/tools/base.py#L134-L144)
  interpolates the Pydantic `ValidationError`, whose normal rendering can include a rejected value.
  Output-model `extra="forbid"` does not affect either input behavior.
- The official [`Client`](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/client/transports.md)
  accepts a URL for Streamable HTTP and accepts a server object for in-memory tests. In-memory calls
  still traverse discovery, validation, and tool invocation through the real protocol layer.
- Current [error handling](https://github.com/modelcontextprotocol/python-sdk/blob/v2.2.0/docs/servers/handling-errors.md)
  distinguishes tool errors from protocol errors. Unexpected handler failures are logged by the
  SDK and returned without exception details. That safe unexpected-exception boundary must not be
  generalized to argument-validation errors, which follow the separate value-disclosing path
  above.
- The SDK's documented
  [server middleware](https://github.com/modelcontextprotocol/python-sdk/blob/v2.2.0/docs/advanced/middleware.md)
  sees raw request parameters before SDK validation and explicitly supports refusing a request by
  raising `MCPError`. The API is provisional, so the project will use it only for this narrow
  refusal policy, pin v2.2.0, and require the focused probe before any SDK upgrade. It will not
  rewrite requests, answer requests itself, or frame JSON-RPC.
- `MCPServer` creates OpenTelemetry spans, but the
  [documented default](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/opentelemetry.md)
  installs only the no-op API. No trace is collected or exported unless an SDK/exporter is added
  and configured; this project will add neither.
- The SDK is [MIT licensed](https://github.com/modelcontextprotocol/python-sdk/blob/main/LICENSE).
  No SDK source code will be copied into this repository.

## Candidate assessment

| Candidate | Fit | Disposition |
|---|---|---|
| Official MCP Python SDK v2.2.0 plus refusal-only middleware | Current published release; high-level typed server, official client, Streamable HTTP, structured results, in-memory protocol tests, maintained unexpected-error boundary, and a documented pre-validation refusal hook for the two missing input guarantees | **Adopt and pin** |
| Official MCP Python SDK v1 | Supported only as a maintenance line and retains the older client/session APIs | Reject for new work |
| Official low-level `Server` API | Useful when exact hand-written protocol objects are required, but would make this project own validation, result conversion, and more error semantics | Reject for this adapter |
| Project-owned JSON-RPC or MCP framing | Duplicates a standardized protocol, expands compatibility risk, and violates the capability's reuse objective | Reject |
| MCP tools that proxy the accepted HTTP API | Avoids direct composition but adds a local network hop and makes one transport depend on another without an accepted deployment need | Reject |
| Defer MCP | Keeps CLI and HTTP sufficient for humans but does not provide the owner-approved external-agent interface | Reject after activation approval |

## Build, adopt, adapt, defer

- **Adopt:** plain `mcp==2.2.0`, using `MCPServer`, `Client`, typed tools, Streamable HTTP, and one
  refusal-only middleware. The exact pin bounds the provisional middleware contract. The CLI extra
  is unnecessary because the application supplies its own module entry point.
- **Adapt:** the existing `RagApplication`, composition root, strategy enums, query/limit contracts,
  dataclass results, parent-citation behavior, and loopback Compose policy.
- **Build:** one server module, two strict project-owned input models, one refusal-only validator,
  two typed tool handlers, explicit domain-to-MCP result mapping, one bounded cached resolver,
  focused parity tests, Compose wiring, and retained live acceptance.
- **Defer:** resources, prompts, stdio acceptance, desktop-host configuration, Mac connection paths,
  auth, non-loopback deployment, multiple workers, tracing exporters, and every new application use
  case.

## Recommendation

Use the high-level `MCPServer` API. Expose a pure `create_mcp_server(resolver)` constructor for
deterministic in-memory tests and a `build_mcp_server()` runtime factory that delegates cache misses
to the existing composition root. Run the same server over Streamable HTTP in Compose. Do not proxy
through FastAPI and do not move MCP types into domain or application modules.

Return explicit Pydantic result models with literal schema versions. Use project-owned Pydantic
models with `extra="forbid"`, strict bounded fields, and `hide_input_in_errors=True` as the source of
the input policy. A single SDK middleware inspects only recognized `tools/call` messages, validates
their raw `arguments`, and either passes the original request through unchanged or refuses it with
a fixed `INVALID_PARAMS` message. It discards the `ValidationError`; it never includes error text,
error data, or a rejected value in the public response. This occurs before SDK tool dispatch, so
neither the resolver nor the application is called. Unknown tool names continue to the SDK's own
normal not-found behavior.

This is the smallest supported correction: the middleware behavior is explicitly documented by
the SDK, while mutating generated argument models would be monkey-patching, an extension would
advertise a capability that does not exist, and the low-level server would make the project own
more validation and result conversion. The middleware does not rewrite or answer requests and the
project does not implement JSON-RPC framing.

Leave unexpected resolver/application exceptions to the SDK's distinct sanitized failure path
rather than returning exception text. Tool annotations declare read-only closed-corpus behavior
but do not claim that `answer_scifact` is free or deterministic; its description states that it
invokes model inference.

## Executable v2.2.0 probe

An isolated in-memory probe used the public `MCPServer(middleware=[...])` and `Client(server)` APIs
against the published `mcp==2.2.0` package. Its handler-call counter and public error assertions
demonstrated:

| Call | Public result | Handler calls after valid baseline |
|---|---|---:|
| valid query and strict integer limit | success | 1 |
| valid fields plus unknown `unexpected` argument containing `REJECTED_VALUE_SENTINEL` | `MCPError`, code `-32602` | 1 |
| `REJECTED_VALUE_SENTINEL` supplied as the strict integer limit | `MCPError`, code `-32602` | 1 |

For both rejected calls, the sentinel was absent from `str(error)` and the structured public
`ErrorData` representation. The error message was the fixed
`Invalid arguments for tool search_scifact`; no exception data was attached. This proves the
mechanism, not implementation or deployment readiness.

## Unknowns and verification plan

- Lock resolution must confirm that v2.2.0 is compatible with the project's existing FastAPI,
  Uvicorn, Pydantic, and HTTP dependencies.
- Focused repository tests must preserve the demonstrated strict-extra and non-disclosure behavior
  for both tools, verify the fixed `INVALID_PARAMS` error, and prove zero resolver/application calls.
- The registered SDK input schemas and project-owned validation models must have a focused
  field/default/constraint parity test so their intentionally separate responsibilities cannot
  drift silently.
- Compose acceptance must verify that an official URL client can discover and call the service at
  the exact `/mcp` path from the DGX host.
- The live supported and insufficient-evidence cases are operational evidence only; they do not
  re-evaluate model quality.

## Reopen triggers

Reopen this decision before upgrading from v2.2.0 because the chosen refusal hook is provisional,
or if implementation requires a non-official protocol layer, another MCP
primitive, another tool, a second service, application-semantic changes, stdio acceptance, a
Mac-hosted consumer, authentication, non-loopback publication, or a dependency beyond the official
SDK and packages it already requires. Reopen the dependency assessment if the supported v2 line or
its security policy changes materially before integration.
