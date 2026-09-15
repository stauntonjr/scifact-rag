# Phase 3 scientific-inference validation

- Date: 2026-09-15
- Governing issue: [#8](https://github.com/stauntonjr/scifact-rag/issues/8)
- Governing decision: [ADR-0030](../adr/0030-scientific-inference-scoring.md)
- Evidence class: internal diagnostic on the frozen 160-claim `train-validation` split
- Reviewed implementation commit: `f73aa368043ce12e92501642d936becedc55b2a0`

## Result

The fixed run completed every one of 21,711 broad-pool candidates with zero assembly or request
failures and zero outcome-unknown attempts. The journal contains exactly one durable attempt-start
and one terminal result per candidate. Citation provenance validation passed for every completed
bundle.

The unchanged retrieval control reproduced nDCG@10 `0.742493`, MAP@10 `0.716753`, recall@10
`0.806250`, precision@10 `0.092500`, and MRR@10 `0.728472` across all 160 claims. This confirms that
the diagnostic did not alter retrieval order.

| Diagnostic | Result |
|---|---:|
| Three-way accuracy | 0.798904 |
| Three-way macro-F1 | 0.324781 |
| Neutral-prior accuracy | 0.994473 |
| Neutral-prior macro-F1 | 0.332410 |
| Evidence-sentence recall | 0.899522 (188/209) |
| Annotated candidate documents with admitted evidence | 201/202 |
| Median inference latency | 57.87 ms |
| Maximum inference latency | 226.29 ms |
| ColBERT/evidence-margin Spearman | -0.040955 |
| ColBERT/polarity-margin Spearman | 0.180858 |

The class result is highly imbalanced because almost every broad-pool candidate is not a cited
document: 21,591 neutral, 77 entailment, and 43 contradiction labels. DeBERTa recalled 48.05% of
entailment and 76.74% of contradiction candidates, but precision was only 3.60% and 0.98%,
respectively. It incorrectly labeled 987 neutral candidates as entailment and 3,329 as
contradiction. The resulting macro-F1 is below the neutral-prior control.

## Decision

The architecture and evidence corpus are retained, but the fixed DeBERTa margins are not promoted
into retrieval fusion or generation. The near-zero correlation between ColBERT relevance and the
evidence margin shows that the channel is not merely duplicating ColBERT, but the poor rare-class
precision means this run does not establish useful incremental ranking signal. No threshold,
weight, calibration, model comparison, test-set confirmation, or label-trained adjustment is
authorized from this result.

The 4,366-row failure-review corpus is retained for the already-declared scientific phenomena:
synonymy, polarity, negation, qualifiers, association versus causation, evidence domain, and
cross-sentence inference. Any later intervention requires a separate fixed hypothesis. Phase 4
proposition-graph work remains separately governed.

## Retained local evidence

The large raw artifacts remain ignored from Git and are retained locally under
`artifacts/scientific-inference-validation-v1/`.

| Artifact | Rows | SHA-256 |
|---|---:|---|
| `manifest.json` | 1 | `121b7ce11a21a5fdfa7cf4f586c02f35015806f47ddc118fea912189092afcc5` |
| `results.jsonl` | 43,422 events | `40701fa9c161662c017602b0ac405e92c0212c0811eea4f4ccad7dbbb6a74b0e` |
| `results.report.json` | 1 | `f43c2df4168229ef9e05c73387d43de0d22047886789da5675b7023f6bac3a68` |
| `results.failures.jsonl` | 4,366 review rows | `599d6c7cd83e8ed3aa945033d36feea7031c5256f8b6121ab90bc5aaa1aed963` |

The manifest records the exact application, PostgreSQL, and inference image IDs; pinned ColBERT
and DeBERTa model/tokenizer revisions; Transformers 5.6.0; the reviewed repository commit; and the
canonical evaluation-set digest.
