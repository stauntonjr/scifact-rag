# Issue #6: retrieval-default validation

- Date: 2026-09-15
- Governing roadmap: `docs/project/roadmap.md`, Phase 2
- Governing decision: ADR-0029
- Evidence class: internal comparative validation
- Runtime default changed: no

## Executive result

The one fixed 160-query comparison completed all 480 planned query-strategy rows with zero
failures and zero empty rankings. The six-generator candidate pool ranked by DP content-max
ColBERT was the clear effectiveness leader: nDCG@10 was 0.742493, recall@10 was 0.806250, and
MRR@10 was 0.728472. It exceeded BM25 plus token-window RRF by 0.068975 nDCG, 0.018750 recall,
0.086524 MAP, and 0.081037 MRR.

That improvement costs a healthy ColBERT GPU service and roughly 560 ms more median retrieval
latency per query. Under the predeclared Pareto rule, the quality gain justifies recommending
`pooled-coref-interval-content-max-colbert` as the retrieval-effectiveness default and retaining
`bm25-token-window-rrf` as the faster no-ColBERT alternative. The whole-document ColBERT candidate
is dominated by content-max on every reported quality metric and on latency.

This report records a recommendation, not a behavior change. The application's existing
`title-token-window-rrf` default remains unchanged. Applying ADR-0029 requires a separate
owner-authorized implementation task.

## Frozen protocol

| Field | Value |
|---|---|
| Run ID | `retrieval-default-validation-20260915T111339Z` |
| Repository commit | `fd232ca8f2354ec74ca7c77815c86509e8035bd0` |
| Host | `spark-3a8f` |
| Source split | deterministic `train-validation` |
| Evidence class | `internal-comparative` |
| Query count | 160 |
| Cutoff | 10 |
| Corpus SHA-256 | `dec31c8182f3d744c7d2c09423756fd1d17cbef75808db13ba01cc0aab4d1ac6` |
| Queries SHA-256 | `8ff84a7c903f722981cd8d595c022660140c51867b27608a6d4910db86080313` |
| Validation qrels SHA-256 | `16ccdc8a34fccf58157aed282232feb898c272755a0ae67a74c34aca000c6cc4` |
| Started / completed | `2026-09-15T11:13:39Z` / `2026-09-15T11:19:07Z` |

The runner selected exactly the 160 qrels-backed validation query IDs from the 1,109 training query
texts; 949 non-validation texts were excluded and no selected query lacked text. The canonical dry
run matched the pre-execution manifest byte for byte before the result file was opened. The live
comparison was then executed once with no parameter, depth, strategy, model, or data change.

```bash
docker compose run --rm --no-deps app retrieval-eval-dry-run \
  --manifest artifacts/retrieval-default-validation/manifest.json
docker compose run --rm app run-retrieval-eval \
  --manifest artifacts/retrieval-default-validation/manifest.json \
  --data-dir data
```

## Component identity

| Component | Identifier | Revision |
|---|---|---|
| Application image | `scifact-rag-app` | `sha256:0542f42a7e4b8f460e7485c39413bf4dee430245e8de9a7a30a1109fdcc7ecb9` |
| Embedding model and tokenizer | `sentence-transformers/paraphrase-MiniLM-L6-v2` | `c9a2bfebc254878aee8c3aca9e6844d5bbb102d1` |
| ColBERT model and tokenizer | `answerdotai/answerai-colbert-small-v1` | `c72aa89bc61afdd85373643f3a1a75b2aad6e0fe` |
| ColBERT runtime | `nvcr.io/nvidia/vllm:26.06-py3` | `sha256:bebcf9576b1720214319ee5c7ee4f7661954cbbf59ed3fcd188cd79a67f1967e` |
| PostgreSQL image | `scifact-rag-postgres:pg17-pgvector0.8.6-vchord-bm250.3.0` | `sha256:f9542714f92ce110c49dc3ebc1c6cff74a9138257295f20e71a81a9aa6082686` |
| pgvector | `vector` | `0.8.6` |
| pg_tokenizer | `pg_tokenizer` | `0.1.1` |
| VectorChord-BM25 | `vchord_bm25` | `0.3.0` |

At execution time PostgreSQL and ColBERT were healthy. PostgreSQL contained 5,183 documents,
19,283 token windows, and all stored representation families required by the three frozen
strategies. MS MARCO and RankZephyr were stopped and did not enter this comparison.

## Integrity and retained evidence

| Artifact | Size | SHA-256 |
|---|---:|---|
| `artifacts/retrieval-default-validation/manifest.json` | 2,572 bytes | `786feca96c2bbb4aeccda5d1b50c0352b7b7800d81f85f3d3e058c5bd3a2af78` |
| `artifacts/retrieval-default-validation/results.jsonl` | 390,592 bytes | `02567945ba44018ade6e89067dec9457a772f45f099f4a090b2926d1b7bd9b5f` |
| `artifacts/retrieval-default-validation/results.report.json` | 71,613 bytes | `729b7ce44fad9e24c86de4bc26d969e2f57a17eef26b222ed7ee3e76d3d1af4d1` |

The artifact directory is intentionally ignored by Git. The raw JSONL contains 480 unique
query-strategy keys: 160 for each frozen strategy. All rows completed successfully; none is empty.
A fresh report recomputation from the manifest, qrels, and raw rows was JSON-equivalent to the
retained report. The first local equality assertion compared Python tuples with their JSON list
representation and failed on type alone; canonical JSON comparison confirmed that no artifact or
metric differed, so no repair or rerun occurred.

## Aggregate results

| Strategy | nDCG@10 | MAP@10 | Recall@10 | Precision@10 | MRR@10 | Mean latency | Median latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| BM25 + token-window RRF | 0.673519 | 0.630229 | 0.787500 | 0.090625 | 0.647436 | 90.70 ms | 78.70 ms |
| Whole-document ColBERT | 0.734958 | 0.707396 | 0.800000 | 0.091875 | 0.722569 | 662.76 ms | 642.45 ms |
| DP content-max ColBERT | **0.742493** | **0.716753** | **0.806250** | **0.092500** | **0.728472** | **639.03 ms** | **638.94 ms** |

The BM25 and ColBERT strategy names above abbreviate `bm25-token-window-rrf`,
`pooled-coref-interval-colbert`, and `pooled-coref-interval-content-max-colbert`. Latency is
end-to-end retrieval time observed by the evaluator, not isolated model inference time.

Relative to BM25, content-max ColBERT improves nDCG by about 10.2% and recall by about 2.4%
relative while its median latency is about 8.1 times the baseline. Relative to whole-document
ColBERT, content-max improves nDCG by 0.007535 and recall by 0.006250 while reducing mean latency
by 23.73 ms and median latency by 3.51 ms. It therefore dominates the other ColBERT candidate in
this fixed comparison.

## Query-level transitions from BM25

| Comparator | Better nDCG | Worse nDCG | Tied | Mean nDCG delta | Relevant IDs gained | Relevant IDs lost | Top document changed |
|---|---:|---:|---:|---:|---:|---:|---:|
| Whole-document ColBERT | 32 | 18 | 110 | +0.061439 | 8 | 6 | 55 |
| DP content-max ColBERT | 39 | 13 | 108 | +0.068975 | 8 | 5 | 57 |

These are query-level changes over the retained top-ten rankings, not causal attributions to one
representation component. In particular, candidate generation and final scoring differ between
BM25 RRF and the ColBERT strategies. The transition counts show that the aggregate gain is not
produced by one isolated outlier, but 13 validation queries still regress under content-max and
must remain visible in later scientific-inference work.

## Decision and limitations

Recommend DP content-max ColBERT for retrieval effectiveness. Retain BM25 plus token windows as an
operationally simpler fallback when the ColBERT service is unavailable or sub-100-ms median
retrieval is more important than the measured quality lift. Do not carry whole-document ColBERT
forward as a default candidate because content-max is better on every measured axis in this run;
keep it selectable as a useful short-document control.

The validation partition had already been inspected in earlier architecture work, and the public
test qrels were used repeatedly before this protocol. These results are therefore internal
comparative evidence, not an unbiased generalization estimate. Candidate recall and oracle nDCG
were not newly materialized by this Issue #6 runner, so no unsupported values are inferred here.
The comparison measures document ranking, not scientific support, contradiction, synonymy,
polarity, negation, or evidence sufficiency. It does not justify parameter tuning or another test
run.
