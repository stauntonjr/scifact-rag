# Feature-preserving pooled-ranking evaluation

- Date: 2026-08-26
- Decision: adapt existing retrievers behind complete pooled scoring and fixed rank aggregation
- Primary metric: nDCG@10
- Guardrail: recall@10 must not regress from the best frozen validation baseline
- Stop condition: two fixed pooled strategies on one deterministic validation partition; no sweep

## Evaluation boundary

The public BEIR SciFact `train.tsv` contains 809 query IDs. SHA-256 of each query ID, interpreted as
an integer modulo five, assigns bucket four to validation and all other buckets to development.
This produces 649 development and 160 validation queries. The partition is deterministic, disjoint,
and exhaustive.

The 300 test queries were already inspected repeatedly while building earlier strategies. They
remain useful exploratory history but are not used for selection. A new test confirmation was
predeclared only if validation nDCG improved without recall regression.

All runs reuse top 50 candidates per generator, cutoff 10, equal RRF `k=60`, the existing MiniLM
vectors, the existing corpus-global VectorChord-BM25 index, and the pinned TEI MS MARCO service.
No weight, depth, constant, model, tokenizer, or representation parameter changed.

## Validation results

| Strategy | nDCG@10 | MAP@10 | Recall@10 | Precision@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| BM25 plus token-window RRF | **0.707033** | **0.670174** | **0.809375** | 0.092500 | **0.681111** |
| Pooled BM25 + three dense + MS MARCO RRF | 0.699656 | 0.660848 | 0.803125 | 0.092500 | 0.675171 |
| Pooled BM25 + three dense RRF | 0.683622 | 0.638278 | 0.806250 | 0.092500 | 0.657341 |
| BM25 plus nominal-coreference RRF | 0.681172 | 0.645154 | 0.778125 | 0.089375 | 0.655685 |

Neither pooled strategy beat the validation leader while preserving recall. No test-set run or
default promotion was performed. The cross-encoder adds useful ordering evidence to the complete
pool, improving pooled nDCG by `0.016035`, but equal five-way rank fusion is still weaker than the
focused BM25/token-window baseline.

## Candidate diagnostics

Both pooled strategies use the same candidate generators.

- Maximum candidate pool: 200 documents.
- Mean deduplicated pool: 105.96875 documents.
- Candidate recall: 0.906250.
- Queries with at least one relevant candidate: 0.912500.
- Oracle nDCG@10 from the existing pool: 0.907664.

| Generator top 50 | Candidate recall | Query hit rate |
|---|---:|---:|
| Token windows | 0.865625 | 0.868750 |
| Strict coreference | 0.862500 | 0.868750 |
| Nominal coreference | 0.853125 | 0.856250 |
| BM25 | 0.837500 | 0.843750 |

The `0.208008` gap between pooled MS MARCO nDCG and candidate oracle nDCG is direct evidence that
ranking the retrieved pool is a larger immediate opportunity than adding more candidate volume.
It does not prove a graph will close the gap, but it gives a proposition-graph scorer a clear,
measurable second-pass role.

## Architecture result

Generation records source rank, score, representation, matched text, and passage ordinal.
Corpus-global BM25 and every dense channel then score every pooled document exactly once. The final
aggregator uses only complete rescored ranks, so generation provenance cannot double-weight BM25 or
another source. A future graph scorer can add one complete provenance-bearing channel through the
same port.

See ADR-0020 and `docs/architecture/retrieval-projection-crosswalk.md`. Graph extraction, graph
storage, graph scoring, graph retrieval, and contextual-sentence embeddings remain unimplemented.
