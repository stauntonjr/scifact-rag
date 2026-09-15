# ADR-0031: Versioned proposition projection and candidate-scoped graph scoring

- Status: proposed
- Date: 2026-09-15
- Decider: Jack Rory Staunton, human owner
- Governing issue: [#9](https://github.com/stauntonjr/scifact-rag/issues/9)

## Context

The Phase 3 NLI diagnostic produced 4,316 neutral-to-decisive false positives in a pool where only
0.55% of candidates have annotated decisive relations. Evidence coverage was high, so missing
evidence does not explain the precision collapse. General-language NLI over a bundled abstract also
does not explicitly preserve scientific entities, argument direction, polarity, or qualifiers.

The project already has a broad candidate pool, exact evidence spans, MiniLM, typed PostgreSQL
persistence, an explicit scorer boundary, and a DGX-hosted Qwen endpoint. Its roadmap selects a
proposition graph as the next scorer and defers Apache AGE until ordinary PostgreSQL is measured as
insufficient. The inactive `semantic-evidence-ledger` capability owns source assertions and
provenance, so an independent proposition ledger would violate the capability reuse rule.

## Decision

Activate the project-specific assertion-projection portion of `semantic-evidence-ledger`. Extract
strictly source-grounded propositions with the existing Qwen endpoint, validate every returned
surface against exact source offsets, and persist immutable versioned projection rows in ordinary
typed PostgreSQL tables. Extracted propositions are source assertions, never canonical scientific
truth.

Retrieve the existing broad candidate pool first, build an induced in-memory proposition/entity
graph over all candidates, and emit independent entity, predicate, argument, polarity, qualifier,
path, and fixed equal-composite features through the existing candidate feature matrix. Use no
learned weights or label-trained thresholds. The first fixed diagnostic does not fuse or promote
the graph channel.

Before interpreting graph results, freeze a deterministic 100-row stratified audit of Phase 3
errors and distinguish likely annotation mismatch, related-but-insufficient evidence, model
reasoning error, evidence-selection error, and indeterminate cases. These review dispositions are
diagnostic judgments, not benchmark labels.

This decision does not activate challenge adjudication or canonical truth resolution, add Apache
AGE, add a model service or dependency, calibrate NLI, train a model, generate candidates from the
graph, or change retrieval or generation defaults.

## Consequences

### Positive

- Scientific relations and their qualifiers become inspectable scoring inputs.
- Every graph feature remains traceable to exact source text and extractor provenance.
- The graph can score candidates that would otherwise move only in a second ranking pass.
- Existing PostgreSQL, model hosting, composition, and feature-matrix surfaces are reused.
- The error audit prevents unannotated candidates from being treated silently as semantic truth.

### Negative

- Qwen extraction adds one generative request per source and can fail strict span validation.
- Deterministic canonical keys do not resolve biomedical synonyms.
- In-memory graph construction and repeated MiniLM field comparisons add query latency.
- The already-inspected validation boundary supports internal diagnosis, not clean promotion.
- A partial capability activation requires explicit documentation of deferred ledger semantics.

### Risks and mitigations

- **Hallucinated extraction:** require exact source spans and fail closed.
- **Prompt or model drift:** bind immutable model, prompt/schema, corpus, and projection identities.
- **Silent stale projection:** score only a completed version matching the configured corpus digest.
- **Graph score overinterpretation:** retain every raw feature and prohibit probability or truth claims.
- **Metric overfitting:** freeze formulas and audit selection before opening graph results; do not tune.
- **Infrastructure expansion:** stop if qualification requires another model, service, or dependency.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| Calibrate DeBERTa | Raw logits and labels exist | Optimizes an inspected, severely imbalanced boundary without fixing task semantics |
| Add a dedicated NLI/OpenIE model | Could improve domain fit | Introduces model selection, service qualification, and GPU cost before representation value is known |
| Apache AGE | Provides graph query syntax | Typed tables and recursive SQL are sufficient for the first bounded candidate graph |
| Keep only bundled NLI | Phase 3 interface is complete | Rare-class precision is too low for promotion and arguments remain implicit |

## Verification and revisit trigger

Verify strict extraction schema and source spans, immutable projection accounting, stale/incomplete
projection refusal, complete per-candidate features, deterministic error sampling, exact provenance,
and report/raw consistency with focused tests and one final repository gate. Qualify the live Qwen
endpoint on fixed schema/span probes before corpus extraction, then run one frozen internal
diagnostic.

Revisit the extractor only if fixed qualification fails or extraction coverage makes the projection
unusable. Revisit PostgreSQL storage only after measured query or maintenance limitations. Any
fusion, default promotion, biomedical entity linker, graph candidate generator, learned scorer,
challenge ledger, or canonical resolution requires a separate owner-approved decision.
