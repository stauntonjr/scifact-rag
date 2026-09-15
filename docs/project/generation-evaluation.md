# Generation evaluation contract

The generation comparison uses a versioned `generation-run-manifest/v1` JSON document. The same
manifest must accompany dry runs, live per-query results, and aggregate reports so a result cannot
lose its data, model, strategy, or runtime boundary.

## Build the fixed input manifest

Generation evaluation needs the official SciFact sentence arrays in addition to the flattened BEIR
corpus. Download the official public release from:

```text
https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz
```

The release observed and validated on 2026-09-14 has these SHA-256 digests:

| Artifact | SHA-256 |
|---|---|
| `data.tar.gz` | `11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be` |
| `data/corpus.jsonl` | `b8d6c89624cb2ed74dee8938effc4f5d8bd2086887880af8110d64be4ceade62` |
| `data/claims_train.jsonl` | `f4c8fa82d8bd0653a9cc8d61a6ea48c25eacea64e90af5dbf390ebb1b74372f0` |

The official URL contains `latest`, so a checksum change is a new data decision. Do not silently
accept a different archive.

After verifying and extracting it, build the deterministic validation input:

```bash
docker compose run --rm app build-generation-eval-manifest \
  --data-dir data \
  --official-data-dir data/scifact-original \
  --split train-validation \
  --output data/evaluation/scifact-generation-context/validation-input.jsonl
```

The builder cross-checks official claim text and evidence annotations against BEIR query metadata,
cross-checks official cited documents against BEIR qrels, verifies every cited document exists in
both corpora, and resolves each evidence index through the official sentence array. Missing,
conflicting, duplicate, or out-of-range records fail rather than being approximated.

The fixed outputs reproduced from the pinned source are:

| Split | Cases | Support | Contradict | No evidence | Rationale sets | Evidence sentences | Manifest SHA-256 |
|---|---:|---:|---:|---:|---:|---:|---|
| `train-development` | 649 | 266 | 138 | 245 | 755 | 816 | `8ce286269e71115372160f45ba6c3c079d255efdd977b0d4417cd1a26845d90b` |
| `train-validation` | 160 | 66 | 35 | 59 | 202 | 209 | `34084490c48515f0c788da0960d7f426c0e64e4dcf9431b8721d824ba0349105` |

No-evidence cases are claims whose official `evidence` object is empty. Their qrels still identify
the source-cited documents, so they are declared `NOT_ENOUGH_INFO` controls rather than generic
unrelated-text negatives.

## Dry run

Validate and canonicalize a complete manifest without constructing the application, opening
PostgreSQL, or calling an embedding, reranking, or generation service:

```bash
docker compose run --rm app generation-eval-dry-run \
  --manifest data/evaluation/scifact-generation-context/manifest.json
```

The command writes the canonical manifest to standard output. It makes no output-file changes and
does not infer missing revision information from a live service. Redirect it only when a new
artifact is intentionally being created.

Run or resume the paired comparison with:

```bash
docker compose run --rm app run-generation-eval \
  --manifest data/evaluation/scifact-generation-context/manifest.json \
  --evaluation-set data/evaluation/scifact-generation-context/validation-input.jsonl
```

The runner validates the input checksum and split against the run manifest, retrieves one parent
ranking per claim, and sends that same ordered ranking to all three context policies. It appends
and flushes one canonical JSONL record at a time. On restart it validates the existing file and
runs only missing `(query_id, context_strategy)` pairs; duplicate, foreign-run, malformed, and
out-of-set rows fail explicitly.

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
| `context_strategy` | One exact policy name, or `paired` for the fixed three-policy comparison |
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
  "context_strategy": "paired",
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
