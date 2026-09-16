# Issue #10 CLI acceptance

Date: 2026-09-16

Issue: [#10](https://github.com/stauntonjr/scifact-rag/issues/10)

Status: accepted for the first CLI release decision, with the limitations below.

## Decision boundary

This run tests the existing CLI-first product on one DGX Spark. It keeps
`pooled-coref-interval-content-max-colbert` as the retrieval default and `whole-document` as the
generation-context default. It does not retune retrieval, repeat model selection, add graph work,
activate another interface, slim images, or claim an unbiased scientific benchmark.

The four live cases come from the already-inspected SciFact train-validation boundary. They are
product examples, not new validation evidence. Query 92 was selected before the new live run from
a retained prior result because it exercises the required exact `insufficient evidence` fallback;
query 622 was rejected as an acceptance example because its retrieved abstracts directly
contradict the nominally unannotated claim.

## Candidate and topology

| Item | Accepted boundary |
|---|---|
| Repository commit used to build the application | `b89c331254be3b7b6c119e26382f984d2fda23d3` |
| Frozen acceptance fixture commit | `2a5a1fafd17481218a84e72c4b3a465259560a8e` |
| Application image | `sha256:43598165e622bd72ea724d9d273654df3172a111a195153a97e1d932bce5da0a` |
| PostgreSQL image | `scifact-rag-postgres:pg17-pgvector0.8.6-vchord-bm250.3.0` |
| Qwen endpoint | `nvidia/Qwen3.6-35B-A3B-NVFP4` through `eugr/spark-vllm@sha256:b1420ff7b3595efc5df7134683595ee8de3b1b650d8538da62e55d7a7951b2e0` |
| ColBERT endpoint | `answerdotai/answerai-colbert-small-v1` at revision `c72aa89bc61afdd85373643f3a1a75b2aad6e0fe` through `nvcr.io/nvidia/vllm:26.06-py3@sha256:bebcf9576b1720214319ee5c7ee4f7661954cbbf59ed3fcd188cd79a67f1967e` |
| Host | `spark-3a8f`, NVIDIA DGX Spark |
| Corpus SHA-256 | `dec31c8182f3d744c7d2c09423756fd1d17cbef75808db13ba01cc0aab4d1ac6` |
| Four-case fixture SHA-256 | `a0b9dc8c6443c73f261a131936a8a854726122b25583602aac33de16eaf54835` |

The acceptance database used the separately named `scifact-rag-acceptance` Compose project and
`scifact-rag-acceptance_postgres-data` volume. Existing project data was not modified. ColBERT and
Qwen were already-running shared inference endpoints; the acceptance process did not manage their
lifecycle.

## Engineering checks

### Clean build and Compose

- A fresh public clone at commit `4967a0d34776b0396d12229e469fade0f9dc7ba1` passed
  `docker compose config --quiet` and built the application image from the locked dependencies.
- The candidate application source at `b89c331` rebuilt successfully as image
  `sha256:43598165e622bd72ea724d9d273654df3172a111a195153a97e1d932bce5da0a`.
- A second clean clone of the pushed Issue #10 branch at
  `2a5a1fafd17481218a84e72c4b3a465259560a8e` was clean, passed Compose configuration, and built
  application image `sha256:2d6a61455d5c829e928e186b367494148899dc29a6bc22da9e878058add8fef7`.
- The exact final repository smoke result is recorded in the Issue/PR checks; it is not reused as
  model-quality evidence.

### Empty-volume ingestion

The first accepted run started from zero documents and completed all 5,183 documents with
`--batch-size 512` in approximately 48 minutes. The final state before the second ingest was:

| Invariant | Before no-op ingest |
|---|---:|
| Documents | 5,183 |
| Non-null BM25 vectors | 5,183 |
| Document `(doc_id, ctid, xmin)` digest | `3b82172b4f5c74dfe4a352af7d806284` |
| BM25 index bytes | 8,306,688 |
| `title` rows | 5,183 |
| `token-window` rows | 18,132 |
| `coref-propn-sentence` rows | 46,166 |
| `coref-nominal-sentence` rows | 46,224 |
| `coref-interval-pack` rows | 19,569 |
| `coref-nominal-dp-minilm` rows | 17,806 |
| `coref-nominal-dp-colbert` rows | 5,573 |

### Existing-volume no-op ingestion

The second run completed all 5,183 documents with the same strategy and batch size. Every value in
the table above was identical afterward, including the document tuple digest and exact BM25 index
size. A subsequent live `bm25` CLI search for `tamoxifen` returned document `13069283` first at
score 30.85799, followed by `20454006` and `31311495`, without reindexing.

### Parameter-limit correction discovered by acceptance

The first fresh attempt failed closed before committing a document. A 512-document application
batch expanded to 15,256 five-column representation rows, requiring 76,280 PostgreSQL bind
parameters in one statement; PostgreSQL permits at most 65,535. The database remained at zero.

Commit `b89c331` partitions only representation inserts at a bound derived from the table's column
count. The document upsert, BM25 update, representation delete, and every insert partition remain
inside one transaction. Regular-CI coverage proves multiple bounded statements use one
transaction; an isolated PostgreSQL test proves a failure in a later partition rolls back the
document and earlier partitions. Lowering the public document batch size was rejected because
strategy-dependent chunk fan-out can reproduce the same failure on larger documents.

## Live four-case artifact

The canonical JSONL artifact records, per policy and query, the parent ranking, supplied contexts,
latencies, model token counts, raw generation, normalized answer, citations, citation validity,
stance, evidence coverage, component model, and any explicit failure. Its aggregate report is
derived from those rows. These local working artifacts are intentionally ignored by Git and
retained under `artifacts/cli-acceptance/`.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `manifest.json` | 3,450 | `0b29e13a3a00b5025748b95b8bc53e3a0fb580c5c39c7b4a3fe6e9fa666d55ca` |
| `evaluation-set.jsonl` | 5,117 | `a0b9dc8c6443c73f261a131936a8a854726122b25583602aac33de16eaf54835` |
| `results-v2.jsonl` | 120,128 | `d128d954e9086dc7a5c38594bfddf541721d0b533704e3d1679805f5ac884a2f` |
| `results-v2.report.json` | 1,392 | `0ec5af7a8e250aa423b263a220dfb69f5d2d449c3bf1fa17ea6006164c7a9de7` |
| `results.jsonl` (failed network attempt) | 7,994 | `81b8bba56fe54298ff91994b880ea9583151c08a75ab5497ba9321c0a5bd811a` |
| `results.report.json` (failed network attempt) | 1,328 | `5210b1b1a4703be493e5e120a0af8b8ef90cf0f24b515a2f8f36f44fb519e932` |

The successful run wrote eight of eight expected whole-document/adaptive rows with zero failures.
Both strategies had 100% valid citations and 4/4 stance accuracy in this selected sample. The
whole-document policy had median retrieval latency 748.97 ms, median generator latency 1,840.87
ms, and median input length 3,382.5 Qwen tokens. Those descriptive values are not a benchmark.

| Query | Acceptance role | Predeclared expectation | Whole-document result |
|---:|---|---|---|
| 30 | supported | support with valid parent citations | SUPPORT; cited supplied parents `24341590` and `13069283`; full gold-sentence coverage |
| 40 | contradicted | contradiction with valid parent citations | CONTRADICT; cited supplied parent `13497630`; full gold-sentence coverage |
| 92 | unsupported | exactly `insufficient evidence`, no citations | NOT_ENOUGH_INFO; exact `insufficient evidence`; zero citations |
| 1084 | scientifically qualified | preserve association language; do not upgrade it to causation | SUPPORT; said antidepressant use “is associated with” risk and cited supplied parent `5691302` |

The user-facing default `ask` command was also run for queries 30 and 92. Query 30 returned a
supported answer whose three citations were all members of its five supplied parents. Query 92
returned exactly `insufficient evidence` with an empty citation list.

The first artifact attempt retained eight `ConnectError` rows because the isolated acceptance
network could reach Qwen on host port 8000 but could not traverse ColBERT's loopback-only host bind
on port 8082. No model result was produced. The corrected temporary Compose override attached only
the acceptance app to the existing `scifact-rag_default` inference network and used the ColBERT
container's DNS name; both endpoints returned HTTP 200 before the separately identified v2 run.

## Evidence classification

| Evidence class | What this report may claim |
|---|---|
| Engineering qualification | Clean build/configuration, transactional ingest, tuple/BM25 invariants, checks, and endpoint reachability observed in this run |
| Validation evidence | Reused historical fixed-validation metrics only; no metric or default was selected here |
| Inspected-test evidence | Historical public test scores remain descriptive and were not rerun or tuned |
| Live examples | Four deliberately selected train-validation cases exercise product behavior; they do not estimate population-level answer quality |
| Manual scientific review | Only explicit inspection of the four retained answers and their supplied contexts; the prior 24-case blinded review remains the broader human evidence |

## Limitations and known failure classes

- The corpus contains short abstracts; this run does not validate the adaptive context strategy on
  long documents.
- The four live cases were selected from an inspected boundary and cannot support a generalization
  or accuracy claim.
- High retrieval coverage does not establish scientific entailment. Synonymy, negation, polarity,
  causal language, population, intervention, comparator, outcome, and cross-sentence inference
  remain explicit scientific failure classes.
- The application image remains large and initial CPU coreference ingestion is slow. Neither
  blocked reproducible operation, so image slimming and ingestion optimization remain downstream.
- Qwen and ColBERT are external live services. Their immutable model/container identities are
  recorded, but this report is not a deployment availability claim.
- Query 622 demonstrates why an empty official evidence annotation is not automatically a useful
  product insufficiency example: independently retrieved text may still contradict the claim.

## Release decision

**Accept the CLI vertical slice for the first release decision.** The clean public branch builds,
the isolated empty and no-op ingests pass, both live model endpoints are identified, the selected
retrieval/generation path completes, citations remain within supplied parents, and exact
insufficiency works in both the retained evaluator and interactive CLI. This approves the CLI
product proof, not clinical use, production deployment, long-document effectiveness, or a new
scientific-quality claim.
