# Evidence-selection error audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a deterministic, text-free audit of the retained 101-prompt selected-context reader results, with fail-closed provenance and one evidence-bounded next-decision statement.

**Architecture:** A tracked standalone Python script adapts only `tools/evidence_inference_reader.py`'s label parser, interval convention, and native metrics. It runs on the Mac planning host against an explicit read-only retained-artifact root, writes one ignored ID/offset-only case artifact, then renders tracked aggregate-only research outputs.

**Tech Stack:** Python 3.12 standard library, pytest, existing reader-audit helpers, JSON/JSONL.

**Spec:** `docs/superpowers/specs/2026-09-19-evidence-selection-error-audit-design.md`

## Recovery rulings — 2026-09-19

The recovery completes the existing accepted slice on its Mac artifact host. Prior helper commits
are retained; they did not meet the full acceptance criteria. The original DGX loop remains
preserved, and recovery evidence starts at `20260919T172022Z-d75f4696` before recovery edits.

The root-permission check in the illustrative design/plan was an implementation mistake: the
owner's retained directory is writable, while the audit must treat its contents as immutable.
Do not chmod or copy it. Check resolved output separation and before/after input digests instead.
This clarification preserves the accepted prohibition on modifying the evidence.

Issue #31 requires definitions frozen before case analysis. Persist an ignored, text-free input
manifest after integrity validation and before deriving outcomes. If analysis then fails, retain
that manifest as failure evidence but emit no successful summary. This supersedes the illustrative
instruction below to leave no partial directory at all. It never permits overwriting an existing
output or treating a partial directory as completion.

## Global Constraints

- Execute only on the Mac planning host with `--reader-artifact-root` set to the retained
  `artifacts/evidence-inference-v2/reader-v1/` directory; do not expect the DGX checkout to hold it.
- Treat the supplied root as read-only; do not copy, stage, regenerate, alter, or repair inputs.
- Bind preparation manifest `888834d7ff034b391f6d90edb9cc819f88e8265823fdf25579f35fce6c88fc20`, runtime `891d04c4be3175c803fd1308f1eb24cc6c56c386885d25851752dbac4ce2db9d`, and ledger `e5f629cd330609a436df7959a115508252b6e510166eb1a81d23c5c4862cd9e2` before case analysis.
- Validate preparation order and inference event order independently; join only by prompt/article IDs.
- Union valid touching/overlapping reference spans; reject malformed intervals and overlapping source windows.
- Make zero network, model, reader, selector, reviewer, or GPU calls; add no dependency or product/runtime/API behavior.
- Keep ignored per-case data under `artifacts/evidence-inference-v2/selection-audit-v1/` and omit all raw article text, prompts, evidence text, and responses.
- Tracked report/summary must be text-free and must not claim clinical correctness, causality, selector quality, semantic role errors, human calibration, or statistical significance.
- Do not modify Issue #28 artifacts or activate `role-separated-analysis`.

## Review Focus

- A Mac root that is missing or has mismatched retained identities must fail before case analysis. Read-only is an audit behavior: owner-writable inputs remain valid; do not chmod them. Reject output paths inside the resolved input tree and verify input hashes after analysis.
- A valid overlap/touch in reference intervals must be unioned, while a source-window overlap must fail instead of being silently merged.
- Preparation order and ledger/inference order may differ; ID joins must remain correct and a broken order within either artifact must fail.
- An `insufficient_evidence` output must remain an abstention, never be normalized to native neutral, and remain wrong in correctness totals.
- The two-window upper bound must select two distinct windows, preserve deterministic ties, and remain below complete coverage for a reference requiring more than two disjoint windows.

### Task 1: Define the fail-closed audit input contract

**Files:**

- Create: `tools/evidence_selection_audit.py`
- Create: `tests/test_evidence_selection_audit.py`

**Interfaces:**

- Consumes: explicit `Path` values for the retained reader-v1 root, tracked public result JSON, and a fresh ignored output directory.
- Produces: `AuditInputs`, `AuditError`, `sha256_file`, `load_json`, `load_jsonl`, and `bind_inputs`.

- [ ] **Step 1: Write the failing input-boundary tests**

```python
def test_bind_inputs_requires_exact_read_only_reader_tree(tmp_path: Path):
    root = tmp_path / "reader-v1"
    root.mkdir()
    with pytest.raises(audit.AuditError, match="prepared-002"):
        audit.bind_inputs(root, tmp_path / "published.json")


def test_bind_inputs_rejects_digest_drift_before_case_loading(tmp_path: Path):
    root, published = make_retained_tree(tmp_path)
    (root / "prepared-002" / "manifest.json").write_text("{}")
    with pytest.raises(audit.AuditError, match="preparation manifest SHA-256 mismatch"):
        audit.bind_inputs(root, published)
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_evidence_selection_audit.py -k 'bind_inputs' -q`

Expected: FAIL because `tools/evidence_selection_audit.py` does not exist.

- [ ] **Step 3: Implement the narrow input contract**

```python
PREPARATION_SHA256 = "888834d7ff034b391f6d90edb9cc819f88e8265823fdf25579f35fce6c88fc20"
RUNTIME_SHA256 = "891d04c4be3175c803fd1308f1eb24cc6c56c386885d25851752dbac4ce2db9d"
LEDGER_SHA256 = "e5f629cd330609a436df7959a115508252b6e510166eb1a81d23c5c4862cd9e2"


@dataclass(frozen=True)
class AuditInputs:
    root: Path
    prepared: Path
    run: Path
    ledger: Path
    evaluation: Path
    public_results: Path


def bind_inputs(root: Path, public_results: Path) -> AuditInputs:
    if not root.is_dir():
        raise AuditError("reader artifact root must be an existing directory")
    prepared = root / "prepared-002"
    run = root / "live-20260919-001"
    ledger = run / "ledger.jsonl"
    evaluation = root / "evaluation-20260919-001" / "report.json"
    required = (prepared / "manifest.json", run / "runtime.json", ledger, evaluation, public_results)
    missing = next((path for path in required if not path.is_file()), None)
    if missing is not None:
        raise AuditError(f"missing required retained path: {missing.relative_to(root)}")
    if sha256_file(prepared / "manifest.json") != PREPARATION_SHA256:
        raise AuditError("preparation manifest SHA-256 mismatch")
    if sha256_file(run / "runtime.json") != RUNTIME_SHA256:
        raise AuditError("runtime SHA-256 mismatch")
    if sha256_file(ledger) != LEDGER_SHA256:
        raise AuditError("ledger SHA-256 mismatch")
    return AuditInputs(root, prepared, run, ledger, evaluation, public_results)
```

- [ ] **Step 4: Run the input-boundary tests to verify they pass**

Run: `uv run pytest tests/test_evidence_selection_audit.py -k 'bind_inputs' -q`

Expected: PASS, with altered/missing roots failing before case rows are read.

- [ ] **Step 5: Commit the input contract**

```bash
git add tools/evidence_selection_audit.py tests/test_evidence_selection_audit.py
git commit -m "feat: bind retained selection audit inputs"
```

### Task 2: Reconcile outcomes without positional joins

**Files:**

- Modify: `tools/evidence_selection_audit.py`
- Modify: `tests/test_evidence_selection_audit.py`

**Interfaces:**

- Consumes: `AuditInputs`, `reader.parse_label`, `reader.native_metrics`, prepared prompt/reference records, and completed ledger events.
- Produces: `OutcomeRow`, `validate_preparation_order`, `validate_inference_order`, and `reconcile_outcomes`.

- [ ] **Step 1: Write failing outcome and ordering tests**

```python
def test_reconcile_outcomes_joins_differently_ordered_sources_by_id():
    prepared = [prompt("p2", "a2"), prompt("p1", "a1")]
    events = completed_events_in_inference_order(["p1", "p2"])
    rows = audit.reconcile_outcomes(prepared, references_for(prepared), events)
    assert [row.prompt_id for row in rows] == ["p2", "p1"]
    assert rows[0].article_id == "a2"


def test_reconcile_outcomes_preserves_abstention_as_wrong():
    rows = audit.reconcile_outcomes(*one_prompt_sources(selected='{"label":"insufficient_evidence"}'))
    assert rows[0].predictions["selected"] == "insufficient_evidence"
    assert rows[0].abstentions["selected"] is True
    assert rows[0].correctness["selected"] is False
```

- [ ] **Step 2: Run them to verify the outcome contract fails**

Run: `uv run pytest tests/test_evidence_selection_audit.py -k 'outcome or ordered' -q`

Expected: FAIL because the reconciliation API is absent.

- [ ] **Step 3: Implement IDs, independent order validation, and all-arm partitioning**

```python
@dataclass(frozen=True)
class OutcomeRow:
    prompt_id: str
    article_id: str
    target: str
    predictions: dict[str, str | None]
    correctness: dict[str, bool]
    abstentions: dict[str, bool]


def index_unique(rows, field: str, label: str) -> dict[str, dict[str, object]]:
    indexed = {row[field]: row for row in rows}
    if len(indexed) != len(rows):
        raise AuditError(f"duplicate {label} identity")
    return indexed


def index_unique_terminal_events(events) -> dict[tuple[str, str], dict[str, object]]:
    indexed = {(row["prompt_id"], row["arm"]): row for row in events}
    if len(indexed) != len(events):
        raise AuditError("duplicate terminal event")
    return indexed


def parse_terminal_label(event: dict[str, object]) -> str | None:
    if event["status"] != "completed":
        raise AuditError("incomplete retained terminal event")
    content = event["response"]["choices"][0]["message"]["content"]
    return reader.parse_label(content)


def validate_preparation_order(manifest: dict[str, object], prompts: list[dict[str, object]]) -> None:
    if [row["prompt_id"] for row in prompts] != manifest["prompt_order"]:
        raise AuditError("preparation prompt order mismatch")


def reconcile_outcomes(prepared, references, terminal_events) -> list[OutcomeRow]:
    prompts = index_unique(prepared, "prompt_id", "prepared prompt")
    refs = index_unique(references, "prompt_id", "reference")
    events = index_unique_terminal_events(terminal_events)
    if set(prompts) != set(refs):
        raise AuditError("prepared/reference prompt membership mismatch")
    rows = []
    for prompt_id in [item["prompt_id"] for item in prepared]:
        prompt, reference = prompts[prompt_id], refs[prompt_id]
        if prompt["article_id"] != reference["article_id"]:
            raise AuditError("prompt/reference article mismatch")
        predictions = {
            arm: parse_terminal_label(events[(prompt_id, arm)])
            for arm in ("full", "selected", "oracle")
        }
        rows.append(OutcomeRow(
            prompt_id=prompt_id,
            article_id=prompt["article_id"],
            target=reference["target"],
            predictions=predictions,
            correctness={arm: predictions[arm] == reference["target"] for arm in predictions},
            abstentions={arm: predictions[arm] == "insufficient_evidence" for arm in predictions},
        ))
    return rows
```

Implement concrete eight-key correctness counting with keys such as `full=1|selected=0|oracle=1`,
paired label-transition tables for all three arm comparisons, and per-arm article counts. Refuse
any non-native/non-abstention label, duplicate ID, missing arm, foreign article ID, or mismatch
with `reader.native_metrics` and the public text-free comparison target.

- [ ] **Step 4: Run the focused outcome suite to verify it passes**

Run: `uv run pytest tests/test_evidence_selection_audit.py -k 'outcome or ordered or abstention' -q`

Expected: PASS, including intentionally different preparation/inference orders.

- [ ] **Step 5: Commit the reconciliation behavior**

```bash
git add tools/evidence_selection_audit.py tests/test_evidence_selection_audit.py
git commit -m "feat: reconcile retained reader outcomes"
```

### Task 3: Add exact coverage, ranks, and two-window diagnostics

**Files:**

- Modify: `tools/evidence_selection_audit.py`
- Modify: `tests/test_evidence_selection_audit.py`

**Interfaces:**

- Consumes: `OutcomeRow`, source windows, selected-window intervals, reference intervals, and recorded selector scores.
- Produces: `validate_source_windows`, `window_geometry`, `two_window_upper_bound`, and `geometry_cross_tabs`.

- [ ] **Step 1: Write failing interval and ranking tests**

```python
def test_reference_spans_union_but_source_window_overlap_fails():
    assert audit.coverage([[0, 4], [3, 8]], [[2, 6]])["reference_characters"] == 8
    with pytest.raises(audit.AuditError, match="overlapping source windows"):
        audit.validate_source_windows([window(0, 4), window(3, 7)])


def test_two_window_bound_uses_distinct_windows_and_offset_ties():
    result = audit.two_window_upper_bound(
        [window(0, 4, score=1), window(4, 8, score=1), window(8, 12, score=0)],
        [[1, 3], [5, 7]],
    )
    assert result.intervals == ((0, 4), (4, 8))
    assert result.recall == 1.0


def test_two_window_bound_cannot_cover_three_disjoint_required_windows():
    result = audit.two_window_upper_bound([window(0, 2), window(4, 6), window(8, 10)], [[0, 2], [4, 6], [8, 10]])
    assert result.recall == pytest.approx(2 / 3)
```

- [ ] **Step 2: Run the geometry tests to verify they fail**

Run: `uv run pytest tests/test_evidence_selection_audit.py -k 'coverage or window or two_window' -q`

Expected: FAIL because the geometry API is absent.

- [ ] **Step 3: Implement exact half-open geometry**

```python
def validate_source_windows(windows: list[dict[str, object]]) -> None:
    ordered = sorted(windows, key=lambda item: (item["start"], item["end"]))
    for previous, current in pairwise(ordered):
        if current["start"] < previous["end"]:
            raise AuditError("overlapping source windows")


def two_window_upper_bound(windows, reference) -> UpperBound:
    pairs = [pair for pair in combinations(windows, 2)] or [(windows[0],)]
    ranked = sorted(
        pairs,
        key=lambda pair: (-coverage([w.interval for w in pair], reference)["intersection_characters"],
                          tuple((w.start, w.end) for w in pair)),
    )
    return UpperBound.from_pair(ranked[0], reference)
```

Use `reader.union_intervals`/`reader.span_coverage` for reference overlap, validate finite scores,
assign ranks by `(-score, start, end)`, and retain selected intervals in original source order.
Cross-tab geometry against outcome groups and produce prompt and article denominators without
calling partial coverage insufficient or complete coverage sufficient.

- [ ] **Step 4: Run the focused geometry suite to verify it passes**

Run: `uv run pytest tests/test_evidence_selection_audit.py -k 'coverage or window or two_window' -q`

Expected: PASS for touching reference spans, source-window refusal, ties, one-window cases, and
more-than-two-window limits.

- [ ] **Step 5: Commit the geometry implementation**

```bash
git add tools/evidence_selection_audit.py tests/test_evidence_selection_audit.py
git commit -m "feat: audit retained selection geometry"
```

### Task 4: Render an auditable, text-free retained analysis

**Files:**

- Modify: `tools/evidence_selection_audit.py`
- Modify: `tests/test_evidence_selection_audit.py`

**Interfaces:**

- Consumes: validated `AuditInputs`, outcome rows, and geometry rows.
- Produces: `run_audit`, `selection-audit-manifest.json`, `case-rows.jsonl`, and an aggregate summary dict.

- [ ] **Step 1: Write failing output-safety tests**

```python
def test_run_audit_refuses_existing_output_and_never_emits_source_text(tmp_path: Path):
    inputs = bound_synthetic_inputs(tmp_path)
    output = tmp_path / "selection-audit-v1"
    output.mkdir()
    with pytest.raises(audit.AuditError, match="audit output exists"):
        audit.run_audit(inputs, output)
    output.rmdir()
    summary = audit.run_audit(inputs, output)
    assert "article text" not in (output / "case-rows.jsonl").read_text()
    assert summary["prompt_count"] == 1
```

- [ ] **Step 2: Run the output tests to verify they fail**

Run: `uv run pytest tests/test_evidence_selection_audit.py -k 'run_audit or output' -q`

Expected: FAIL because no renderer exists.

- [ ] **Step 3: Implement the deterministic CLI and output schema**

```text
uv run python tools/evidence_selection_audit.py run \
  --reader-artifact-root "$READER_ARTIFACT_ROOT" \
  --public-results docs/research/evidence-inference-reader-results.json \
  --output artifacts/evidence-inference-v2/selection-audit-v1
```

Require `output` not to exist. Write `selection-audit-manifest.json` with input relative paths,
SHA-256 values, declared counts, script digest, and format version; write `case-rows.jsonl` with
only IDs, interval offsets, labels, boolean statuses, scores, ranks, and counts; write
`summary.json` with all aggregate totals. Before rendering, enforce the Issue #31 20/101/101/303/
101/1,599 counts and the 92/79/92 correctness plus 0/5/1 abstention totals. Any mismatch exits
nonzero and writes no partial directory.

- [ ] **Step 4: Run the output-safety suite to verify it passes**

Run: `uv run pytest tests/test_evidence_selection_audit.py -k 'run_audit or output' -q`

Expected: PASS, with a fresh text-free artifact only after complete validation.

- [ ] **Step 5: Execute the retained audit on the Mac planning host**

Set `READER_ARTIFACT_ROOT` to the exact absolute `reader-v1` path in the Mac planning worktree,
not a copied DGX location. Run with the verified Python 3.12 environment after identity checks pass. On the planning Mac, `/tmp/scifact-reader-env/bin/python` and `/opt/homebrew/bin/uv` are available; non-login SSH PATH discovery is not a runtime availability check.
Record the exact absolute root in the ignored manifest only. If the input root is unavailable or
any identity mismatches, record the evidence stop in the tracked report instead; do not regenerate
or transplant inputs.

- [ ] **Step 6: Commit the executable audit contract**

```bash
git add tools/evidence_selection_audit.py tests/test_evidence_selection_audit.py
git commit -m "feat: render selection audit evidence"
```

### Task 5: Publish only the evidence-bound conclusion

**Files:**

- Create: `docs/research/evidence-selection-error-audit.md`
- Create: `docs/research/evidence-selection-error-audit-summary.json`
- Modify: `docs/project/handoff.md`

**Interfaces:**

- Consumes: fresh ignored `summary.json`, `selection-audit-manifest.json`, and case artifact IDs/offsets.
- Produces: text-free tracked report, aggregate JSON summary, and handoff entry.

- [ ] **Step 1: Add a failing tracked-output contract test**

```python
def test_published_audit_summary_is_derived_from_audited_aggregate(tmp_path: Path):
    summary = audit.run_audit(bound_synthetic_inputs(tmp_path), tmp_path / "out")
    published = audit.public_summary(summary)
    assert published["prompt_count"] == summary["prompt_count"]
    assert "raw_text" not in published
    assert published["claim_boundary"] == "deterministic overlap and rank audit only"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_evidence_selection_audit.py -k 'published_audit_summary' -q`

Expected: FAIL because `public_summary` does not exist.

- [ ] **Step 3: Implement the aggregate projection and write documentation from it**

```python
def public_summary(summary: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "evidence-selection-error-audit-summary/v1",
        "claim_boundary": "deterministic overlap and rank audit only",
        "input_digests": summary["input_digests"],
        "prompt_count": summary["prompt_count"],
        "article_count": summary["article_count"],
        "outcomes": summary["outcomes"],
        "geometry": summary["geometry"],
        "decision": summary["decision"],
    }
```

Write the report with exact aggregate outcomes, geometry cross-tabs, unresolved interpretations,
the no-intervention or one-hypothesis decision, fresh article-disjoint validation requirement,
Issue #28 separation, and bounded future Lattice relevance. Use `VERIFIED`, `INFERRED`, and
`UNAVAILABLE` labels. Update the handoff with the same boundary; never include raw case text or
responses. If Task 4 stopped, publish only the explicit evidence stop and preserve the next-owner
decision.

- [ ] **Step 4: Run the published-output test to verify it passes**

Run: `uv run pytest tests/test_evidence_selection_audit.py -k 'published_audit_summary' -q`

Expected: PASS, and manually inspect JSON/report text for no raw content or causal overclaim.

- [ ] **Step 5: Commit the published audit evidence**

```bash
git add docs/research/evidence-selection-error-audit.md \
  docs/research/evidence-selection-error-audit-summary.json \
  docs/project/handoff.md tools/evidence_selection_audit.py tests/test_evidence_selection_audit.py
git commit -m "docs: report evidence selection audit"
```

### Task 6: Verify, review, and finish the loop

**Files:**

- Modify: `.harness/runs/20260919T160057Z-c72c4f05/*` through `tools/loop.py` only

**Interfaces:**

- Consumes: stable candidate, recorded tests, retained audit manifest, report/summary, and independent reviewer evidence.
- Produces: criterion-linked checks, release-impact recommendation, review verdict, loop report, and handoff completion state.

- [ ] **Step 1: Run targeted checks and record their evidence**

Run: `uv run pytest tests/test_evidence_selection_audit.py -q`

Expected: PASS. Record it as `targeted` against AC1–AC4, including elapsed time.

- [ ] **Step 2: Run affected reader-contract checks and record them**

Run: `uv run pytest tests/test_evidence_inference_reader.py tests/test_evidence_inference_reader_run.py -q`

Expected: PASS. Record it as `affected` against AC1–AC3.

- [ ] **Step 3: Record the release impact before the final gate**

Run: `python3 tools/loop.py record-release-impact --run 20260919T160057Z-c72c4f05 --level none --reason "The tracked change adds an offline research audit and documentation only; no public compatibility contract changes."`

Expected: current candidate impact record succeeds.

- [ ] **Step 4: Run exactly one final full gate and static checks**

Run: `make smoke && git diff --check && git status --short`

Expected: `make smoke` exits 0; diff check is clean; status contains only declared Issue 31 paths and ignored artifacts.

- [ ] **Step 5: Obtain independent stable-candidate review**

Provide the reviewer the governing Issue #31, this spec/plan, base `c72c4f0`, candidate commit,
ignored audit-manifest digest, and exact commands. The reviewer reproduces outcome partition and
geometry, checks text-free publication and claim limits, records a deduplicated batch, then gives
an approve/revise/reject verdict bound to the unchanged candidate.

- [ ] **Step 6: Reconcile the loop without external mutations**

Run: `python3 tools/loop.py finish --run 20260919T160057Z-c72c4f05`

Expected: a reported run only after all AC evidence, current release impact, independent approval,
and declared write scope validate. Do not change GitHub Issue or Project state without separate
explicit authorization.
