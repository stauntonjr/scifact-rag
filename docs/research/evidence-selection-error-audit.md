# Retained evidence-selection error audit

Date: 2026-09-19. [Issue #31](https://github.com/stauntonjr/scifact-rag/issues/31).
Scope: deterministic CPU analysis of the completed [fixed-reader diagnostic](evidence-inference-reader-results.md).

The selected-context deficit contains differences in both directions: full context is correct
where selection is wrong on 15 prompts, while selection is correct where full context is wrong
on two. Annotated-span loss is common, including among selected-correct controls. It cannot
explain every disagreement. No selector, context, reader, or Lattice change is justified by this
audit alone.

## Verified population and integrity

All 101 prompts from 20 articles enter this audit once. The retained run contains 101 selector
requests, 303 reader requests, 1,599 scored pairs and 101 complete reader triplets. Preparation
order and inference schedule are checked independently; joins use prompt/article identity.
Abstentions count wrong and remain distinct from the native neutral label.

| Arm | Correct prompts / contributing articles | Wrong prompts / articles | Abstentions / articles |
|---|---:|---:|---:|
| Full | 92 / 20 | 9 / 5 | 0 / 0 |
| Selected | 79 / 20 | 22 / 8 | 5 / 5 |
| Oracle | 92 / 20 | 9 / 6 | 1 / 1 |

Article counts are distinct contributing articles within each cell; they are not additive.
These are related prompts from an inspected training cohort, not independent observations.

## Verified paired outcomes

One means the arm matches the native reference label; zero includes wrong labels and abstentions.
The columns are full, selected, oracle, in that order.

| Correctness triple | Prompts | Articles |
|---|---:|---:|
| 000 | 3 | 3 |
| 001 | 4 | 4 |
| 010 | 1 | 1 |
| 011 | 1 | 1 |
| 100 | 3 | 2 |
| 101 | 12 | 6 |
| 110 | 2 | 2 |
| 111 | 75 | 20 |

Full-correct/selected-wrong comprises 15 prompts from seven articles; its reverse comprises two
prompts from two articles. Oracle-correct/selected-wrong comprises 16 prompts from eight articles;
its reverse comprises three prompts from three articles. Full and oracle disagree in correctness
on five prompts from four articles in each direction. Three prompts from three articles are wrong
in all arms. Equal aggregate full/oracle accuracy therefore does not mean identical successes.

The machine-readable summary includes all paired label transitions, preserving abstention labels,
plus contributing article counts. The fixed error population is all 26 prompts from nine articles
with any incorrect/abstaining arm; it includes every reverse contrast. Every case remains in the
local deterministic bundle, with the 75 all-correct controls retained rather than excluded.

## Verified coverage and rank geometry

The audit uses exact half-open offsets in the qualified LF view. Touching/overlapping reference
spans are unioned; source windows must be valid and non-overlapping. Each window retains its
indexed selector score, descending-score rank with ascending-offset ties, and reference-overlap
length. Every retained selection matches the two highest scores, then preserves source order.

The diagnostic enumerates existing distinct window pairs and maximizes annotated intersection
length; equal maxima use ascending source offsets. A one-window article would use one window.
This is an annotation-overlap upper bound, not an executable selector or an answer-quality oracle.
Equality and completeness use exact character counts, not tuned floating-point thresholds.

| Actual coverage versus maximum | Maximum coverage | All prompts / articles | Selected correct / articles | Selected wrong / articles |
|---|---|---:|---:|---:|
| Below | Complete | 56 / 19 | 39 / 18 | 17 / 6 |
| Below | Partial | 5 / 4 | 3 / 2 | 2 / 2 |
| Equal | Complete | 39 / 15 | 36 / 15 | 3 / 3 |
| Equal | Partial | 1 / 1 | 1 / 1 | 0 / 0 |

Mean actual annotated-reference recall is 0.4698023420; mean maximum existing-pair recall is
0.9922696412. Six prompts cannot reach complete annotated coverage with two existing windows.
The summary retains geometry crossed with every correctness triple, paired contrasts, and
per-article aggregates. The local bundle retains the full score/rank/offset calculations.

For the 26-case error population, the four geometry rows above contain respectively 18 prompts
from seven articles, three from three, five from four, and zero. No case is selected to support
a preferred explanation. Their interpretation remains a geometry observation and an unresolved
semantic cause.

## Interpretation and next decision

**Observed:** 17 selected-wrong prompts could have complete annotated coverage using another
existing pair. Two further selected-wrong prompts fall below an incomplete maximum. However,
39 selected-correct controls also fall below an achievable complete maximum, and three
selected-wrong prompts already have complete annotated coverage. Coverage alone is therefore
neither a necessary nor sufficient condition for native-label correctness in these observations.

**Hypothesis, not established:** preserving complementary decisive evidence could help selected
context. These retained comparisons do not identify an implementable scoring change or show that
substituting the maximum-overlap pair would improve reader answers. A maximum pair can include a
zero-overlap companion when one window already covers the reference, so its ranks must not be
read as proof of a ranking failure.

**Unresolved:** annotations are not an exhaustive evidence set; partial coverage can suffice,
and complete annotated coverage can omit necessary surrounding context. Label differences do not
establish intervention/comparator/outcome role confusion, clinical correctness, entailment,
causality, or an error in the reference annotation.

**Decision: no intervention now.** Do not widen the context budget, change scoring, tune on these
101 prompts, train a model, or build graph infrastructure from this result. A future proposal must
choose and freeze one candidate mechanism before evaluation, preserve a fixed reader and context
budget, define native-label and coverage metrics, cost accounting and a stop rule, and obtain
separate authorization for fresh article-disjoint validation. This audit neither selects nor
acquires that validation material and does not authorize another experiment.

For Lattice, the useful future question is whether its representations preserve decisive evidence
under a fixed context budget. This audit supplies a downstream measurement pattern, not evidence
of learned role induction or a reason to change current CPU-probe work. Issue #28 remains the owner
of reviewer qualification and confirmation custody. No cases were added to its pilot, no reviewer
was called, and its qualification does not automatically authorize semantic adjudication here.

## Reproduction and evidence boundary

Use the source-controlled `tools/evidence_selection_audit.py` with Python 3.12 on the Mac planning
host. The retained root is the original `reader-implementation` worktree's
`artifacts/evidence-inference-v2/reader-v1`; do not copy, regenerate, chmod or repair it.
The environment-specific absolute path is recorded only in the ignored audit manifest.

```sh
.venv/bin/python tools/evidence_selection_audit.py run \
  --reader-artifact-root "$READER_ARTIFACT_ROOT" \
  --public-results docs/research/evidence-inference-reader-results.json \
  --output artifacts/evidence-inference-v2/selection-audit-v1/final
```

The output must be fresh and outside the retained tree. Preparation constituents, payload hashes,
selected artifacts, schedule, scores and published metrics are reconciled before successful
publication. The ignored manifest records definitions and input/script digests before case analysis;
a retained manifest without a successful summary is not completion. Before/after input identities
must agree. The source code and ignored case bundle contain the reproducibility boundary; tracked
publication contains aggregate metadata only, never article text, prompts or responses.

Frozen identities:

- Preparation: `888834d7ff034b391f6d90edb9cc819f88e8265823fdf25579f35fce6c88fc20`.
- Runtime: `891d04c4be3175c803fd1308f1eb24cc6c56c386885d25851752dbac4ce2db9d`.
- Ledger: `e5f629cd330609a436df7959a115508252b6e510166eb1a81d23c5c4862cd9e2`.

The accepted execution is retained under `selection-audit-v1/final/`; the earlier parent output
is preserved as superseded intermediate evidence, without per-article summaries. The final run
verified unchanged hashes for every audited input. Its case-row SHA-256 is
`5eb024d7aea28a4ca83e0bb7eed843dfb20f584ba27f415c06277bbfd4ea2ba8`.
The [aggregate summary](evidence-selection-error-audit-summary.json) is the validated projection
of that output. It contains 20 anonymous article ordinals in stable source-identity order.

An independent calculation from the primary artifacts reproduced every partition, paired contrast,
score/rank, intersection, maximum pair and geometry cell. The implementation's focused synthetic
suite passed 32 tests, including malformed/missing identities, order drift, overlap, ties,
one-window articles, abstentions, output reuse refusal and nested publication-content refusal.
No model, network or GPU call occurred during audit execution. Repository verification and
independent candidate review are recorded in loop `20260919T172022Z-d75f4696`.
