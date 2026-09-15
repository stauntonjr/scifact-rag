# Retrieval Default Evaluation Design

Date: 2026-09-15

Governing issue: [#6](https://github.com/stauntonjr/scifact-rag/issues/6)

Status: owner-approved design

## Objective

Run one reproducible comparison of the three already-frozen retrieval-default candidates on the
160-query `train-validation` split and retain enough raw evidence to make a no-tuning default
recommendation. The split and earlier aggregate results have already been inspected, so the result
is internal comparative evidence, not pristine selection or confirmation evidence.

The exact strategies are:

1. `bm25-token-window-rrf`;
2. `pooled-coref-interval-colbert`;
3. `pooled-coref-interval-content-max-colbert`.

All run at cutoff 10. A different split, strategy set, cutoff, or evidence classification requires
a new Issue and run manifest.

## Solution assessment and capability disposition

Adapt the existing generation-evaluation structure: immutable dataclasses, strict canonical JSON,
append-and-flush JSONL records, resume by a unique query/policy key, raw-row-derived reports, and
Typer commands at the composition root. Reuse the existing pure retrieval metrics rather than
introducing an evaluation dependency.

Capability dispositions:

- `application-composition-root`: `use-active`; construct each existing strategy through the
  current composition root.
- `cli-interface`: `use-active`; add dry-run and execution commands without adding another
  transport.
- `product-validation-challenges`: `use-active`; use the existing deterministic SciFact
  validation partition and qrels.
- every inactive capability: `not-applicable`; no memory, graph, HTTP, MCP, web, role, security,
  provenance-platform, or architecture-analysis capability is activated.

## Considered approaches

### Separate retrieval evaluator — selected

Create a small evaluation module around the existing `Retriever` and `CorpusSource` ports. It owns
run records, persistence, resume, aggregation, and comparisons, while production search behavior
remains unchanged. This keeps experiment mechanics out of `RagApplication` and mirrors a proven
repository pattern.

### Add candidate introspection to every retriever — rejected

Extending reciprocal-rank fusion and every other retriever with pooled-candidate provenance would
make candidate recall and oracle metrics uniform, but it changes production interfaces only to
serve this comparison. Existing pooled strategies may still expose their already-implemented
candidate diagnostics as supplementary context; lack of that interface on the simple hybrid does
not justify broadening Issue #6.

### Capture existing CLI aggregate output — rejected

Console aggregates do not preserve query order, raw scores, failures, or query-level transitions
and cannot be resumed or independently recomputed. They are insufficient for a default decision.

## Architecture

The evaluation path is separate from generation:

```text
retrieval-run-manifest/v1
          |
          v
manifest dry-run validation
          |
          v
BEIR SciFact train-validation queries + qrels
          |
          +------------------------------+
          |                              |
          v                              v
existing composition root         canonical qrels digest
          |
          v
three existing retrievers, one per frozen strategy
          |
          v
retrieval evaluator: query -> ordered SearchHit rows or explicit failure
          |
          v
append + flush retrieval-evaluation-record/v1 JSONL
          |
          v
report builder reloads raw rows + qrels
          |
          +--> standard aggregate metrics
          +--> per-query baseline transitions
          +--> latency/failure summaries
```

No evaluator branch changes a score, candidate depth, representation, or model call. The command
builds each strategy once and evaluates the same canonical query order.

## Manifest contract

`RetrievalRunManifest` uses schema `retrieval-run-manifest/v1` with exactly these fields:

- `schema_version`;
- `run_id`;
- `repository_commit`;
- `corpus_sha256`, the exact BEIR `corpus.jsonl` SHA-256;
- `queries_sha256`, the exact BEIR `queries.jsonl` SHA-256;
- `qrels_sha256`, a canonical digest of the selected validation qrels after deterministic split;
- `source_split`, exactly `train-validation`;
- `evidence_class`, exactly `internal-comparative`;
- `strategies`, exactly the ordered three-strategy tuple above;
- `cutoff`, exactly 10;
- `components`, a non-empty, uniquely named tuple of identifiers and revisions;
- `started_at` and nullable `completed_at` UTC timestamps;
- `host`;
- `results_path`, a safe repository-relative JSONL path;
- `test_qrels_inspected`, exactly `true`.

Canonical serialization sorts component records by component name but preserves the fixed strategy
order. Parsing rejects missing, unknown, wrongly typed, unsafe, or noncanonical boundary values.

`retrieval-eval-dry-run --manifest PATH` parses and emits canonical JSON without constructing an
application, reading the corpus, opening PostgreSQL, or calling ColBERT.

At execution, the CLI verifies the three file/dataset digests, source split, fixed strategies, and
cutoff before constructing retrievers. The application image deliberately excludes `.git`, so
`repository_commit` is operator-recorded provenance rather than a runtime assertion. The required
application-image component digest binds the executable container to that recorded source build.
Other required component names document at least the PostgreSQL image, MiniLM checkpoint, ColBERT
checkpoint and tokenizer, and PostgreSQL retrieval extensions. Identifiers and revisions are
operator-recorded values; the runner does not infer mutable service versions after the run starts.

## Raw result contract

Each `retrieval-evaluation-record/v1` contains `run_id` plus one
`retrieval-evaluation-result/v1` with:

- `query_id`;
- `strategy`;
- `cutoff`;
- `latency_ms`;
- `hits`, an ordered tuple of `{doc_id, score}` records;
- nullable `error_type` and `error_message`.

Rank is defined by tuple position and is not serialized redundantly. Successful empty retrieval is
represented by empty `hits` and null error fields. A failed retrieval has empty `hits` and both
error fields populated. Duplicate document IDs, non-finite scores, excess hits, non-numeric IDs,
unsafe run IDs, malformed JSON, unknown fields, and mismatched schema versions fail validation.

Every planned query-strategy pair produces one row, even when search raises. Results are appended
one canonical line at a time, flushed, and `fsync`ed. Resume reloads and validates the complete
file, rejects duplicate, foreign-run, unknown-query, and unplanned-strategy rows, and executes only
missing pairs. Existing failure rows are retained evidence and count as completed; retrying them
requires a new run identity rather than rewriting the fixed run.

## Report contract

`retrieval-evaluation-report/v1` is derived only from the raw rows and the digest-verified qrels.
For each strategy it records:

- planned, completed, successful, failed, and empty-result row counts;
- nDCG@10, MAP@10, recall@10, precision@10, and MRR@10 over all 160 planned queries;
- mean and median retrieval latency.

A failed or missing query contributes an empty ranking to metrics, so quality cannot improve by
dropping failures. Completion and failure counts remain explicit beside the metrics.

The simple hybrid is the declared baseline. For each ColBERT strategy and each query, the report
records:

- relevant document IDs gained in the top 10 versus baseline;
- relevant document IDs lost versus baseline;
- whether the top-ranked document changed;
- per-query nDCG delta.

It also aggregates counts of queries improved, regressed, and tied on nDCG. These are descriptive
transitions, not a new optimization objective. Candidate-pool recall, oracle nDCG, and channel
provenance are supplementary only where already exposed by the existing pooled diagnostic port;
Issue #6 does not add a new retriever interface to make them uniform.

## CLI and composition

Add two commands:

- `retrieval-eval-dry-run --manifest PATH`;
- `run-retrieval-eval --manifest PATH --data-dir data`.

The run command loads `BeirSciFact` with `QrelsSplit.TRAIN_VALIDATION`, validates digests, builds
exactly the manifest strategies through `build_application`, adapts each application's public
`search` method to `Retriever`, runs/resumes the raw JSONL, and atomically refreshes the sibling
`.report.json` file. It emits only the execution summary and report path to standard output.

The existing `evaluate` and `diagnose-candidates` commands and the default interactive retrieval
strategy do not change during evidence collection. A later owner decision may update the default
in a separate commit after the fixed report is opened.

## Error and stop behavior

- Manifest or dataset mismatch stops before constructing retrievers or writing results.
- One strategy's query failure becomes a raw row and does not suppress other strategies.
- Persistence, malformed existing data, duplicate keys, or report inconsistency stops the run.
- A missing or unhealthy ColBERT service is not repaired by changing the candidate set or falling
  back to another scorer.
- No parameter, code, service, or manifest repair occurs after opening the fixed result. A runtime
  fault that invalidates the run is preserved and requires an explicit new Issue #6 attempt/run
  identity before re-execution.

## Verification

TDD covers:

- canonical manifest serialization, round trip, exact frozen boundary, paths, timestamps, digests,
  components, and Python types;
- qrels canonical digest stability;
- ordered hit/score serialization and invalid result rejection;
- successful empty retrieval and explicit search failure;
- shared query order across strategies;
- append durability and missing-pair resume;
- foreign, duplicate, unknown, and malformed existing rows;
- raw-row-derived aggregate metrics with failures penalized as empty rankings;
- relevant-document gains/losses and per-query nDCG transitions;
- dry-run isolation from composition and run-command manifest/dataset checks.

The final engineering candidate runs the repository's full `make smoke` gate exactly once, followed
by `python3 tools/product_version.py`, `git diff --check`, and `git status --short`. The live run is
external evidence and cannot replace the full repository gate.

## Live execution and decision boundary

After implementation and independent review, create one complete manifest under
`artifacts/retrieval-default-validation/`, verify the current DGX services without restarting them,
run the three-strategy comparison once, and retain raw results, report, exact digests, and elapsed
time. Publish a short Issue #6 report and ADR-0029.

The default recommendation follows the roadmap's fixed rule: choose the simplest Pareto-efficient
candidate across ranking quality, relevant-document recall, and operational cost. ColBERT may be
recommended only when its fixed benefit justifies the hosted GPU dependency. DP content-max may be
recommended as the scalable long-document scorer without replacing a stronger short-document
control. The already-inspected validation result cannot support a clean generalization claim, and
the already-inspected test qrels cannot be used to tune or repair the decision.
