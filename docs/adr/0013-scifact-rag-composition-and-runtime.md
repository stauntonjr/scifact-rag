# ADR-0013: SciFact RAG composition and runtime

- Status: accepted
- Date: 2026-08-25
- Decider: Jack Rory Staunton
- Governing issue: local greenfield prototype decision; no GitHub Issue exists yet

## Context

The owner selected a separate Python greenfield repository, Python dataclasses and Typer, Docker
Compose on one DGX Spark, PostgreSQL with pgvector, `paraphrase-MiniLM-L6-v2`, and
`nvidia/Qwen3.6-35B-A3B-NVFP4`. The first interface is CLI; API, MCP, and a small web UI are later
possibilities. Procurement Intelligence Lab already demonstrates a semantic core, application
use cases, ports/adapters, constructor injection, and one visible composition root.

Observed live state on 2026-08-25: a different SparkRun Qwen Coder model is served on host port
8000 and consumes about 60.6 GiB of GPU memory. This repository must not silently start, stop, or
replace it. The selected NVFP4 generator therefore remains an explicit external prerequisite.

Subsequent verification on 2026-08-26 deliberately replaced that workload after operator approval.
The selected NVFP4 checkpoint now serves successfully through SparkRun's no-MTP recipe at TP1 and
32K context. This does not change the external-service boundary.

## Decision

- Keep domain values and application result contracts as frozen Python dataclasses.
- Define ports with Python protocols and keep concrete libraries inside adapters.
- Use SQLAlchemy Core plus psycopg and pgvector only in the PostgreSQL adapter; do not use SQLModel.
- Wire the dataset, embedder, store, generator, and application service in one composition root.
- Run PostgreSQL and the CLI image with Docker Compose. Reach model serving through the published
  host OpenAI-compatible endpoint.
- Embed SciFact title plus abstract as one normalized 384-dimensional MiniLM vector initially.
- Require generated answers to contain only retrieved document IDs as citations; otherwise return
  `insufficient evidence`.
- Activate only the application-composition-root and cli-interface capability entries. Keep all
  other optional capabilities inactive.

## Consequences

### Positive

- The CLI, future HTTP/MCP/UI adapters, and tests can share one application layer.
- Storage, embedding, dataset, and generation implementations remain replaceable.
- GPU lifecycle remains outside the application and cannot collide silently with another model.
- Grounding failure is explicit rather than returning uncited model text.

### Negative

- First-use MiniLM download and container build are substantial.
- One vector per abstract may lose information beyond MiniLM's 128-token limit.
- Sequential evaluation of 300 queries favors clarity over throughput.
- The external generator must be managed separately before `ask` can succeed.

### Risks and mitigations

- Model endpoint mismatch: expose exact base URL and model through environment variables and verify
  `/v1/models` before a live run.
- GPU memory collision: inspect the live workload and require a deliberate operator transition.
- Dataset drift: verify the official BEIR archive MD5 before extraction.
- Ungrounded output: accept only citations that match the retrieved evidence set.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| SQLModel domain objects | Convenient CRUD/API integration | Couples domain contracts to Pydantic/ORM behavior before an API exists |
| Direct psycopg SQL everywhere | Small dependency surface | Makes table and vector expressions less explicit and harder to replace cleanly |
| LangChain or LlamaIndex | Broad RAG integrations | Adds a framework before this small composition root proves a need |
| Generator service inside this Compose project | One command could launch everything | Duplicates SparkRun lifecycle and risks GPU memory/port collision |
| Build API/MCP/UI now | Demonstrates interface reuse | Delays the first working CLI and violates the accepted scope |

## Verification and revisit trigger

Verify unit behavior, package installation, Compose configuration, PostgreSQL vector search,
5,183-document ingestion, BEIR retrieval metrics, and one live grounded answer. Supersede this ADR
if document-level truncation materially limits retrieval, a concrete non-CLI consumer appears, or
the external model-serving boundary prevents reliable single-Spark operation.
