# Listwise reranking and published-ColBERT protocol assessment

## 1. Decision and scope

Assess a maintained open listwise reranker behind the existing complete candidate-scorer port and
explain how this project's ColBERT results compare with the published SciFact number. The bounded
RankZephyr integration was implemented, but the effectiveness run is deferred after measured
throughput and the owner's model-provenance preference. Training, scorer fusion, a parameter sweep,
and a full-corpus ColBERT index are out of scope.

## 2. Search date, queries, and source rules

- Search date: 2026-08-27.
- Queries covered current RankLLM HTTP serving, RankZephyr vLLM support, listwise window/stride
  defaults, immutable model revisions, license, and the AnswerAI SciFact result and indexing
  protocol.
- Only canonical repositories, original papers, official model cards, and current runtime source
  were admitted for implementation claims. Search-result summaries and marketing claims were not
  treated as executable contracts.

## 3. Project constraints and comparison dimensions

The solution must run in Docker Compose on one ARM64 DGX Spark, remain opt-in, preserve the frozen
six-generator pool, score every candidate exactly once, add no dependency to the application
image, and avoid test-qrels tuning. Candidates were compared on listwise fitness, maintenance,
license, immutable provenance, ARM64/vLLM feasibility, memory, integration size, operating cost,
first-stage-order sensitivity, and evidence quality.

## 4. Candidate comparison

| Candidate | Primary source | License / evidence | Decision |
|---|---|---|---|
| RankZephyr 7B V1 Full | [model card](https://huggingface.co/castorini/rank_zephyr_7b_v1_full), [paper](https://arxiv.org/abs/2312.02724) | MIT checkpoint; 7B BF16 listwise model; intended for RankLLM | Integration retained; practical use deferred for runtime and distilled-frontier provenance |
| RankLLM | [canonical repository](https://github.com/castorini/rank_llm), [pinned tree](https://github.com/castorini/rank_llm/tree/8ad18be76c90aa97ffae50b84dbc326bedc724fd) | Apache-2.0; current HTTP API and vLLM OpenAI-SDK coordinator | Adopt protocol/runtime at pinned commit |
| RankVicuna | [RankLLM repository](https://github.com/castorini/rank_llm) | Supported older open listwise family | Defer; no advantage over the selected RankZephyr baseline for this slice |
| LiT5 Distill | [RankLLM repository](https://github.com/castorini/rank_llm) | Supported listwise encoder-decoder family with a different serving/runtime profile | Defer as a later architecture comparator |
| Bespoke prompt parser and listwise runtime | No maintained source | Would own prompt construction, permutation parsing, retries, and window aggregation | Reject as duplicate implementation |
| Full-corpus AnswerAI ColBERT index | [official model card](https://huggingface.co/answerdotai/answerai-colbert-small-v1) | Apache-2.0; published SciFact nDCG@10 0.7477 | Defer to a separate reproduction protocol |

## 5. License and provenance

RankLLM is Apache-2.0 at commit `8ad18be76c90aa97ffae50b84dbc326bedc724fd`, committed
2026-08-24. RankZephyr's model card declares MIT; Compose downloads exact revision
`aa11d9da444ec3490827656c3b961d5c5f3af0eb`. The NVIDIA vLLM image remains pinned to digest
`sha256:bebcf9576b1720214319ee5c7ee4f7661954cbbf59ed3fcd188cd79a67f1967e` and retains its
separate NVIDIA terms. No upstream source is copied into the MIT application.

## 6. Evidence-backed findings

RankZephyr is a zero-shot listwise reranker: RankLLM constructs a prompt containing the query and
a window of candidate passages, the model emits a permutation of candidate identifiers, and
RankLLM applies overlapping windows to produce a complete order. The selected upstream defaults
are a 20-passage window and stride 10. `variable_passages` lets the final short window contain its
actual number of candidates. Greedy decoding is enforced by current RankLLM source.

RankLLM's HTTP endpoint accepts a query plus candidates and returns a `castorini.cli.v1` envelope
whose `rerank-results` artifact contains candidates in final listwise order. Numeric scores in the
returned candidates are not the authoritative ranking contract; the application converts list
positions to strictly descending ordinal scores only to pass through its existing scalar scorer
port.

The selected RankLLM commit has an upstream CLI integration defect: `serve http` supplies
`use_litellm` to a `ServerConfig` that lacks that field. Its canonical FastAPI factory and runtime
work when constructed directly. This project therefore adapts the factory rather than patching
upstream ranking code or changing revisions after selection.

The AnswerAI model card's SciFact 0.7477 is a full-corpus BEIR retrieval result produced with the
model's ColBERT indexing/search stack. The first local 0.734958 result was a second-stage score over
a deduplicated candidate pool on a deterministic 160-query partition of public train qrels. The
later owner-authorized run over all 300 BEIR test queries reached 0.744417 over the title-separated
six-generator pool, 0.003283 below the published score. The pool reached candidate recall 0.950333
and oracle nDCG 0.951169. The project serves the checkpoint through vLLM `HF_ColBERT`; parity with
the model card's query markers, query augmentation, token masking, and indexing implementation has
not been established. The near-equality is encouraging directional evidence, not a reproduction.

The local ColBERT service right-truncates title-plus-abstract inputs at 512 tokens. Exact corpus
measurement shows 455 of 5,183 documents exceed the 510-content-token allowance, so tail evidence
can be lost. A full-corpus reproduction would need the official document/query encoder semantics,
an index over all documents, the 300-query BEIR test protocol, and retained per-query rankings.

## 7. Build, adopt, adapt, and defer options

- Build: reject a bespoke listwise server/parser because RankLLM already owns that behavior.
- Adopt: the implemented spike uses the RankZephyr checkpoint and RankLLM HTTP/result contract
  unchanged.
- Adapt: split serving into a memory-bounded vLLM model service and lightweight RankLLM
  coordinator, then strictly translate candidate identities/order into the existing scorer port.
- Defer: RankZephyr effectiveness evaluation and practical use, RankVicuna, LiT5, scorer fusion,
  training, and full-corpus ColBERT reproduction remain separate decisions.

## 8. Recommendation and confidence

Do not use RankZephyr on the practical path. A live bounded probe observed roughly seven seconds
per sequential 20-document window and about eleven windows per query, projecting roughly 3.4 hours
for 160 queries. The owner also prefers not to rely on its distilled-frontier-model approach. Keep
the opt-in integration as reproducible experimental evidence, with its services stopped, and use
the much faster AnswerAI ColBERT scorer as the practical leader. ColBERT processed 300 test queries
over a 137.69-document mean pool in 165.07 seconds and reached nDCG 0.744417.

## 9. Unknowns and verification spike

- Whether RankZephyr would improve SciFact is intentionally unmeasured because its cost and model
  lineage failed the practical selection criteria.
- Whether RankLLM's 300-word passage cap removes important conclusion text.
- How much candidate order affects this exact six-generator pool.
- Whether vLLM OpenAI-SDK generation exactly matches RankLLM's local-vLLM path.

The bounded spike verified one obvious relevance order, model/tokenizer identity, a complete
candidate permutation, and live throughput. It deliberately stopped before an effectiveness run
and does not vary these unknowns.

## 10. Trigger, stop condition, and disposition

- Trigger: a 0.191456 gap between expanded-pool oracle nDCG 0.926414 and ColBERT nDCG 0.734958.
- Stop condition reached: the pinned service and strict adapter worked, but bounded throughput
  projected about 3.4 hours for 160 queries.
- Disposition: **defer RankZephyr effectiveness evaluation and practical use**; retain the
  integration without recommending it.

## 11. Reopen conditions

Reopen research if implementation requires a different model, revision, prompt, passage window,
stride, candidate depth/order, more than one pass, a new parser, a different server protocol, or
materially more memory; if repair would patch RankLLM internals; or if full-corpus ColBERT
reproduction becomes the accepted objective.

## 12. Reopened-assessment lineage

The current engineering loop's revision-2 assessment was reopened when direct inspection showed
that RankLLM's local vLLM path hardcodes a 0.90 memory fraction. Revision 3 supersedes that stale
candidate design with a separate 0.20-memory vLLM service plus HTTP coordinator. The prior
assessment remains in loop history; no blocked assessment was deleted.
