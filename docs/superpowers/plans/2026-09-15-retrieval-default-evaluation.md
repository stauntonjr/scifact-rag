# Retrieval Default Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run one resumable, raw-row-backed comparison of the three frozen SciFact retrieval-default candidates.

**Architecture:** Add one evaluation-only module around existing `Retriever` and `CorpusSource` contracts. Strict dataclasses own manifest, raw JSONL, resume, report, and query-transition behavior; two Typer commands validate or execute the fixed comparison through the existing composition root without changing retrieval behavior.

**Tech Stack:** Python 3.12, frozen dataclasses, Typer, existing SciFact adapters and retrieval metrics, canonical JSON/JSONL, pytest, Docker Compose on one DGX Spark.

**Spec:** `docs/superpowers/specs/2026-09-15-retrieval-default-evaluation-design.md`

## Global Constraints

- Governing work item is GitHub Issue #6.
- Evidence class is exactly `internal-comparative`; the 160-query split has already been inspected.
- Strategies, in order, are `bm25-token-window-rrf`, `pooled-coref-interval-colbert`, and `pooled-coref-interval-content-max-colbert`.
- Source split is exactly `train-validation`; cutoff is exactly 10.
- Do not change retriever behavior, candidate limits, representations, scores, models, weights, thresholds, or service topology.
- Do not add a dependency or activate an inactive template capability.
- Preserve Phase 1 Issue #5 and its blank human-review worksheet unchanged.
- Use TDD for every production behavior: add one focused failing test, confirm its intended failure, implement the minimum behavior, and rerun the focused test.
- Run the complete `make smoke` gate exactly once on the final engineering candidate, after release-impact assessment and independent review readiness.
- Commit each completed task and push each commit as the owner requested; do not publish a release.

---

### Task 1: Frozen manifest and dataset digests

**Files:**
- Create: `src/scifact_rag/retrieval_evaluation.py`
- Create: `tests/test_retrieval_evaluation.py`

**Interfaces:**
- Consumes: `ComponentRevision` from `scifact_rag.evaluation`.
- Produces: `RETRIEVAL_DEFAULT_STRATEGIES`, `RetrievalRunManifest`, `sha256_file(path: Path) -> str`, and `canonical_qrels_sha256(qrels: Mapping[str, Mapping[str, int]]) -> str`.

- [ ] **Step 1: Write manifest serialization and boundary tests**

Add a `_manifest(**overrides)` fixture and tests that assert canonical JSON contains exactly the
specified fields, component records sort by component name, and strategies preserve frozen order:

```python
def test_retrieval_run_manifest_emits_canonical_frozen_boundary() -> None:
    payload = json.loads(_manifest().to_json())

    assert payload["schema_version"] == "retrieval-run-manifest/v1"
    assert payload["source_split"] == "train-validation"
    assert payload["evidence_class"] == "internal-comparative"
    assert payload["strategies"] == list(RETRIEVAL_DEFAULT_STRATEGIES)
    assert payload["cutoff"] == 10
    assert [item["component"] for item in payload["components"]] == sorted(
        item["component"] for item in payload["components"]
    )
```

Add parameterized rejection tests for a wrong schema, unsafe run ID/path, non-hex commit or
digests, any other split/evidence class/strategy order/cutoff, empty or duplicate components,
invalid timestamps, `completed_at` before `started_at`, and `test_qrels_inspected != True`.

- [ ] **Step 2: Run the manifest test and confirm RED**

Run:

```bash
uv run pytest tests/test_retrieval_evaluation.py -k manifest -q
```

Expected: collection fails because `scifact_rag.retrieval_evaluation` does not exist.

- [ ] **Step 3: Implement the strict manifest contract**

Create the module with the frozen strategy tuple and dataclass:

```python
RETRIEVAL_DEFAULT_STRATEGIES = (
    RetrievalStrategyName.BM25_TOKEN_WINDOW_RRF,
    RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT,
    RetrievalStrategyName.POOLED_COREF_INTERVAL_CONTENT_MAX_COLBERT,
)

@dataclass(frozen=True, slots=True)
class RetrievalRunManifest:
    schema_version: str
    run_id: str
    repository_commit: str
    corpus_sha256: str
    queries_sha256: str
    qrels_sha256: str
    source_split: str
    evidence_class: str
    strategies: tuple[RetrievalStrategyName, ...]
    cutoff: int
    components: tuple[ComponentRevision, ...]
    started_at: str
    completed_at: str | None
    host: str
    results_path: str
    test_qrels_inspected: bool

    def to_json(self) -> str:
        values = asdict(self)
        values["strategies"] = [strategy.value for strategy in self.strategies]
        return json.dumps(values, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, serialized: str) -> "RetrievalRunManifest":
        raw = json.loads(serialized)
        if not isinstance(raw, dict):
            raise TypeError("manifest must be a JSON object")
        if set(raw) != {field.name for field in fields(cls)}:
            raise ValueError("manifest fields do not match retrieval-run-manifest/v1")
        raw["strategies"] = tuple(
            RetrievalStrategyName(value) for value in raw["strategies"]
        )
        raw["components"] = tuple(
            ComponentRevision(**value) for value in raw["components"]
        )
        return cls(**raw)
```

Implement every validation named in Step 1. Serialize enum strategies by value through
`dataclasses.asdict` followed by `json.dumps(values, indent=2, sort_keys=True) + "\n"`.
Parsing must require an exact field set and construct `ComponentRevision` plus
`RetrievalStrategyName` values explicitly.

- [ ] **Step 4: Add deterministic digest tests**

```python
def test_qrels_digest_is_stable_across_mapping_order() -> None:
    left = {"2": {"20": 1, "10": 2}, "1": {"30": 1}}
    right = {"1": {"30": 1}, "2": {"10": 2, "20": 1}}
    assert canonical_qrels_sha256(left) == canonical_qrels_sha256(right)

def test_sha256_file_hashes_exact_bytes(tmp_path: Path) -> None:
    source = tmp_path / "data.jsonl"
    source.write_bytes(b"one\ntwo\n")
    assert sha256_file(source) == hashlib.sha256(b"one\ntwo\n").hexdigest()
```

- [ ] **Step 5: Run the digest tests and confirm RED**

Run:

```bash
uv run pytest tests/test_retrieval_evaluation.py -k 'digest or sha256_file' -q
```

Expected: failures report missing digest functions.

- [ ] **Step 6: Implement exact file and canonical qrels digests**

Use streaming binary reads for files. Canonicalize qrels without losing integer grades:

```python
def canonical_qrels_sha256(qrels: Mapping[str, Mapping[str, int]]) -> str:
    rows = [
        {"query_id": query_id, "relevance": sorted(relevance.items())}
        for query_id, relevance in sorted(qrels.items())
    ]
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
```

Reject empty qrels, blank/non-string IDs, boolean/non-integer grades, and negative grades.

- [ ] **Step 7: Verify and commit Task 1**

Run:

```bash
uv run pytest tests/test_retrieval_evaluation.py -k 'manifest or digest or sha256_file' -q
uv run ruff check src/scifact_rag/retrieval_evaluation.py tests/test_retrieval_evaluation.py
git diff --check
```

Commit and push:

```bash
git add src/scifact_rag/retrieval_evaluation.py tests/test_retrieval_evaluation.py
git commit -m "feat: add frozen retrieval run manifest"
git push origin main
```

---

### Task 2: Durable per-query evaluation and resume

**Files:**
- Modify: `src/scifact_rag/retrieval_evaluation.py`
- Modify: `tests/test_retrieval_evaluation.py`

**Interfaces:**
- Consumes: `Retriever`, `SearchHit`, `RetrievalStrategyName`, fixed manifest strategy tuple.
- Produces: `RankedRetrievalHit`, `RetrievalEvaluationResult`, `RetrievalEvaluationRecord`, `RetrievalEvaluationExecutionSummary`, `RetrievalEvaluationExecutor.run(...)`, and `read_retrieval_evaluation_records(path: Path)`.

- [ ] **Step 1: Write result validation and JSON round-trip tests**

```python
def test_retrieval_record_round_trips_ordered_hits_and_scores() -> None:
    result = RetrievalEvaluationResult(
        schema_version="retrieval-evaluation-result/v1",
        query_id="17",
        strategy=RetrievalStrategyName.BM25_TOKEN_WINDOW_RRF,
        cutoff=10,
        latency_ms=12.5,
        hits=(RankedRetrievalHit("2", 0.7), RankedRetrievalHit("1", 0.6)),
        error_type=None,
        error_message=None,
    )
    record = RetrievalEvaluationRecord("retrieval-validation-1", result)
    assert RetrievalEvaluationRecord.from_json(record.to_json()) == record
```

Add rejection cases for duplicate/non-numeric document IDs, non-finite scores, more than cutoff
hits, negative/non-finite latency, mixed error fields, hits on a failed row, unknown fields, and
wrong schemas.

- [ ] **Step 2: Run the result tests and confirm RED**

Run:

```bash
uv run pytest tests/test_retrieval_evaluation.py -k 'record or result' -q
```

Expected: imports fail for the new result types.

- [ ] **Step 3: Implement result and record dataclasses**

Use these exact public shapes:

```python
@dataclass(frozen=True, slots=True)
class RankedRetrievalHit:
    doc_id: str
    score: float

@dataclass(frozen=True, slots=True)
class RetrievalEvaluationResult:
    schema_version: str
    query_id: str
    strategy: RetrievalStrategyName
    cutoff: int
    latency_ms: float
    hits: tuple[RankedRetrievalHit, ...]
    error_type: str | None
    error_message: str | None

@dataclass(frozen=True, slots=True)
class RetrievalEvaluationRecord:
    run_id: str
    result: RetrievalEvaluationResult
    schema_version: str = "retrieval-evaluation-record/v1"
```

Validate at construction as well as parse time so invalid programmatic rows cannot be serialized.

- [ ] **Step 4: Write executor behavior tests**

Use recording retrievers and a two-query fixture. Prove canonical numeric query order reaches all
strategies, each strategy receives cutoff 10, returned scores/order are preserved, an empty result
is successful, and one raised `TimeoutError` produces a failed row without suppressing another
strategy. Add a resume test seeded with one valid row and assert only five of six pairs execute.

```python
summary = RetrievalEvaluationExecutor(retrievers, clock=fake_clock).run(
    run_id="retrieval-validation-1",
    queries={"2": "second", "1": "first"},
    strategies=RETRIEVAL_DEFAULT_STRATEGIES,
    cutoff=10,
    output=output,
)
assert summary.expected_rows == 6
assert summary.written_rows == 6
```

Add existing-file rejection tests for malformed JSON, another run ID, duplicate key, unknown query,
unplanned strategy, and cutoff mismatch.

- [ ] **Step 5: Run executor tests and confirm RED**

Run:

```bash
uv run pytest tests/test_retrieval_evaluation.py -k 'executor or resume or existing' -q
```

Expected: failures report missing executor/read functions.

- [ ] **Step 6: Implement append-durable execution**

Implement:

```python
class RetrievalEvaluationExecutor:
    def __init__(
        self,
        retrievers: Mapping[RetrievalStrategyName, Retriever],
        *,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._retrievers = dict(retrievers)
        self._clock = clock

    def run(
        self,
        *,
        run_id: str,
        queries: Mapping[str, str],
        strategies: Sequence[RetrievalStrategyName],
        cutoff: int,
        output: Path,
    ) -> RetrievalEvaluationExecutionSummary:
        existing_records = read_retrieval_evaluation_records(output)
        existing = {
            (record.result.query_id, record.result.strategy): record
            for record in existing_records
        }
        written = 0
        for strategy in strategies:
            for query_id in sorted(queries, key=int):
                if (query_id, strategy) in existing:
                    continue
                result = self._evaluate(
                    query_id, queries[query_id], strategy, cutoff
                )
                _append_retrieval_record(
                    output, RetrievalEvaluationRecord(run_id, result)
                )
                written += 1
        return RetrievalEvaluationExecutionSummary(
            expected_rows=len(queries) * len(strategies),
            preexisting_rows=len(existing_records),
            written_rows=written,
            failed_rows=sum(
                record.result.error_type is not None
                for record in read_retrieval_evaluation_records(output)
            ),
        )
```

Load and validate the full existing file before search. Iterate strategies in the supplied frozen
order and queries by `int(query_id)`. Wrap only the `retriever.search(query, cutoff)` call, measure
latency in a `finally` block, and convert valid hits to `RankedRetrievalHit`. Append each record with
parent-directory creation, `flush`, and `os.fsync`. Do not cache or retry failed rows.

- [ ] **Step 7: Verify and commit Task 2**

Run:

```bash
uv run pytest tests/test_retrieval_evaluation.py -k 'record or result or executor or resume or existing' -q
uv run ruff check src/scifact_rag/retrieval_evaluation.py tests/test_retrieval_evaluation.py
git diff --check
```

Commit and push:

```bash
git add src/scifact_rag/retrieval_evaluation.py tests/test_retrieval_evaluation.py
git commit -m "feat: retain resumable retrieval rankings"
git push origin main
```

---

### Task 3: Raw-row-derived report and query transitions

**Files:**
- Modify: `src/scifact_rag/retrieval_evaluation.py`
- Modify: `tests/test_retrieval_evaluation.py`

**Interfaces:**
- Consumes: `evaluate_rankings`, digest-verified qrels, raw records, frozen strategy tuple.
- Produces: `RetrievalStrategySummary`, `RetrievalQueryTransition`, `RetrievalStrategyComparison`, `RetrievalEvaluationReport`, `build_retrieval_evaluation_report(...)`, and `write_retrieval_evaluation_report(...)`.

- [ ] **Step 1: Write aggregate report tests**

Create two qrels and explicit raw rows, including one failed query. Assert each strategy's metrics
equal a direct `evaluate_rankings` call where the failed query maps to `[]`, rather than a metric
computed over successful rows only:

```python
expected = evaluate_rankings(
    qrels,
    {"1": ["10", "99"], "2": []},
    cutoff=2,
)
report = build_retrieval_evaluation_report(
    records,
    run_id="retrieval-validation-1",
    queries={"1": "first", "2": "second"},
    qrels=qrels,
    strategies=strategies,
    cutoff=2,
)
assert report.strategies[0].metrics == expected
assert report.strategies[0].failed_rows == 1
```

Assert planned/completed/success/failed/empty counts and latency mean/median. Add rejection tests for
foreign run IDs, duplicate records, queries/qrels mismatch, record cutoff mismatch, and unplanned
strategies.

- [ ] **Step 2: Run aggregate tests and confirm RED**

Run:

```bash
uv run pytest tests/test_retrieval_evaluation.py -k 'report and not transition' -q
```

Expected: imports fail for report types and builder.

- [ ] **Step 3: Implement report summaries from raw rows**

Use `evaluate_rankings(qrels, rankings, cutoff)` without duplicating metric formulas. Build a
ranking entry for every qrels query, defaulting missing or failed rows to an empty list. Report
`complete` only when every planned key is present, regardless of failure status. Write canonical
report JSON through a same-directory `NamedTemporaryFile`, `flush`, `fsync`, mode `0644`, and atomic
replace.

- [ ] **Step 4: Write baseline transition tests**

Use BM25 as baseline and each ColBERT strategy as comparator. Construct one improved, one regressed,
and one tied query. Assert exact gained/lost relevant IDs, top-document change, signed per-query
nDCG delta, and aggregate improved/regressed/tied counts:

```python
comparison = report.comparisons[0]
assert comparison.baseline is RetrievalStrategyName.BM25_TOKEN_WINDOW_RRF
assert comparison.comparator is RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT
assert (comparison.improved_queries, comparison.regressed_queries, comparison.tied_queries) == (
    1,
    1,
    1,
)
```

- [ ] **Step 5: Run transition tests and confirm RED**

Run:

```bash
uv run pytest tests/test_retrieval_evaluation.py -k transition -q
```

Expected: comparisons are absent or incomplete.

- [ ] **Step 6: Implement descriptive transitions**

For each comparator and query, calculate one-query metrics with the existing metric function.
Relevant gains/losses use positive-grade qrels intersected with each top-cutoff ranking. Compare
nDCG deltas with a fixed numerical tolerance of `1e-12` only for tie classification; serialize the
unrounded float delta. Preserve query IDs in numeric order and comparator order from the manifest.

- [ ] **Step 7: Verify and commit Task 3**

Run:

```bash
uv run pytest tests/test_retrieval_evaluation.py -q
uv run ruff check src/scifact_rag/retrieval_evaluation.py tests/test_retrieval_evaluation.py
git diff --check
```

Commit and push:

```bash
git add src/scifact_rag/retrieval_evaluation.py tests/test_retrieval_evaluation.py
git commit -m "feat: derive retrieval comparison report"
git push origin main
```

---

### Task 4: CLI preflight and execution wiring

**Files:**
- Modify: `src/scifact_rag/cli.py`
- Modify: `tests/test_cli.py`
- Create: `docs/project/retrieval-evaluation.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: all Task 1–3 contracts, `BeirSciFact`, `QrelsSplit.TRAIN_VALIDATION`, and `build_application(retrieval_strategy=...)`.
- Produces: `retrieval-eval-dry-run` and `run-retrieval-eval` commands.

- [ ] **Step 1: Write dry-run isolation tests**

Create a valid manifest file, monkeypatch `build_application` and `BeirSciFact.ensure` to raise if
called, invoke `retrieval-eval-dry-run`, and assert canonical manifest JSON. Add one invalid-manifest
case asserting a Typer parameter error.

- [ ] **Step 2: Run dry-run tests and confirm RED**

Run:

```bash
uv run pytest tests/test_cli.py -k retrieval_eval_dry_run -q
```

Expected: CLI reports no such command.

- [ ] **Step 3: Implement the dry-run command**

Follow the generation dry-run pattern exactly:

```python
@app.command("retrieval-eval-dry-run")
def retrieval_eval_dry_run(
    manifest: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Complete retrieval-run-manifest/v1 JSON file.",
        ),
    ],
) -> None:
    try:
        validated = RetrievalRunManifest.from_json(manifest.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--manifest") from exc
    typer.echo(validated.to_json(), nl=False)
```

- [ ] **Step 4: Write run-command boundary tests**

Monkeypatch the corpus, application builder, executor, record reader, report builder, and writer.
Assert the command:

- loads only `TRAIN_VALIDATION`;
- verifies exact corpus/query file hashes and canonical qrels hash before application construction;
- rejects a manifest missing any of `application-image`, `postgres-image`, `embedding-model`,
  `colbert-model`, `colbert-tokenizer`, `pg-tokenizer-extension`, `pgvector-extension`, or
  `vchord-bm25-extension`;
- builds each frozen strategy once in manifest order;
- passes the same query mapping, cutoff, run ID, and output path to the executor;
- derives the report from reread raw rows and the corpus qrels;
- emits expected/preexisting/written/failed rows plus report path;
- stops before building applications on any digest mismatch.

- [ ] **Step 5: Run command tests and confirm RED**

Run:

```bash
uv run pytest tests/test_cli.py -k run_retrieval_eval -q
```

Expected: CLI reports no such command.

- [ ] **Step 6: Implement a narrow application adapter and run command**

Keep the adapter private to the CLI module:

```python
class _ApplicationSearchRetriever:
    def __init__(self, application: RagApplication) -> None:
        self._application = application

    def search(self, query: str, limit: int) -> list[SearchHit]:
        return self._application.search(query, limit=limit)
```

The command must validate dataset digests before this construction:

```python
retrievers = {
    strategy: _ApplicationSearchRetriever(build_application(retrieval_strategy=strategy))
    for strategy in manifest.strategies
}
```

Then run the executor, reread raw records, build/write the sibling report, and emit the summary.
Do not alter `evaluate`, `diagnose-candidates`, `build_application`, or the default strategy.

- [ ] **Step 7: Document the operator contract**

In `docs/project/retrieval-evaluation.md`, record schemas, fixed values, digest definitions, dry-run
and run commands, resume/error semantics, internal-evidence limitation, and the no-repair-after-open
rule. Add concise links and command examples to README. Add an Unreleased changelog entry that
states no retrieval default has yet changed.

- [ ] **Step 8: Verify and commit Task 4**

Run:

```bash
uv run pytest tests/test_cli.py tests/test_retrieval_evaluation.py -q
uv run ruff format --check src tests
uv run ruff check src tests
uv run pyright
git diff --check
```

Commit and push:

```bash
git add src/scifact_rag/cli.py src/scifact_rag/retrieval_evaluation.py tests/test_cli.py tests/test_retrieval_evaluation.py docs/project/retrieval-evaluation.md README.md CHANGELOG.md
git commit -m "feat: add reproducible retrieval comparison CLI"
git push origin main
```

---

### Task 5: Stable evaluator review before live evidence

**Files:**
- Modify only if review findings are accepted through the Issue #6 loop and remain within declared paths.
- Evidence: `.harness/runs/issue-6-retrieval-default.json` through `tools/loop.py`.

**Interfaces:**
- Consumes: completed Tasks 1–4 and Issue #6 criteria AC1–AC3/AC5.
- Produces: independent evaluator verdict, affected-check evidence, and a pushed live-run candidate.

- [ ] **Step 1: Freeze the evaluator review candidate**

Record the current commit, worktree status, and baseline-relative paths in the engineering loop.
Do not modify the candidate after review starts.

- [ ] **Step 2: Obtain one independent bounded review**

The verifier must map AC1–AC3 and AC5 to the spec, code, raw test evidence, and exact candidate
identity; inspect error/resume behavior and claim boundaries; and return one deduplicated finding
batch or a clean verdict. Do not ask the verifier to redesign retrieval or investigate unrelated
security surfaces.

- [ ] **Step 3: Resolve any finding batch through the loop contract**

If findings exist, disposition all of them before mutation, record proportionality, start one new
attempt for accepted in-scope repairs, and rerun affected checks. If a finding requires retriever
behavior, candidate introspection, dependency, or write-scope expansion, stop and revise the owner
contract rather than absorbing it.

- [ ] **Step 4: Run affected checks before consuming live evidence**

Run:

```bash
uv run pytest tests/test_retrieval_evaluation.py tests/test_cli.py -q
uv run ruff check src tests
uv run pyright
git diff --check
git status --short
```

Record these commands at targeted or affected tiers. The one full `make smoke` gate belongs only
in Task 7 after result recording and documentation reconciliation.

- [ ] **Step 5: Commit and push review repairs if any**

```bash
git add src/scifact_rag/retrieval_evaluation.py src/scifact_rag/cli.py tests/test_retrieval_evaluation.py tests/test_cli.py docs/project/retrieval-evaluation.md README.md CHANGELOG.md
git commit -m "fix: close retrieval evaluation review"
git push origin main
```

If the review is clean and there is no diff, do not create an empty commit.
If a repair commit exists, repeat the bounded review on that new commit and require a clean verdict
before Task 6.

---

### Task 6: Fixed DGX execution and retrieval-default decision evidence

**Files:**
- Create locally: `artifacts/retrieval-default-validation/manifest.json`
- Create locally: `artifacts/retrieval-default-validation/results.jsonl`
- Create locally: `artifacts/retrieval-default-validation/results.report.json`
- Create: `docs/reports/issue-6-retrieval-default-validation.md`
- Create: `docs/adr/0029-retrieval-default-selection.md`
- Modify: `docs/reports/scifact-retrieval-leaderboard.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: verified engineering candidate, current DGX containers/database, exact manifest/digest contracts.
- Produces: one immutable local raw run, retained report hashes, a no-tuning ADR decision, and Issue #6 evidence.

- [ ] **Step 1: Inspect services without mutation**

Read Compose service state, PostgreSQL extension/row counts, ColBERT health/model identity, app image
identity, and current Git commit. Do not start, stop, restart, pull, or rebuild until existing state
is known. Stop if the database representation or service revisions differ from the manifestable
frozen boundary.

- [ ] **Step 2: Create and dry-run one complete manifest**

Use exact SHA-256 values for `data/scifact/corpus.jsonl`, `data/scifact/queries.jsonl`, and canonical
validation qrels; exact image/model/extension revisions from current configuration and live state;
the current engineering commit; and results path
`artifacts/retrieval-default-validation/results.jsonl`.

Run:

```bash
docker compose run --rm app retrieval-eval-dry-run \
  --manifest artifacts/retrieval-default-validation/manifest.json
```

The canonical output must equal the manifest bytes. This command must not contact PostgreSQL or
ColBERT.

- [ ] **Step 3: Run the fixed comparison once**

Run:

```bash
docker compose run --rm app run-retrieval-eval \
  --manifest artifacts/retrieval-default-validation/manifest.json \
  --data-dir data
```

Do not change code, manifest parameters, services, or data after opening results. If the run records
a genuine retrieval failure, retain it and stop for Issue #6 disposition rather than rerunning under
the same run ID.

- [ ] **Step 4: Verify result integrity without selecting parameters**

Check exact row count `480`, unique query-strategy keys, zero malformed rows, report recomputation,
manifest/results/report SHA-256 values, and per-strategy failure counts. Compare each strategy's
metrics, latency, relevant-document gains/losses, and top-rank transitions. Do not run another
strategy or alter cutoff.

- [ ] **Step 5: Record the evidence and decision**

Write `docs/reports/issue-6-retrieval-default-validation.md` with exact commands, revisions, hashes,
counts, metrics, transitions, latency, failures, service requirements, and the explicit
already-inspected evidence limitation. Update the leaderboard with one clearly labeled internal
comparison table.

Write ADR-0029 using the predeclared Pareto rule. Select the simplest non-dominated default; keep
other strategies named and opt-in. If operational cost and quality do not support a unique choice,
retain the current default and state that the evidence is inconclusive rather than inventing a
tie-break after results.

- [ ] **Step 6: Record the result without changing the product default**

Update the changelog with the retained evidence and ADR disposition. Comment on Issue #6 with exact
commit and artifact hashes, but keep it open until Task 7 reconciles the product default and final
gate. Do not alter the existing CLI/composition default or Issue #5 in this task.

- [ ] **Step 7: Verify documentation consistency and commit**

Run targeted report/hash consistency checks, `git diff --check`, and the smallest documentation
contract checks required by the repository. Do not rerun the live comparison or claim a second
full engineering gate for documentation-only result recording.

Commit and push:

```bash
git add docs/reports/issue-6-retrieval-default-validation.md docs/adr/0029-retrieval-default-selection.md docs/reports/scifact-retrieval-leaderboard.md CHANGELOG.md
git commit -m "docs: record retrieval default decision"
git push origin main
```

---

### Task 7: Reconcile the recommendation and close the final gate

**Files:**
- Modify: `docs/project/roadmap.md`
- Modify: `docs/project/handoff.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Evidence: `.harness/runs/issue-6-retrieval-default.json` through `tools/loop.py`.

**Interfaces:**
- Consumes: ADR-0029 and the retained fixed report from Task 6.
- Produces: an explicit default recommendation, final independent approval, release-impact recommendation, one full gate, loop report, and reconciled Issue #6.

- [ ] **Step 1: Reconcile user-facing documentation without changing runtime behavior**

Update roadmap, handoff, README, and changelog with ADR-0029's recommendation, the two alternatives,
the internal-evidence limitation, and operational service costs. Keep the existing runtime default
unchanged in Issue #6: applying a different recommendation is a separate owner-authorized behavior
change after the evidence is reviewed. Do not claim clean validation, external generalization,
generation improvement, or release readiness.

- [ ] **Step 2: Check, commit, and push the reconciled documentation**

```bash
git diff --check
git add docs/project/roadmap.md docs/project/handoff.md README.md CHANGELOG.md
git commit -m "docs: close retrieval default evaluation"
git push origin main
```

Re-read `origin/main` and confirm the worktree is clean before opening final review.

- [ ] **Step 3: Obtain final independent review of the exact clean commit**

Review AC1–AC5 against the exact code, raw artifact hashes, report, ADR, documentation, and current
worktree digest. The verifier must not have authored the candidate. Resolve one complete finding
batch through the engineering loop before mutation; any accepted repair starts a new attempt and
invalidates prior checks.

- [ ] **Step 4: Record release impact and run exactly one final full gate**

Record `patch`: optional evaluation commands and schemas are added while existing command behavior
and the runtime retrieval default remain unchanged. Then run exactly once on the final reviewed
attempt:

```bash
make smoke
python3 tools/product_version.py
git diff --check
git status --short
```

Record `make smoke` as the only `full` check and the other commands at their accurate narrower
tiers. Any repair after this point requires a new attempt, a new independent review, and a new
single full gate.

- [ ] **Step 5: Finish the loop and reconcile Issue #6**

Re-read `origin/main`, Issue #6, and local status. Mark Issue #6 complete only when every criterion
is evidenced, finish the engineering loop report, and leave Issue #5 unchanged. No repository
commit follows the final review/full gate. If the owner later accepts a recommendation that differs
from the current runtime default, open a separate bounded behavior-change task with its own TDD and
release-impact gate.
