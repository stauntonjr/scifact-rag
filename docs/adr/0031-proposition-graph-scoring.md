# ADR-0031: Test grounded proposition pairs before building a graph

- Status: accepted; experiment stopped at qualification
- Date: 2026-09-15
- Decider: Jack Rory Staunton, human owner
- Governing issue: [#9](https://github.com/stauntonjr/scifact-rag/issues/9)

## Context

The fixed Phase 3 NLI diagnostic produced 4,316 neutral-to-decisive false positives among 21,711
candidates. Evidence coverage was high, so the next hypothesis is that explicit scientific
subjects, predicates, objects, polarity, and qualifiers can distinguish decisive evidence from
topically related negatives.

The first proposed Phase 4 design also included a corpus-wide PostgreSQL projection, induced graph,
six graph features, path scoring, and a partial `semantic-evidence-ledger` activation. Human review
accepted the representation direction but found that infrastructure disproportionate before the
scientific hypothesis is tested. Exact entity joins also make graph-path failure confounded with
the deliberately deferred biomedical synonym problem.

## Decision

Run one bounded proposition-pair diagnostic before building graph infrastructure. Extract only the
160 frozen claims and distinct documents in their unchanged broad candidate pools. Use the existing
Qwen endpoint with strict JSON Schema and exact source-span validation, and retain immutable local
manifest and JSONL artifacts. Do not add PostgreSQL tables or a runtime proposition store.

Compute exactly five predeclared pairwise features: entity similarity, predicate similarity,
argument direction, polarity agreement, and same-role qualifier similarity. Select a proposition
pair by the fixed structural formula and report a fixed equal mean. Defer graph connectivity and
path scoring.

Freeze the 100-row Phase 3 error-audit manifest before extraction. Audit review may run independently
of extraction but must finish before results are interpreted. Apply the predeclared extraction
coverage stop rule before feature computation.

The `semantic-evidence-ledger` capability remains inactive. These finite diagnostic artifacts are
owned by the active product-validation capability and are not a runtime assertion ledger or
canonical truth projection. Any durable proposition store, challenge lifecycle, or truth
resolution must activate or supersede that capability through a later owner decision.

The representation earns a separate graph experiment only if all extraction gates pass and the
fixed proposition-pair mean reaches ROC-AUC `0.65` plus average precision at least twice the
decisive prevalence on the predeclared decisive-versus-Phase-3-false-positive comparison. Passing
does not authorize fusion or default promotion.

## Consequences

### Positive

- The scientific representation hypothesis can be tested before infrastructure is built.
- Only sources needed by the fixed candidate pool incur extraction cost.
- The exact retained Phase 3 manifest/results digests and every candidate identity are revalidated
  against the fixed evaluation set and corpus before the Phase 4 source manifest is accepted.
- Strict source grounding and assertion-not-truth semantics remain intact.
- Graph paths, PostgreSQL lifecycle, and capability activation must earn their complexity.
- Failure can terminate this experiment within one implementation cycle.

### Negative

- Local artifacts cannot serve runtime retrieval or other consumers.
- The experiment does not measure connected graph behavior.
- MiniLM surface similarity does not resolve biomedical synonyms.
- Qwen extraction may fail the predeclared coverage gate.
- The inspected validation boundary supports diagnosis, not clean generalization.

### Risks and mitigations

- **Hallucinated extraction:** require exact source spans and fail closed.
- **Prompt/model drift:** bind model, prompt/schema, source, and artifact digests.
- **Audit delay:** freeze first, run review independently, require completion only before interpretation.
- **Coverage ambiguity:** require 100% usable claims, decisive documents, audit documents, and
  documents in the fixed decisive-versus-false-positive comparison; 99% schema-valid terminal
  sources; and 95% usable candidate documents.
- **Metric fishing:** freeze five formulas and the stop/continuation threshold before extraction.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| Calibrate DeBERTa | Raw logits and labels exist | Tunes the symptom on an inspected and highly imbalanced boundary |
| Build full PostgreSQL proposition projection | Would support runtime scoring | Infrastructure is unnecessary to answer the first hypothesis |
| Add graph-path scoring now | Would test connectivity | Exact joins confound path utility with unresolved synonymy |
| Add another extractor or entity linker | Could improve domain fit | Adds a model/dependency comparison before representation value is known |

## Verification and revisit trigger

Focused tests verify strict spans, schema validation, identities, deterministic audit selection,
resume semantics, exact feature formulas, coverage gates, and report derivation. Fixed DGX probes
qualify schema/span behavior before extraction. The existing full repository gate remains the final
engineering check; no harness expansion is part of the change.

If extraction fails the frozen gate, stop and diagnose rather than changing the prompt or model in
the same run. If the fixed pair score fails either signal threshold, retain the evidence and do not
build the graph. If it passes both, a new owner-approved issue may design graph connectivity,
durable PostgreSQL projection, and the associated `semantic-evidence-ledger` activation.

## Outcome

The authenticated preflight reproduced 160 claims and 4,867 distinct candidate documents from the
exact retained Phase 3 manifest (`121b7ce1...`) and results (`40701fa9...`). The frozen source
manifest contains 5,027 requests; its SHA-256 is `73581347...`. The deterministic 100-row audit
manifest SHA-256 is `0cb2803a...`.

The four-probe qualification artifact (`2c337f76...`) records two passes and two failures. Positive
relation passed with one grounded proposition in 12,110.63 ms, and no-relation passed with an empty
result in 1,467.96 ms. Explicit negation failed exact span grounding in 4,023.65 ms; scientific
qualifier failed the same invariant in 4,600.99 ms. These ASCII probes rule out a Unicode byte-offset
explanation, but the fail-closed adapter intentionally retained no invalid proposition payload.

Per this ADR, Issue #9 stops before pool extraction, MiniLM scoring, audit interpretation, graph
paths, or PostgreSQL projection. The proposition-value hypothesis is therefore not accepted or
rejected; the selected Qwen extraction configuration failed the prerequisite needed to test it.
