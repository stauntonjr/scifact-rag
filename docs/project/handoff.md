# Project handoff

## Current objective

Deliver the first working CLI-first SciFact RAG vertical slice on one DGX Spark:

```text
BEIR SciFact -> MiniLM -> PostgreSQL/pgvector -> retrieved evidence
                                                    |
                                                    v
                               Qwen NVFP4 -> cited answer or insufficient evidence
```

The same dataclass application layer is the future composition root for HTTP, MCP, and a small web
UI, but only CLI is active now.

## Accepted decisions

- Python 3.12, frozen dataclasses, Typer, SQLAlchemy Core, psycopg, and explicit constructor wiring.
- Docker Compose owns PostgreSQL and the application image.
- SparkRun/vLLM remains an external OpenAI-compatible host service; this project never manages its
  lifecycle implicitly.
- Embeddings use `sentence-transformers/paraphrase-MiniLM-L6-v2` with `vector(384)`.
- Generation uses `nvidia/Qwen3.6-35B-A3B-NVFP4` without tool calls.
- BEIR SciFact qrels evaluate retrieval. The original SciFact hidden test labels are not claimed.
- Only `application-composition-root` and `cli-interface` are active in
  `harness/capabilities.json`.

See `docs/adr/0013-scifact-rag-composition-and-runtime.md` and
`docs/research/scifact-rag-existing-solutions.md`.

## Live environment observed 2026-08-26

- Host architecture: AArch64 DGX Spark.
- With explicit operator approval, SparkRun job `8337765ded59` serving
  `Intel/Qwen3-Coder-Next-int4-AutoRound` was stopped to release port 8000 and unified memory.
- SparkRun 0.2.40 now runs `nvidia/Qwen3.6-35B-A3B-NVFP4` as a TP1 host-network vLLM service at
  port 8000 with a 32,768-token context limit. Its estimate was 21.82 GB of weights plus 1.25 GB
  of KV cache.
- The default `@eugr/qwen3.6-35b-a3b-nvfp4` recipe failed because its generated
  `--speculative-config` value retained doubled JSON braces. The official
  `@eugr/qwen3.6-35b-a3b-nvfp4-no-mtp` recipe serves the same checkpoint successfully; MTP is an
  optional decoding optimization and is not part of the RAG contract.

## Implementation state

- Generated project intake is sufficient for bounded planning.
- Local scaffold baseline: `703c8e5`.
- Dataclass domain/ports, application services, SciFact/MiniLM/Postgres/generator adapters, Typer
  CLI, Docker Compose, dependency contract, ADR, research note, and focused tests are authored.
- The dependency lock resolves 75 packages. Ruff, Pyright, seven focused unit tests, clean-wheel
  installation, Compose parsing, the application image build, containerized CLI help, and the
  pgvector round trip pass. The first integration invocation raced initial database startup; the
  unchanged test passed after Compose reported healthy.
- The official checksum-verified corpus contains 5,183 documents. All were ingested. Evaluation
  over 300 BEIR test queries at cutoff 10 reports nDCG 0.526066, MAP 0.477665, recall 0.661722,
  precision 0.073000, and MRR 0.495447.
- The application image is 10.69 GB because the standard sentence-transformers/PyTorch resolution
  includes the CUDA runtime even though Compose does not grant the application GPU access. Record
  this as an optimization candidate after the end-to-end prototype, not a precondition.
- Live generation is verified. A directly supported vitamin-D/MS animal-model statement returned
  citation `22843838`. The broader human risk-reduction claim was explicitly qualified as not
  directly established by the supplied evidence, rather than treating association and an animal
  result as human causality. An unsupported Moon/green-cheese claim returned exactly
  `insufficient evidence` with no citations.
- Qwen initially used its 512-token answer budget for reasoning and returned null final content.
  The adapter now passes the checkpoint's supported `enable_thinking=false` chat-template option;
  an adapter regression test covers that request contract.
- No GitHub repository, Issue, Project item, image publication, or deployment has been created.
- The copied template `LICENSE` says MIT while intake deliberately keeps publication licensing
  provisional. Reconcile that owner decision before any remote publication.

## Measured template friction

Instantiation produced 214 files and roughly 26,000 lines before application code, largely from
template maintenance history, plugin distribution, and deferred evaluation machinery. The copied
tests are correctly absent, so the earlier 256-test failure is fixed. Treat the remaining scaffold
volume as evidence for a later simplification decision; do not interrupt this product proof to
build that cleanup first.
