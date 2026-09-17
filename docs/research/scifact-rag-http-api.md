# SciFact RAG HTTP adapter existing-solution review

- Date inspected: 2026-09-17
- Governing issue: [#11](https://github.com/stauntonjr/scifact-rag/issues/11)
- Decision: select the smallest maintained HTTP stack that can expose the existing application
  layer with typed, inspectable contracts.
- Disposition: adopt FastAPI and Uvicorn.
- Stop condition: primary sources establish request/response validation, OpenAPI generation,
  in-process testing, serving, license, and the integration boundary. A general Python web-framework
  survey is not needed.

## Decision boundary

The project needs one local, read-only JSON adapter for the existing `search` and `ask` use cases,
plus a liveness endpoint. Domain and application objects must remain standard-library dataclasses.
The HTTP framework may validate transport schemas, but it must not own retrieval, ranking, context
assembly, generation, citations, model lifecycle, or database behavior.

The first service is loopback-only and non-production. Authentication, TLS termination, public
deployment, rate limiting, streaming, background jobs, ingest, evaluation, MCP, and a web UI are
outside this decision.

## Constraints and comparison dimensions

The important dimensions are:

- generated and reviewable JSON Schema/OpenAPI contracts;
- strict request validation and explicit response filtering;
- direct in-process tests without a live socket;
- an ASGI serving path suitable for Docker Compose;
- minimal project-owned framework code;
- Python 3.12 support and compatibility with the existing synchronous application layer;
- a permissive license and active primary documentation;
- low replacement cost because the adapter is intentionally thin.

## Candidate assessment

| Candidate | Evidence and provenance | Fit | Disposition |
|---|---|---|---|
| FastAPI + Uvicorn | [FastAPI request models](https://fastapi.tiangolo.com/tutorial/body/), [response models](https://fastapi.tiangolo.com/tutorial/response-model/), [testing](https://fastapi.tiangolo.com/tutorial/testing/), and [Uvicorn serving](https://fastapi.tiangolo.com/deployment/manually/). FastAPI is [MIT licensed](https://github.com/fastapi/fastapi/blob/master/LICENSE); Uvicorn is [BSD-3-Clause](https://github.com/encode/uvicorn/blob/master/LICENSE.md). | Generates OpenAPI and JSON Schema from typed boundary models, validates input, filters output, supports `TestClient`, and has a documented ASGI server path. | **Adopt** |
| Starlette + Uvicorn | [Starlette documentation](https://www.starlette.io/). Starlette is [BSD-3-Clause licensed](https://github.com/encode/starlette/blob/master/LICENSE.md). | A smaller ASGI toolkit, but the project would have to own more schema, validation, serialization, and OpenAPI machinery. That work adds no SciFact value. | Reject for this adapter |
| `http.server` | [Python documentation](https://docs.python.org/3/library/http.server.html). Python Software Foundation license. | No first-class typed JSON/OpenAPI contract and the standard-library documentation says it is not recommended for production. Even for a local prototype it creates avoidable bespoke protocol code. | Reject |
| Defer HTTP | Existing Typer CLI remains sufficient for one operator. | Avoids dependencies, but blocks the roadmap's next independently consumable interface and later web/MCP adapters cannot exercise a stable network contract. | Reject after owner activation |

License statements refer to the canonical project repositories and package metadata as inspected on
the date above. No copied framework code enters this repository.

## Build, adopt, adapt, defer

- **Adopt:** FastAPI for HTTP boundary models, validation, OpenAPI, and in-process tests; Uvicorn as
  the Compose ASGI server.
- **Adapt:** the existing application composition root, strategy enums, dataclass results, CLI JSON
  conventions, and loopback Compose policy.
- **Build:** only transport schemas, deterministic dataclass-to-response mapping, an injected
  application resolver, safe error envelopes, three route handlers, and a live acceptance smoke.
- **Defer:** authentication, TLS, CORS, public ingress, rate limiting, streaming, job queues,
  framework-managed persistence, MCP, web UI, and any retrieval or generation change.

## Recommendation

Use FastAPI and Uvicorn as direct runtime dependencies. Keep Pydantic models in the HTTP module;
do not replace domain dataclasses or introduce framework types into the application layer. Expose a
pure `create_http_app(resolver)` construction function for tests and a `build_http_app()` runtime
factory for Uvicorn. The injected resolver selects and caches applications composed by the existing
composition root, preserving the CLI's strategy choices without constructing adapters in handlers.

Run one Uvicorn worker in the local Compose service. The application is synchronous, so route
handlers remain synchronous and FastAPI executes them through its normal worker-thread path. This
phase makes no throughput or multi-worker guarantee.

## Unknowns and reopen conditions

- The live acceptance run must confirm that the current model and database clients behave safely
  when invoked through FastAPI's synchronous handler execution.
- Reopen application lifetime management if a measured workload requires explicit startup/shutdown
  hooks or resources prove unsafe when cached across requests.
- Reopen the framework choice only if an accepted consumer requires streaming, asynchronous jobs,
  or a protocol feature FastAPI cannot provide without substantial custom machinery.
- Reopen deployment controls before binding beyond loopback or accepting untrusted traffic.
