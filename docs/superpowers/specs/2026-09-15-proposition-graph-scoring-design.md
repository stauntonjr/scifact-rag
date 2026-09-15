# Proposition-graph scoring design

- Date: 2026-09-15
- Status: proposed for human review
- Governing issue: [#9](https://github.com/stauntonjr/scifact-rag/issues/9)
- Governing ADR: [ADR-0031](../../adr/0031-proposition-graph-scoring.md)

## Objective

Audit the dominant Phase 3 stance-classification errors, then add one provenance-bearing
proposition-graph scorer over every document in the existing broad candidate pool. The slice must
test whether explicit entity, relation, argument, polarity, and qualifier alignment separates true
SciFact evidence from the topically similar negatives that caused the fixed NLI model's precision
collapse.

This is an internal architectural diagnostic. It does not change retrieval or generation defaults
and does not claim clean generalization from the already-inspected 160-claim validation split.

## Context and observed evidence

The fixed Phase 3 run scored 21,711 candidates. Only 120 candidates had an annotated decisive
relation, while the model predicted 4,392 candidates as entailment or contradiction. It produced
4,316 neutral-to-decisive false positives and a three-way macro-F1 of 0.324781. Evidence assembly
recalled 188 of 209 annotated sentences and admitted annotated evidence for 201 of 202 candidate
documents, so missing evidence cannot explain the false-positive volume.

The remaining ambiguity is material: a non-annotated candidate is operationally neutral for the
benchmark, but that does not prove its text is logically neutral toward the claim. The next slice
must distinguish likely annotation mismatch from actual model reasoning failures before using the
failure corpus as an architectural oracle.

Existing project surfaces already provide:

- a DGX-hosted Qwen OpenAI-compatible endpoint;
- sentence and source-span handling;
- typed SQLAlchemy Core/PostgreSQL persistence;
- an existing broad candidate pool and complete candidate feature matrix;
- MiniLM semantic similarity and ColBERT relevance scoring;
- raw Phase 3 logits, evidence bundles, labels, and failure records.

## Capability and solution disposition

The solution disposition is **adapt**. Reuse the existing Qwen endpoint, composition root,
PostgreSQL store, evidence spans, MiniLM embedder, candidate pool, and feature-matrix boundary.
Build only proposition-specific contracts, strict extraction validation, versioned persistence,
matching, diagnostics, and focused tests.

The inactive `semantic-evidence-ledger` capability owns append-oriented assertions and provenance.
Issue #9 proposes its first project-specific activation for versioned extracted source assertions
and their rebuildable scoring projection. This activation does not implement assertion challenges,
cross-source truth resolution, or a canonical scientific truth projection. Those responsibilities
remain owned by the capability and unavailable until separately designed.

Human approval of this design explicitly authorizes that narrow activation. Without that approval,
implementation stops after the proposed design and ADR.

Other capability dispositions:

| Capability | Disposition | Reason |
|---|---|---|
| `application-composition-root` | `use-active` | New ports and adapters use existing explicit wiring. |
| `cli-interface` | `use-active` | Projection and diagnostic operations remain CLI-first. |
| `product-validation-challenges` | `use-active` | The fixed Phase 3 failure corpus supplies real challenge examples. |
| `semantic-evidence-ledger` | `propose-activation` | Versioned source assertions and exact provenance are required. |
| All other inactive capabilities | `not-applicable` | No memory, handoff, architecture-metrics, security, API, or deployment capability is needed. |

## Approaches considered

### A. Calibrate or threshold the current NLI logits

This is the cheapest route to a better validation number, but it optimizes an already-inspected,
0.55%-positive boundary and does not resolve annotation semantics, scientific argument alignment,
or qualifier errors. It is rejected for this phase.

### B. Add another NLI or dedicated OpenIE service

A model comparison could improve extraction or stance quality, but it adds checkpoint selection,
service qualification, GPU memory, and a new comparison dimension before the representation is
proven useful. It is deferred. The first slice adapts the already-hosted Qwen model.

### C. Strict Qwen extraction plus typed PostgreSQL projection and in-process graph matching

This is selected. It adds no runtime service or package, makes every extracted assertion
inspectable, and tests the proposition representation independently of learned graph ranking.
Strict source-span validation rejects unsupported output rather than turning model text into fact.

### D. Apache AGE and native graph queries

AGE may be useful after graph query requirements and scale are measured. Ordinary typed tables and
recursive SQL are sufficient for the first candidate-scoped graph, avoid another extension, and
keep provenance straightforward. AGE remains deferred.

## Fixed Phase 3 error audit

Before proposition-scoring results are opened, generate a deterministic 100-row audit manifest:

1. include all 50 errors whose gold label is entailment or contradiction;
2. select 25 neutral-to-entailment false positives;
3. select 25 neutral-to-contradiction false positives;
4. for each false-positive direction, sort by evidence margin, partition into five equal-frequency
   bands, and choose five candidates per band by ascending stable candidate ID.

The manifest stores the source Phase 3 artifact digest, candidate ID, query ID, document ID, claim,
evidence bundle, gold and predicted labels, logits, margins, and stratum. Selection code must fail
if counts, identities, or the source digest differ from the fixed run.

A review record may assign exactly one disposition:

- `likely_annotation_gap`: the candidate appears decisive but is not an annotated SciFact relation;
- `related_insufficient`: topically or propositionally related without establishing the claim;
- `model_reasoning_error`: the admitted text does not justify the predicted stance;
- `evidence_selection_error`: decisive source evidence exists but is absent or obscured in the bundle;
- `indeterminate`: the available abstract and annotations do not support a reliable disposition.

It may also assign any of the predeclared phenomenon tags: synonymy, argument direction, polarity,
negation, population/intervention/comparator/outcome qualifier, association-versus-causation,
species/evidence boundary, or cross-sentence reasoning. Reviewer identity and a concise rationale
are mandatory. These are diagnostic judgments, not new training labels or benchmark truth.
Because the sample is stratified, the report gives counts by stratum and never extrapolates an
overall error prevalence.

## Proposition contract

An extracted proposition is a source assertion, not accepted truth. Each proposition contains:

- stable identity from projection version, source identity, sentence span, and canonical payload;
- source kind (`document` or `claim`) and source identifier;
- complete source text digest;
- sentence text and exact start/end offsets in that source;
- subject, predicate, and object arguments;
- polarity (`positive` or `negative`);
- modality (`asserted`, `possible`, `conditional`, or `unknown`);
- zero or more typed qualifiers for population, species, intervention, comparator, outcome,
  measurement, time, and study context;
- extractor model, prompt/schema version, extraction timestamp, and projection version.

Every subject, predicate, object, and qualifier stores verbatim surface text plus exact offsets in
the source. Canonical keys are deterministic lowercase Unicode/whitespace/punctuation
normalizations of the verified surface text. They improve exact graph joins but are not biomedical
entity resolution.

Offsets use Python Unicode code-point indexing with a half-open `[start, end)` interval. Validation
requires `source[start:end] == surface_text`, containment within the sentence span, non-overlapping
source identity, allowed enum values, and a non-empty subject, predicate, and object. Invalid model
output becomes an explicit extraction failure; it is never repaired silently.

## Extraction adapter

Add a model-neutral `PropositionExtractor` port and one OpenAI-compatible Qwen adapter. The adapter
sends a versioned system instruction, JSON Schema response format, temperature zero, one source
document or claim per request, and the configured deterministic seed. The model returns only
surface strings and offsets; the application computes canonical keys and identities after strict
validation.

The response must match the exact schema, source digest, and source identifier. JSON outside the
schema, mismatched spans, invented text, non-finite metadata, duplicate proposition identities, or
transport failure becomes a typed failure. No regex recovery, alternate model, retry with a
different prompt, or ungrounded normalization is allowed inside a fixed projection run.

The first qualification uses fixed positive, negative, qualified, and no-proposition probes. It
establishes schema and span fidelity only, not scientific extraction quality. If the existing Qwen
endpoint cannot pass qualification, the scope-revision trigger fires and implementation stops
before corpus projection.

## Versioned PostgreSQL projection

Use ordinary typed tables:

- `proposition_projection_runs`: version, corpus digest, extractor model, prompt/schema digest,
  status, timestamps, expected/complete/failed source counts;
- `source_propositions`: immutable proposition rows keyed by projection version and proposition ID;
- `proposition_arguments`: subject, predicate, object, and qualifier surface spans with canonical
  keys and qualifier roles;
- `proposition_extraction_failures`: source identity, typed error, and safe diagnostic metadata.

Rows are append-oriented within a version. A completed version is immutable. Rebuilding creates a
new version; it never mutates a completed projection. An incomplete version cannot be selected by
the scorer. Deleting source documents continues to cascade through explicit foreign keys, while
the projection run retains aggregate failure evidence.

The store exposes narrow ports to start a projection, persist one source result transactionally,
mark completion only when source accounting is exact, load one complete version, and load candidate
propositions. It refuses mixed corpus/model/prompt identities and stale or incomplete versions.

## Query-time induced graph and features

For a query, retrieve the existing broad pool first. Extract the claim once, then load propositions
for every candidate document from one complete projection version. Build an in-memory induced
bipartite graph with proposition nodes and canonical argument/entity nodes. Shared canonical entity
keys connect propositions across all candidates; graph construction is not gated by current top-10
recall.

One matcher computes the following raw features for every candidate:

- `graph-entity`: maximum MiniLM similarity between claim and document subject/object arguments;
- `graph-predicate`: maximum MiniLM similarity between predicates;
- `graph-argument`: best aligned subject-to-subject plus object-to-object similarity, retaining the
  crossed subject/object score as an argument-reversal diagnostic;
- `graph-polarity`: best aligned proposition pair scored `1` for matching polarity, `-1` for
  conflicting polarity, and `0` when no proposition pair exists;
- `graph-qualifier`: mean best-match similarity for claim qualifiers of the same role, with missing
  roles retained as zero rather than silently ignored;
- `graph-path`: reciprocal shortest evidence-bearing path between claim argument nodes and candidate
  proposition nodes using exact canonical entity joins, or zero when disconnected;
- `graph-composite`: the arithmetic mean of the six features after fixed range mapping to `[0, 1]`.

No feature threshold, learned weight, label-trained adjustment, or post-result formula change is
allowed. Each channel is exposed independently through the existing complete feature matrix. The
composite is an opt-in scorer, not a relevance probability. Every score record retains the matched
claim/document proposition IDs and exact source spans that produced it.

Documents with a completed, valid zero-proposition extraction receive explicit zero features.
Documents with missing or failed extraction make the diagnostic incomplete; they do not receive a
neutral or zero substitute.

## Composition and CLI

Add explicit composition functions rather than modifying the default application implicitly.
CLI operations are:

- build and validate the Phase 3 error-audit manifest;
- initialize or resume one proposition projection version;
- inspect projection coverage and failures;
- run the fixed proposition-graph diagnostic.

Existing `search`, `ask`, and retrieval-evaluation defaults remain unchanged. A named opt-in graph
strategy may be exposed only after the projection and scorer contracts are complete; it must fail
clearly when the configured projection version is unavailable.

## Fixed diagnostic

The first diagnostic uses the same 160-claim internal validation partition and the unchanged Phase
2 broad candidate pool. It reports:

- corpus and claim extraction coverage, zero-proposition counts, failures, and latency;
- exact source-span provenance validity;
- ranking metrics for each raw graph feature and the fixed composite;
- correlations with ColBERT and Phase 3 inference margins;
- separation of each audited Phase 3 error stratum and reviewer disposition;
- unchanged default retrieval metrics as a control;
- complete component, dataset, prompt, model, projection, and artifact digests.

The graph scorer is not fused with the default in this run. Results may justify a later fixed
fusion comparison only through a separate owner-approved issue. The public test set is not opened.

## Failure and recovery behavior

- Projection configuration mismatch stops before extraction.
- Per-source invalid output or transport failure is durable and visible.
- Resume skips transactionally completed sources and retries only sources with no committed result;
  this is idempotent client behavior, not an exactly-once remote guarantee.
- A projection with any missing accounting cannot become complete.
- An incomplete projection cannot be scored or represented as a leaderboard result.
- Diagnostic artifacts are immutable after results are opened; repair requires a new run identity.
- No failure falls back to a different extractor, prompt, graph representation, or ranking policy.

## Verification and proportionality

Focused tests cover contracts that could invalidate results: strict source spans, schema rejection,
stable identities, transactional projection accounting, incomplete-version refusal, graph feature
construction, complete candidate scoring, deterministic audit sampling, and report/raw consistency.
The implementation budget permits no more than 15 new focused test functions and no combinatorial
harness expansion.

Regular CI uses fake extractors and stores. Live DGX qualification performs only the fixed schema
and span probes before the one corpus projection. Exactly one complete repository gate runs on the
final current attempt. Independent review covers the stable candidate once per attempt.

## Rollout and stop gates

1. Approve this design, ADR-0031, and the narrow `semantic-evidence-ledger` activation.
2. Write the implementation plan and freeze schemas, prompts, formulas, and artifact identities.
3. Implement contracts, adapter, projection store, matcher, CLI, and focused tests.
4. Qualify Qwen schema/span fidelity. Stop if qualification fails.
5. Freeze and review the 100-row Phase 3 audit sample.
6. Build one corpus projection and run one fixed internal diagnostic.
7. Retain or reject the graph scorer from evidence; do not promote defaults in Issue #9.

The contract must be revised before adding a dependency, service, extractor comparison, learned
weight, calibration, AGE, graph candidate generation, or a new evaluation boundary.
