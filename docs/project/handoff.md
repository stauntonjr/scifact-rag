# Project handoff

## Current objective

The governing delivery sequence is `docs/project/roadmap.md`. The automatic generation-context
comparison and the fixed retrieval-default comparison are complete. Phase 1 still has its frozen
human review outstanding, while ADR-0029's retrieval-default recommendation awaits a separate
owner-authorized implementation. Scientific inference is the next architecture phase; graph,
adapters, and template evaluation remain downstream.

Deliver the first working CLI-first SciFact RAG vertical slice on one DGX Spark:

```text
BEIR SciFact -> MiniLM -> PostgreSQL/pgvector -> retrieved evidence
                                                    |
                                                    v
                               Qwen NVFP4 -> cited answer or insufficient evidence
```

The same dataclass application layer is the future composition root for HTTP, MCP, and a small web
UI, but only CLI is active now.

## Accepted decisions

- Python 3.12, frozen dataclasses, Typer, SQLAlchemy Core, psycopg, and explicit constructor wiring.
- Docker Compose owns PostgreSQL and the application image.
- SparkRun/vLLM remains an external OpenAI-compatible host service; this project never manages its
  lifecycle implicitly.
- Embeddings use `sentence-transformers/paraphrase-MiniLM-L6-v2` with `vector(384)`. Documents are
  represented by one dedicated title vector plus overlapping abstract-only 126-token windows with
  32-token overlap; fixed equal RRF between those two channels is the default. The best score in
  each channel is aggregated back to one document. Experimental strict proper-noun, broader
  nominal, and max-fused coreference-sentence strategies are independently selectable and exclude
  the title.
- PostgreSQL-native keyword, VectorChord-BM25, strict-dense-plus-keyword RRF, and seven fixed
  BM25-plus-vector RRF pairings are selectable experiments. None replaces the default.
- A pinned MS MARCO cross-encoder over the fixed pooled candidate union is a separately
  hosted TEI GPU experiment. It does not replace the default.
- Feature-preserving pooled ranking retains generation and matching-passage provenance, completely
  rescores the pool through each configured channel, and applies fixed equal RRF without counting
  generation ranks twice. Graph scoring can enter through the same scorer boundary later.
- Pooled scorer output now materializes as a complete immutable candidate feature matrix. Separate
  normalizer and setwise ranking-policy ports support existing RRF and one opt-in four-channel
  robust normalized mean; bounded normalized values are not relevance probabilities.
- A pinned AnswerAI ColBERT model is an opt-in complete scorer over the same pooled candidates.
  Native vLLM MaxSim alone defines its order; explicit 512-token right truncation is reported.
- The long-document ColBERT path is separately opt-in as `pooled-coref-nominal-dp-colbert`. One
  nominal-policy analysis derives rewritten sentence candidates plus raw 112/126 MiniLM-DP and raw
  510-token ColBERT-DP profiles. Exactly four generators form the pool; ColBERT separately scores
  titles and all large raw content views, keeps the content maximum, then equal-means the two
  robust-normalized channels. It does not change the default.
- `pooled-coref-interval-multiview-colbert` is a fixed-pool ablation: it applies the same multiview
  scorer, normalizer, and equal-mean policy to the existing six-generator interval pool. It reuses
  stored representations, adds no scoring algorithm or parameter, and remains opt-in.
- `pooled-coref-interval-content-max-colbert` and
  `pooled-coref-interval-raw-mean-colbert` are fixed-pool component ablations. The first ranks only
  max content; the second takes the equal mean of unscaled title and max-content scores through the
  generic identity normalizer. Both remain opt-in and leave existing strategies unchanged.
- ADR-0029 recommends `pooled-coref-interval-content-max-colbert` as the
  retrieval-effectiveness default after a fixed 160-query comparison, and retains
  `bm25-token-window-rrf` as the fast/no-ColBERT alternative. The runtime still defaults to
  `title-token-window-rrf`; applying the recommendation requires separate owner authorization.
- MS MARCO, ColBERT, and pinned RankZephyr/RankLLM scorers are independently selectable over the
  latest six-generator global coreference-interval pool: BM25, title, token windows, proper-noun
  coreference, nominal coreference, and interval packing. They do not combine scorer outputs or
  change candidate depth. ColBERT is the practical leader; RankZephyr is retained only as a
  deferred opt-in experiment.
- Deterministic sentence packing, greedy proper-noun coreference-aware packing, and global
  equal-cost coreference-interval packing are opt-in MiniLM representations with a 112-token target
  and absolute 126-token content limit. Titles stay separate, original offsets define boundaries,
  and all abstract-derived packers exclude the title. Each packer also has fixed BM25 fusion and a separate
  one-at-a-time incremental pool strategy.
- Generation uses `nvidia/Qwen3.6-35B-A3B-NVFP4` without tool calls.
- Generation context is an application port with two distinct policies. `whole-document` remains
  the compatibility default; `adaptive` keeps exact one-view abstracts whole and ColBERT-selects at
  most two raw DP chunks for longer parents. The accepted legacy name `top-dp-chunks` is now an
  exact alias for `adaptive`, not a third evaluation arm. The corrected 160-claim automatic
  comparison is retained; its blinded human groundedness review remains pending.
- BEIR SciFact qrels evaluate retrieval. The original SciFact hidden test labels are not claimed.
- `application-composition-root`, `cli-interface`, and the bounded
  `product-validation-challenges` corpus are active in `harness/capabilities.json`.

See `docs/adr/0013-scifact-rag-composition-and-runtime.md`,
`docs/adr/0015-modular-coreference-retrieval.md`,
`docs/adr/0017-vectorchord-bm25.md`, and
`docs/adr/0018-msmarco-cross-encoder-reranking.md`.
`docs/adr/0020-pooled-ranking-and-projection-alignment.md` records the separate SciFact application
and Procurement semantic-platform direction; no cross-repository dependency exists.
`docs/adr/0021-generic-feature-ranking-and-robust-score-fusion.md` records the generic feature
matrix and fixed robust normalization contract.
`docs/adr/0022-hosted-colbert-late-interaction-scoring.md` records the hosted late-interaction
experiment and its no-promotion result.
`docs/adr/0023-coreference-aware-semantic-chunking.md` records the fixed semantic-chunk comparison
and its no-promotion result.
`docs/adr/0024-global-coreference-interval-packing.md` records the global optimizer, equal chain
cost, incremental pool comparisons, and idempotent document/BM25 persistence repair.
`docs/adr/0025-expanded-coreference-interval-pool-rerankers.md` records the independent fixed-scorer
comparison over that latest pool.
`docs/adr/0026-title-separated-pooling-and-listwise-reranking.md` records the dedicated title
channel, fixed title-plus-token default, six-generator pool, completed practical scorer comparison,
and RankZephyr deferral.
`docs/adr/0027-dual-dp-multiview-colbert.md` records raw dual-profile boundaries,
exact ColBERT tokenizer revision, four-generator ownership, and title/max-content score fusion.
`docs/adr/0028-generation-context-assembly.md` records the whole-document control, canonical
adaptive DP selection, legacy `top-dp-chunks` alias, and parent-document citation boundary.
`docs/adr/0029-retrieval-default-selection.md` records the content-max ColBERT recommendation, BM25
fallback, operational tradeoff, and unchanged-runtime boundary.

## Live environment observed 2026-08-27

- Host architecture: AArch64 DGX Spark.
- With explicit operator approval, SparkRun job `8337765ded59` serving
  `Intel/Qwen3-Coder-Next-int4-AutoRound` was stopped to release port 8000 and unified memory.
- SparkRun 0.2.40 now runs `nvidia/Qwen3.6-35B-A3B-NVFP4` as a TP1 host-network vLLM service at
  port 8000 with a 32,768-token context limit. Its estimate was 21.82 GB of weights plus 1.25 GB
  of KV cache.
- Compose now also runs the much smaller MS MARCO reranker on the DGX GPU at loopback port 8081
  through the digest-pinned Hugging Face TEI `sm_121` ARM64 image. The live logs show the exact
  model revision loaded as `FlashBert` on CUDA with a 512-token boundary; the service is healthy.
- Compose runs `answerdotai/answerai-colbert-small-v1` at immutable revision
  `c72aa89bc61afdd85373643f3a1a75b2aad6e0fe` on loopback port 8082 through the cached,
  digest-pinned NVIDIA vLLM 26.06 ARM64 image. Live logs report vLLM 0.22.1, `HF_ColBERT`,
  float16 CUDA inference, a 512-token boundary, and healthy `/rerank` MaxSim service.
- Compose can run `castorini/rank_zephyr_7b_v1_full` at immutable revision
  `aa11d9da444ec3490827656c3b961d5c5f3af0eb` in the same digest-pinned vLLM image on loopback
  port 8084. Live logs report vLLM 0.22.1, `MistralForCausalLM`, BF16, an 8,192-token model limit,
  a 0.20 memory ceiling, 13.5 GiB loaded weights, and healthy service state. The model is now
  stopped after measured throughput projected about 3.4 hours for 160 queries.
- A separate RankLLM coordinator built from Apache-2.0 commit
  `8ad18be76c90aa97ffae50b84dbc326bedc724fd` was verified on loopback port 8083. A bounded live
  request ranked the aspirin passage first and returned a complete `castorini.cli.v1` envelope.
  The pinned CLI's broken `serve http` constructor is bypassed through its own FastAPI factory;
  upstream ranking and prompt code remain unchanged. The coordinator is stopped with the deferred
  model.
- The default `@eugr/qwen3.6-35b-a3b-nvfp4` recipe failed because its generated
  `--speculative-config` value retained doubled JSON braces. The official
  `@eugr/qwen3.6-35b-a3b-nvfp4-no-mtp` recipe serves the same checkpoint successfully; MTP is an
  optional decoding optimization and is not part of the RAG contract.

## Implementation state

- Generated project intake is sufficient for bounded planning.
- Phase 0 Issue #3 governs generation-evaluation reproducibility. The versioned
  `generation-run-manifest/v1` contract and `generation-eval-dry-run` CLI command validate a
  complete run boundary without constructing the application or calling PostgreSQL, ColBERT, or
  Qwen. Default-selection manifests cannot name the already-inspected test split.
- Phase 1 Issue #4 adds the fixed input builder. It joins all 809 BEIR training claims and qrels to
  the official SciFact sentence arrays, preserves exact SUPPORT/CONTRADICT rationales, and declares
  empty official evidence as NOT_ENOUGH_INFO. The reproduced validation input contains 160 cases
  and has SHA-256 `34084490c48515f0c788da0960d7f426c0e64e4dcf9431b8721d824ba0349105`.
- Issue #6 completed its one frozen retrieval comparison with 480/480 successful rows and no empty
  rankings. DP content-max ColBERT reached nDCG@10 0.742493, recall@10 0.806250, and 638.94 ms
  median latency; BM25 plus token windows reached 0.673519, 0.787500, and 78.70 ms. The result is
  internal comparative evidence because the validation split was already inspected.
- Local scaffold baseline: `703c8e5`.
- Dataclass domain/ports, application services, SciFact/MiniLM/Postgres/generator adapters, Typer
  CLI, Docker Compose, dependency contract, ADR, research note, and focused tests are authored.
- Retrieval representation is now an application port. FastCoref is lazy-loaded only by
  coreference ingestion; titles and policy-specific sentences coexist with token windows in a
  strategy-aware PostgreSQL table. The dependency lock resolves 122 packages.
- The official checksum-verified corpus contains 5,183 documents and 19,283 token windows. All were
  ingested. Actual pgvector evaluation over 300 BEIR test queries at cutoff 10 reports nDCG
  0.601929, MAP 0.556945, recall 0.727944, precision 0.081000, and MRR 0.568218. The original
  one-vector baseline was nDCG 0.526066 and recall 0.661722.
- Twelve public-qrels baseline misses rescued by windowing form the active product challenge set;
  all twelve pass through the Compose application and updated database.
- Full 300-query evaluations place strict proper-noun resolution first at nDCG 0.618163 and recall
  0.779500. Nominal resolution is close at 0.617592 and 0.773944. Max fusion regresses to 0.613820
  and 0.772833, so no strategy is automatically promoted. The internal leaderboard records all
  metrics and row counts.
- Keyword-only retrieval reports nDCG 0.404084 and recall 0.531667, rescuing 13 of strict dense's 62
  zero-hit queries. Symmetric top-50 RRF with `k=60` reports nDCG 0.608786 and recall 0.749222; it
  rescues 16 strict misses but loses 24 prior hit queries. Both remain experimental. Do not tune
  fusion on the public test qrels.
- The PostgreSQL service now uses a pinned multi-stage image that retains PostgreSQL 17 and
  pgvector 0.8.6 while copying only pg_tokenizer 0.1.1 and VectorChord-BM25 0.3.0 from the pinned
  official multi-architecture suite. The existing volume remains at 5,183 documents and now holds
  176,333 dense representation rows; all 5,183 documents also have a BM25 vector and native index.
- Independent BM25 over unweighted raw title plus abstract reports nDCG 0.681034, MAP 0.631044,
  recall 0.821889, precision 0.091000, and MRR 0.641601 across all 300 queries. It retrieves a
  judged document for 247 queries, rescues 25 strict-dense zero-hit queries, and regresses on 16
  queries strict dense retrieved. It was the strongest independent lexical baseline at that stage,
  but no default promotion or fusion tuning was made from repeated use of the public qrels.
- Four predeclared symmetric BM25 fusions reuse top 50 candidates per source and `k=60`, without
  weights or a sweep. Nominal fusion leads nDCG at 0.697360; token-window fusion leads recall at
  0.842667 and retrieves a judged document for 256 queries, with 26 strict-miss rescues and eight
  strict-hit regressions. All four results are exploratory because the public qrels have been
  examined repeatedly; they do not authorize parameter tuning or default promotion.
- A pinned MS MARCO MiniLM cross-encoder now reranks the deduplicated top-50 union from BM25, token
  windows, strict coreference, and nominal coreference through TEI. The single completed 300-query
  GPU run took 87.91 seconds and reports nDCG 0.686962, MAP 0.642502, recall 0.806556, precision
  0.090333, and leaderboard-leading MRR 0.658184. It ranks fourth by nDCG and lowers recall versus
  standalone BM25 and every fixed BM25-vector fusion, so it remains experimental and token windows
  remain the default.
- The public train qrels now have a deterministic 649-query development and 160-query validation
  partition. On validation, BM25 plus token windows leads nDCG at 0.707033 and recall at 0.809375.
  Complete four-channel pooling reaches nDCG 0.683622 and recall 0.806250; adding MS MARCO reaches
  nDCG 0.699656 and recall 0.803125. Neither clears the promotion gate, so no test confirmation or
  default change occurred.
- The pooled candidate surface averages 105.97 documents, reaches recall 0.906250, and has oracle
  nDCG 0.907664. Ranking is therefore the dominant measured bottleneck. An evidence-grounded
  proposition graph remains an approved later scorer direction, stored first in typed PostgreSQL
  tables; graph retrieval and Apache AGE remain deferred.
- Fixed four-channel robust normalized mean fusion reaches validation nDCG 0.688954, MAP 0.645051,
  recall 0.806250, precision 0.092500, and MRR 0.661119. It improves equal four-channel RRF nDCG by
  0.005333 without changing recall but remains below the validation leader, so it is selectable
  evidence only; no test run or default promotion occurred.
- Hosted ColBERT scoring over the unchanged pool reaches validation nDCG 0.734958, MAP 0.707396,
  recall 0.800000, precision 0.091875, and MRR 0.722569. It is the strongest validation ranker on
  nDCG, MAP, and MRR, but recall is 0.009375 below the BM25/token-window guardrail. It therefore
  remained opt-in at that validation boundary; the later fixed test comparison is recorded below.
- The latest interval-expanded pool averages 114.11 candidates, reaches candidate recall 0.925000,
  and has oracle nDCG 0.926414. Ranking it only with MS MARCO reaches nDCG 0.701572 and recall
  0.790625. Ranking it only with ColBERT leaves the prior ColBERT top-10 metrics unchanged at nDCG
  0.734958 and recall 0.800000. The extra candidates therefore do not close the top-10 recall gap;
  neither strategy was promoted at that validation boundary.
- The owner later authorized one frozen comparison on all 300 already-inspected test queries. The
  title-separated six-generator pool averages 137.69 candidates, reaches candidate recall 0.950333,
  and has oracle nDCG 0.951169. ColBERT leads at nDCG 0.744417, MAP 0.703911, recall 0.852667, and
  MRR 0.716210 in 165.07 seconds. MS MARCO reaches nDCG 0.688308 and recall 0.812222 in 141.95
  seconds. The ColBERT score is 0.003283 below AnswerAI's published full-corpus 0.7477, but the local
  candidate-reranking and published indexing/search protocols are not equivalent.
- The raw dual-DP strategy now stores 17,807 embedded MiniLM chunks and 5,573 non-embedded ColBERT
  content chunks over all 5,183 documents. Exact tokenizer audits report maxima of 126 and 510 with
  zero violations; every DP text is an original abstract substring. The fixed 649-query development
  run averages 126.56 candidates, reaches candidate recall 0.955059 and oracle nDCG 0.955886, and
  ranks at nDCG 0.657331, MAP 0.607033, recall 0.795095, and MRR 0.620860. No validation/test run,
  weight sweep, or default promotion followed.
- The unchanged prior six-generator, whole-title-plus-abstract ColBERT strategy was then measured
  on the same 649 development queries. It averages 137.47 candidates, reaches candidate recall
  0.954289 and oracle nDCG 0.955290, and ranks at nDCG 0.759619, MAP 0.719683, recall 0.869055, and
  MRR 0.730180. Against that architecture-level control, dual-DP changes candidate recall by only
  +0.000770 but final nDCG by -0.102288. Because pool composition, title separation, chunk scoring,
  max aggregation, and robust normalization all change together, the result locates the regression
  in the combined ranking architecture but does not identify one causal component. The first
  identical control execution lost its stdout; one disclosed recovery execution produced the
  retained artifact. Neither strategy was promoted.
- The fixed-pool multiview ablation uses those exact six-generator candidates and reaches nDCG
  0.655268, MAP 0.604133, recall 0.795095, and MRR 0.618217. Relative to whole-document scoring it
  changes nDCG by -0.104351 with identical candidate recall and oracle nDCG. Relative to the
  four-generator multiview result it changes nDCG by only -0.002063 with identical final recall.
  The regression therefore belongs to the complete title/max-content robust-fusion bundle, not
  pool composition. A stale-image CLI preflight made no model request; the rebuilt application
  image then produced the only result-bearing run.
- The completed component ablations hold that six-generator pool fixed. Content-max-only reaches
  nDCG 0.755459, MAP 0.714034, recall 0.870853, and MRR 0.724220. Raw title/content equal mean
  reaches nDCG 0.716835, MAP 0.668757, recall 0.847997, and MRR 0.683461. Adding raw title fusion
  changes nDCG by -0.038623 from content-only; separately robust-normalizing those channels changes
  it by a further -0.061568 to 0.655268. The content-only versus whole-document comparison still
  couples title omission, chunking, max aggregation, and truncation, so it does not isolate max
  alone. Exactly two development diagnostics ran; no weight sweep, validation/test run, promotion,
  or further model evaluation followed.
- The current BM25-plus-abstract-token RRF reaches test nDCG 0.669962 and recall 0.819222. The
  owner-selected dedicated-title plus abstract-token equal-RRF default reaches only nDCG 0.548652
  and recall 0.705167, so the default policy is a current revisit item. No automatic change was
  made from reused test qrels.
- RankZephyr was not evaluated for effectiveness. Its live window throughput projected roughly 3.4
  hours for 160 queries, and the owner declined both that cost and its distilled-frontier-model
  approach. Its model and coordinator services are stopped; the opt-in implementation remains.
- Exact cached-tokenizer measurement over all 5,183 documents shows MiniLM's 126-content-token
  boundary is exceeded by 96.55% of abstracts and 97.88% of title-plus-abstract inputs. Median
  title-plus-abstract length is 314 tokens. ColBERT covers 91.22% within 510 content tokens; 455
  documents (8.78%) may lose tail content.
- The semantic-chunk comparison is complete. Sentence packing stored 19,569 chunks and reached
  validation nDCG 0.622347, MAP 0.578863, recall 0.737500, precision 0.084375, and MRR 0.596654.
  Coreference-aware packing stored 20,329 chunks and reached nDCG 0.624108, MAP 0.577408, recall
  0.751563, precision 0.086250, and MRR 0.592924. Global equal-cost interval packing stored 19,571
  chunks and leads the packers at nDCG 0.630108, MAP 0.581919, recall 0.762500, precision 0.087500,
  and MRR 0.596143. Its BM25 fusion reaches nDCG 0.694759 and recall 0.793750; BM25 plus token
  windows remains stronger. No packing strategy was tested on test qrels or promoted.
- Adding sentence packing individually to the existing pool increases candidate recall from
  0.906250 to 0.918750 and oracle nDCG from 0.907664 to 0.920164. Adding either coreference packer
  reaches candidate recall 0.925000 and oracle nDCG 0.926414. Equal five-channel RRF regresses nDCG
  for all three additions, so no reranker was invoked automatically.
- Repeated representation ingestion previously rewrote unchanged document and BM25-vector tuples;
  VectorChord-BM25 retained obsolete heap locations and required one index-only rebuild. Document
  and BM25 writes are now conditional. An isolated integration test and a full 5,183-document
  no-op ingestion preserved tuple identities and BM25 index size, followed by successful BM25
  retrieval without reindexing.
- The first in-process CPU evaluation was deliberately interrupted after 417.39 seconds without
  metrics when the owner required hosted GPU inference. The host Compose CLI rejected an ad hoc
  `docker compose run --gpus` flag; GPU access now belongs to the durable TEI service definition.
- TEI's pinned Candle backend logs an efficient GeLU-tanh approximation instead of Transformers'
  exact GeLU. This may create subtle score/order differences and is part of the reported runtime
  boundary, not an unreported substitution.
- Retrieval still needs explicit handling for scientific inference across sentences, biomedical
  synonymy and aliases, directional polarity, and negation or contradiction. Coreference does not
  own these responsibilities, and document-recall metrics do not measure stance correctness.
- BM25 remains a lexical-ranking experiment, not a proposed solution for inference or stance.
  Any fusion change, scientific tokenizer change, or default promotion requires a new decision
  and a validation boundary separate from the reported public qrels.
- Raw queries remain one normalized MiniLM vector. The 300 evaluated queries have a maximum of 62
  content tokens and a 95th percentile of 39, with no truncation; query-side FastCoref is excluded
  to isolate the document-side experiment.
- The application image is 11.71 GB because the standard sentence-transformers/PyTorch and
  FastCoref resolutions include large runtime and training-oriented dependencies. Record this as
  an optimization candidate after the product experiment, not a precondition.
- Live generation is verified. A directly supported vitamin-D/MS animal-model statement returned
  citation `22843838`. The broader human risk-reduction claim was explicitly qualified as not
  directly established by the supplied evidence, rather than treating association and an animal
  result as human causality. An unsupported Moon/green-cheese claim returned exactly
  `insufficient evidence` with no citations.
- Qwen initially used its 512-token answer budget for reasoning and returned null final content.
  The adapter now passes the checkpoint's supported `enable_thinking=false` chat-template option;
  an adapter regression test covers that request contract.
- The public GitHub repository and bounded Issues exist. No dedicated roadmap Project, image
  publication, or deployment has been created.
- The owner selected MIT for the application. `LICENSE`, package metadata, intake, project
  contract, charter, and README are reconciled. pg_tokenizer remains Apache-2.0 and
  VectorChord-BM25 remains separately dual-licensed under AGPLv3 or Elastic License v2; the custom
  database image does not relicense either extension as MIT.

## Measured template friction

Instantiation produced 214 files and roughly 26,000 lines before application code, largely from
template maintenance history, plugin distribution, and deferred evaluation machinery. The copied
tests are correctly absent, so the earlier 256-test failure is fixed. Treat the remaining scaffold
volume as evidence for a later simplification decision; do not interrupt this product proof to
build that cleanup first.

## Engineering-loop recovery policy

- The human owner raised the retry ceiling to five consecutive failures for newly started
  engineering-loop runs. Failure five blocks at attempt five without creating attempt six.
- Existing run records retain the ceiling bound when they were created. A blocked run still
  requires a structured `human:IDENTITY` handoff and resumes as a new evidence revision.
- Pi's separate three-unavailable-tool-call ceiling is unchanged. ADR-0019 records the boundary.
