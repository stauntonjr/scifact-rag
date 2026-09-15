# ADR-0030: Scientific inference scoring

- Status: accepted
- Date: 2026-09-15
- Decider: Jack Rory Staunton, human owner
- Governing issue: [GitHub Issue #8](https://github.com/stauntonjr/scifact-rag/issues/8)

## Context

The selected retrieval architecture ranks relevant documents effectively, but lexical, vector,
and late-interaction relevance scores do not distinguish scientific support, contradiction, or
insufficient evidence. Phase 3 therefore needs one structured inference channel over every
document in the existing broad candidate pool before graph scoring or another retrieval change.

The first proposed checkpoint, `tasksource/ModernBERT-large-nli` at revision
`ca476cb923a8637073d4ceb0f19f7fc236e260d4`, cannot support a clean SciFact diagnostic. Its pinned
configuration lists `scifact_entailment` among its training tasks, while the frozen 160-claim
validation boundary is derived from SciFact training data. `dleemiller/ModernCE-large-nli` is also
unsuitable because its model card says it initializes from that checkpoint and freezes most of the
inherited layers.

The selected `cross-encoder/nli-deberta-v3-large` model card identifies SNLI and MultiNLI as its
training sources and exposes native contradiction, entailment, and neutral labels. That provenance
is a published source claim, not an independent audit of all upstream data. The immutable selected
revision is `bab4bc7178836f731dcfd18c06ca9def0a137712`.

The model accepts at most 512 tokens per premise/hypothesis pair. The project already stores raw,
non-overlapping `coref-nominal-dp-minilm` chunks bounded to 126 content tokens and already hosts a
ColBERT scorer. Reusing those surfaces permits selective evidence assembly for documents longer
than a single model context without adding a third chunk optimizer.

The pinned NVIDIA vLLM runtime does not explicitly list DeBERTa as a supported architecture.
Automatic conversion is not adequate evidence that the trained classification head and label
order are preserved.

## Decision

Serve `cross-encoder/nli-deberta-v3-large` at revision
`bab4bc7178836f731dcfd18c06ca9def0a137712` through a dedicated Transformers process in an opt-in
Docker Compose service. Reuse the existing digest-pinned NVIDIA 26.06 image as the PyTorch/CUDA
runtime base, but do not use vLLM model execution. Runtime qualification must prove the exact
checkpoint, tokenizer, label map, pair order, 512-token limit, and finite raw logits before any
model-quality run.

For each candidate document, score all stored `coref-nominal-dp-minilm` chunks against the raw
claim with ColBERT. Attempt admission in descending ColBERT order, keep each chunk whole, restore
admitted chunks to source order, and include explicit omitted-ordinal markers. Count the complete
serialized premise/hypothesis pair with the pinned DeBERTa tokenizer. The client and service must
agree on the observed token count; a mismatch fails rather than truncating.

Return separate entailment, contradiction, and neutral logits plus two uncalibrated diagnostics:
`logsumexp(entailment, contradiction) - neutral` and `entailment - contradiction`. Keep this
structured result parallel to scalar candidate ranking. The first run neither fuses these values
nor changes retrieval or generation.

Create candidate identity before evidence assembly. Store the evidence-bundle digest only after
assembly and the attempt ID only after a request is fully constructed. Append and `fsync` an
attempt-start event before the single allowed HTTP request. A started attempt without a terminal
result is `outcome_unknown` and is never resubmitted under the same run ID. This is an at-most-once
client policy, not an exactly-once server guarantee.

Use only the frozen 160-claim `train-validation` partition for the first diagnostic. Do not access
the public test qrels, train or compare models, tune parameters, calibrate scores, or alter a fixed
run after results are opened. The result is internal validation evidence only.

## Consequences

### Positive

- Scientific stance becomes an explicit, inspectable signal rather than an interpretation of
  relevance scores.
- The selected checkpoint has no identified SciFact overlap in its published training sources.
- Existing DP chunks and ColBERT scoring provide a scalable evidence selector without another
  representation family.
- Tokenizer agreement, complete-chunk admission, and source-order restoration remain observable.
- An interrupted long run can resume missing work without silently duplicating uncertain model
  requests.

### Negative

- DeBERTa sees only a selected 512-token bundle, so evidence selection can omit decisive context.
- The diagnostic adds another GPU service and roughly one request per pooled candidate.
- At-most-once recovery deliberately leaves interrupted attempts unresolved within a run.
- SNLI/MultiNLI training may transfer poorly to scientific claims even without known benchmark
  overlap.

### Risks and mitigations

- **Published provenance is incomplete:** record the model card and immutable revision and avoid a
  clean-generalization claim.
- **Label or pair-order inversion:** fail runtime qualification on fixed entailment,
  contradiction, and unrelated probes.
- **Client/service tokenizer drift:** carry the expected pair count in each request and require the
  service to compute and echo the same count.
- **Evidence omission:** retain admitted and rejected chunks, scores, gap metadata, and rationale
  coverage in raw records and reports.
- **Operational interruption:** preserve attempt-start state and require a new run ID before any
  retry of an unknown outcome.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| `tasksource/ModernBERT-large-nli` | Its pinned configuration lists `scifact_entailment` training | The validation boundary is derived from SciFact training data |
| `dleemiller/ModernCE-large-nli` | Its model card describes initialization from the contaminated tasksource checkpoint | Later SNLI/MultiNLI fine-tuning does not erase inherited exposure |
| vLLM-hosted DeBERTa | DeBERTa is not explicitly listed in the pinned vLLM supported-model table | Correct classification-head and label behavior are not established |
| Train a scientific NLI model | Could improve domain fit | Adds label use, model selection, and tuning before the fixed pretrained diagnostic |
| Whole-document truncation | Simpler request construction for short abstracts | Does not extend naturally to longer documents and can discard decisive trailing evidence |
| Begin graph retrieval now | A graph may ultimately represent scientific relations better | Graph extraction and scoring are separately governed Phase 4 work |

## Verification and revisit trigger

Regular CI uses fake token budgets, scorers, and inference clients. Live qualification on one DGX
must verify the immutable model and tokenizer revisions, exact label map, premise/hypothesis order,
512-token rejection, client/service token-count parity, finite logits, and response schema. The
fixed diagnostic then reports stance metrics, evidence coverage, failure counts, latency, label-
prior control, and correlations with unchanged ColBERT ranking.

Revisit this decision only if runtime qualification shows the pinned Transformers path is
incompatible, the model provenance is corrected or contradicted by new primary evidence, evidence
assembly dominates failures, or the completed diagnostic justifies a separately approved fusion
or model experiment. Graph scoring remains Phase 4.
