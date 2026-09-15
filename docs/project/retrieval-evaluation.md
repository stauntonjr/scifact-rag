# Retrieval-default evaluation contract

Issue #6 compares three already-implemented retrieval strategies through one fixed,
resumable run. It does not tune them or change the interactive default:

1. `bm25-token-window-rrf`
2. `pooled-coref-interval-colbert`
3. `pooled-coref-interval-content-max-colbert`

The source split is exactly `train-validation`, the cutoff is exactly 10, and the evidence class
is `internal-comparative`. The 160-query validation split and the public test qrels have already
been inspected, so this run can compare the frozen candidates but cannot support an unexposed-test
or generalization claim.

## Manifest and digests

Every run starts from a complete `retrieval-run-manifest/v1` JSON document. Unknown, missing,
wrongly typed, or noncanonical fields fail validation.

| Field | Contract |
|---|---|
| `schema_version` | Exactly `retrieval-run-manifest/v1` |
| `run_id` | Safe stable name using letters, digits, periods, underscores, or hyphens |
| `repository_commit` | Full lowercase 40-character Git commit recorded by the operator |
| `corpus_sha256` | SHA-256 of the exact bytes in `scifact/corpus.jsonl` |
| `queries_sha256` | SHA-256 of the exact bytes in `scifact/queries.jsonl` |
| `qrels_sha256` | SHA-256 of canonical, split-filtered qrels described below |
| `source_split` | Exactly `train-validation` |
| `evidence_class` | Exactly `internal-comparative` |
| `strategies` | The three strategies above, in that order |
| `cutoff` | Exactly 10 |
| `components` | Non-empty, uniquely named component identifiers and immutable revisions |
| `started_at` | ISO-8601 UTC timestamp ending in `Z` |
| `completed_at` | Matching UTC completion timestamp or `null` before execution |
| `host` | Non-empty operator-recorded host identity |
| `results_path` | Safe repository-relative `.jsonl` path |
| `test_qrels_inspected` | Exactly `true` |

The qrels digest is independent of Python mapping order. It canonicalizes the filtered mapping as
query rows sorted by query ID, each containing document/grade pairs sorted by document ID, then
uses compact key-sorted JSON. Grades remain non-negative integers; they are not converted to
binary labels for the digest.

The application image excludes `.git`, so the runner cannot infer or verify
`repository_commit` inside the container. The operator records that source provenance, while the
required `application-image` revision binds execution to the built artifact. A live manifest must
also contain these component names:

- `application-image`
- `postgres-image`
- `embedding-model`
- `colbert-model`
- `colbert-tokenizer`
- `pg-tokenizer-extension`
- `pgvector-extension`
- `vchord-bm25-extension`

The runner requires their presence but does not replace operator-recorded immutable identifiers by
querying mutable services after the run starts.

## Validate, run, and resume

Validate and canonicalize a manifest without reading SciFact data, constructing an application,
opening PostgreSQL, or calling ColBERT:

```bash
docker compose run --rm app retrieval-eval-dry-run \
  --manifest artifacts/retrieval-default-validation/manifest.json
```

Run or resume the fixed comparison:

```bash
docker compose run --rm app run-retrieval-eval \
  --manifest artifacts/retrieval-default-validation/manifest.json \
  --data-dir data
```

The run command loads only `TRAIN_VALIDATION`, verifies all three data digests, checks the required
component inventory, and only then constructs the three applications in manifest order. It never
falls back to another strategy or scorer.

The raw result at `results_path` is append-only JSONL. Each
`retrieval-evaluation-record/v1` contains the run ID and one
`retrieval-evaluation-result/v1`: query ID, strategy, cutoff, measured latency, ordered document
IDs with raw scores, and nullable error type/message. Tuple position defines rank. A successful
empty result has no hits and no error; a failed search has no hits and both error fields.

Each row is appended, flushed, and `fsync`ed before the next pair runs. Resume validates the whole
existing file first and treats every valid query/strategy row—including a failure row—as complete.
It executes only missing pairs. Malformed JSON, duplicate pairs, another run ID, unknown queries,
unplanned strategies, or a different cutoff stop without searching. Retrying a retained failure
requires a new run identity; the fixed evidence is never overwritten.

After each invocation, the runner atomically refreshes a sibling report. For
`artifacts/example/results.jsonl`, that path is `artifacts/example/results.report.json`.
`retrieval-evaluation-report/v1` is derived only from the reread raw rows and digest-verified
qrels. It reports completion, success/failure/empty counts, mean and median latency, and nDCG, MAP,
recall, precision, and reciprocal rank at 10 for each strategy. Failed and missing rows contribute
empty rankings to every metric denominator.

For each ColBERT comparator, the report also retains per-query relevant document IDs gained and
lost versus BM25/token-window RRF, whether the top document changed, and the signed nDCG delta.
Improved, regressed, and tied query counts are descriptive diagnostics, not a new tuning target.

## Fixed-run stop rule

Once the result file has been opened, do not repair parameters, models, code, service topology,
candidate limits, weights, thresholds, or manifest values in place. Preserve any runtime failure.
If it invalidates the comparison, record the failed attempt and create a new explicitly authorized
Issue #6 attempt and run identity. The report can inform a recommendation; changing the product's
retrieval default remains a separate owner-authorized change.
