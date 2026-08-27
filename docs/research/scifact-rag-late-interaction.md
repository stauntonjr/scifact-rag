# Hosted late-interaction scoring solution assessment

- Search date: 2026-08-26
- Decision: adapt a pinned AnswerAI ColBERT checkpoint behind the existing pooled scorer port
- Disposition: adapt
- Trigger: the complete candidate pool has validation recall 0.906250 but prior rankers leave a
  large gap to oracle nDCG 0.907664
- Stop condition: one model, one scorer-only strategy, and one frozen 160-query validation result

## Need and constraints

The experiment needs a genuinely new second-pass scorer rather than another normalization or
fusion sweep. It must reuse the existing BM25, token-window, strict-coreference, and
nominal-coreference candidate pool, run on one DGX Spark, avoid a new database index, and remain an
opt-in strategy. The application dependency graph must not be upgraded merely to obtain
late-interaction inference.

Primary sources were selected from the original ColBERT project, official model cards, and
maintainer documentation for vLLM, Sentence Transformers, TEI, and Infinity. Search queries covered
ColBERT MaxSim serving, DGX-compatible ARM64 images, immutable model revisions, licenses, token
limits, and native rerank APIs. Comparison dimensions were retrieval fit, SciFact evidence,
license, model size, DGX compatibility, integration effort, truncation behavior, and maintenance.

## Existing solutions compared

| Candidate | Primary evidence | License / runtime | Disposition |
|---|---|---|---|
| `answerdotai/answerai-colbert-small-v1` | Official model card reports 33.4M parameters, 96-dimensional token vectors, 512-token document examples, and SciFact nDCG@10 0.7477 | Apache-2.0 | Adopt checkpoint |
| `colbert-ir/colbertv2.0` | Canonical ColBERT implementation and model family | MIT implementation; larger BERT-base model; model-card comparison reports SciFact 0.693 | Defer as a larger, weaker published SciFact baseline |
| vLLM native ColBERT scoring | Official pooling documentation supports `HF_ColBERT`, MaxSim, `/score`, and `/rerank`; the cached NVIDIA 26.06 image is ARM64 | vLLM Apache-2.0; NVIDIA container terms remain separate | Adapt serving path |
| Sentence Transformers 6 `MultiVectorEncoder` | Official v6 documentation loads the selected checkpoint and implements token projection, masking, normalization, and MaxSim | Apache-2.0; requires Transformers 5 and a main-application dependency upgrade | Defer to avoid an unrelated dependency migration |
| Hugging Face TEI `/embed_all` | Official API returns unpooled token embeddings | Apache-2.0; no documented native loading of this checkpoint's ColBERT projection and query expansion | Defer |
| Infinity ColBERT embeddings | Canonical repository lists the selected model as tested | MIT; native ColBERT reranking remains an open feature request | Defer |
| Bespoke MaxSim server | Technically possible | New server, batching, tokenization, projection, and error-contract ownership | Reject |

## Adaptation boundary

Compose pins `nvcr.io/nvidia/vllm:26.06-py3` to digest
`sha256:bebcf9576b1720214319ee5c7ee4f7661954cbbf59ed3fcd188cd79a67f1967e`
and pins `answerdotai/answerai-colbert-small-v1` to revision
`c72aa89bc61afdd85373643f3a1a75b2aad6e0fe`. The live image reports vLLM 0.22.1,
resolves the checkpoint as `HF_ColBERT`, downcasts it to float16, exposes MaxSim through
`/rerank`, and reports a 512-token maximum.

`pooled-colbert` reuses the four existing top-50 generators and their unchanged deduplicated pool.
The raw query and raw title plus newline plus abstract are sent to vLLM. The adapter explicitly
requests right truncation at 512 tokens. ColBERT alone defines order; the existing one-channel RRF
policy is a monotonic rank representation and adds no retrieval score, weight, or second scorer.

There is no corpus-wide ColBERT index, stored token matrix, model training, fusion, model sweep,
query rewrite, test-qrels run, or default promotion.

## MiniLM and abstract-length evidence

The local, checksum-verified SciFact corpus contains 5,183 documents. Lengths were measured with
the exact cached `paraphrase-MiniLM-L6-v2` WordPiece tokenizer, without truncation.

| Input | Mean | p25 | Median | p75 | p90 | p95 | p99 | Maximum |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Abstract only | 313.65 | 224 | 293 | 384.5 | 472 | 539 | 733.9 | 1,921 |
| Title plus abstract | 335.19 | 242.5 | 314 | 408 | 500 | 565.9 | 758.7 | 1,937 |

Sentence Transformers constrains MiniLM to 128 total tokens, leaving 126 content tokens after two
special tokens. Abstract-only input exceeds 126 tokens for 5,004 documents (96.55%); title plus
abstract exceeds it for 5,073 documents (97.88%). This confirms that the original whole-document
MiniLM baseline discarded most abstracts and explains why overlapping windows helped.

ColBERT's 512-token boundary covers much more: 4,728 title-plus-abstract inputs (91.22%) fit within
510 content tokens, while 455 (8.78%) may lose tail content under explicit right truncation.

## Frozen validation result

On the deterministic 160-query validation partition, the one completed `pooled-colbert` run
reported nDCG@10 0.734958, MAP@10 0.707396, recall@10 0.800000, precision@10 0.091875, and MRR@10
0.722569. The pool remained unchanged at mean size 105.96875, recall 0.906250, and oracle nDCG
0.907664.

This is the best validation nDCG, MAP, and MRR recorded in the project, but recall is 0.009375 below
the BM25-plus-token-window guardrail. The result therefore retains the strategy without promoting
it or opening the test split.

## Semantic chunking follow-on result

ADR-0023 completed the separately scoped MiniLM representation comparison. `sentence-pack`
preserves sentence boundaries and packs toward 112 content tokens under a hard 126-token limit.
`coref-aware-pack` uses original mention offsets to continue across a soft boundary crossed by a
strict proper-noun coreference chain, then canonicalizes after grouping. No embedding-similarity
threshold was introduced.

On the same 160-query validation partition, sentence packing reached nDCG@10 0.622347 and recall
0.737500; coreference-aware packing reached nDCG 0.624108 and recall 0.751563. The latter gained
0.014063 recall and 0.001761 nDCG, while MAP and MRR declined. Neither approaches the retained
BM25-plus-token-window or ColBERT leaders, so the result does not justify promotion, fusion, a
parameter sweep, or test-qrels confirmation.

ColBERT chunk scoring remains undecided. If revisited, it must separately fix whether to score the
best chunk or all chunks with document-level max aggregation; the MiniLM result does not authorize
that expansion.

## Unknowns and reopen triggers

- Published model-card metrics are external evidence, not a reproduction of this project's pooled
  protocol.
- Right truncation may disproportionately remove conclusions from the longest abstracts.
- The strategy improves rank-sensitive metrics but lowers top-10 recall; error analysis should
  precede fusion or default changes.
- Reopen the decision if vLLM/model revisions change, semantic chunks require a different scorer
  contract, or GPU resource contention requires stopping the generator.

## Primary sources

- vLLM ColBERT and MaxSim serving:
  <https://docs.vllm.ai/en/v0.22.0/models/pooling_models/token_embed/>
- vLLM scoring APIs:
  <https://docs.vllm.ai/en/latest/models/pooling_models/scoring/>
- Selected model card and Apache-2.0 license:
  <https://huggingface.co/answerdotai/answerai-colbert-small-v1>
- Immutable selected model tree:
  <https://huggingface.co/answerdotai/answerai-colbert-small-v1/tree/c72aa89bc61afdd85373643f3a1a75b2aad6e0fe>
- Sentence Transformers multi-vector support:
  <https://github.com/huggingface/blog/blob/main/multi-vector-encoder.md>
- TEI API and supported model families:
  <https://github.com/huggingface/text-embeddings-inference>
- Infinity ColBERT support and boundary:
  <https://github.com/michaelfeil/infinity>
- Infinity native-rerank feature request:
  <https://github.com/michaelfeil/infinity/issues/503>
- Canonical ColBERT implementation and MIT license:
  <https://github.com/stanford-futuredata/ColBERT>
