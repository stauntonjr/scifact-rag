# SciFact RAG MCP adapter existing-solution review

- Date inspected: 2026-09-17
- Governing issue: [#12](https://github.com/stauntonjr/scifact-rag/issues/12)
- Decision: select the smallest maintained MCP implementation that can expose the existing
  application layer to one named local client with typed, inspectable contracts.
- Disposition: adopt the official MCP Python SDK v2 and adapt the existing application composition
  root.
- Stop condition: current primary sources establish the supported release line, license, tool
  schemas, structured results, Streamable HTTP serving, in-memory tests, client behavior, and safe
  unexpected-error boundary. A general agent-framework survey is not needed.

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
- generated input and output schemas with strict validation;
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
- [`MCPServer` tools](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/servers/tools.md)
  derive input schemas from type annotations and Pydantic constraints, reject bad arguments before
  the handler runs, generate structured content from typed returns, and accept read-only/open-world
  annotations as client hints.
- The official [`Client`](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/client/transports.md)
  accepts a URL for Streamable HTTP and accepts a server object for in-memory tests. In-memory calls
  still traverse discovery, validation, and tool invocation through the real protocol layer.
- Current [error handling](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/servers/handling-errors.md)
  distinguishes tool errors from protocol errors. Unexpected handler failures are logged by the
  SDK and returned without exception details; tests can assert the public result.
- `MCPServer` creates OpenTelemetry spans, but the
  [documented default](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/opentelemetry.md)
  installs only the no-op API. No trace is collected or exported unless an SDK/exporter is added
  and configured; this project will add neither.
- The SDK is [MIT licensed](https://github.com/modelcontextprotocol/python-sdk/blob/main/LICENSE).
  No SDK source code will be copied into this repository.

## Candidate assessment

| Candidate | Fit | Disposition |
|---|---|---|
| Official MCP Python SDK v2.2 | Current supported line; high-level typed server, official client, Streamable HTTP, structured results, in-memory protocol tests, maintained error boundary, MIT license | **Adopt** |
| Official MCP Python SDK v1 | Supported only as a maintenance line and retains the older client/session APIs | Reject for new work |
| Official low-level `Server` API | Useful when exact hand-written protocol objects are required, but would make this project own validation, result conversion, and more error semantics | Reject for this adapter |
| Project-owned JSON-RPC or MCP framing | Duplicates a standardized protocol, expands compatibility risk, and violates the capability's reuse objective | Reject |
| MCP tools that proxy the accepted HTTP API | Avoids direct composition but adds a local network hop and makes one transport depend on another without an accepted deployment need | Reject |
| Defer MCP | Keeps CLI and HTTP sufficient for humans but does not provide the owner-approved external-agent interface | Reject after activation approval |

## Build, adopt, adapt, defer

- **Adopt:** plain `mcp>=2.2,<3`, using `MCPServer`, `Client`, typed tools, and Streamable HTTP.
  The CLI extra is unnecessary because the application supplies its own module entry point.
- **Adapt:** the existing `RagApplication`, composition root, strategy enums, query/limit contracts,
  dataclass results, parent-citation behavior, and loopback Compose policy.
- **Build:** one server module, two typed tool handlers, explicit domain-to-MCP result mapping, one
  bounded cached resolver, focused parity tests, Compose wiring, and retained live acceptance.
- **Defer:** resources, prompts, stdio acceptance, desktop-host configuration, Mac connection paths,
  auth, non-loopback deployment, multiple workers, tracing exporters, and every new application use
  case.

## Recommendation

Use the high-level `MCPServer` API. Expose a pure `create_mcp_server(resolver)` constructor for
deterministic in-memory tests and a `build_mcp_server()` runtime factory that delegates cache misses
to the existing composition root. Run the same server over Streamable HTTP in Compose. Do not proxy
through FastAPI and do not move MCP types into domain or application modules.

Return explicit Pydantic result models with literal schema versions. Use annotated query, limit,
and strategy arguments so malformed calls fail before resolution. Leave unexpected exceptions to
the SDK's sanitized failure path rather than returning exception text. Tool annotations declare
read-only closed-corpus behavior but do not claim that `answer_scifact` is free or deterministic;
its description states that it invokes model inference.

## Unknowns and verification plan

- Lock resolution must confirm that v2.2 is compatible with the project's existing FastAPI,
  Uvicorn, Pydantic, and HTTP dependencies.
- A focused probe must confirm exact v2.2 tool registration, annotation, structured-result, and
  error shapes before implementation relies on them.
- Compose acceptance must verify that an official URL client can discover and call the service at
  the exact `/mcp` path from the DGX host.
- The live supported and insufficient-evidence cases are operational evidence only; they do not
  re-evaluate model quality.

## Reopen triggers

Reopen this decision if implementation requires a non-official protocol layer, another MCP
primitive, another tool, a second service, application-semantic changes, stdio acceptance, a
Mac-hosted consumer, authentication, non-loopback publication, or a dependency beyond the official
SDK and packages it already requires. Reopen the dependency assessment if the supported v2 line or
its security policy changes materially before integration.
