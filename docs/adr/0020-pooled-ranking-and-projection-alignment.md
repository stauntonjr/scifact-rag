# ADR-0020: Feature-preserving pooled ranking and projection alignment

- Status: accepted
- Date: 2026-08-26
- Decider: Jack Rory Staunton, human owner
- Governing issue: local retrieval-effectiveness decision; no GitHub repository or Issue exists

## Context

The existing BM25, token-window, strict-coreference, and nominal-coreference channels retrieve
complementary SciFact documents. The first MS MARCO experiment deduplicated their top-50 results
but discarded all first-stage rank and score evidence before letting the cross-encoder define the
final order. It improved MRR on the repeatedly inspected test qrels but lowered nDCG and recall.

The owner selected nDCG@10 as the primary objective with recall non-regression, accepted a
deterministic development/validation partition of the public train qrels, and requested that every
pooled candidate receive corpus-global BM25 and cross-channel dense scores. The owner also selected
an evidence-grounded proposition graph as the next scorer after this refactor, while keeping the
SciFact application separate from Procurement Intelligence Lab.

Procurement's inspected architecture treats lexical, vector, and graph indexes as rebuildable
derived projections over provenance-bearing assertions. That direction is compatible with SciFact,
but Procurement has not yet selected or implemented its second vertical and its vector/graph
adapters remain future work.

## Decision

- Separate candidate generation, candidate scoring, and rank aggregation behind application ports.
- Generate top 50 candidates independently from BM25, token windows, strict coreference, and
  nominal coreference; deduplicate to at most 200 documents while preserving generation rank,
  score, representation, matched passage, and passage ordinal.
- Rescore every pooled document through corpus-global BM25 and all three dense channels. Preserve
  the best matching passage and ordinal for each dense score.
- Add `pooled-four-channel-rrf`, which applies equal RRF with fixed `k=60` to the four complete
  rescored rankings. Generation ranks are diagnostic provenance and do not receive a second vote.
- Add `pooled-msmarco-rrf`, which adds the existing pinned MS MARCO score as a fifth complete rank.
- Partition the 809 train-qrels queries deterministically by SHA-256 query ID into 649 development
  and 160 validation queries. The already inspected 300 test queries are exploratory confirmation,
  not a tuning boundary.
- Add candidate-pool recall, query-hit, per-generator, mean-pool-size, final-ranking, and oracle
  nDCG diagnostics.
- Keep all existing strategies and the `token-window` default unchanged. Run no weight, depth,
  rank-constant, representation, or model sweep.
- Align terminology and future ownership with Procurement's evidence/projection direction without
  copying its code, adding a cross-repository dependency, mutating its repository, or claiming
  SciFact is already its second vertical.
- Defer proposition extraction, semantic-ledger activation, graph construction, graph scoring,
  graph retrieval, and contextual-sentence embeddings to later separately measured decisions.

## Consequences

### Positive

- Every ranker can inspect complete lexical and semantic evidence instead of interpreting missing
  source ranks as scores.
- Dense results retain the exact matching passage needed by a future proposition graph, passage
  reranker, evidence display, and error analysis.
- Candidate recall and oracle nDCG distinguish candidate-generation failures from ranking failures.
- A future graph scorer can enter through the same scorer port without owning retrieval or the
  composition root.

### Negative

- Pooled evaluation performs additional filtered PostgreSQL scoring queries and may call TEI for
  up to 200 documents.
- Equal RRF is deliberately simple and may underperform a strong two-channel baseline.
- The new train/validation boundary cannot undo prior inspection of the test qrels.

### Risks and mitigations

- BM25 could be counted twice: only the complete pooled BM25 ranking enters aggregation;
  generation ranks remain diagnostics.
- Candidate-local BM25 could make scores query-pool dependent: the scorer constructs its query
  from the persistent corpus index and only filters returned document IDs.
- A broad architectural layer could overtake product work: the slice adds no dependency, schema,
  service, graph implementation, or default change and stops after two fixed validation runs.
- Procurement and SciFact could drift: the crosswalk records ownership and promotion gates, while
  shared code extraction waits for two proven consumers.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| Keep cross-encoder-only reranking | Test MRR improved, but nDCG and recall declined | Discards complementary first-stage evidence |
| Add raw-score weights | BM25, cosine, and cross-encoder scores have unrelated scales | Requires calibration and creates a tuning surface |
| Add another contextual vector representation first | Sentence context may matter | Would change representation and ranking simultaneously |
| Build the proposition graph first | Graphs may represent scientific relations better | A stable candidate/scorer boundary and ranking diagnostics are prerequisites |
| Move SciFact into Procurement Intelligence Lab | Procurement already defines related semantics | Sacrifices the separate greenfield/template proof and crosses an unready second-vertical gate |

## Measured validation result

On the frozen 160-query validation partition, the existing BM25-plus-token-window RRF baseline led
at nDCG@10 `0.707033` and recall@10 `0.809375`. Pooled four-channel RRF reached nDCG `0.683622`
and recall `0.806250`. Adding MS MARCO improved pooled nDCG to `0.699656` but reduced recall to
`0.803125`. Neither pooled strategy cleared the promotion gate, so no test confirmation or default
change occurred.

The shared candidate pool nevertheless reached recall `0.906250` with oracle nDCG@10 `0.907664`
and a mean of `105.97` documents. The observed gap identifies second-pass ranking as the current
dominant bottleneck and supports the separately scoped proposition-graph scorer as the next
experiment.

## Verification and revisit trigger

Focused tests must cover deterministic split membership, candidate deduplication, passage
provenance, complete scorer coverage, one-vote-per-channel aggregation, diagnostics, and filtered
PostgreSQL scoring. The repository smoke gate and independent review must pass.

Revisit if a scorer cannot express required provenance, a graph needs candidate generation rather
than second-pass scoring, pooled query cost becomes material, a model change is proposed, or two
consumers demonstrate a stable shared contract suitable for extraction.
