# Evidence-selection error audit design

- Date: 2026-09-19
- Governing issue: [#31](https://github.com/stauntonjr/scifact-rag/issues/31)
- Engineering-loop run: `20260919T160057Z-c72c4f05`
- Owner-approved boundary: deterministic retained-artifact audit only

## Goal

Explain the retained fixed-reader selected-context deficit as far as deterministic joins, native
labels, interval geometry, and selector ranks permit. The audit may recommend at most one
separately authorized selection hypothesis. It must not treat its observations as clinical
correctness, a demonstrated causal mechanism, or a generation-quality improvement.

## Scope and authority

Included:

- one tracked narrow CPU-only audit script, its focused tests, and ignored per-case outputs;
- exact integrity checks over the retained preparation, runtime, ledger, and evaluation inputs;
- every-prompt outcome reconciliation, abstention accounting, and article-aware aggregates;
- exact LF-view coverage and selector-rank geometry; and
- text-free report, JSON summary, and handoff updates with independent verification.

Excluded:

- reader, selector, reviewer, or other model calls; GPU allocation; and new dependencies;
- product, runtime, selector, prompt, API, deployment, or public-interface changes;
- source acquisition, new articles, confirmation content, training, or tuning;
- semantic adjudication, clinical conclusions, causal role-error conclusions, and statistical
  independence or significance claims; and
- any edit to Issue #28 artifacts or activation of `role-separated-analysis`.

Missing or mismatched frozen inputs, a need for semantic judgment, any model call, a new
dependency, or any excluded write is a stop or scope-revision trigger rather than an implementation
convenience.

## Capability and solution disposition

`product-validation-challenges` is active and supplies the project pattern for deterministic,
bounded checks. This audit reuses that pattern where applicable. `role-separated-analysis` is
not applicable: the work has one deterministic analysis flow and independent verification, not
three parallel domain lanes. No inactive capability is activated.

The solution disposition is `adapt`. `tools/evidence_inference_reader.py` already defines native
label parsing, native metrics, LF-view interval conventions, and the retained reader artifacts.
The audit adapts those stable, local contracts in one purpose-specific script instead of extending
the runner or introducing a general audit framework.

## Architecture

```text
immutable prepared manifest + runtime + ledger + evaluation report
                              |
                              v
                 fail-closed integrity binding
                              |
                 +------------+-------------+
                 v                          v
      arm outcome reconciliation       window/rank geometry
                 |                          |
                 +------------+-------------+
                              v
          ignored per-case, ID/offset-only audit artifact
                              |
                              v
          text-free aggregate summary and bounded interpretation
```

The script takes explicit retained-input and output paths. It reads all required JSON/JSONL
artifacts before publishing an audit result. It rejects duplicate, missing, reordered, or
unreconcilable prompt/article identities; it never fills gaps from memory, regenerates a response,
or overwrites a pre-existing audit directory.

### Execution location and input staging

The audit runs on the Mac planning host that retains the fixed-reader artifacts, using the Issue
#31 checkout for the tracked script and tests. It does not assume that the DGX checkout contains
the artifacts and does not copy, stage, or regenerate them. Invocation requires an explicit,
read-only absolute `--reader-artifact-root` pointing to the Mac planning worktree's
`artifacts/evidence-inference-v2/reader-v1/` directory. The script derives only these fixed
children from that root: `prepared-002/`, `live-20260919-001/`, and
`evaluation-20260919-001/report.json`.

The local absolute root is environment-specific and appears only in the ignored audit manifest;
tracked outputs retain relative artifact names and SHA-256 values. The script refuses a missing,
non-directory, writable-by-the-process root or a root that is not the exact declared tree. It
binds the three Issue #31 SHA-256 identities and all constituent membership before any case-level
analysis. A hash failure is an evidence stop, not a request to transplant artifacts into the DGX
checkout or reconstruct data.

### Integrity and outcome ledger

The audit binds the Issue #31 SHA-256 values for the preparation manifest, runtime identity, and
immutable ledger, then rechecks constituent digests and membership. Its input contract requires:

- 20 articles, 101 prompt identities, 101 complete three-arm result triplets;
- 303 reader requests, 101 selector requests, and 1,599 scored pairs; and
- the published text-free comparison target to reconcile to the retained native results.

Preparation order and inference order are separate recorded sequences. The audit validates each
against the ordering field or event sequence in its own retained artifact, then joins prompt and
article rows strictly by their IDs; it never compares row positions across the two artifacts.
Duplicate IDs, missing IDs, and a broken order within either source fail the integrity gate, while
the intentionally different preparation and inference orders do not.

For every prompt, the output preserves only IDs, labels, correctness, and abstention state. It
creates one row joined by exact prompt and article identity, with reference label and parsed
`full`, `selected`, and `oracle` predictions. It assigns every row to one of the eight correctness
triples and tabulates paired label transitions separately. `insufficient_evidence` remains an
abstention, distinct from neutral and counted wrong for native-label correctness. Published totals
must reconcile to full 92/101 correct with zero abstentions, selected 79/101 with five
abstentions, and oracle 92/101 with one abstention; otherwise no interpretation is published.

### Coverage and selector geometry

The audit uses the reader helper's half-open LF-view interval convention. It unions overlapping
reference intervals before counting intersection length, so touching/overlapping spans contribute
once. Identical text at different offsets remains distinct evidence.

For each existing source window, the per-case artifact retains source offset, selector score,
rank, and reference-overlap length. Rank is descending finite score with ascending source offset
as the tie-breaker; the selected-window list retains its original source order. For a one-window
article the diagnostic uses that one window, not a duplicate pair.

The script enumerates at most two distinct existing windows and selects the pair with greatest
union intersection against the annotated reference, breaking ties by ascending source offsets.
This is an annotated-overlap upper bound only: it neither runs the reader nor claims a deployable
selector or answer-quality oracle. A disjoint reference spread over more than two windows cannot
be represented as an impossible 100% upper bound.

Each prompt is described only by observable categories: actual selected recall equals the maximum,
actual recall is below the maximum, and the maximum has or lacks complete annotated-reference
coverage. Cross-tabs retain selected-correct controls, reverse disagreements, and article-level
counts. They do not call partial coverage a failure, complete coverage sufficient evidence, or any
category a proven ranking/reasoning/role error.

### Publication and decision boundary

Ignored artifacts under `artifacts/evidence-inference-v2/selection-audit-v1/` may contain
case-level IDs, offsets, labels, scores, and derived counts but no raw article text, prompts,
evidence text, or responses. The tracked report and summary JSON are text-free aggregates and
ID/offset references only.

The synthesis inspects the fixed population: every prompt where any arm is incorrect or abstains,
plus every reverse contrast. It labels claims as observation, hypothesis, or unresolved. It either
recommends no intervention or one prospective selection hypothesis whose future issue must freeze
one candidate change, retain the same context budget, account for native-label and coverage
metrics and cost, define a stop rule, and use fresh article-disjoint validation. The audit neither
acquires that validation material nor reruns the current cohort.

Potential Lattice relevance is limited to a future decisive-evidence-preservation test. It does not
establish learned role induction, alter Lattice CPU-probe work, or overlap Issue #28's reviewer
qualification or confirmation-custody scope.

## Failure behavior

- Reject any missing, duplicate, or extra prompt/article/source-window identity.
- Reject altered bound digests, membership, arm totals, request/pair totals, labels, offsets, or
  non-finite selector scores.
- Accept valid half-open reference spans even when they touch or overlap, and union them before
  coverage counting. Reject only malformed reference intervals (non-integers, out-of-bounds, or
  `start >= end`) and malformed/overlapping source-window structure, because source windows must
  remain distinct existing views with a determinate order.
- Reject output paths that already exist instead of overwriting retained evidence.
- Stop publication of interpretation when integrity or denominator checks fail.
- Never retrieve external content, call a model, change a selector, or repair retained inputs.

## Verification design

TDD applies to the audit script. Focused tests first exercise all issue-mandated refusal and
geometry boundaries using tiny synthetic data: duplicate/missing prompt IDs, overlaps counted
once, identical strings at distinct offsets, tie-breaking, one-window articles, abstentions, and
the more-than-two-window upper-bound limit.

The retained audit then verifies all 101 rows and produces the ID/offset-only artifact. Targeted
checks cover the new audit tests and its deterministic run. Affected checks cover the existing
reader helpers and research documentation. Exactly one `make smoke` runs after the final
release-impact record. An independent verifier reproduces the outcome partition and rank/overlap
calculations against the stable candidate, reviews interpretation claims, and closes one findings
batch before any repair.

## Files and ownership

| Path | Responsibility |
|---|---|
| `tools/evidence_selection_audit.py` | Purpose-specific retained-artifact loader, validator, and deterministic audit renderer |
| `tests/test_evidence_selection_audit.py` | Synthetic refusal, partition, interval, rank, and upper-bound tests |
| `artifacts/evidence-inference-v2/selection-audit-v1/` | Ignored per-case reproducibility artifact with no raw text/response export |
| `docs/research/evidence-selection-error-audit.md` | Text-free evidence-bound interpretation and prospective decision |
| `docs/research/evidence-selection-error-audit-summary.json` | Machine-readable aggregate totals and provenance digests |
| `docs/project/handoff.md` | Current Issue #31 outcome, bounds, and next authority boundary |

## Implementation order

1. Write focused failing tests for canonical parsing and error refusal.
2. Implement only enough audited loader and interval/rank logic to satisfy each test.
3. Run the retained 101-prompt audit after all bound digests reconcile; publish ignored per-case
   artifact, report, and summary only from that output.
4. Reconcile report wording against the no-semantic-overclaim boundary and update the handoff.
5. Run targeted and affected checks, record release impact, then run one final full gate.
6. Obtain independent review, disposition one complete findings batch if needed, and finish the
   engineering loop without any external Issue or Project mutation.
