# Project charter

Status: active

## Purpose

A grounded retrieval-augmented generation prototype with CLI, loopback HTTP, loopback MCP, and a
small loopback evidence-inspection web interface over the public SciFact corpus, using PostgreSQL
with pgvector, MiniLM embeddings, and a DGX-hosted NVFP4 generator.

Primary users:

- Developer or researcher evaluating a small inspectable RAG system

## Outcomes and success measures

Desired outcomes:

- Ingest the SciFact corpus, retrieve relevant evidence, and generate an answer with document citations or an explicit insufficient-evidence result
- Measure retrieval against the public BEIR SciFact qrels using standard metrics

Success measures:

- All 5,183 SciFact corpus documents can be ingested reproducibly
- The CLI reports nDCG, MAP, recall, precision, and MRR from public qrels
- Retrieval exceeds the original nDCG@10 baseline of 0.526066 without reducing recall@10 below
  0.661722
- An end-to-end ask command returns a grounded cited answer or insufficient evidence

## Scope

### In

- Typer CLI commands for ingest, search, ask, and retrieval evaluation
- A thin loopback HTTP API for liveness, search, and ask over the same application layer
- A thin loopback MCP service exposing `search_scifact` and `answer_scifact` over the same
  application layer
- A small loopback web UI for inspecting answers, active strategies, citations, and supplied
  parent-document evidence through the existing HTTP contracts
- Python dataclass domain and application contracts
- One explicit composition root with PostgreSQL/pgvector, MiniLM, SciFact, and OpenAI-compatible generation adapters
- Docker Compose operation on one DGX Spark

### Out

- Pi or weaker-model effectiveness comparisons
- A bespoke adoption-effectiveness evaluation framework
- Tool-calling by the generation model
- Production deployment or multi-node operation

## Constraints

- Security: No secrets in the repository
- Data classification: public benchmark data and locally generated evaluation artifacts
- Deployment: Docker Compose on one NVIDIA DGX Spark; generator reached through a published OpenAI-compatible host endpoint
- Budget: One DGX Spark and locally hosted open components; no paid service is required for the prototype
- Licensing: Application code: MIT, SciFact claims and evidence annotations: CC BY 4.0, SciFact abstracts from S2ORC: ODC-By 1.0, MiniLM and Qwen NVFP4 model checkpoints: Apache-2.0, pgvector: PostgreSQL license

## Engineering and release contract

- Primary check: make smoke
- Dependency lock: uv.lock
- Coverage policy: branch-coverage-baseline-required-before-release
- Product versioning: semver at 0.1.0
- Version source: harness/project.yaml:engineering.versioning.current
- Public contract: CLI commands, versioned HTTP/JSON result schemas, versioned MCP tool argument,
  result, and error contracts, loopback evidence-inspection routes and packaged assets, Docker
  Compose environment-variable contract
- Harness version: 0.5.0

## Authority

- Autonomy level: supervised
- Network writes: explicit-human-approval
- Destructive actions: explicit-human-approval
- Release: human-only
- Policy changes: human-review

Generated from `harness/project.yaml` and `harness/intake.json`.
