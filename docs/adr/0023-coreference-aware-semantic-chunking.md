# ADR-0023: Coreference-aware semantic chunking

- Status: accepted for experiment; no default-strategy promotion
- Date: 2026-08-26
- Decider: Jack Rory Staunton, human owner
- Governing issue: local retrieval-effectiveness decision; no GitHub repository or Issue exists

## Context

MiniLM accepts 126 content tokens through the current SentenceTransformer wrapper. Exact corpus
measurement shows that 97.88% of title-plus-abstract inputs exceed that boundary, while the accepted
default uses overlapping token windows. The owner approved a bounded comparison of sentence-aware
packing and coreference-informed boundaries before further scoring or graph expansion.

The repository already contains spaCy sentence segmentation, full-abstract FastCoref analysis,
strict proper-noun canonicalization, MiniLM tokenization, strategy-aware PostgreSQL representation
storage, and a deterministic 160-query validation partition. A new dependency, storage schema,
similarity threshold, or chunking service is unnecessary.

## Decision

- Add `sentence-pack` as an opt-in representation. Keep titles separate and split before a
  proposed multi-sentence group exceeds 112 MiniLM content tokens, with an absolute 126-token limit
  for an indivisible sentence.
- Add `coref-aware-pack` under the same limits. Use original sentence and mention offsets to delay
  a soft boundary when a strict proper-noun coreference cluster has mentions on both sides.
- Treat coreference cohesion as a soft constraint. It may use the 14-token slack between target and
  hard maximum, but it never overrides the 126-token limit.
- Select boundaries before rewriting text. After grouping, replace eligible mentions within the
  chunk using the canonical proper noun selected from full-abstract analysis, including when the
  antecedent is outside the chunk.
- If a single sentence or canonicalized group is still too long, use overlapping token windows and
  shrink decoded slices until re-tokenization confirms at most 126 content tokens.
- Reuse existing title/chunk persistence and best-chunk document aggregation. Keep `token-window`
  as the CLI default.
- Fix this as a two-strategy comparison. Do not add embedding-similarity thresholds, rhetorical or
  proposition models, BM25 fusion, ColBERT chunk scoring, query rewriting, parameter sweeps,
  test-qrels evaluation, or default promotion.

## Consequences

### Positive

- Preserves sentence coherence without introducing a threshold or dependency.
- Tests coreference as boundary information independently from sentence packing alone.
- Preserves source offsets for boundary decisions and fails closed on invalid segmentation spans.
- Both representations coexist with every prior strategy in the existing table.

### Negative

- `sentence-pack` stores 19,569 chunk rows and `coref-aware-pack` stores 20,329, versus 19,283
  existing title-plus-abstract token windows.
- Coreference-aware ingestion requires the much slower full FastCoref pass.
- Proper-noun coreference is general-domain inference and may make biomedical mistakes.
- A bounded token fallback can split an unusually long individual sentence.

### Risks and mitigations

- Canonicalization can expand a chunk beyond its original token count: re-tokenize every completed
  chunk and use a bounded fallback under the hard limit.
- Rewriting before segmentation can invalidate source offsets: group original spans first and
  rewrite only the selected source range.
- Hard coreference closure can create whole-abstract chunks: use crossing chains only to delay a
  soft target boundary, never the hard maximum.
- Repeated benchmark use can overfit the design: run each fixed strategy once on validation, do not
  inspect test qrels, and make no follow-up threshold or fusion choice from the result.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| Existing overlapping token windows | Accepted default and strongest simple dense representation | Retained control; does not test sentence or entity cohesion |
| Sentence packing | Existing spaCy segmentation and MiniLM tokenizer | Selected as deterministic baseline |
| Coreference-aware sentence packing | Existing full-abstract clusters and original offsets | Selected as the only additional variable |
| Adjacent-embedding similarity breakpoints | Common semantic-chunking pattern | Adds a threshold and validation-tuning surface |
| Rhetorical or proposition segmentation | Better alignment with scientific discourse or claims | Requires a new model and overlaps later inference/graph work |
| Never split a coreference chain | Maximum entity cohesion | Can violate the model limit or recreate whole abstracts |

## Measured result

Both strategies ingested all 5,183 documents and were evaluated exactly once on the deterministic
160-query train-validation partition at cutoff 10.

| Strategy | Chunks | nDCG@10 | MAP@10 | Recall@10 | Precision@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| `sentence-pack` | 19,569 | 0.622347 | 0.578863 | 0.737500 | 0.084375 | 0.596654 |
| `coref-aware-pack` | 20,329 | 0.624108 | 0.577408 | 0.751563 | 0.086250 | 0.592924 |

Coreference-aware packing improves nDCG by 0.001761, recall by 0.014063, and precision by 0.001875
over sentence packing, while slightly lowering MAP and MRR. Both trail the retained validation
leaders by a wide margin. Neither is promoted, fused, or evaluated on test qrels.

## Verification and revisit trigger

Focused tests cover sentence ordering, title separation, soft and hard boundaries, proper-noun
canonicalization after grouping, overlong fallback, retokenization growth, invalid offsets, lazy
FastCoref loading, and independent strategy selection. Stored row counts and the two fixed
validation results provide operational evidence.

Revisit only with a separately accepted hypothesis: error analysis showing boundary-specific
misses, a fixed ColBERT chunk-aggregation contract, or a scientific discourse/proposition model
that justifies its dependency and evaluation cost. Do not tune the 112-token target on these
validation results.
