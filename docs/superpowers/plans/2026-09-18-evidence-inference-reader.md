# Evidence Inference fixed-reader implementation plan

> **For agentic workers:** Use the repository engineering loop and
> `superpowers:executing-plans` for an accepted implementation issue. Checkboxes are prospective;
> this planning issue does not implement the runner or authorize model execution.

**Goal:** Produce a finite, auditable three-arm native-label diagnostic on the frozen 101 prompts.

**Architecture:** A standalone offline preparation/evaluation tool and one explicit network runner.
Keep source/reference preparation separate from inference inputs. Reuse the existing tokenizer and
ColBERT adapter, preserving source offsets and charging selector work. No application API change.

**Tech stack:** Configured Python 3.12, existing httpx/transformers/numpy dependencies, JSON/JSONL,
pytest, existing Qwen and ColBERT services when available. No additional service or dependency.

**Spec:** [Fixed-reader protocol v1](../../research/evidence-inference-reader-protocol.md).
Read it in full; it defines all task contracts, messages, metrics and failure conditions.

## Global constraints

- Same 20 articles / 101 prompts; frozen cohort SHA-256
  `54b5a291513d0e500678641a1d1dfd2c8721f1df5c3a652bf23619990df6d642`.
- At most 303 reader requests, 101 selector requests, 20,000 selector pairs and 5,400 seconds;
  preflight is included, maximum 600 seconds. No retries or automatic resume.
- No inference while Lattice owns the GPU; exact model/template identities required before dispatch.
- Original source bytes, existing coordinate failures and rights limitations remain immutable.
- No test-split inspection, tuning, new data, deployment, training or graph work.
- Planning artifacts are not runtime evidence. Do not fill missing model revisions from a name.

## Task 1: Offline inputs and exact source windows

Files: create `tools/evidence_inference_reader.py` and `tests/test_evidence_inference_reader.py`.
Consume frozen cohort/provenance/coordinate manifests plus original archive. Produce a prepared
directory with `manifest.json`, `prompts.jsonl`, `references.jsonl` and `windows.jsonl`.
`prepare(archive: Path, cohort: Path, provenance: Path, coordinates: Path, output: Path) -> dict`
must reject an existing output directory and any digest, membership or eligibility mismatch.

- [ ] Test digest tampering, removed/extra prompt, disputed label and failed span remain rejected.
  Synthetic examples must include repeated identical strings at distinct offsets and CRLF/Unicode
  roundtrips. Verify two annotator rows for one prompt produce one target and a union of intervals.
- [ ] Read only frozen prompt IDs; derive native reference code from agreeing qualifying rows.
  Keep reference targets and oracle intervals outside the full/selected builder interface.
- [ ] Adapt the existing tokenizer's consecutive source-window algorithm with direct boundary
  retention; verify every window's serialized selector input fits 512 tokens. Do not add a new
  coreference/DP implementation or recover intervals using `str.find`.
- [ ] Freeze full/oracle message token counts, windows, prompt order and score-pair counts. Persist
  exact serialized request content locally; commit only text-free hashes and counts. Preserve the
  article attribution records for any later permitted exported fixture.
- [ ] Test no selector payload contains reference evidence, labels, row IDs or gold coordinates.
  Run focused tests and review resulting schemas before accepting this preparation boundary.

## Task 2: Reader contract and inference ledger with fake transport

Files: create `tools/evidence_inference_reader_run.py` and
`tests/test_evidence_inference_reader_run.py`; reuse Task 1's preparation format.
Interfaces: `parse_label(text: str) -> str` returns one of the four protocol values or raises
`ValueError`; `run(prepared: Path, runtime: Path, output: Path, execute: bool) -> dict` defaults to
network-disabled validation. Runtime JSON records verified model/template identities and exclusive
resource availability evidence; `execute=True` alone cannot bypass missing/mismatched identity.

- [ ] Test strict parser: accept `{"label":"decreased"}`; reject extra keys, duplicate `label`
  keys, arrays, Markdown fences and trailing prose. Preserve abstention separately from native 0.
- [ ] Implement the exact system/user serialization and decoding settings from the protocol.
  Do not reuse the public `ask` prompt or its insufficiency behavior for the native diagnostic.
- [ ] Wrap `VllmColbertReranker.score` with the protocol's finite-score, cardinality and token-fit
  checks. Select two by descending score then source offset; serialize selected contexts in source
  order, preserving direct boundary maps. Record preparation and ranking costs separately.
- [ ] Using fake transport and a fake monotonic clock, test started-before-send, unknown-on-timeout,
  no second dispatch after uncertainty, no duplicate preflight requests and no automatic retry.
  Test 60-second request deadlines, 600-second preflight and 5,400-second run stop, including the
  case with fewer than 60 seconds remaining. HTTP inactivity timeouts alone do not meet this test.
- [ ] Implement and test outcome-independent preflight selection, pair-count ceiling, latency
  projection and arm rotation. Responses are retained but never used for adaptive prompt changes.
  Verify an interrupted output path is refused rather than silently reused or completed.

## Task 3: Offline evaluation and report

Files: extend `tools/evidence_inference_reader.py`, its tests, and create
`docs/research/evidence-inference-reader-readiness.md` with actual offline acceptance evidence.
Interface: `evaluate(prepared: Path, ledger: Path, output: Path) -> dict` must verify input/run
identities and reject duplicate completed arm/prompt pairs or unmatched references.

- [ ] Test a synthetic matrix with one correct result, one wrong native result, one abstention,
  one malformed response, one overflow and one undispatched record. Check native confusion counts,
  false negatives, completion rate, common-fit triplets and attrition are separately correct.
- [ ] Test overlapping evidence unions count characters once and preserve whitespace. Report
  coverage as span coverage, never as inferred entailment or reference completeness.
- [ ] Implement fixed-three-class metrics and 2,000-replicate article-cluster bootstrap using numpy
  PCG64 seed 1729; synthetic paired articles must move together with all prompt multiplicities.
- [ ] Include reader/selector token and time totals, invalid/unknown records and partial-run status.
  Never emit a completed-study claim when any scheduled request is unaccounted for.
- [ ] Run targeted tests, independent review and one full `make smoke` on the final implementation
  candidate; document exact model-free acceptance evidence. Do not manufacture experiment scores.

## Task 4: Separately gated execution handoff

Files: update readiness report and `docs/project/handoff.md`; ignored run artifacts only.

- [ ] Obtain a free GPU allocation from the resource owner and inspect current services/processes.
  No service restart or Lattice interruption. Freeze exact runtime/model/template identity and
  actual offline counts before any request. If unavailable, hand off the working offline runner.
- [ ] With an accepted execution issue and the above gates met, perform the predeclared preflight
  once. Publish its measured projection and remaining budget; retain its requests in the final
  ledger. Stop if qualification fails; no retry, substitution or budget expansion.
- [ ] Only after the preflight continuation rule passes, execute the remaining frozen schedule
  within the same ceilings. Evaluate once, report scope/attrition and preserve raw artifacts.
- [ ] Independently review accounting and descriptive conclusions before deciding on any later
  representation-fidelity study. Lattice receives evidence for discussion, not a replacement plan.
