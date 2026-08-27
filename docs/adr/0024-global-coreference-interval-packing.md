# ADR-0024: Global coreference-interval packing and incremental pooling

- Status: accepted for experiment; no default-strategy promotion
- Date: 2026-08-26
- Decider: Jack Rory Staunton, human owner
- Governing issue: local retrieval-effectiveness decision; no GitHub repository or Issue exists
- Supersedes: the boundary-selection portion of ADR-0023; its greedy strategies remain retained
  baselines

## Context

ADR-0023 tested a greedy left-to-right packer whose proper-noun coreference signal could only use
the 112-to-126-token slack. That algorithm could consume early capacity and later be forced to cut
a chain that a globally earlier boundary would have preserved. It also left the new packing
representations out of the existing fixed BM25 fusion and four-channel pooled-ranking architecture.

The owner selected equal cut cost for every eligible proper-noun coreference chain and directed
that each packing representation be added individually to the existing pool. Existing FastCoref
clusters, source offsets, MiniLM token accounting, PostgreSQL representation storage, symmetric
BM25 RRF, complete-score pooling, and the frozen 160-query train-validation split already provide
the required boundaries. No new model, schema, dependency, or parameter sweep is needed.

During evaluation, repeated representation ingestion exposed a separate persistence defect:
unchanged document and BM25-vector tuples were rewritten for every representation batch. The
VectorChord-BM25 index retained obsolete heap locations and required a one-time index rebuild.

## Decision

- Add `coref-interval-pack` as an opt-in representation. Map every eligible cluster mention to its
  original sentence position and treat the gap between sentences as a candidate boundary.
- Give each proper-noun coreference cluster crossing a candidate boundary a cost of one. Do not
  weight by mention count, confidence, entity type, or SciFact performance.
- Use dynamic programming over contiguous sentence groups. Compare complete partitions by the
  fixed lexicographic objective: total chain cuts, total squared deviation from the 112-token
  target, number of chunks, then sentence-boundary ordinals for deterministic ties.
- Enforce 126 MiniLM content tokens as a hard multi-sentence limit. An indivisible overlong sentence
  remains eligible as a singleton and uses the existing overlapping bounded-token fallback.
- Continue to select groups from validated original offsets and canonicalize proper-noun references
  only when rendering a candidate group. Titles remain separately retrievable.
- Retain `sentence-pack` and greedy `coref-aware-pack` as comparison strategies. Keep
  `token-window` as the CLI default.
- Add a fixed symmetric BM25 RRF strategy for each of the three packers. Reuse top 50 candidates
  per source, `k=60`, no weights, and cutoff 10.
- Add three separate incremental pool strategies. Each preserves the existing BM25, token-window,
  strict-proper-noun, and nominal-coreference generators and complete scorers, then adds exactly one
  packing generator/scorer as a fifth channel. Do not combine packers in one experiment.
- Make representation ingestion tuple-idempotent at the document layer. Update an existing
  document only when title/text changed or its retained embedding was missing; update its BM25
  vector only when retokenization differs. Representation rows remain independently replaceable.
- Do not run test qrels, tune weights/depth/limits, invoke MS MARCO or ColBERT, or promote a default
  in this decision.

## Consequences

### Positive

- The optimizer can move an earlier boundary to preserve a later entity chain instead of making an
  irreversible greedy choice.
- Equal chain cost is corpus-independent and introduces no learned or validation-selected weight.
- Fixed fusion isolates lexical complementarity, while incremental pool diagnostics distinguish
  candidate recall from the ranking policy's ability to exploit those candidates.
- Unchanged representation ingestion no longer creates new document tuple versions or invalidates
  BM25 tuple references.

### Negative

- Candidate segment enumeration is quadratic in the number of abstract sentences and repeatedly
  renders/tokenizes valid spans. SciFact abstracts are small enough for the observed ingestion, but
  this is not a long-document algorithm claim.
- A chain spanning distant mentions penalizes every intervening boundary equally, including gaps
  whose intermediate sentences are not semantically important to that entity.
- Minimizing chain cuts before length balance may select less uniform chunks when overlapping
  intervals make cuts unavoidable.
- Adding a fifth complete scorer worsened equal-RRF ranking even when it improved candidate recall.

### Risks and mitigations

- Canonicalization can expand a candidate beyond the hard limit: token-count every rendered edge
  and reject over-limit multi-sentence edges; retain bounded singleton fallback.
- Overlapping intervals can make a zero-cut partition impossible: minimize the count of cut chains
  rather than treating closure as an infeasible hard constraint.
- Validation-driven weighting would overfit: keep every chain cost equal and preserve all existing
  retrieval and fusion parameters.
- Repeated ingestion can churn custom-index tuple references: condition both document and BM25
  writes and retain an integration test that checks tuple identity plus a post-ingest BM25 query.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| Retain greedy coreference slack only | ADR-0023 improved recall slightly | Cannot reconsider an earlier boundary when the hard limit later cuts a chain |
| Never split a coreference interval | Maximizes local entity closure | Overlapping or long intervals can exceed MiniLM's hard limit or recreate whole abstracts |
| Weight chains by mentions, type, or confidence | Could prioritize salient entities | Adds an uncalibrated or SciFact-tuned weighting policy the owner explicitly avoided |
| Replace prior coreference channels in the pool | Holds pool width constant | Owner selected additive one-at-a-time comparisons against the existing pool |
| Add all packers to one pool | Maximizes candidate diversity | Obscures individual contribution and expands the pool without a bounded attribution test |

## Measured result

All 5,183 documents produced 19,571 interval chunks. An exact tokenizer audit found a maximum of
126 content tokens and zero violations.

| Standalone packer | nDCG@10 | MAP@10 | Recall@10 | Precision@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| Sentence pack | 0.622347 | 0.578863 | 0.737500 | 0.084375 | 0.596654 |
| Greedy coreference pack | 0.624108 | 0.577408 | 0.751563 | 0.086250 | 0.592924 |
| Global coreference interval pack | **0.630108** | **0.581919** | **0.762500** | **0.087500** | 0.596143 |

| BM25 fusion | nDCG@10 | MAP@10 | Recall@10 | Precision@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| BM25 + sentence pack | 0.689889 | 0.649854 | **0.796875** | **0.091250** | 0.666081 |
| BM25 + greedy coreference pack | 0.694328 | 0.655565 | **0.796875** | **0.091250** | **0.670813** |
| BM25 + interval pack | **0.694759** | **0.657183** | 0.793750 | 0.090625 | 0.670799 |

| Incremental pool | Mean size | Candidate recall | Oracle nDCG@10 | RRF nDCG@10 | RRF recall@10 |
|---|---:|---:|---:|---:|---:|
| Existing four-channel control | 105.97 | 0.906250 | 0.907664 | **0.683622** | **0.806250** |
| + sentence pack | 114.22 | 0.918750 | 0.920164 | 0.681954 | 0.800000 |
| + greedy coreference pack | 114.26 | **0.925000** | **0.926414** | 0.677932 | 0.793750 |
| + interval pack | 114.11 | **0.925000** | **0.926414** | 0.673584 | **0.806250** |

The interval optimizer improves the three standalone packers' nDCG, MAP, recall, and precision. Its
BM25 fusion leads the packing fusions on nDCG and MAP but remains below BM25 plus token windows.
Both coreference packers add the same best candidate recall and oracle nDCG to the existing pool,
while the five-channel equal-RRF policies regress ranking. This supports a separately authorized
complete-reranker comparison, not automatic reranking or promotion.

## Verification and revisit trigger

Focused tests cover greedy look-ahead failure, equal per-chain boundary cost, overlong fallback,
strategy mappings, one-at-a-time pool selection, unchanged defaults, and idempotent document
persistence. Live checks cover all-row token limits, the fixed validation runs, exact corpus-scale
tuple identity before and after no-op ingestion, unchanged BM25 index size, and successful BM25
retrieval without reindexing.

Revisit only with a separately accepted hypothesis: a complete reranker over the improved pools, a
long-document workload that invalidates quadratic enumeration, or an entity-confidence source that
justifies replacing equal cut cost. Do not derive chain weights or packing limits from these SciFact
validation results.
