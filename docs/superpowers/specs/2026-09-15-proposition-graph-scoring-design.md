# Grounded proposition-pair diagnostic design

- Date: 2026-09-15
- Status: accepted with scope guidance
- Governing issue: [#9](https://github.com/stauntonjr/scifact-rag/issues/9)
- Governing ADR: [ADR-0031](../../adr/0031-proposition-graph-scoring.md)
- Human decision: approve `c3395d7` direction, trim the first implementation before coding

## Objective

Within one implementation cycle, produce a frozen artifact showing whether grounded proposition-
pair features separate annotated decisive evidence from the Phase 3 neutral-to-decisive false-
positive population.

The experiment decomposes claim and candidate text into source-grounded `(subject, predicate,
object, polarity, qualifiers)` records, computes five fixed pairwise features, and stops. It does
not build a connected graph, graph-path feature, corpus-wide projection, PostgreSQL schema, runtime
retrieval strategy, or default integration.

## Evidence and hypothesis

Phase 3 scored 21,711 candidates. Only 120 had an annotated decisive relation, while DeBERTa
predicted 4,392 as decisive and produced 4,316 neutral-to-decisive false positives. Evidence
assembly recalled 188 of 209 annotated sentences and admitted annotated evidence for 201 of 202
candidate documents. The dominant unresolved question is therefore not evidence availability but
whether explicit proposition structure can distinguish decisive relations from topical overlap.

A benchmark-neutral candidate is an operational label, not proof that its text is logically
neutral. A fixed error audit must separate likely annotation mismatch from model reasoning failure
before the proposition results are accepted or interpreted.

## Capability and solution disposition

The solution disposition is **adapt**. Reuse the existing Qwen OpenAI-compatible endpoint, source
spans, MiniLM embedder, frozen candidate pool, Phase 3 artifacts, CLI composition style, and
evaluation/report patterns. Add no package, service, database table, API surface, or runtime
retrieval strategy.

| Capability | Disposition | Reason |
|---|---|---|
| `application-composition-root` | `use-active` | The diagnostic uses explicit existing adapters. |
| `cli-interface` | `use-active` | One opt-in CLI command drives the experiment. |
| `product-validation-challenges` | `use-active` | Phase 3 errors are real retained challenge examples. |
| `semantic-evidence-ledger` | `not-applicable` for this slice | Immutable diagnostic JSONL is evaluation evidence, not a runtime assertion ledger or canonical projection. Activation is deferred until proposition signal justifies durable application storage. |
| All other inactive capabilities | `not-applicable` | The experiment needs no memory, handoff, architecture-metrics, security, API, or deployment capability. |

This narrower disposition supersedes the proposed partial activation in `c3395d7`. The inactive
capability continues to own any later durable assertion, challenge, and resolution lifecycle; this
experiment must not invent one.

## Alternatives

- **Calibrate DeBERTa:** rejected because it tunes an inspected, 0.55%-positive boundary without
  testing scientific structure.
- **Build PostgreSQL/graph infrastructure now:** deferred because pairwise proposition features can
  test the representation hypothesis first.
- **Add AGE, biomedical entity linking, or another extractor:** deferred because each adds an
  independent variable and operational cost.
- **Strict Qwen extraction into immutable diagnostic artifacts:** selected because it reuses the
  running model and preserves exact source evidence without committing to runtime infrastructure.

## Frozen source set

Build the source manifest before extraction from exactly:

1. all 160 claims in the existing frozen `train-validation` evaluation set;
2. every distinct candidate document in those claims' unchanged Phase 2 broad pools;
3. no unrelated SciFact document.

Deduplicate sources by `(source_kind, source_id, source_sha256)`. The manifest binds the evaluation-
set digest, Phase 3 results digest, retrieval strategy and pool configuration, ordered query and
document identities, extractor configuration, prompt/schema digest, and output paths. A mismatch
stops before opening results.

## Frozen error-audit sample

Create a deterministic 100-row manifest before proposition results are opened:

1. include all 50 Phase 3 errors whose gold label is entailment or contradiction;
2. select 25 neutral-to-entailment false positives;
3. select 25 neutral-to-contradiction false positives;
4. for each false-positive direction, sort by evidence margin, split into five equal-frequency
   bands, and choose five candidates per band by ascending stable candidate ID.

Each row retains the source Phase 3 digest, candidate identity, claim and document identity,
evidence bundle, labels, logits, margins, and stratum. Review assigns one disposition:

- `likely_annotation_gap`;
- `related_insufficient`;
- `model_reasoning_error`;
- `evidence_selection_error`;
- `indeterminate`.

Optional phenomenon tags remain limited to synonymy, argument direction, polarity, negation,
population/intervention/comparator/outcome qualifiers, association-versus-causation,
species/evidence boundary, and cross-sentence reasoning. Reviewer identity and concise rationale
are required. These are diagnostic judgments, not training labels or benchmark truth.

The sample must be frozen before extraction, but review may proceed independently of extraction.
It must be complete before proposition results are interpreted or accepted. Because selection is
stratified, the report gives per-stratum counts and does not extrapolate population prevalence.

## Proposition schema and grounding

One extracted proposition contains:

- stable source kind, source ID, and source digest;
- sentence text and half-open Unicode code-point offsets in the complete source;
- non-empty subject, predicate, and object surface text with exact source offsets;
- polarity: `positive` or `negative`;
- zero or more qualifiers with role, surface text, and exact source offsets;
- extractor model, prompt/schema version, and deterministic request configuration.

Qualifier roles are fixed to population, species, intervention, comparator, outcome, measurement,
time, and study context. Canonical keys are computed locally by lowercase Unicode, whitespace, and
edge-punctuation normalization of verified surfaces. They are matching aids, not biomedical entity
resolution.

Every span must satisfy `source[start:end] == surface_text` and remain inside its sentence span.
The application rejects unsupported enum values, malformed JSON, missing fields, duplicate stable
identities, invented text, and out-of-range or mismatched spans. It never repairs model text or
promotes extracted assertions into scientific truth.

## Extraction adapter and artifacts

Add a model-neutral `PropositionExtractor` port and one Qwen OpenAI-compatible adapter. Send one
source per request with a versioned system instruction, strict JSON Schema response format,
temperature zero, and the configured seed. The response carries the source identity and digest so
the client can reject cross-request contamination.

Persist a manifest plus append-only result JSONL with exactly one terminal record per source. A
terminal record is either schema-valid propositions, a valid empty extraction, or a typed failure.
Append and flush before proceeding. Resume skips terminal sources and retries only sources absent
from the artifact. Duplicate or conflicting terminal identities invalidate the run. This is a
diagnostic artifact, not a general assertion store.

Qualification uses four fixed probes: positive relation, explicit negation, scientific qualifier,
and no relation. It establishes schema and span fidelity only. Failure stops before candidate-pool
extraction; no alternate prompt, retry variant, or fallback model is allowed inside the run.

## Predeclared extraction stop rule

After source extraction and before pairwise feature computation, stop and diagnose extraction if
any condition fails:

- 100% of the 160 claims have at least one valid grounded proposition;
- 100% of annotated decisive candidate documents have at least one valid grounded proposition;
- 100% of documents represented in the 100-row audit have at least one valid grounded proposition;
- at least 99% of all source records are terminal and schema-valid, including valid empty results;
- at least 95% of distinct candidate documents contain one or more valid grounded propositions.

The thresholds are qualification gates, not quality claims. A stopped run retains coverage and
failure evidence but does not proceed to scoring, graph work, or prompt/model changes.

## Five fixed proposition-pair features

Embed each verified subject, predicate, object, and qualifier surface with the existing MiniLM
model. Map cosine similarity from `[-1, 1]` to `[0, 1]`. For every claim/document proposition pair,
compute:

1. `entity`: maximum of subject-subject, subject-object, object-subject, and object-object
   similarities;
2. `predicate`: predicate-predicate similarity;
3. `argument_direction`: `((subject-subject + object-object) - (subject-object + object-subject)) / 2`,
   retaining its `[-1, 1]` range;
4. `polarity`: `1` for equal polarity and `-1` for conflicting polarity;
5. `qualifier`: mean, over claim qualifiers, of the best same-role document-qualifier similarity;
   use `0` when the claim has no qualifiers or a role is absent from the document proposition.

Select one proposition pair per claim/document candidate using the highest arithmetic mean of
`entity`, `predicate`, and `(argument_direction + 1) / 2`; break ties by stable proposition IDs.
Report the five selected raw features. Also report a frozen `proposition_pair_mean`, the arithmetic
mean after mapping both signed features to `[0, 1]`. It is a diagnostic score, not a probability.

No threshold, weight, learned adjustment, graph traversal, synonym edge, or post-result formula
change is allowed.

## Diagnostic and decision rule

The diagnostic joins all 120 annotated decisive candidates with all 4,316 Phase 3 neutral-to-
decisive false positives and reports, for each feature and the fixed mean:

- ROC-AUC and average precision for decisive-versus-false-positive separation;
- label prevalence as the average-precision control;
- score distributions by gold label, Phase 3 prediction, audit stratum, and audit disposition;
- extraction coverage, typed failures, span validation, latency, and exact artifact digests;
- correlations with ColBERT, Phase 3 evidence margin, and polarity margin.

The representation earns a separately governed graph-connectivity experiment only if the fixed
`proposition_pair_mean` achieves ROC-AUC at least `0.65` and average precision at least twice the
decisive prevalence on this fixed comparison, with all extraction gates passing. This threshold
justifies another experiment; it does not authorize retrieval fusion or default promotion.

If either threshold fails, stop this branch of experimentation and retain the schema, artifacts,
and report without building graph paths or PostgreSQL infrastructure.

## Interfaces and implementation boundary

Add one opt-in CLI workflow with dry-run manifest validation, extraction/resume, audit validation,
and report derivation. The internal modules are limited to proposition contracts/matching, the
Qwen adapter, and diagnostic execution/reporting. Existing `search`, `ask`, retrieval evaluation,
PostgreSQL schemas, Compose services, and defaults remain unchanged.

Focused tests cover strict spans and schema rejection, stable identities, resume/duplicate
handling, deterministic 100-row audit selection, the five exact formulas and tie-break, extraction
stop rules, and raw/report consistency. The revised budget permits no more than 10 new focused test
functions and no harness expansion.

## Execution order

1. Freeze schemas, formulas, source manifest, audit selection, gates, and artifact identities.
2. Implement contracts and focused tests.
3. Implement and qualify the Qwen extraction adapter.
4. Freeze the audit manifest; audit review and candidate-source extraction may proceed independently.
5. Apply the extraction stop rule.
6. If it passes, compute the pairwise artifacts and fixed report.
7. Complete the audit before interpreting the report.
8. Record the stop-or-graph-next decision; do not implement a graph in Issue #9.

Any PostgreSQL table, runtime scorer, new dependency or service, graph/path feature, model or prompt
comparison, calibration, learned weight, public-test access, or default change requires a new issue
and owner approval.
