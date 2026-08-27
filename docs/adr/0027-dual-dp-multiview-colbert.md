# ADR-0027: Dual raw-text coreference DP and multiview ColBERT scoring

- Status: accepted implementation; fixed development measurement complete; not promoted
- Date: 2026-08-27
- Decider: Jack Rory Staunton, human owner
- Governing issue: local retrieval-effectiveness decision; no GitHub repository or Issue exists

## Context

The prior pooled ColBERT strategies used MiniLM representations only to generate a candidate pool,
then scored each candidate's complete title-plus-abstract text once. The service right-truncated
that input at 512 tokens. On SciFact, 455 of 5,183 title-plus-abstract inputs exceed the model's
510-token content budget; the loss would be substantially larger for longer real-world documents.
The stored candidate-generating sentence and 112-token pack text did not solve this problem because
the reranker did not score those stored views.

Coreference-aware global interval packing already supplies a general boundary objective: minimize
the number of entity chains cut by chunk boundaries, with each eligible chain having equal cost,
then minimize squared deviation from a target size, chunk count, and boundary ordinals. A single
boundary profile cannot serve both MiniLM retrieval and ColBERT scoring well because their useful
content budgets differ.

## Decision

- Analyze each abstract once with the pinned FastCoref model. A `NOUN` or `PROPN` mention may anchor
  a chain for both nominal sentence rewriting and boundary costs.
- Persist two independent global-DP boundary profiles from the same validated source sentence spans
  and coreference analysis:
  - `coref-nominal-dp-minilm`: target 112, hard limit 126, embedded by MiniLM and eligible to
    generate candidates.
  - `coref-nominal-dp-colbert`: target and hard limit 510, stored without a MiniLM embedding and
    used only as a ColBERT content view.
- Render both DP profiles from exact raw abstract substrings. Coreference affects cut placement only;
  it does not rewrite the DP text. Nominal rewriting remains confined to the separate
  `coref-nominal-sentence` candidate representation.
- Use offset-aware fast tokenizers for the exact pinned MiniLM and ColBERT model names. If an
  indivisible sentence exceeds a hard limit, slice exact source substrings and shrink each boundary
  until the isolated substring retokenizes within the profile limit.
- Form the primary candidate pool from exactly four independent top-50 generators: VectorChord BM25,
  title MiniLM embeddings, nominal-coreference sentence MiniLM embeddings, and raw MiniLM-DP
  embeddings. Token windows, proper-noun sentences, plain sentence packs, prior interval packs, and
  the ColBERT-DP profile remain selectable history but do not generate candidates here.
- Score every deduplicated candidate in two ColBERT channels. The title channel scores only the raw
  title. The content channel scores every stored raw 510-token DP chunk and retains the maximum raw
  score, with the winning chunk ordinal and text as provenance.
- Normalize title and max-content scores independently within each query's complete candidate set
  using the existing median/MAD robust normalizer and deterministic fallbacks. Rank by their equal
  arithmetic mean. Candidate-generation scores do not enter final ordering.
- Run one fixed diagnostic at cutoff 10 over all 649 deterministic `train-development` queries. Do
  not inspect validation or test qrels, sweep limits or weights, or promote the strategy to default.
- Expose `pooled-coref-interval-multiview-colbert` as an opt-in ablation that holds the prior
  six-generator interval pool fixed while reusing the exact title/max-content scorers, robust
  normalizer, and equal-mean policy. It adds no scorer or parameter and does not replace either
  strategy.

## Consequences

Long abstracts no longer lose all content after one right-truncation point. Every content region has
an opportunity to supply the document's ColBERT content score, while the independent title signal is
counted exactly once. The max operator intentionally asks whether any content view is a strong match;
it does not reward repeated evidence or aggregate multiple passages.

The approach increases stored representation rows and reranker inputs. The 510-token views do not
consume pgvector storage, and retrieval remains bounded by the four top-50 generators. The strategy
is opt-in as `pooled-coref-nominal-dp-colbert`; the existing default and historical strategies are
unchanged.

The one fixed 649-query development run averages 126.56 candidates, reaches candidate recall
0.955059 and oracle nDCG@10 0.955886, then ranks at nDCG 0.657331, MAP 0.607033, recall 0.795095,
and MRR 0.620860. The wide oracle-to-ranking gap confirms that candidate availability is not the
limiting factor for this result.

A subsequent same-split control ran the unchanged prior `pooled-coref-interval-colbert` strategy.
Its six-generator pool averages 137.47 candidates, reaches candidate recall 0.954289 and oracle
nDCG@10 0.955290, then ranks at nDCG 0.759619, MAP 0.719683, recall 0.869055, and MRR 0.730180.
Dual-DP therefore changes candidate recall by only +0.000770 and oracle nDCG by +0.000596, while
changing final nDCG by -0.102288, MAP by -0.112650, recall by -0.073960, and MRR by -0.109320. Its
oracle-to-final nDCG gap is 0.298556 versus 0.195671 for the control.

The fixed-pool ablation then applies the exact multiview scoring bundle to the control's unchanged
six-generator candidates. Pool size, candidate recall, query-hit rate, every channel metric, and
oracle nDCG are identical to the whole-document control. Final nDCG is 0.655268, MAP 0.604133,
recall 0.795095, and MRR 0.618217: changes of -0.104351, -0.115549, -0.073960, and -0.111963 from
whole-document scoring. The oracle-to-final nDCG gap expands from 0.195671 to 0.300022.

Conversely, holding the multiview scorer fixed while changing from the six-generator pool to the
four-generator DP pool changes nDCG by only +0.002063, MAP by +0.002899, recall by 0, and MRR by
+0.002643. The scoring-bundle regression therefore persists when pool composition is fixed; the
pool change did not cause it. This still does not identify whether robust normalization, equal
title/content fusion, maximum chunk aggregation, title separation, or content chunking is the
responsible component. No further component or weight sweep was run, and neither strategy is
promoted as the default.

The first execution of this control completed but its final JSON was lost to tool-output
truncation and the ephemeral container was already removed. One identical recovery execution
produced the retained artifact; no further model run was made.

An ingestion attempt exposed a tokenizer-boundary edge case: a raw substring selected from 510
full-context token offsets can retokenize to more than 510 tokens in isolation. The final splitter
keeps raw text but adaptively shrinks the boundary and tests this contrastive case. The failed
attempt produced no evaluation result and did not change the strategy contract.

## Alternatives

| Alternative | Reason not selected |
|---|---|
| Rerank whole title plus abstract | Right truncation discards later content and conflates title with content |
| Rerank candidate-generating sentences and small packs | Multiplies scoring work and overrepresents the deliberately fine-grained retrieval views |
| Rewrite both DP profiles with resolved coreferences | Changes source language and makes scorer evidence harder to audit |
| Persist a third MS MARCO boundary profile | The current experiment is ColBERT-specific; a cross-encoder profile would need a separately justified query-plus-document budget |
| Use one 126-token DP profile for both models | Leaves most of ColBERT's context unused and greatly increases view count |
| Tune title/content weights | The inspected data does not support a weight sweep or general claim |

## Verification and revisit triggers

Focused tests cover shared analysis, nominal boundary costs, raw-text preservation, exact profile
identity, selective embeddings, exact generator/scorer composition, complete multiview scoring,
max selection, deterministic ties, and failure on missing views. PostgreSQL integration verifies
nullable scorer-only embeddings, verbatim loading, and exclusion from vector retrieval. Full-corpus
checks must confirm row counts, hard limits with exact tokenizers, raw-source containment, document
tuple identity, BM25 index stability, and post-ingest BM25 usability before the fixed diagnostic.

Revisit if model revisions or tokenizer budgets change; if documents become long enough that all
chunks per candidate are operationally expensive; if max scoring proves too sensitive to isolated
false positives; or if a separately justified MS MARCO, listwise, graph, or hierarchical scoring
view is introduced.
