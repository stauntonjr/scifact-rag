# Issue #12 MCP adapter acceptance

Date: 2026-09-17

Issue: [#12](https://github.com/stauntonjr/scifact-rag/issues/12)

Status: accepted for the thin DGX-local loopback MCP slice, subject to final branch integration.

## Decision boundary

This acceptance tests the MCP transport over the already-accepted SciFact application. It does not
retune retrieval, prompts, thresholds, context selection, or models; estimate answer quality; add
resources, prompts, administration, authentication, public deployment, stdio or Mac acceptance; or
activate the web capability.

The answer cases are the predeclared Issue #10 and Issue #11 examples: query 30 for support with
parent citations and query 92 for exact insufficiency. They are product acceptance examples from
an already-inspected boundary, not new model-quality evidence.

## Candidate and topology

| Item | Accepted boundary |
|---|---|
| Application source commit used to build MCP | `161fe973b20c3443b76bfabed000ca64d2adb2d0` |
| Host | `spark-3a8f`, Linux ARM64 NVIDIA DGX Spark |
| MCP image | `scifact-rag-mcp`, image ID `b0490480b967` |
| PostgreSQL image | `scifact-rag-postgres:pg17-pgvector0.8.6-vchord-bm250.3.0`, image ID `f9542714f92c` |
| MCP SDK | official Python SDK `2.2.0` |
| Negotiated protocol | `2026-07-28` |
| Server identity | `SciFact RAG` v0.1.0 |
| MCP publication | `127.0.0.1:8091:80`, endpoint `/mcp` |
| Retrieval strategy | `pooled-coref-interval-content-max-colbert` |
| Generation-context strategy | `whole-document` |
| Retrieval limit | 5 |
| Generator model reported by responses | `nvidia/Qwen3.6-35B-A3B-NVFP4` |

The service ran one process from the common application image and used the existing PostgreSQL
volume, loopback-published ColBERT service, and host OpenAI-compatible generator. Container
inspection confirmed that port 80 was published only to host `127.0.0.1:8091`.

## Engineering verification

`make smoke` passed in 17.8 seconds:

- the harness and Compose configuration checks passed;
- all 56 Python files matched formatting;
- Ruff passed;
- Pyright reported zero errors and warnings;
- 335 non-integration tests passed; the final review suite consolidates the MCP/interface
  contract into 19 focused checks, including table-driven coverage of every rejected input
  category through the public client boundary and full normalized schema parity;
- source distribution, wheel build, isolated installation, and package import passed.

All three affected integrations passed in 12.84 seconds against the existing loopback services:
pgvector round trip, transactional representation-partition rollback, and all retained retrieval
challenges.

The first integration invocation skipped because `DATABASE_URL` was absent. The next invocation
proved both database checks and failed the retrieval challenge before retrieval because the
isolated worktree lacked ignored `data/scifact`. Pointing `SCIFACT_DATA_DIR` at the existing source
checkout reached scoring but exposed the container-only default hostname `late-interaction` from a
host process. The final unchanged run supplied the existing loopback PostgreSQL, dataset, and
healthy ColBERT endpoint; all three checks passed. No code, corpus, database, strategy, or model
changed between attempts.

## Official-client live results

The official `mcp==2.2.0` URL client connected to
`http://127.0.0.1:8091/mcp`, negotiated protocol `2026-07-28`, and discovered exactly
`answer_scifact` and `search_scifact`. Resources, resource templates, and prompts were all empty.

| Operation | Latency | Contract result |
|---|---:|---|
| Query 30 `search_scifact` | 5.231615 s | `mcp-search-result/v1`; five ordered parent documents; gold parent `24341590` ranked first |
| Query 30 `answer_scifact` | 6.262084 s | `mcp-answer-result/v1`; cited supported answer; citations `24341590`, `13069283`, and `20454006` |
| Query 92 `answer_scifact` | 1.102210 s | `mcp-answer-result/v1`; exact `insufficient evidence`; zero citations |
| Unknown search argument | bounded | protocol error `-32602`; fixed message, no data, sentinel absent |

The supported answer returned evidence parents `24341590`, `13069283`, `20454006`, `12438901`,
and `24349992`. Every citation was a member of that supplied evidence set and the gold parent was
present. The insufficiency result retained five retrieved evidence parents but the application
grounding gate returned exact `insufficient evidence` and an empty citation list.

The invalid request included `REJECTED_VALUE_SENTINEL` as the value of an unknown argument. The
client received code `-32602`, fixed message `Invalid arguments for tool search_scifact`, and no
error data; the sentinel was absent from the structured public error. Focused in-memory tests cover
the same disclosure and zero-downstream-call invariants for both tools and invalid strict limits.

Service logs independently recorded successful ColBERT and generator calls for the accepted
requests. The invalid request returned HTTP 400 at the transport boundary and did not invoke an
application dependency.

## Evidence classification and limitations

| Evidence class | Supported claim |
|---|---|
| Engineering qualification | Locked build, package, static checks, tests, Compose configuration, service startup, discovery, schemas, and loopback calls passed |
| Interface parity | Deterministic tests prove normalized CLI/MCP search and answer parity; live cases preserve parent citations and exact insufficiency |
| Input isolation | Public-client tests prove unknown/invalid recognized arguments are refused without rejected-value disclosure or downstream calls |
| Model quality | No new claim; the two selected cases do not estimate population-level performance |
| Deployment | DGX-local loopback operation only; no Mac path, authentication, TLS, rate-limit, availability, or public-ingress claim |

The first request for a strategy pair constructs its application and can load local model assets;
the process-local resolver then reuses that instance. The Compose application image remains large
because it contains the existing scientific Python and GPU dependency set. Resource sharing across
multiple processes and workers is not claimed.

## Acceptance decision

**Accept the MCP adapter as the second Phase 6 composition adapter.** It exposes exactly two tools,
preserves the application and CLI contracts, rejects invalid recognized input before application
resolution, returns safe versioned structured results, runs only on DGX host loopback, and passed
the complete engineering, affected integration, official-client discovery, supported-answer,
exact-insufficiency, parent-citation, and invalid-input gates.

This acceptance does not authorize a web UI, resources, prompts, stdio or Mac acceptance,
authentication infrastructure, public deployment, or changes to retrieval and generation. The
next bounded interface action is the separately approved small web adapter only if the owner elects
to activate it.
