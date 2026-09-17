# Issue #11 HTTP API acceptance

Date: 2026-09-17

Issue: [#11](https://github.com/stauntonjr/scifact-rag/issues/11)

Status: accepted for the thin loopback HTTP slice, subject to final branch integration.

## Decision boundary

This acceptance tests the new HTTP transport over the already-accepted SciFact application. It
does not retune retrieval, prompts, thresholds, context selection, or models; re-evaluate answer
quality; add authentication or public deployment; or activate MCP or web capabilities.

The two answer cases are the predeclared Issue #10 live examples: query 30 for support with parent
citations and query 92 for exact insufficiency. They are product acceptance examples from an
already-inspected boundary, not new model-quality evidence.

## Candidate and topology

| Item | Accepted boundary |
|---|---|
| Repository commit | `742efc41f430c920bdfe358bb21670e8e5ce23d1` |
| Host | `spark-3a8f`, NVIDIA DGX Spark |
| API image | `scifact-rag-api`, image ID `13387a8234c2`, Linux ARM64 |
| PostgreSQL image | `scifact-rag-postgres:pg17-pgvector0.8.6-vchord-bm250.3.0`, image ID `f9542714f92c` |
| ColBERT image | pinned NVIDIA vLLM image, image ID `59f44d868668` |
| Generator model reported by responses | `nvidia/Qwen3.6-35B-A3B-NVFP4` |
| API publication | `127.0.0.1:8090:80` |
| Retrieval strategy | `pooled-coref-interval-content-max-colbert` |
| Generation-context strategy | `whole-document` |
| Retrieval limit | 5 |

Compose used one Uvicorn worker and the same PostgreSQL volume and inference services as the
accepted CLI topology. Starting `api` rebuilt its application image and recreated the PostgreSQL
container against the existing named volume; PostgreSQL returned healthy before API startup.

## Engineering verification

`make smoke` passed in 16.6 seconds:

- harness and Compose configuration checks passed;
- all 54 Python files matched formatting;
- Ruff passed;
- Pyright reported zero errors and warnings;
- 311 non-integration tests passed, including 22 focused HTTP/interface cases;
- source distribution, wheel build, isolated installation, and package import passed.

The affected integration suite passed all three checks in 12.48 seconds against loopback
PostgreSQL and ColBERT: pgvector round trip, transactional partition rollback, and all retained
retrieval challenges. An initial host-side invocation omitted `LATE_INTERACTION_BASE_URL`, so the
two database tests passed and retrieval failed while resolving the container-only hostname
`late-interaction`. Repeating the unchanged tests with the healthy published endpoint
`http://127.0.0.1:8082` passed; no code or data changed between attempts.

## Live HTTP results

| Operation | HTTP | Latency | Contract result |
|---|---:|---:|---|
| `GET /healthz` | 200 | 0.004328 s | Exact `health/v1` and `ok`; no application resolution |
| Query 30 `POST /v1/ask` | 200 | 7.638888 s | `answer/v1`; supported answer; citations `24341590`, `13069283`, and `20454006` |
| Query 92 `POST /v1/ask` | 200 | 1.038191 s | `answer/v1`; exact `insufficient evidence`; zero citations |

For query 30, all three citations were members of the five returned evidence parent IDs and the
gold parent `24341590` was present. For query 92, the response retained five retrieved evidence
parents but the application grounding gate returned the exact insufficiency result with an empty
citation list. These are the same parent-citation and insufficiency semantics accepted through the
CLI in Issue #10.

One preliminary supported request used a typographic apostrophe instead of the frozen ASCII claim.
It also returned HTTP 200 with parent-valid citations, but it is not the canonical row above. The
exact frozen ASCII claim was rerun immediately without changing any setting; only that 7.638888-
second response is used for acceptance.

The deterministic contract suite separately drives CLI and HTTP through equivalent application
results and proves normalized equality for ordered search hits, answers, evidence, and parent
citations. Live generated prose is not required to be byte-identical across stochastic model
requests.

## Evidence classification and limitations

| Evidence class | Supported claim |
|---|---|
| Engineering qualification | Locked build, package, static checks, tests, Compose configuration, service startup, schemas, and loopback responses passed |
| Interface parity | Deterministic tests prove normalized CLI/HTTP result parity; live cases preserve the accepted citation and insufficiency invariants |
| Model quality | No new claim; the two selected cases do not estimate population-level performance |
| Deployment | Local loopback operation only; no authentication, TLS, rate-limit, availability, or public-ingress claim |

The API process loads the existing application dependencies on the first strategy-pair request,
and the application image remains 11.7 GB. Liveness intentionally does not test PostgreSQL or model
readiness. The service uses a process-local strategy cache and one worker; multi-worker or public
operation requires a new design boundary.

## Acceptance decision

**Accept the HTTP adapter as the first Phase 6 composition adapter.** It exposes only health,
search, and ask; preserves the application and CLI contracts; rejects invalid inputs before
application resolution; returns safe versioned errors; runs on host loopback; and passed the full
engineering, integration, supported-answer, exact-insufficiency, and parent-citation gates.

This acceptance does not authorize MCP, web UI, authentication infrastructure, public deployment,
or changes to retrieval and generation. The next bounded product action is a separate MCP adapter
issue over the same application layer.

