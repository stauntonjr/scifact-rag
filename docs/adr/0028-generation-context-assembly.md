# ADR-0028: Document-aware generation context assembly

- Status: accepted; whole-document default confirmed after automatic and blinded human validation
- Date: 2026-08-29
- Decider: Jack Rory Staunton, human owner
- Governing issue: [#5](https://github.com/stauntonjr/scifact-rag/issues/5)

## Context

The existing `ask` path sends every retrieved title and complete abstract directly to the external
Qwen generator. That is a useful control for short SciFact abstracts but does not scale to longer
documents. The repository already stores raw `coref-nominal-dp-colbert` content views with a hard
510-token ColBERT limit and already has a hosted ColBERT reranker adapter. Those views preserve
exact abstract substrings and give long documents multiple opportunities to match a query.

Observed implementation evidence is limited to repository contracts and stored-representation
design. No generation-quality comparison has established that chunks outperform parent documents,
and the ColBERT token boundary is not a Qwen prompt-token guarantee.

## Decision

- Add a `GenerationContextAssembler` application port after document retrieval and before the
  existing `AnswerGenerator` port. Retrieval remains responsible for parent-document ranking;
  context assembly owns only the evidence text supplied to generation.
- Depend on a narrow `StoredChunkSource` port for context loading rather than the full evidence
  store contract; the PostgreSQL store satisfies both ports through its existing `load_chunks`.
- Expose two distinct generation policies while retaining three accepted
  `ask --context-strategy` values:
  - `whole-document` preserves the retrieved title and complete abstract unchanged and remains the
    compatibility default.
  - `adaptive` preserves a whole abstract only when its stored DP representation is exactly one
    view equal to that abstract. Otherwise it loads every stored raw
    `coref-nominal-dp-colbert` view for the parent, scores chunk text without the title in one
    ColBERT request, and selects at most two. The title is restored only in generator context.
  - `top-dp-chunks` remains accepted as a compatibility alias for `adaptive`; it is not separately
    assembled or evaluated.
- Preserve retrieved parent order so every document can contribute before a later document is
  considered. Within each parent, select by descending ColBERT score with lower ordinal as the
  deterministic tie-break, then restore source ordinal order for generator readability.
- Retain the parent title and retrieval score on every selected chunk. Multiple selected chunks may
  share one parent document ID. The `Answer.evidence` field reports the actual contexts supplied to
  the generator.
- Continue validating generated citations against retrieved parent document IDs, not chunk
  ordinals. Reject an assembler that supplies an unretrieved parent before calling the generator.
- Fail explicitly when a requested parent lacks the required DP representation or the store or
  reranker returns missing, duplicate, foreign, blank, misaligned, or non-finite data.
- Do not change the generation prompt, retrieval strategy, DP persistence, model revisions,
  service lifecycle, or default context strategy in this decision.

## Consequences

### Positive

- Short SciFact abstracts retain the established whole-document control.
- Long documents can contribute bounded, query-relevant passages without one right-truncated
  document prompt.
- Parent rank, title, document citations, and exact raw evidence text remain visible.
- Context policy is independently replaceable for future HTTP, MCP, or UI composition roots.

### Negative

- The opt-in chunk policy requires the stored DP representation and one additional ColBERT scoring
  request after retrieval when the document has multiple stored views.
- Two chunks from one parent repeat its title and document ID in the prompt and in returned
  evidence.
- The fixed two-per-parent policy and lack of a global Qwen-token counter are implementation
  constraints, not measured optima.

### Risks and mitigations

- A selected chunk may omit a negation, qualifier, experimental condition, or antecedent. Preserve
  the whole-document default and evaluate evidence sufficiency before adding local expansion.
- ColBERT relevance may not identify the best context for Qwen generation. Treat the modes as
  selectable architecture, not a quality claim, until downstream evaluation exists.
- ColBERT's 510-token boundary does not prove that the assembled prompt fits Qwen's tokenizer or
  32K runtime window. The CLI limit and two-per-parent cap bound growth, but token-fit verification
  remains required before broader documents or defaults are adopted.
- Missing DP rows could otherwise cause silent fallback to whole documents. Explicit failure keeps
  ingestion/runtime drift observable.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| Always send whole parents | Existing `ask` behavior and strong short-abstract retrieval control | Does not scale with document length |
| Globally take the highest-scoring chunks | Common passage-RAG shape | Can let one parent consume the context and discard document-rank diversity |
| Send every stored DP chunk | Complete stored evidence | Context and scoring work grow with document length |
| Add adjacent-sentence or coreference expansion now | Plausible mitigation for missing local context | Needs a trigger, token budget, and downstream evaluation not yet selected |
| Add a generator-tokenizer budget now | Would provide a stronger prompt-fit guarantee | Introduces a model-specific dependency and tuning boundary beyond this slice |

## 2026-09-14 validation review

The first fixed 160-claim execution is retained in
`docs/reports/issue-5-generation-context-diagnostic.md`. It completed all 480 rows, but exposed that
`top-dp-chunks` and `adaptive` are operationally identical for the current raw DP representation
and that unseeded temperature-0.1 sampling confounds their answer differences. DP did not lower
median input tokens overall or on the long/retrieved subset and omitted some gold evidence. The
whole-document compatibility default is therefore retained. That initial execution was not a
completed downstream quality comparison: deterministic stance output and the fixed human review
were still missing from it.

## 2026-09-14 corrected validation

The repaired execution in `docs/reports/issue-5-generation-context-validation.md` completed 480/480
rows with a strict parseable verdict and exact-prompt response reuse. Whole-document and DP stance
accuracy were 0.8125 and 0.8250 overall and tied at 0.8387 on the 31 long/retrieved claims. DP did
not reduce median input tokens, increased the long-subset median, and reduced conditional gold
evidence recall. Whole-document is retained as the default. The two chunk strategy names produced
identical contexts and outcomes for all 160 claims, so their duplication is a simplification
follow-up rather than evidence for either label. That follow-up now makes `adaptive` canonical,
retains `top-dp-chunks` as an exact CLI alias, and limits future paired evaluation to
`whole-document` and `adaptive`; retained three-policy records remain reportable. No prospective
non-inferiority margin exists, so no promotion claim is made.

## 2026-09-16 blinded human review

The fixed 24-claim review contains 42 distinct deduplicated responses. After source-bound
validation and policy-map join, every policy has 18/24 grounded answers and 5/24 material
overstatements. Top-DP and adaptive have identical categorical rubric judgments; whole-document
differs categorically on one query but not in groundedness or overstatement. This parity is
expected for short abstracts and does not establish long-document superiority or failure. It
confirms the existing decision:
whole-document remains the compatibility default and adaptive remains the explicit scalable
opt-in. Issue #5 is complete without a model rerun, policy retuning, or default change.

## Verification and revisit trigger

Focused tests must prove compatibility-default behavior, exact adaptive qualification, bounded
per-parent selection, deterministic ordering and ties, batch scorer alignment, malformed-store
failure, composition and CLI exposure, actual-context handoff, and retrieved-parent citation
validation. No live model result is required for implementation acceptance.

The SciFact downstream comparison is complete. Revisit only when a larger-document application
exposes prompt overflow, truncation, or a measured context-loss class that requires a global
generator-token budget, neighboring evidence expansion, more than one representation, or a
different passage scorer.
