# ADR-0025: Independent neural reranking of the expanded coreference-interval pool

Date: 2026-08-26

Status: accepted experiment; no default promotion

## Context

ADR-0024 showed that adding global coreference-interval packing to the existing BM25,
token-window, proper-noun coreference, and nominal-coreference generators raises validation
candidate recall from 0.906250 to 0.925000 and oracle nDCG from 0.907664 to 0.926414. Equal
five-channel RRF did not exploit that higher ceiling. The project already has two fixed hosted
neural scorers: the MS MARCO cross-encoder from ADR-0018 and the ColBERT late-interaction scorer
from ADR-0022.

The owner selected a bounded comparison of those scorers independently over the latest pool. A
combined MS MARCO-ColBERT fusion, model change, parameter sweep, test-qrels run, and default change
remain outside this decision.

## Decision

- Add `pooled-coref-interval-msmarco` and `pooled-coref-interval-colbert` as opt-in strategies.
- Generate top-50 candidates independently from BM25, token windows, proper-noun coreference,
  nominal coreference, and global coreference-interval packing, then deduplicate by document ID.
- Score every pooled candidate exactly once with only the strategy's named existing scorer. The
  single-scorer rank policy is monotonic with that scorer and mixes no retrieval score or second
  neural score into the order.
- Reuse the pinned TEI MS MARCO and vLLM ColBERT services, model revisions, raw query and raw
  title-plus-abstract inputs, and their existing 512-token behavior unchanged.
- Run exactly one 160-query `train-validation` diagnostic per strategy at cutoff 10. Keep
  `token-window` as the default and do not access public test qrels.

## Consequences

The comparison isolates whether broader generation helps either existing scorer. It adds two CLI
strategy names and composition wiring but no dependency, database schema, representation,
service, model, fusion policy, or parameter.

The expanded pool averages 114.1125 candidates, reaches candidate recall 0.925000, query-hit rate
0.931250, and oracle nDCG 0.926414.

| Scorer over expanded pool | nDCG@10 | MAP@10 | Recall@10 | Precision@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| MS MARCO | 0.701572 | 0.668323 | 0.790625 | 0.090625 | 0.677733 |
| ColBERT | **0.734958** | **0.707396** | **0.800000** | **0.091875** | **0.722569** |

The prior validation MS MARCO result combined BM25, three dense scores, and MS MARCO through RRF;
its nDCG 0.699656 and recall 0.803125 are context, not a controlled pool-only comparator for this
single-scorer strategy. ColBERT's top-10 metrics are identical to its previous four-generator run,
showing no change at the aggregate effectiveness boundary; per-query top-ten identities were not
retained. ColBERT remains the validation ranking leader, but its recall remains below the
BM25-plus-token-window guardrail of 0.809375. Neither strategy is promoted.

## Alternatives

| Alternative | Reason not selected |
|---|---|
| Combine MS MARCO and ColBERT | The owner selected independent attribution first; fusion adds another policy decision |
| Add both to robust normalized fusion | Changes the accepted comparison and assumes equal contribution |
| Increase candidate depth | Confounds generator breadth with depth and adds a parameter choice |
| Run test qrels | The validation recall guardrail is not met |

## Verification and revisit trigger

Focused tests must cover interval-pool mapping, exact single-scorer selection, unchanged existing
strategies, and the repository gate. Live evidence must bind the healthy pinned services and the
two frozen diagnostics. Independent review must confirm exact metrics, scope, and absence of a
combined fusion or default change.

Revisit only with a separately accepted fusion design, a protected training/validation protocol,
a model/runtime revision, or evidence that a different generator supplies candidates either
scorer can rank into the top ten.
