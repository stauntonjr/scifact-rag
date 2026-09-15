# Scientific Inference Scoring Design

Date: 2026-09-15

Governing roadmap: `docs/project/roadmap.md`, Phase 3

Status: owner-approved design

## Objective

Add one provenance-bearing scientific inference channel over every document in the existing broad
candidate pool. The channel must distinguish support, contradiction, and neutral or insufficient
evidence without asking lexical, vector, or late-interaction relevance scores to stand in for
scientific stance.

The first implementation is diagnostic. It records structured inference results beside the current
candidate features but does not change the default retrieval order, generation behavior, or public
CLI contract. The frozen 160-claim `train-validation` partition is the only model-quality boundary.
The already-inspected public test qrels remain unavailable for tuning, repair, model selection, or
promotion.

A bounded GitHub Issue for Phase 3 must be created and linked before implementation begins. This
design commit does not authorize creating that external planning state.

## Solution assessment

Adopt [`tasksource/ModernBERT-large-nli`](https://huggingface.co/tasksource/ModernBERT-large-nli)
as the one primary pretrained inference model, subject to runtime qualification and an immutable
model revision. It provides native entailment, contradiction, and neutral outputs, has an
Apache-2.0 license, and exposes a larger context boundary than the 512-token DeBERTa alternative.
The application must not train or fine-tune it on SciFact evaluation labels.

Adapt the existing explicit composition root, stored DP evidence views, hosted ColBERT scorer,
canonical evaluation artifacts, resume semantics, and raw-row-derived report pattern. Build only
the project-specific evidence-bundle contract, structured inference port, vLLM adapter,
coordination service, and diagnostic evaluator. Defer score fusion, calibration, graph scoring,
hierarchical evidence selection, a second NLI checkpoint, and any model training.

The declared controls are:

- existing ColBERT ordering without an inference feature for ranking;
- the validation label prior for stance classification.

The first slice does not serve a second NLI model merely to create a model-to-model comparison.

## Capability disposition

- `application-composition-root`: `use-active`; add structured ports and explicit adapter wiring
  without a service locator or import-time model construction.
- `cli-interface`: `use-active`; expose dry-run, execution, and reporting through the existing
  Typer composition boundary rather than another transport.
- `product-validation-challenges`: `use-active`; use the existing deterministic SciFact validation
  partition and retain characterized scientific-inference failures.
- `semantic-evidence-ledger`: `not-applicable`; run records describe model outputs and evaluation
  evidence, not governed source assertions or a canonical truth projection.
- every other inactive capability: `not-applicable`; this phase does not activate graph, durable
  memory, HTTP, MCP, web, role, security, or architecture-analysis skeletons.

No inactive capability is reimplemented under a new name.

## Considered approaches

### ModernBERT three-way inference over a bounded evidence bundle — selected

Rank the stored large-context DP chunks with the existing ColBERT service, admit complete chunks
under the NLI tokenizer budget, restore them to source order, and run one document-level
premise/hypothesis classification. This preserves cross-sentence context, scales beyond short
abstracts, and yields the three signals required by the roadmap.

### DeBERTa-v3-large three-way inference — rejected for the first slice

`cross-encoder/nli-deberta-v3-large` is a strong established sentence-pair control, but its
512-token input boundary is poorly matched to the project's explicit long-document direction. A
second hosted model would add cost without answering the first question: whether a structured
inference feature contributes unique signal at all.

### Scientific-domain NLI training or checkpoint selection — deferred

Scientific NLI corpora demonstrate that domain shift is material, but their label semantics do not
map cleanly to SciFact support, contradiction, and insufficient evidence. Fine-tuning would also
introduce a new label-use and selection boundary. Domain adaptation is justified only after the
fixed pretrained diagnostic identifies a concrete, retained failure class.

## Architecture

The structured inference path is parallel to scalar candidate scoring:

```text
broad deduplicated candidate pool
          |
          +--> existing retrieval and reranking features
          |
          +--> stored large-context DP chunks
                       |
                       v
              ColBERT chunk ordering
                       |
                       v
          token-budgeted evidence assembler
                       |
                       v
          ModernBERT three-way NLI service
                       |
                       v
      structured inference result plus provenance
                       |
                       v
        diagnostic feature record and evaluator
```

The existing `CandidateScorer` returns one scalar `CandidateScore`; it must not be overloaded with
three logits, evidence-bundle provenance, or inference failures. Add a separate structured
scientific-inference port and immutable result types. Existing scalar rankers and the default
ranking policy remain unchanged.

Every candidate document in the broad pool receives either one complete structured result or one
explicit failure record. The inference stage must not see only the current top 10.

## Components

### Evidence bundle assembler

The assembler is a deterministic, model-tokenizer-aware application component. It accepts the raw
claim, one candidate document, the document's stored `coref-nominal-dp-colbert` chunks, their
ColBERT scores, and a token budget. It returns an immutable evidence bundle or a typed assembly
failure.

### Scientific inference client

The model-neutral port accepts premise/hypothesis pairs and returns exactly three finite logits
with an explicit canonical label mapping. It does not return an unlabeled positional vector.

### vLLM scientific inference adapter

The adapter calls the DGX-hosted classification endpoint, validates its response, and maps the
checkpoint's labels to `entailment`, `contradiction`, and `neutral`. It performs exactly one HTTP
request for each attempt identifier. A timeout or transport failure becomes an explicit failure
record; the adapter has no hidden request retry loop. vLLM's classification interface is
documented at <https://docs.vllm.ai/en/v0.21.0/models/pooling_models/classify/>; compatibility is a
runtime hypothesis until qualified in the project's pinned NVIDIA container.

### Scientific inference scorer

The scorer coordinates chunk scoring, bundle assembly, inference, derived diagnostics, provenance,
and resumable result identity. It does not normalize or fuse the outputs into ranking.

### Scientific inference evaluator

The evaluator runs the fixed validation boundary, writes canonical raw records, derives reports
only from those records, and creates the diagnostic leaderboard entry and retained failure corpus.

## Evidence assembly contract

For each claim and candidate document:

1. Load every stored `coref-nominal-dp-colbert` chunk for that document.
2. Reject missing, duplicate-ordinal, foreign-document, or wrong-representation chunks.
3. Score every chunk against the unmodified claim with the existing ColBERT service.
4. Order chunks by descending finite ColBERT score, breaking ties by ascending chunk ordinal.
5. Start the premise with the document title exactly once as contextual metadata.
6. Iterate chunks in relevance order. Tentatively add each complete chunk, restore all admitted
   chunks to ordinal source order, add boundary markers for omitted ordinal ranges, serialize the
   title and chunks, and measure the complete premise/hypothesis pair with the exact ModernBERT
   tokenizer. Admit the chunk only when the serialized pair stays within the model limit. If a
   chunk does not fit, record `token_budget` and continue to later chunks that may fit.
7. Submit the completed bundle as the premise and the raw claim as the hypothesis.

The model limit is 2,048 tokens unless runtime qualification of the immutable checkpoint proves a
different limit, in which case configuration and documentation must be reconciled before a run.
Special tokens, title, separators, gap markers, and claim all count. No chunk is silently
truncated. If the title and claim do not fit, or no complete evidence chunk can be admitted, the
candidate receives an explicit assembly failure rather than an inference score.

Stored DP chunks are non-overlapping source-order partitions. Duplicate chunk identities are
invalid rather than heuristically merged by text. Boundary markers identify omitted chunk ordinal
ranges; they must not invent sentence numbers unavailable from the stored representation.
ColBERT scores and rejection reasons are retained as provenance but are not written into the model
premise.

The evidence-bundle interface may later support a hierarchical selector, but the first
implementation performs one bundled document-level inference call and no separate per-chunk NLI
calls.

## Candidate and attempt identity

Create a stable `candidate_id` before loading or scoring evidence. It is the SHA-256 of canonical
JSON containing:

- `run_id`;
- `query_id`;
- `document_id`;
- the raw claim SHA-256;
- the candidate document's title-and-content SHA-256.

The immutable run manifest binds the candidate-pool, model, tokenizer, scorer, and assembly
configuration. A content or configuration change therefore requires a new run rather than silently
changing an existing candidate identity.

`bundle_digest` is a separate nullable field. It remains null when chunk loading, chunk scoring, or
assembly fails and becomes the SHA-256 of the exact canonical evidence bundle after successful
assembly. Pre-assembly failure records are therefore identifiable and resumable without pretending
that a bundle exists.

After assembly, derive the only allowed `attempt_id` from canonical JSON containing the
`candidate_id`, `bundle_digest`, serialized HTTP request SHA-256, and attempt ordinal `1`. Append
and `fsync` a `scientific-inference-attempt-started/v1` event containing those identifiers before
calling the service. This is an at-most-once client policy, not an exactly-once claim.

## Structured result contract

One successful candidate result retains at least:

- run, query, claim, document, candidate, bundle, and attempt identifiers;
- model identifier and immutable revision;
- tokenizer identifier, immutable revision, and observed maximum length;
- scorer and evidence-assembly configuration version;
- entailment, contradiction, and neutral raw logits;
- predicted canonical label, defined by the greatest logit with a documented deterministic tie
  rule;
- `evidence_margin = logsumexp(entailment, contradiction) - neutral`;
- `polarity_margin = entailment - contradiction`;
- serialized premise digest and pair token count;
- every admitted chunk's representation, ordinal, text digest, text, and ColBERT score;
- every rejected chunk's ordinal and rejection reason;
- source-order restoration and omitted-ordinal boundary metadata;
- title inclusion and input claim text;
- latency and attempt count;
- null error fields.

The margins are uncalibrated diagnostics, not probabilities. `evidence_margin` measures whether a
candidate appears useful for verification regardless of direction. `polarity_margin` records the
support-versus-contradiction direction. A contradicting document therefore remains potentially
retrieval-relevant.

A failed record retains the same identity and provenance available before failure plus a typed
error stage, error code, sanitized message, attempt count, and null logits, label, and margins.
`bundle_digest` and `attempt_id` are nullable independently. `bundle_digest` is null whenever no
complete bundle exists, and `attempt_id` is null whenever no request attempt durably started. A
post-assembly, pre-request failure may therefore retain a bundle digest without an attempt ID. A
record has `attempt_count = 0` when `attempt_id` is null and `attempt_count = 1` otherwise. A failure
must never be serialized as `neutral`, zero, or a successful empty response.

## Identity, persistence, and resume

Raw evidence is an append-and-flush canonical JSONL event journal keyed by `candidate_id`. A
pre-inference failure writes one terminal result event. An inference candidate first writes and
`fsync`s its attempt-started event, then performs its one HTTP request, then writes and `fsync`s one
terminal success or request-failure result event referencing the same `candidate_id` and
`attempt_id`.

Resume validates the complete journal, rejects duplicate or foreign identifiers and impossible
event transitions, and classifies each planned candidate as follows:

- a terminal result event is complete and is not executed again;
- no event means the candidate has not started and may be processed;
- an attempt-started event without a terminal result means `outcome_unknown` and must not be sent
  again in that run.

The unmatched start may represent interruption before the send, during the request, or after the
response but before durable result persistence. The client cannot distinguish those cases without
server-side idempotency. `outcome_unknown` therefore has no logits or inferred label, counts as an
incomplete candidate, and is surfaced by report derivation without rewriting the journal. Retrying
it requires a new run identity. Existing explicit failure results likewise remain fixed evidence
and require a new run identity for another attempt.

The report is regenerated atomically from the journal. There is no cross-run inference-result
cache in this first implementation.

The run manifest records repository commit, validation input digest, candidate-pool strategy and
depth, DP representation, ColBERT model/tokenizer revisions, ModernBERT model/tokenizer revisions,
container identity, endpoint, context limit, request-attempt policy fixed at one, start and
completion timestamps, host, raw result path, and evidence class. Dry-run validation performs no
database or model calls.

## Runtime topology and qualification

ModernBERT runs as a separate explicit Docker Compose service using the project's pinned NVIDIA
vLLM image. The application receives its endpoint through configuration. It must not start, stop,
or reconfigure other DGX model services implicitly; the operator may free RAM before starting the
new service.

Before model-quality evaluation, a runtime qualification must verify:

- the immutable checkpoint loads in the current container;
- the service exposes the required classification behavior;
- premise/hypothesis serialization reaches the model as the intended pair;
- the observed label configuration maps exactly to the three canonical labels;
- the tokenizer and serving context limit match the recorded configuration;
- outputs are finite and structurally valid for fixed entailment, contradiction, and unrelated
  probes.

These probes establish integration behavior, not scientific quality. A label-map, tokenizer,
model-revision, context-limit, or response-contract mismatch stops before opening the evaluation
artifact.

## Evaluation protocol

Use exactly the existing deterministic 160-claim `train-validation` partition. No public test-set
access, fit, fine-tuning, calibration, threshold selection, weight sweep, checkpoint comparison,
or repair based on validation outcomes is authorized.

Label a gold claim-document relation from the public SciFact annotation as support or
contradiction. Candidate documents without an annotated relation are the benchmark's operational
neutral class; the report must state that this is an evaluation convention rather than proof that
the literature contains no relevant relation.

Report:

- three-way accuracy and macro-F1;
- per-class precision, recall, F1, and support;
- the label-prior control;
- scored, failed, skipped, and total candidate counts;
- result coverage and latency;
- the existing ColBERT no-inference ranking metrics, unchanged;
- inference metrics partitioned into gold document absent from the candidate pool, gold document
  present but annotated evidence absent from the admitted bundle, and annotated evidence present
  in the admitted bundle;
- descriptive distributions and rank correlations for raw logits and derived margins;
- evidence-sentence recall and citation correctness separately from stance metrics;
- categorized failures for synonymy, polarity, negation, qualifiers, association versus
  causation, species or evidence boundaries, and cross-sentence reasoning.

Phenomenon tags are retained error-analysis annotations, not new training labels. The run must not
invent unsupported tags merely to complete every category.

The first diagnostic does not add a fusion row. After the complete report is reviewed, a separate
owner-approved experiment may pass `evidence_margin` and `polarity_margin` through the existing
robust normalized feature-ranking architecture and compare ranking with and without inference on
the same fixed pool. No fusion parameter may be inferred from this first run.

## Failure and stop behavior

- Invalid manifest, dataset digest, candidate pool, model revision, tokenizer, label map, or
  service contract stops before results are opened.
- An individual request receives one attempt. A timeout, transport error, or invalid response then
  becomes an explicit candidate failure row.
- An unmatched attempt-started event becomes `outcome_unknown` on resume and is never resubmitted
  under the same run identity.
- Candidate failures do not suppress other candidates, but the run remains visibly incomplete.
- Any `outcome_unknown` candidate also makes the run incomplete.
- A partial run cannot be represented as a complete leaderboard result or promoted.
- Persistence failure, malformed prior records, duplicate keys, non-finite logits, or report/raw
  inconsistency stops the run.
- Service failure never falls back to a different model, evidence representation, or ranking
  policy.
- No runtime repair changes the fixed manifest after results are opened. An invalidated run is
  preserved and requires a new run identity.

## Verification

Focused TDD covers the result-invalidating boundaries rather than generating a combinatorial test
suite:

- exact token-budget admission with title, claim, separators, gaps, and special tokens included;
- relevance-order admission and source-order serialization;
- deterministic ties and rejection reasons;
- invalid stored chunk identities and missing document evidence;
- no silent truncation and explicit no-fit failures;
- canonical label mapping and response validation;
- finite logits, predicted label, and both margin calculations;
- failure records that cannot masquerade as neutral results;
- stable pre-assembly candidate identity and separate nullable bundle and attempt identifiers;
- journal transitions for pre-assembly failure, attempt start, terminal success, and terminal
  request failure;
- interruption before assembly, before durable attempt start, and after durable attempt start but
  before result persistence;
- resume that processes no-event candidates but never resubmits terminal or `outcome_unknown`
  candidates;
- canonical raw-record append, validation, resume, and report derivation;
- stance metrics, label-prior control, coverage partitions, and failed-row accounting;
- dry-run isolation from PostgreSQL, ColBERT, and ModernBERT.

Regular CI uses unit and contract tests with fake inference and token-budget implementations. It
does not require a GPU or download ModernBERT. DGX qualification is a separate integration gate.

The rollout sequence is:

1. pass regular CI and repository smoke checks;
2. qualify the live ModernBERT service and label mapping;
3. run a small fixed operational smoke sample to expose serving and serialization failures only;
4. run the frozen 160-claim validation evaluation once;
5. retain the manifest, raw candidate rows, derived report, categorized failure artifact, exact
   component revisions, and elapsed time;
6. add one diagnostic, explicitly non-fused internal leaderboard entry;
7. stop for owner review before any fusion or promotion proposal.

Before handoff, run exactly one final `make smoke` for the current candidate, followed by
`python3 tools/product_version.py`, `git diff --check`, and `git status --short`, and record their
outcomes in the engineering-loop evidence.

## Exit gate

The phase may propose a later fusion experiment only when the fixed report is complete and the
inference outputs contribute a measurable signal not already represented by ColBERT. Default
ranking or generation may change only under a later owner-approved decision that preserves
evidence recall and documents scientific failure modes.

If the model merely reproduces relevance ordering, is dominated by evidence-assembly failures, or
harms the predeclared evidence boundary, retain the structured interface, run evidence, and failure
corpus but do not promote the model. Graph scoring remains Phase 4 and is not pulled into this
implementation.
