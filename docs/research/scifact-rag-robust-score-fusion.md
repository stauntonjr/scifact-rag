# Robust normalized score-fusion evaluation

- Date: 2026-08-26
- Strategy: `pooled-four-channel-robust-sum`
- Primary metric: nDCG@10
- Guardrail: recall@10 must not regress from the frozen validation leader
- Search budget: one fixed strategy, one 160-query validation run, no sweep

## Architecture boundary

The existing four candidate generators and complete corpus-global scorers are unchanged. Each
query produces an immutable feature matrix with one row per candidate and one provenance-bearing
raw feature per BM25, token-window, strict-coreference, and nominal-coreference scorer. Generation
ranks remain diagnostic only.

Each channel is normalized independently across the query's candidate pool. Nonconstant channels
with positive median absolute deviation use scaled robust z-scores followed by a logistic function.
Constant channels map to `0.5`; nonconstant zero-MAD channels use a tied-midrank empirical CDF.
The final score is the unweighted mean of all four normalized features. It is not a relevance
probability.

## Frozen validation result

| Strategy | nDCG@10 | MAP@10 | Recall@10 | Precision@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| BM25 plus token-window RRF | **0.707033** | **0.670174** | **0.809375** | 0.092500 | **0.681111** |
| Four-channel robust normalized mean | 0.688954 | 0.645051 | 0.806250 | 0.092500 | 0.661119 |
| Four-channel equal RRF | 0.683622 | 0.638278 | 0.806250 | 0.092500 | 0.657341 |

The robust policy improves pooled nDCG by `0.005333`, MAP by `0.006773`, and MRR by `0.003777`
without changing recall. It still trails the validation leader by `0.018079` nDCG and `0.003125`
recall, so it is not promoted and no test-qrels run occurred.

The candidate pool is unchanged: mean size `105.96875`, recall `0.906250`, query-hit rate
`0.912500`, and oracle nDCG@10 `0.907664`. Robust normalization recovers a small amount of score
spacing information but does not close the ranking gap. This supports keeping the generic feature
architecture while moving the next product experiment to a genuinely new scorer rather than a
normalization sweep.

## Reproduction

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
DATABASE_URL=postgresql+psycopg://scifact:scifact-local@127.0.0.1:5432/scifact \
python -m scifact_rag.cli diagnose-candidates \
  --strategy pooled-four-channel-robust-sum \
  --split train-validation --cutoff 10
```

The run used the already healthy loopback PostgreSQL service and locally cached MiniLM model. It
did not call the TEI reranker, mutate the corpus, restart a service, or access the test qrels.
