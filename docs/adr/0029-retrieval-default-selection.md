# ADR-0029: Retrieval-default selection

- Status: accepted and implemented by GitHub Issue #7
- Date: 2026-09-15
- Decider: Jack Rory Staunton, human owner
- Governing issue: GitHub Issue #6

## Context

The application's compatibility default, `title-token-window-rrf`, performed materially worse than
several already-implemented retrieval strategies on the previously inspected public test qrels.
The roadmap therefore froze three candidates before one validation comparison:

1. `bm25-token-window-rrf`, the simple hybrid control;
2. `pooled-coref-interval-colbert`, the six-generator pool scored from title plus abstract; and
3. `pooled-coref-interval-content-max-colbert`, the same pool scored by the maximum raw ColBERT
   score across scalable DP content views.

The deterministic 160-query validation partition had also been inspected previously, so it can
support an internal comparison but not a clean generalization claim. The protocol prohibited
adding candidates, tuning weights or depths, or changing models after opening the results.

## Decision

Recommend `pooled-coref-interval-content-max-colbert` as the retrieval-effectiveness default. In
the one fixed run it achieved nDCG@10 0.742493, MAP@10 0.716753, recall@10 0.806250, and MRR@10
0.728472 with 638.94 ms median latency and no failures. Against `bm25-token-window-rrf`, it gained
0.068975 nDCG, 0.086524 MAP, 0.018750 recall, and 0.081037 MRR. The improvement occurred on 39
queries versus 13 regressions and justified the existing ColBERT GPU dependency under the
predeclared Pareto rule.

Retain `bm25-token-window-rrf` as the explicitly supported fast/no-ColBERT alternative. Its median
latency was 78.70 ms, but its nDCG@10 was 0.673519 and recall@10 was 0.787500.

Do not select `pooled-coref-interval-colbert` as the default. DP content-max was higher on every
reported ranking metric and slightly faster in the same execution, so the whole-document scorer
is dominated for this decision. It remains available as a short-document control and diagnostic.

GitHub Issue #7 applies the decision through one shared `DEFAULT_RETRIEVAL_STRATEGY` constant used
by the CLI and both composition builders. `ingest`, `search`, `ask`, `evaluate`,
`build_application`, and `build_generation_evaluator` now default to content-max ColBERT. Every
explicit strategy remains selectable, including `bm25-token-window-rrf` and the former
`title-token-window-rrf` default. No test-qrels confirmation, parameter sweep, or new retrieval
experiment follows from this decision.

## Consequences

### Positive

- The recommended strategy is the strongest of the three fixed candidates on every reported
  effectiveness metric.
- Its raw DP content views avoid whole-document right truncation as document length grows.
- The BM25 hybrid remains a named operational fallback rather than being deleted or obscured.
- The recommendation preserves the existing modular strategy boundary; no new model, score, or
  workflow layer is introduced.

### Negative

- The recommended path requires a healthy hosted ColBERT service and has about 8.1 times BM25's
  observed median latency.
- Its six candidate generators and stored representation families are more operationally complex
  than the BM25 hybrid.
- Thirteen of 160 queries regress in nDCG relative to BM25, including five relevant document IDs
  lost from the top ten.

### Evidence boundary

- The result is internal comparative evidence because both validation and test surfaces were
  already inspected.
- The evaluation reports document ranking only. It does not establish scientific entailment,
  contradiction handling, grounded generation quality, or performance on longer corpora.
- Candidate recall and oracle nDCG remain useful earlier diagnostics but were not rematerialized by
  the fixed Issue #6 runner and are not used as promotion gates here.
- Runtime latency reflects the live single-DGX Compose topology and is not a throughput or
  concurrency benchmark.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Keep `title-token-window-rrf` by inertia | Existing evidence identifies it as a weak compatibility default; it remains selectable but is no longer the default |
| Select BM25 plus token-window RRF | Much faster and simpler, but the fixed quality gap is too large for the product's retrieval-effectiveness objective |
| Select whole-document ColBERT | Dominated by DP content-max on all reported quality metrics and latency in the fixed run |
| Fuse title and DP content scores | Earlier fixed ablations showed regression; reopening weights or normalization violates this decision boundary |
| Add RankZephyr, a graph scorer, or another model | Outside the frozen candidate set and not needed to decide among working retrieval strategies |

## Verification and revisit trigger

The complete run, component revisions, hashes, metrics, and query transitions are recorded in
`docs/reports/issue-6-retrieval-default-validation.md`. Revisit this decision only with a named new
hypothesis and a fresh evaluation boundary, or if operational measurement shows that the ColBERT
dependency makes the selected product latency or availability unacceptable. The next architectural
phase is scientific inference scoring, not retrieval-default retuning.
