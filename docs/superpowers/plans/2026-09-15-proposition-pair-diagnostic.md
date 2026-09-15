# Grounded Proposition-Pair Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one frozen artifact showing whether grounded proposition-pair features separate annotated decisive candidates from Phase 3 neutral-to-decisive false positives.

**Architecture:** Reuse the fixed Phase 3 candidate/results boundary, existing Qwen endpoint, and MiniLM embedder. Extract only claims and documents present in the frozen pools into an immutable JSONL diagnostic artifact, apply strict source-span validation and predeclared coverage gates, then compute five fixed pairwise features and one fixed mean. No database, connected graph, runtime scorer, or default changes.

**Tech Stack:** Python 3.12 dataclasses, Typer, httpx, existing MiniLM adapter, immutable JSON/JSONL artifacts, Docker Compose application client.

**Spec:** `docs/superpowers/specs/2026-09-15-proposition-graph-scoring-design.md`

## Global constraints

- Work only on Issue #9 in the isolated `phase4-proposition-graph` worktree.
- Add no package, service, database table, harness feature, or public API.
- Keep PostgreSQL schemas, Compose services, `search`, `ask`, evaluation defaults, and the public-test boundary unchanged.
- Treat extracted propositions as source-grounded diagnostic assertions, never truth.
- Freeze the source/audit manifests, extraction prompt/schema, five formulas, coverage gates, and signal threshold before live results.
- Add no more than nine focused test functions; use parametrization inside them for invalid cases.
- Push each commit. Do not open proposition results before the implementation candidate passes focused checks and independent review.

## File structure

- Create `src/scifact_rag/proposition.py`: proposition value objects, strict grounding validation, canonical identities, and five pairwise formulas.
- Create `src/scifact_rag/proposition_evaluation.py`: fixed source/audit manifests, extraction journal, coverage gates, executor, raw pair records, ROC-AUC/AP report derivation, and atomic artifact writes.
- Create `src/scifact_rag/adapters/proposition_extraction.py`: strict OpenAI-compatible Qwen JSON-Schema adapter.
- Modify `src/scifact_rag/ports.py`: add the model-neutral `PropositionExtractor` protocol.
- Modify `src/scifact_rag/composition.py`: explicitly wire the existing Qwen and MiniLM adapters for this diagnostic only.
- Modify `src/scifact_rag/cli.py`: add prepare/dry-run/run commands without changing existing defaults.
- Create `tests/test_proposition.py`: three contract/formula/gate tests.
- Create `tests/test_proposition_evaluation.py`: three audit/manifest/journal/report tests.
- Create `tests/test_proposition_extraction_adapter.py`: two strict transport/schema tests.
- Modify `tests/test_cli.py`: one CLI isolation and validation test.
- Modify only after live evidence: ADR outcome, roadmap, handoff, technical reference, changelog, and one report.

---

### Task 1: Grounded proposition contract and fixed pair features

**Files:**
- Create: `src/scifact_rag/proposition.py`
- Test: `tests/test_proposition.py`

**Interfaces:**
- Produces: `SourceKind`, `PropositionPolarity`, `QualifierRole`, `GroundedSpan`, `PropositionQualifier`, `GroundedProposition`, `PropositionPairFeatures`, `source_identity()`, `proposition_identity()`, and `score_proposition_pairs()`.
- Consumes later: extraction adapter returns `GroundedProposition`; evaluation executor embeds surfaces and calls `score_proposition_pairs()`.

- [ ] **Step 1: Write three failing tests**

Test 1 constructs a source and valid proposition, then parametrizes mismatched text, out-of-range
offsets, foreign sentence containment, empty core arguments, unsupported polarity/qualifier roles,
and duplicate proposition identities. Require exact half-open Unicode spans and deterministic
canonical keys.

Test 2 supplies hand-computable normalized vectors and verifies exactly:

```python
entity = max(ss, so, os, oo)
predicate = pp
argument_direction = ((ss + oo) - (so + os)) / 2
polarity = 1.0 if claim.polarity == document.polarity else -1.0
qualifier = mean(best same-role similarity per claim qualifier) if claim.qualifiers else 0.0
structural = mean((entity, predicate, (argument_direction + 1.0) / 2.0))
pair_mean = mean((entity, predicate, (argument_direction + 1.0) / 2.0,
                  (polarity + 1.0) / 2.0, qualifier))
```

It also verifies stable-ID tie-breaking and that no proposition pair raises a typed error rather
than inventing zero evidence.

Test 3 verifies the frozen coverage gate: 100% usable claims, decisive documents, and audit
documents; at least 99% schema-valid terminal sources; and at least 95% usable candidate documents.
The fixed decisive-versus-false-positive comparison additionally requires 100% usable documents so
the canonical metrics cannot silently omit candidates.
Boundary values pass; each one-step violation stops with a named failed condition.

- [ ] **Step 2: Run the tests and confirm contract failures**

Run: `uv run pytest tests/test_proposition.py -q`

Expected: collection fails because `scifact_rag.proposition` does not exist.

- [ ] **Step 3: Implement the minimum immutable contracts and formulas**

Use frozen dataclasses with `slots=True`. `GroundedSpan.validate(source, sentence)` must compare the
exact source slice. `score_proposition_pairs()` accepts pre-normalized surface vectors through a
mapping keyed by `(proposition_id, field, qualifier_index)` so it contains no model dependency.
Map cosine values with `(value + 1.0) / 2.0`, reject non-finite/out-of-range inputs, rank pairs by
`(-structural, claim_proposition_id, document_proposition_id)`, and return the selected provenance.

- [ ] **Step 4: Run the focused tests**

Run: `uv run pytest tests/test_proposition.py -q`

Expected: 3 passed.

- [ ] **Step 5: Commit and push**

```bash
git add src/scifact_rag/proposition.py tests/test_proposition.py
git commit -m "feat: define grounded proposition pairs"
git push origin phase4-proposition-graph
```

### Task 2: Frozen source/audit manifests and resumable artifact journal

**Files:**
- Create: `src/scifact_rag/proposition_evaluation.py`
- Test: `tests/test_proposition_evaluation.py`

**Interfaces:**
- Consumes: `GenerationEvaluationSet`, `ScientificInferenceResult`, `EvidenceDocument`, and Task 1 proposition types.
- Produces: `PropositionRunManifest`, `PropositionSource`, `PropositionAuditRow`, `PropositionAuditReview`, `PropositionExtractionResult`, `PropositionExtractionJournal`, `build_source_manifest()`, `build_error_audit()`, and canonical JSON/JSONL readers/writers.

- [ ] **Step 1: Write three failing tests**

Test 4 constructs a miniature Phase 3 result set with all six confusion directions. Verify that
`build_error_audit()` includes every decisive-label error and selects neutral false positives by
prediction, evidence-margin quintile, and ascending candidate ID. Parameterize altered source
digests, counts, and duplicate candidate identities as failures.

Test 5 verifies that `build_source_manifest()` includes every claim and only distinct documents
present in Phase 3 results, sorts sources by `(kind, id)`, binds text digests and all fixed runtime
components, and rejects an evaluation/Phase 3 identity mismatch.

Test 6 appends success, valid-empty, and typed-failure terminal results; reopens exact state;
verifies missing-only resume; and rejects duplicate, conflicting, truncated, foreign-run, or
source-digest-mismatched rows. In the same test, verify report/raw digest consistency and exact
ROC-AUC/AP on a four-record fixture.

- [ ] **Step 2: Run the tests and confirm missing interfaces**

Run: `uv run pytest tests/test_proposition_evaluation.py -q`

Expected: collection fails because the evaluation module does not exist.

- [ ] **Step 3: Implement canonical manifests, audit selection, and journal**

Reuse the repository's strict dataclass parsing pattern: exact field sets, schema-version constants,
safe run IDs/paths, lowercase SHA-256 validation, finite numerics, deterministic ordering, and
atomic manifest/report replacement. JSONL append must flush and `os.fsync()` before returning.
Journal state has one terminal identity per source; unlike Phase 3, there is no attempt-start state
because the local read-only model request may be repeated only when no terminal result exists.

Implement binary metrics without adding a dependency:

- ROC-AUC is the Mann-Whitney probability with average ranks for ties.
- Average precision sorts by descending score then stable candidate ID and averages precision at
  positive ranks over total positives.

- [ ] **Step 4: Run the focused tests**

Run: `uv run pytest tests/test_proposition_evaluation.py -q`

Expected: 3 passed.

- [ ] **Step 5: Commit and push**

```bash
git add src/scifact_rag/proposition_evaluation.py tests/test_proposition_evaluation.py
git commit -m "feat: freeze proposition diagnostic artifacts"
git push origin phase4-proposition-graph
```

### Task 3: Strict Qwen extraction adapter

**Files:**
- Create: `src/scifact_rag/adapters/proposition_extraction.py`
- Modify: `src/scifact_rag/ports.py`
- Test: `tests/test_proposition_extraction_adapter.py`

**Interfaces:**
- Consumes: `PropositionSource` and Task 1 proposition types.
- Produces: `PropositionExtractor.extract(source) -> tuple[GroundedProposition, ...]` and `OpenAiCompatiblePropositionExtractor`.

- [ ] **Step 1: Write two failing tests**

Test 7 intercepts the HTTP request and verifies exact model, source ID/digest, temperature `0`, seed
`1729`, thinking disabled, strict `json_schema` response format, one request, and valid exact-span
conversion.

Test 8 parametrizes non-2xx response, invalid chat envelope, non-JSON content, extra/missing schema
fields, wrong source identity/digest, invented or mismatched spans, duplicate identities, and
unsupported enums. Require typed extraction failures and no fallback request.

- [ ] **Step 2: Run the tests and confirm missing adapter/port**

Run: `uv run pytest tests/test_proposition_extraction_adapter.py -q`

Expected: collection fails because the adapter and protocol do not exist.

- [ ] **Step 3: Implement the adapter**

Add the `PropositionExtractor` protocol under `TYPE_CHECKING` imports in `ports.py`. In the adapter,
freeze `PROPOSITION_PROMPT_ID`, prompt SHA-256, JSON Schema SHA-256, and seed. Use `httpx.post()` at
`{base_url}/chat/completions`; require one JSON object in message content; deserialize only exact
fields; then construct Task 1 value objects so source validation is centralized. Convert transport,
HTTP, envelope, JSON, schema, and grounding failures to distinct error codes without retries.

- [ ] **Step 4: Run adapter and affected existing tests**

Run: `uv run pytest tests/test_proposition_extraction_adapter.py tests/test_openai_compatible.py -q`

Expected: 5 passed.

- [ ] **Step 5: Commit and push**

```bash
git add src/scifact_rag/ports.py src/scifact_rag/adapters/proposition_extraction.py tests/test_proposition_extraction_adapter.py
git commit -m "feat: extract source-grounded propositions"
git push origin phase4-proposition-graph
```

### Task 4: Executor, fixed report, composition, and CLI

**Files:**
- Modify: `src/scifact_rag/proposition_evaluation.py`
- Modify: `src/scifact_rag/composition.py`
- Modify: `src/scifact_rag/cli.py`
- Modify: `tests/test_proposition_evaluation.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Produces: `PropositionEvaluationExecutor.run()`, `build_proposition_report()`, `build_proposition_evaluator()`, `prepare-proposition-pair-eval`, `proposition-pair-eval-dry-run`, and `run-proposition-pair-eval`.

- [ ] **Step 1: Extend the existing report test and add one CLI test**

Without adding another test function, extend Test 6 to execute a fake extractor/embedder over two
claims and candidate documents. Verify missing-only resume, exact embedding surface batches, the
coverage stop boundary, selected proposition provenance, five features, fixed mean, correlations,
artifact digests, and that an incomplete audit permits raw extraction but prevents accepted report
interpretation.

Add Test 9 in `tests/test_cli.py`. Use fake composition to verify that prepare writes the frozen
manifest/audit before any extraction, dry-run performs no network/database call, run validates the
fixed 160-case boundary and manifest digests, and existing CLI defaults are unchanged.

- [ ] **Step 2: Run the tests and confirm executor/CLI failures**

Run: `uv run pytest tests/test_proposition_evaluation.py tests/test_cli.py -q`

Expected: failures name the missing executor, report, composition, and commands.

- [ ] **Step 3: Implement the bounded workflow**

The prepare command reads the fixed evaluation set, Phase 3 journal, and local SciFact corpus;
derives distinct sources and the 100-row audit; writes immutable manifest/audit templates; and
refuses existing conflicting files. Dry-run re-derives every identity without calling Qwen or
MiniLM. Run resumes missing extraction, evaluates the coverage gate, embeds unique verified
surfaces in batches, writes raw pair records, and writes the accepted report only when audit review
is complete. All output files live beneath the manifest's relative artifact directory.

Composition must bind `Settings.generator_base_url`, `Settings.generator_model`,
`Settings.generator_api_key`, and `Settings.embedding_model`; it must not alter `build_application()`.

- [ ] **Step 4: Run focused and affected checks**

Run: `uv run pytest tests/test_proposition.py tests/test_proposition_evaluation.py tests/test_proposition_extraction_adapter.py tests/test_cli.py -q`

Run: `uv run ruff format --check src tests && uv run ruff check src tests && uv run pyright`

Expected: 9 new focused tests pass; existing tests in touched files remain green; static checks pass.

- [ ] **Step 5: Commit and push**

```bash
git add src/scifact_rag/proposition_evaluation.py src/scifact_rag/composition.py src/scifact_rag/cli.py tests/test_proposition_evaluation.py tests/test_cli.py
git commit -m "feat: run proposition pair diagnostic"
git push origin phase4-proposition-graph
```

### Task 5: Stable review, live diagnostic, decision, and documentation

**Files:**
- Create locally: `artifacts/proposition-pair-v1/manifest.json`
- Create locally: `artifacts/proposition-pair-v1/audit.jsonl`
- Create locally: `artifacts/proposition-pair-v1/audit-review.jsonl`
- Create locally: `artifacts/proposition-pair-v1/extractions.jsonl`
- Create locally only if gates pass: `artifacts/proposition-pair-v1/pairs.jsonl`, `artifacts/proposition-pair-v1/report.json`
- Create: `docs/reports/phase-4-proposition-pair-validation.md`
- Modify: `docs/adr/0031-proposition-graph-scoring.md`
- Modify: `docs/project/roadmap.md`
- Modify: `docs/project/handoff.md`
- Modify: `docs/project/technical-reference.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes the stable implementation candidate and fixed local Phase 3/evaluation/corpus artifacts.
- Produces exact qualification evidence, immutable diagnostic hashes, and `stop` or `graph-next` under the frozen rule.

- [ ] **Step 1: Obtain independent implementation review before opening results**

Review AC1-AC5 against the stable branch. Repair one deduplicated batch only through a new loop
attempt. Do not open proposition results until focused/affected checks and review are clean.

- [ ] **Step 2: Prepare and dry-run the frozen artifacts**

Run the prepare command once, record source/audit counts and SHA-256 values, then run dry-run to
rederive the exact boundary. Commit no large local artifact.

- [ ] **Step 3: Qualify the existing Qwen endpoint**

Run exactly the four fixed probes. Record model/endpoint identity, request schema/prompt digests,
span fidelity, and latency. If any probe fails, stop Issue #9 without changing the prompt/model.

- [ ] **Step 4: Extract sources and apply the stop rule**

Run/resume one extraction configuration. Report exact claim, decisive-document, audit-document,
schema-valid, and usable-document coverage. If any frozen gate fails, write the stopped report and
do not compute pair features.

- [ ] **Step 5: Complete the audit and derive the diagnostic if qualified**

Review all 100 rows with the fixed dispositions and allowed phenomenon tags. If coverage passed,
run the fixed pair scorer and derive ROC-AUC/AP, prevalence control, correlations, distributions,
and artifact hashes. Apply the frozen `0.65` ROC-AUC and `2x` prevalence AP decision mechanically.

- [ ] **Step 6: Document and commit the evidence**

Record verified values without promotion or generalization claims. Keep graph work deferred unless
the fixed continuation rule passes. Commit and push the report, ADR outcome, roadmap, handoff,
technical reference, and changelog.

- [ ] **Step 7: Run exactly one final full gate for the current attempt**

Run: `make smoke`

Then run: `python3 tools/product_version.py`, `git diff --check`, and `git status --short`.
Record release impact before the full gate. Do not repeat the full gate in the same attempt.

- [ ] **Step 8: Complete independent final review and reconcile Issue #9**

Record the clean criterion-bound verdict, finish the engineering loop, merge only the approved
branch commits to `main`, push, re-read GitHub Actions, and close Issue #9 only when every accepted
criterion has evidence.
