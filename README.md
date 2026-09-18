# SciFact RAG

An inspectable scientific retrieval-augmented generation system built for one NVIDIA DGX Spark.
It retrieves evidence from 5,183 biomedical abstracts, ranks it with lexical, dense, coreference,
and late-interaction methods, then asks a locally hosted Qwen model for a cited answer or an
explicit `insufficient evidence` result.

This project is deliberately more than a plausible RAG demo: retrieval and generation decisions
are measured, failure cases remain visible, evaluation component revisions are recorded, selected
images and checkpoints are pinned, and experimental strategies stay modular rather than
accumulating in the production score.

**Status: completed DGX-local prototype.** CLI, HTTP, MCP, and web interfaces are accepted.
The [roadmap](docs/project/roadmap.md) records completed and stopped experiments. Template/Pi
evaluation now belongs to [agentic-project-template #59](https://github.com/stauntonjr/agentic-project-template/issues/59);
further scientific research or deployed-service work requires a new scope decision.

## Measured result

The selected retrieval architecture builds a broad six-channel candidate pool and ranks each
document by its best ColBERT score across bounded, coreference-informed content chunks.

| Retrieval strategy | nDCG@10 | Recall@10 | MRR@10 | Median latency |
|---|---:|---:|---:|---:|
| DP content-max ColBERT — selected default | **0.742493** | **0.806250** | **0.728472** | 638.94 ms |
| Whole-document ColBERT | 0.734958 | 0.800000 | 0.722569 | 642.45 ms |
| BM25 + token-window RRF | 0.673519 | 0.787500 | 0.647436 | **78.70 ms** |

These are internal comparative results over a fixed 160-query SciFact validation partition that
had already been inspected. They support an engineering choice, not an unbiased generalization
claim. The selected default improves nDCG by 0.068975 over the BM25 hybrid while accepting an
approximately 8.1x median-latency cost and a ColBERT GPU-service dependency. BM25 remains the
supported fast/no-ColBERT alternative.

## What the project demonstrates

- A clean application core built from frozen Python dataclasses and replaceable ports, with thin
  Typer CLI, FastAPI HTTP, official-SDK MCP, and browser presentation adapters.
- PostgreSQL 17 with pgvector and VectorChord-BM25 as one inspectable evidence store rather than a
  collection of hidden managed services.
- Dedicated candidate generation, feature-preserving pooling, complete reranking, and parent-level
  citation provenance.
- Coreference-aware dynamic-programming chunk boundaries that scale beyond short abstracts while
  preserving exact source text.
- Locally hosted MiniLM, ColBERT, and Qwen inference on a single DGX Spark through Docker Compose
  and OpenAI-compatible model serving.
- Reproducible evaluations with frozen manifests, raw per-query rows, resumability, artifact
  digests, query-level transitions, and explicit evidence limitations.
- Negative results retained as design evidence: title/content score fusion and robust normalization
  were not promoted after controlled ablations regressed ranking quality.

## Architecture

```text
SciFact corpus
      |
      v
PostgreSQL + pgvector + VectorChord-BM25
      |
      +--> BM25, title, token-window, coreference-sentence,
      |    and coreference-interval candidate generators
      |
      v
deduplicated candidate pool
      |
      v
ColBERT MaxSim over bounded DP content views
      |
      v
ranked parent documents + matching-passage provenance
      |
      v
whole-document or adaptive generation context
      |
      v
Qwen NVFP4 --> cited answer or `insufficient evidence`
```

The pipeline is a modular monolith with one explicit composition root. LangGraph is intentionally
absent: the current request path is deterministic and does not need a stateful agent workflow.
The CLI, loopback HTTP API, loopback MCP service, and small evidence-inspection page share the same
application services. The browser calls the existing HTTP contracts rather than implementing a
second retrieval or generation path.

## Try it

Requirements are Docker Compose, access to an NVIDIA DGX Spark, and the required model assets. The
ColBERT service is required by the selected retrieval default; `ask` also expects the configured
Qwen OpenAI-compatible endpoint.

```bash
docker compose up -d postgres late-interaction
docker compose build app
docker compose run --rm app download
docker compose run --rm app ingest
docker compose run --rm app search \
  "What evidence links immune signaling to disease?"
docker compose run --rm app ask \
  "What evidence links immune signaling to disease?"
```

Start the local HTTP adapter over the same application layer:

```bash
docker compose up -d api
curl http://127.0.0.1:8090/healthz
curl -X POST http://127.0.0.1:8090/v1/search \
  -H 'content-type: application/json' \
  -d '{"schema_version":"search-request/v1","query":"immune signaling","limit":5}'
```

The API is a loopback-only prototype, not a public deployment. Complete request, response, error,
and OpenAPI details are in the [technical reference](docs/project/technical-reference.md#http-api).

The same API service hosts the evidence inspector:

```bash
docker compose up -d --build api
# Open http://127.0.0.1:8090/
```

It shows the active strategies, answer status, citations, ordered parent-document evidence,
document IDs, scores, matching passages, and the complete text supplied to generation. It is a
local inspection surface without authentication, TLS, public ingress, or independent retrieval
logic.

Start the DGX-local MCP service over the same application layer:

```bash
docker compose up -d mcp
```

It publishes only `http://127.0.0.1:8091/mcp` and exposes exactly `search_scifact` and
`answer_scifact`. Complete tool, result, validation, and client details are in the
[technical reference](docs/project/technical-reference.md#mcp-service).

Use the fast fallback explicitly when ColBERT is unavailable:

```bash
docker compose run --rm app search \
  --strategy bm25-token-window-rrf \
  "What evidence links immune signaling to disease?"
```

## Current status

- Retrieval default: `pooled-coref-interval-content-max-colbert`.
- Retrieval fallback: `bm25-token-window-rrf`.
- Generation-context default: `whole-document`; `adaptive` is the scalable opt-in policy.
- CLI, loopback HTTP, DGX-local loopback MCP, and the small evidence-inspection web UI are accepted.
  Graph scoring and agent-development evaluation remain downstream.
- The fixed blinded generation review is complete: all three recorded policy names scored 18/24
  grounded answers, which is expected on short abstracts and does not test long-document scaling.
- The CLI release gate is accepted: a clean public branch builds, isolated empty/no-op ingests
  preserve all 5,183 documents and BM25 invariants, and the retained live sample verifies support,
  contradiction, scientific qualification, exact insufficiency, and parent-only citations.
- The loopback HTTP adapter passed full engineering, integration, supported-answer,
  exact-insufficiency, and parent-citation acceptance. The MCP adapter passed the full engineering
  and affected integration gates plus official-client discovery, supported-answer,
  exact-insufficiency, parent-citation, and invalid-input acceptance.

## Documentation

- [Technical and operator reference](docs/project/technical-reference.md): all retrieval
  strategies, commands, schemas, provenance, model revisions, and operational details formerly in
  this README.
- [Roadmap](docs/project/roadmap.md): ordered product phases, gates, and deferrals.
- [Architecture decisions](docs/adr/): durable design choices and measured dispositions.
- [Retrieval leaderboard](docs/reports/scifact-retrieval-leaderboard.md): historical and fixed
  comparisons with evidence boundaries.
- [Issue #6 validation report](docs/reports/issue-6-retrieval-default-validation.md): raw artifact
  hashes, component revisions, metrics, and query-level transitions behind the selected default.
- [Issue #10 CLI acceptance](docs/reports/issue-10-cli-acceptance.md): clean-build, transactional
  ingest, live generation, citation, latency, provenance, limitation, and failure evidence.
- [Issue #11 HTTP acceptance](docs/reports/issue-11-http-api-acceptance.md): schema, parity,
  loopback, integration, supported-answer, insufficiency, and parent-citation evidence.
- [Issue #12 MCP acceptance](docs/reports/issue-12-mcp-acceptance.md): official-client discovery,
  strict validation, parity, loopback topology, integration, citation, and insufficiency evidence.
- [Issue #13 web UI acceptance](docs/reports/issue-13-web-ui-acceptance.md): packaged-resource,
  browser-state, citation, insufficiency, failure, restoration, and local-only evidence.
- [Project handoff](docs/project/handoff.md): current implementation and operating state.

## Development

```bash
make smoke
```

The gate checks the harness contract, formatting, linting, static types, unit tests, package
build/install, and Docker Compose configuration. Integration and live-model evaluations remain
separate because they exercise retained data and GPU services.

## License

Application code is MIT licensed. Dataset, model, container, PostgreSQL extension, and other
third-party components retain their own licenses; see the
[technical reference](docs/project/technical-reference.md) and [LICENSE](LICENSE).
