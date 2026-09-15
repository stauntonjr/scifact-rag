# Generation evaluation contract

The generation comparison uses a versioned `generation-run-manifest/v1` JSON document. The same
manifest must accompany dry runs, live per-query results, and aggregate reports so a result cannot
lose its data, model, strategy, or runtime boundary.

## Dry run

Validate and canonicalize a complete manifest without constructing the application, opening
PostgreSQL, or calling an embedding, reranking, or generation service:

```bash
docker compose run --rm app generation-eval-dry-run \
  --manifest artifacts/generation-validation/manifest.json
```

The command writes the canonical manifest to standard output. It makes no output-file changes and
does not infer missing revision information from a live service. Redirect it only when a new
artifact is intentionally being created.

## Fields

| Field | Contract |
|---|---|
| `schema_version` | Exactly `generation-run-manifest/v1` |
| `run_id` | Stable safe name containing letters, digits, periods, underscores, or hyphens |
| `repository_commit` | Full lowercase 40-character Git commit |
| `corpus_sha256` | SHA-256 of the exact corpus input |
| `evaluation_manifest_sha256` | SHA-256 of the exact query/annotation manifest |
| `source_split` | `train-development`, `train-validation`, or `test` |
| `purpose` | `development`, `default-selection`, or `test-confirmation` |
| `retrieval_strategy` | Exact CLI retrieval strategy name |
| `context_strategy` | Exact generation-context strategy name |
| `retrieval_limit` | Number of retrieved parent documents, from 1 through 100 |
| `components` | Non-empty, uniquely named component identifiers and revisions |
| `generator` | Temperature, maximum answer tokens, and thinking setting |
| `started_at` | ISO-8601 UTC timestamp ending in `Z` |
| `completed_at` | Matching UTC completion timestamp or `null` before execution |
| `host` | Host identity recorded by the operator |
| `results_path` | Safe repository-relative path for per-query results |
| `test_qrels_inspected` | Must be `true` to preserve the known test-set exposure |

Every serialized document must contain exactly these fields. Unknown and missing fields fail
validation rather than being ignored.

## Component inventory

The Phase 1 fixed comparison records each component that can change results, even if one context
policy does not call it for every query:

- application image;
- PostgreSQL image;
- pgvector, pg_tokenizer, and VectorChord-BM25 extensions;
- MiniLM model and tokenizer;
- ColBERT model, tokenizer, and serving runtime;
- Qwen model and serving runtime.

Each entry has this shape:

```json
{
  "component": "generator-model",
  "identifier": "nvidia/Qwen3.6-35B-A3B-NVFP4",
  "revision": "operator-recorded-immutable-revision"
}
```

The contract requires a non-empty revision but does not pretend a model name is an immutable
checkpoint. The operator must record the actual revision or digest used by the service.

## Data-selection boundary

The 300-query BEIR test qrels have already been inspected repeatedly. Every manifest records that
fact with `test_qrels_inspected: true`.

- `default-selection` may use only `train-development` or `train-validation`.
- A manifest combining `default-selection` with `test` is invalid.
- `test-confirmation` permits one frozen confirmation run after a default decision; it cannot
  authorize tuning or reopen the chosen parameters.
- Development failures, timeouts, insufficient-evidence outputs, and malformed responses remain
  in per-query artifacts and aggregate denominators.

## Example

```json
{
  "completed_at": null,
  "components": [
    {
      "component": "embedding-model",
      "identifier": "sentence-transformers/paraphrase-MiniLM-L6-v2",
      "revision": "operator-recorded-immutable-revision"
    },
    {
      "component": "generator-model",
      "identifier": "nvidia/Qwen3.6-35B-A3B-NVFP4",
      "revision": "operator-recorded-immutable-revision"
    }
  ],
  "context_strategy": "adaptive",
  "corpus_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "evaluation_manifest_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "generator": {
    "maximum_answer_tokens": 512,
    "temperature": 0.1,
    "thinking_enabled": false
  },
  "host": "spark-3a8f",
  "purpose": "default-selection",
  "repository_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "results_path": "artifacts/generation-validation/results.jsonl",
  "retrieval_limit": 10,
  "retrieval_strategy": "pooled-coref-interval-colbert",
  "run_id": "generation-validation-20260914T120000Z",
  "schema_version": "generation-run-manifest/v1",
  "source_split": "train-validation",
  "started_at": "2026-09-14T12:00:00Z",
  "test_qrels_inspected": true
}
```

The shortened component list and repeated hexadecimal characters make this a format example, not a
claim about a completed run. A live comparison must include the full component inventory and exact
checksums and revisions.
