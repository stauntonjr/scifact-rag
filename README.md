# SciFact RAG

A small, inspectable retrieval-augmented generation prototype over the public SciFact benchmark.
It uses PostgreSQL with pgvector for retrieval, `paraphrase-MiniLM-L6-v2` for 384-dimensional
embeddings, and `nvidia/Qwen3.6-35B-A3B-NVFP4` through an OpenAI-compatible endpoint hosted on one
DGX Spark.

Retrieval defaults to fixed equal reciprocal-rank fusion between a dedicated title embedding and
overlapping 126-token abstract windows with 32 tokens of overlap. `token-window` remains selectable
as an abstract-only diagnostic. Three experimental abstract-only coreference strategies are also
selectable: strict proper-noun sentence resolution, broader explicit-nominal sentence resolution,
and maximum-score fusion across both. Coreference is resolved over each abstract before sentence
splitting. No abstract-derived embedding channel contains the title; every channel aggregates its
best representation score back to one document result, preserving document IDs for citations.

Three semantic-chunking experiments are independently selectable. `sentence-pack` preserves original
sentence boundaries and splits before a proposed multi-sentence group exceeds 112 content tokens,
with a hard 126-token MiniLM limit for indivisible sentences. `coref-aware-pack` uses original
mention offsets to delay that soft boundary when a proper-noun coreference chain crosses it, then
canonicalizes mentions after grouping. `coref-interval-pack` globally selects contiguous sentence
groups by minimizing equal-cost proper-noun chain cuts before a fixed length-balance tie-break.
None introduces a tuned similarity threshold or entity weight.

Lexical experiments are also retained. `keyword` uses PostgreSQL's native English full-text
search over the raw title and abstract. `bm25` uses VectorChord-BM25 with the BERT uncased
tokenizer over the same raw fields. `hybrid-rrf` combines keyword's top 50 candidates with the
strict coreference dense ranking. Seven additional strategies pair BM25 separately with token
windows, strict coreference, nominal coreference, coreference-max, sentence packing, greedy
coreference packing, and global interval packing. Every fusion is symmetric RRF over top-50
candidates with `k=60`; no weights or parameters were tuned.

`rerank-msmarco` is a bounded second-stage experiment. It unions top 50 candidates from BM25,
token windows, strict coreference, and nominal coreference, deduplicates at most 200 documents, and
ranks their raw title plus abstract with the pinned Apache-2.0
`cross-encoder/ms-marco-MiniLM-L6-v2`. The raw query is unchanged. No retrieval score is mixed into
the final score, and no parameter or model sweep is performed.

Three feature-preserving pooled strategies reuse the same broad candidate surface. The legacy name
`pooled-four-channel-rrf` now rescores every candidate through corpus-global BM25, title,
abstract-token, strict-coreference, and nominal-coreference channels before equal rank fusion.
`pooled-msmarco-rrf` adds the existing MS MARCO score as a sixth rank. Both retain source and
matching-passage provenance; generation ranks are diagnostic and are not counted again.
`pooled-four-channel-robust-sum` instead normalizes the same five complete raw-score columns with a
fixed query-local median/MAD logistic transform and averages them equally. Constant columns map to
`0.5`; nonconstant zero-MAD columns use tied empirical-CDF ranks. These bounded values are not
relevance probabilities.

Three additional pooled diagnostics preserve that existing surface and add exactly one of
`sentence-pack`, `coref-aware-pack`, or `coref-interval-pack` as a sixth generator and
complete scorer. They measure incremental candidate coverage without combining packers or changing
candidate depth, RRF parameters, or the default.

`pooled-colbert` is a separate late-interaction experiment over the same five-generator pool. A
digest-pinned vLLM service scores each raw query against every deduplicated raw title plus abstract
with `answerdotai/answerai-colbert-small-v1` MaxSim. The adapter explicitly right-truncates at 512
tokens; no retrieval score is mixed into the ColBERT order.

`pooled-coref-interval-msmarco`, `pooled-coref-interval-colbert`, and
`pooled-coref-interval-rankzephyr` preserve the latest six-generator pool: BM25, title,
abstract-token windows, strict coreference, nominal coreference, and global coreference-interval
packing. Each strategy ranks every deduplicated candidate with only its named scorer. RankZephyr
uses a pinned RankLLM coordinator and a separate memory-bounded vLLM model service. The three
strategies do not fuse rerankers or mix retrieval scores into their order.

The product boundary is CLI-first. Domain and application contracts are Python dataclasses; one
visible composition root wires replaceable corpus, embedding, storage, and generation adapters.
HTTP, MCP, web UI, model tool-calling, and Pi effectiveness evaluation are intentionally inactive.
The ordered delivery plan, phase gates, stop rules, and explicit deferrals are documented in
[`docs/project/roadmap.md`](docs/project/roadmap.md).

Generation context is separately selectable from retrieval. `whole-document` remains the
compatibility default and sends each retrieved title and complete abstract. `adaptive` keeps a
complete abstract when its DP representation is one exact matching view; otherwise it scores the
stored raw 510-token `coref-nominal-dp-colbert` views with hosted ColBERT and sends at most two
chunks per retrieved parent. The legacy `top-dp-chunks` CLI value is retained as an exact alias for
`adaptive`, not a third policy. Parent retrieval order is preserved; selected chunks are restored
to source order within each parent, titles remain attached, and citations still name parent
document IDs.

Before a live generation comparison, validate its complete versioned run manifest without opening
the database or calling a model service:

```bash
mkdir -p artifacts
docker compose run --rm app generation-eval-dry-run \
  --manifest artifacts/generation-validation/manifest.json
docker compose run --rm app run-generation-eval \
  --manifest artifacts/generation-validation/manifest.json \
  --evaluation-set artifacts/scifact-generation-validation.jsonl
```

The field contract and the prohibition on default selection from the already-inspected test qrels
are documented in
[`docs/project/generation-evaluation.md`](docs/project/generation-evaluation.md).
That document also records the pinned official SciFact sentence-level source and the
`build-generation-eval-manifest` command. The deterministic validation input contains 160 cases and
has SHA-256 `34084490c48515f0c788da0960d7f426c0e64e4dcf9431b8721d824ba0349105`.
The paired runner retrieves parents once per claim, applies the two distinct policies, flushes each
raw result row durably, and resumes only missing claim-policy pairs. Its run manifest must declare
`context_strategy` as `paired`; it does not change the interactive `ask` default. Server-reported
Qwen prompt/completion tokens, a fixed per-request seed, a parseable SciFact verdict, separate
assembly/generator timings, and a sibling
`results.report.json` aggregate remain traceable to the raw rows.

Retrieval-default comparison is a separate fixed run over the 160-query validation split. It
compares BM25/token-window RRF with the two selected ColBERT interval scorers, retains every raw
ranking or failure, resumes only missing query/strategy pairs, and derives metrics plus per-query
gains/losses from those rows:

```bash
docker compose run --rm app retrieval-eval-dry-run \
  --manifest artifacts/retrieval-default-validation/manifest.json
docker compose run --rm app run-retrieval-eval \
  --manifest artifacts/retrieval-default-validation/manifest.json \
  --data-dir data
```

The complete manifest, digest, component, resume, and no-repair contract is in
[`docs/project/retrieval-evaluation.md`](docs/project/retrieval-evaluation.md). This comparison is
internal evidence because the split has already been inspected; implementing or running it does
not itself change the retrieval default.

## Run with Docker Compose

The generator is external to this Compose project. It must be reachable from the host at
`http://127.0.0.1:8000/v1` or through `GENERATOR_BASE_URL`. The RAG project never stops, replaces,
or starts that GPU workload. The MS MARCO, ColBERT, and RankZephyr experiments are separate
services owned by this Compose project and exposed only on host loopback ports 8081 through 8084.

```bash
docker compose up -d postgres
docker compose build app
docker compose run --rm app download
docker compose run --rm app ingest
docker compose run --rm app search "What evidence links immune signaling to disease?"
docker compose run --rm app ask "What evidence links immune signaling to disease?"
docker compose run --rm app evaluate --cutoff 10
```

The chunk-aware generation policy requires the existing DP rows and the healthy ColBERT service.
It does not change retrieval and can be paired with any retrieval strategy. The legacy command is
shown only to document compatibility; both commands now select the same adaptive policy:

```bash
docker compose run --rm app ingest --strategy pooled-coref-nominal-dp-colbert
docker compose run --rm app ask \
  --context-strategy top-dp-chunks \
  "What evidence links immune signaling to disease?"
docker compose run --rm app ask \
  --context-strategy adaptive \
  "What evidence links immune signaling to disease?"
```

To populate and compare the coreference strategies without replacing token-window rows:

```bash
docker compose run --rm app ingest --strategy coref-max
docker compose run --rm app ingest --strategy sentence-pack
docker compose run --rm app ingest --strategy coref-aware-pack
docker compose run --rm app ingest --strategy coref-interval-pack
docker compose run --rm app evaluate --strategy coref-propn --cutoff 10
docker compose run --rm app evaluate --strategy coref-nominal --cutoff 10
docker compose run --rm app evaluate --strategy coref-max --cutoff 10
docker compose run --rm app evaluate --strategy sentence-pack \
  --split train-validation --cutoff 10
docker compose run --rm app evaluate --strategy coref-aware-pack \
  --split train-validation --cutoff 10
docker compose run --rm app evaluate --strategy coref-interval-pack \
  --split train-validation --cutoff 10
docker compose run --rm app ingest --strategy keyword
docker compose run --rm app evaluate --strategy keyword --cutoff 10
docker compose run --rm app ingest --strategy bm25
docker compose run --rm app evaluate --strategy bm25 --cutoff 10
docker compose run --rm app evaluate --strategy hybrid-rrf --cutoff 10
docker compose run --rm app evaluate --strategy bm25-token-window-rrf --cutoff 10
docker compose run --rm app evaluate --strategy bm25-coref-propn-rrf --cutoff 10
docker compose run --rm app evaluate --strategy bm25-coref-nominal-rrf --cutoff 10
docker compose run --rm app evaluate --strategy bm25-coref-max-rrf --cutoff 10
docker compose run --rm app evaluate --strategy bm25-sentence-pack-rrf \
  --split train-validation --cutoff 10
docker compose run --rm app evaluate --strategy bm25-coref-aware-pack-rrf \
  --split train-validation --cutoff 10
docker compose run --rm app evaluate --strategy bm25-coref-interval-pack-rrf \
  --split train-validation --cutoff 10
docker compose run --rm app ingest --strategy rerank-msmarco
docker compose run --rm app evaluate --strategy rerank-msmarco --cutoff 10
docker compose run --rm app ingest --strategy pooled-four-channel-rrf
docker compose run --rm app diagnose-candidates --strategy pooled-four-channel-rrf \
  --split train-validation --cutoff 10
docker compose run --rm app diagnose-candidates --strategy pooled-msmarco-rrf \
  --split train-validation --cutoff 10
docker compose run --rm app diagnose-candidates --strategy pooled-four-channel-robust-sum \
  --split train-validation --cutoff 10
docker compose run --rm app diagnose-candidates --strategy pooled-colbert \
  --split train-validation --cutoff 10
docker compose run --rm app diagnose-candidates --strategy pooled-sentence-pack-rrf \
  --split train-validation --cutoff 10
docker compose run --rm app diagnose-candidates --strategy pooled-coref-aware-pack-rrf \
  --split train-validation --cutoff 10
docker compose run --rm app diagnose-candidates --strategy pooled-coref-interval-pack-rrf \
  --split train-validation --cutoff 10
docker compose run --rm app diagnose-candidates --strategy pooled-coref-interval-msmarco \
  --split train-validation --cutoff 10
docker compose run --rm app diagnose-candidates --strategy pooled-coref-interval-colbert \
  --split train-validation --cutoff 10
docker compose run --rm app ingest --strategy pooled-coref-nominal-dp-colbert
docker compose run --rm app diagnose-candidates --strategy pooled-coref-nominal-dp-colbert \
  --split train-development --cutoff 10
docker compose run --rm app diagnose-candidates \
  --strategy pooled-coref-interval-multiview-colbert \
  --split train-development --cutoff 10
docker compose run --rm app diagnose-candidates \
  --strategy pooled-coref-interval-content-max-colbert \
  --split train-development --cutoff 10
docker compose run --rm app diagnose-candidates \
  --strategy pooled-coref-interval-raw-mean-colbert \
  --split train-development --cutoff 10
docker compose up -d reranker late-interaction rankzephyr-model rankllm
docker compose run --rm app diagnose-candidates --strategy pooled-coref-interval-rankzephyr \
  --split train-validation --cutoff 10
```

`coref-max` ingestion resolves each abstract once and stores both policy-specific sentence sets.
The two individual strategies remain independently queryable. Keyword and BM25 ingestion store
canonical documents without loading MiniLM or FastCoref. BM25 tokenizes the unweighted title plus
abstract in PostgreSQL and maintains a native BM25 index. Hybrid ingestion materializes the strict
coreference representation as well. `title-token-window-rrf` is the fixed CLI default;
`token-window` is an abstract-only selectable baseline.

`sentence-pack` loads spaCy sentence segmentation without loading the FastCoref model.
`coref-aware-pack` and `coref-interval-pack` perform one full-abstract FastCoref analysis per
ingestion batch. All three exclude the title and use existing pgvector best-chunk document
aggregation; pooled strategies add the one dedicated title channel separately. The interval
strategy globally minimizes equal per-chain cuts before fixed length and
deterministic tie-breaks. If one sentence or canonicalized group exceeds 126 tokens, a bounded
overlapping fallback shrinks decoded windows until they re-tokenize within the MiniLM limit.

`pooled-coref-nominal-dp-colbert` is the opt-in long-document scoring path. One nominal-policy
coreference analysis produces rewritten sentence candidates plus two independent raw-source DP
profiles. The 112-target/126-hard MiniLM profile generates candidates; the 510-hard ColBERT
profile is stored without pgvector embeddings and is never a candidate generator. Its tokenizer is
loaded from the same immutable `c72aa89bc61afdd85373643f3a1a75b2aad6e0fe` revision as the live
model. Exact source-offset hard splits shrink until the isolated raw substring retokenizes within
budget.

The fixed pool has exactly four top-50 generators: BM25, title embeddings, rewritten nominal
sentence embeddings, and raw MiniLM-DP embeddings. ColBERT scores titles separately, scores every
stored raw 510-token content chunk, and uses the maximum content score per document. Title and
max-content scores are robust-normalized separately within the query pool and combined by an equal
mean. Retrieval scores and candidate-only sentence views do not enter the final ranking.

`pooled-coref-interval-multiview-colbert` applies that exact two-channel scorer, normalizer, and
equal-mean policy to the existing six-generator interval pool. It is a fixed-pool ablation: the
whole-document and multiview variants receive identical candidates, so their difference measures
the complete scoring bundle rather than pool composition. Two further fixed-pool strategies expose
its component boundary. `pooled-coref-interval-content-max-colbert` ranks only the raw maximum
content score. `pooled-coref-interval-raw-mean-colbert` takes the equal mean of raw title and
maximum-content scores without rescaling them. All three remain opt-in and leave the default
unchanged.

Representation ingestion replaces only the selected representation rows. Existing document tuples
and BM25 vectors are updated only when their underlying values change, so adding an unchanged
vector representation does not require rebuilding the native BM25 index.

`rerank-msmarco` ingestion materializes the title, token-window, and both coreference
representations in one pass; BM25 remains document-native. The application sends at most 250 raw
documents to the
separate Hugging Face TEI `/rerank` service, whose official ARM64 `sm_121` image uses the DGX GPU.
The TEI image is pinned by digest and the selected checkpoint is fixed at revision
`233902d25c440f23af6f7d6e94d2946bac0bee0a`; NER, triple extraction, knowledge-graph construction,
and graph retrieval are deferred.

`pooled-colbert` uses the digest-pinned NVIDIA vLLM 26.06 ARM64 image and immutable AnswerAI model
revision `c72aa89bc61afdd85373643f3a1a75b2aad6e0fe`. The live service resolves the model as
`HF_ColBERT`, computes MaxSim on the GPU, and accepts at most 512 tokens per query or document.
Start it explicitly with `docker compose up -d late-interaction`; other CLI strategies do not
depend on or automatically start it.

`pooled-coref-interval-rankzephyr` uses `castorini/rank_zephyr_7b_v1_full` at immutable revision
`aa11d9da444ec3490827656c3b961d5c5f3af0eb`. The model runs in the pinned NVIDIA vLLM image with
BF16 weights, an 8,192-token model limit, one sequence, and a 0.20 memory ceiling on loopback port
8084. RankLLM is built from Apache-2.0 commit
`8ad18be76c90aa97ffae50b84dbc326bedc724fd` and exposes the strict listwise API at port 8083.
Start both explicitly with `docker compose up -d rankzephyr-model rankllm`; no other strategy
depends on them.

On this DGX, another SparkRun model may already occupy the endpoint and GPU memory. Stop or replace
that workload deliberately before starting the selected model; do not launch both blindly. The
verified TP1 command for SparkRun 0.2.40 is:

```bash
sparkrun run @eugr/qwen3.6-35b-a3b-nvfp4-no-mtp \
  --hosts 127.0.0.1 --tp 1 --port 8000 \
  --served-model-name nvidia/Qwen3.6-35B-A3B-NVFP4 \
  --max-model-len 32768 --no-follow
```

The corresponding MTP recipe currently emits malformed doubled braces around its speculative
decoding JSON. The no-MTP recipe serves the same checkpoint; speculative decoding is not required
by this application.

## Result contracts

- `search` emits ranked documents with `doc_id`, title, text, and a strategy-specific score:
  cosine similarity, PostgreSQL cover-density rank, positive BM25 relevance, or
  reciprocal-rank-fusion score. Robust normalized fusion emits an equal mean in `[0, 1]`, not a
  calibrated probability.
- `ask` accepts only citations matching retrieved document IDs. Missing or invalid citations are
  converted to `insufficient evidence` rather than returned as an ungrounded answer. Its `evidence`
  list is the actual whole-document or chunk context supplied to the generator; chunk modes may
  return two entries with the same parent document ID.
- `evaluate` reports mean nDCG, MAP, recall, precision, and reciprocal rank at the selected cutoff
  over the selected public BEIR SciFact qrels split.
- `diagnose-candidates` reports per-generator and union candidate recall, mean pool size, oracle
  nDCG, and final ranking metrics for a pooled strategy.

BM25 plus nominal coreference RRF leads the internal leaderboard at nDCG@10 0.697360. BM25 plus
token-window RRF leads recall@10 at 0.842667 and rescues 26 of strict dense's 62 zero-hit queries.
These are fixed-protocol exploratory results from before title separation, not tuned validation
results. The original one-vector baseline was nDCG 0.526066 and recall 0.661722. See
[the retrieval leaderboard](docs/reports/scifact-retrieval-leaderboard.md) for all metrics and
provenance.

The hosted MS MARCO reranker leads only MRR at 0.658184. It reaches nDCG@10 0.686962 and recall@10
0.806556 in 87.91 seconds for 300 GPU-served queries, ranking fourth by nDCG and lowering recall
versus standalone BM25. It remains an exploratory selectable strategy, not the default.

On the deterministic 160-query validation partition, BM25 plus token windows remains strongest at
nDCG 0.707033 and recall 0.809375. Complete pooled scoring with MS MARCO reaches nDCG 0.699656 and
recall 0.803125, so it is not promoted. The candidate pool itself reaches recall 0.906250 and oracle
nDCG 0.907664, identifying second-pass ranking as the larger opportunity. Robust normalized
four-channel fusion reaches nDCG 0.688954 and recall 0.806250: a small gain over four-channel RRF,
but still below the leader. These validation results were inspected repeatedly and are comparative,
not a pristine selection boundary.

On that same validation partition, `pooled-colbert` now leads nDCG at 0.734958, MAP at 0.707396,
and MRR at 0.722569, while recall falls to 0.800000. Because this misses the 0.809375 recall
guardrail, it remained opt-in at that decision point.

The later raw dual-DP multiview strategy was measured once on the separate 649-query development
partition. Its four-generator pool reaches recall 0.955059 and oracle nDCG 0.955886, while equal
robust-normalized ColBERT title/max-content scoring reaches nDCG 0.657331, MAP 0.607033, recall
0.795095, and MRR 0.620860. This is not directly comparable to the earlier validation/test rows:
both split and scoring protocol differ. The large oracle gap is evidence to improve ranking rather
than expand this candidate pool; no weight sweep or default promotion follows.

The same fixed six-generator pool was then used for two component ablations. Content-max-only
ranking reaches nDCG 0.755459, MAP 0.714034, recall 0.870853, and MRR 0.724220. Raw equal-mean
title/content fusion reaches nDCG 0.716835, MAP 0.668757, recall 0.847997, and MRR 0.683461. The
existing robust-normalized equal mean reaches nDCG 0.655268. Relative to content-only, adding raw
50/50 title fusion changes nDCG by -0.038623; adding separate robust normalization changes it by a
further -0.061568. The content-only comparison with whole-title-plus-abstract scoring still
couples title omission, chunking, maximum aggregation, and avoided right truncation, so it is not
a pure max-operator estimate. No weight sweep, validation/test run, or default promotion followed.

Scoring the expanded interval pool independently did not convert its higher validation
candidate ceiling into higher top-10 recall. MS MARCO reaches nDCG 0.701572 and recall 0.790625;
the prior 0.699656 pooled MS MARCO result fused five complete score channels and is therefore not a
controlled pool-only comparison. ColBERT returns the same nDCG 0.734958 and recall 0.800000 as its
four-generator run at the aggregate metric boundary. The retained evidence does not compare
per-query top-ten identities. Both strategies remain diagnostic and opt-in.

The later owner-authorized, fixed 300-query test comparison uses the title-separated six-generator
pool and performs no tuning. It reaches candidate recall 0.950333 and oracle nDCG 0.951169.
AnswerAI ColBERT leads at nDCG 0.744417, MAP 0.703911, recall 0.852667, and MRR 0.716210 in 165.07
seconds. MS MARCO reaches nDCG 0.688308 and recall 0.812222 in 141.95 seconds. The ColBERT result is
0.003283 below AnswerAI's published full-corpus SciFact nDCG 0.7477, but the protocols differ:
this project reranks a bounded pool through vLLM rather than reproducing the model's full-corpus
indexing/search stack. Because the test qrels influenced earlier decisions, this is exploratory
comparison evidence rather than an untouched estimate.

The current BM25-plus-abstract-token RRF reaches test nDCG 0.669962 and recall 0.819222. The
dedicated-title plus abstract-token equal-RRF default reaches only nDCG 0.548652 and recall
0.705167. The code still exposes that owner-selected default, but its policy is now a revisit item.
RankZephyr was not run: its observed throughput projected roughly 3.4 hours for the 160-query
validation set, and the owner declined both that cost and its distilled-frontier-model approach.
Its two Compose services are stopped; the opt-in experiment remains reproducible but deferred.

The fixed semantic-chunk comparison did not improve the architecture leader. `sentence-pack`
stored 19,569 chunks and reached validation nDCG 0.622347 and recall 0.737500.
`coref-aware-pack` stored 20,329 chunks and reached nDCG 0.624108 and recall 0.751563. Coreference
cohesion recovered 0.014063 recall and slightly improved nDCG relative to sentence packing, while
MAP and MRR declined. `coref-interval-pack` stored 19,571 chunks and leads the packers at nDCG
0.630108 and recall 0.762500. Its BM25 fusion reaches nDCG 0.694759 and recall 0.793750.

Adding either coreference packer individually to the existing four-channel pool increases candidate
recall from 0.906250 to 0.925000 and oracle nDCG from 0.907664 to 0.926414. Equal five-channel RRF
does not exploit that gain: its nDCG falls to 0.677932 for greedy packing and 0.673584 for interval
packing. The interval pool was subsequently sent independently to the existing MS MARCO and
ColBERT scorers as described above. The later six-generator test comparison is reported above; no
packer or scorer was automatically promoted from it.

MiniLM's 128-token sequence limit leaves 126 content tokens. In the local 5,183-document corpus,
96.55% of abstracts and 97.88% of title-plus-abstract inputs exceed that content limit; the median
title-plus-abstract length is 314 tokens. ColBERT's 512-token limit covers 91.22% within 510 content
tokens, leaving an 8.78% long tail. A sentence-boundary semantic-chunk comparison is therefore a
reasonable separately scoped experiment; the completed MiniLM comparison above did not beat the
retained leaders.

Keyword-only retrieval reaches recall@10 0.531667 but rescues 13 of the strict strategy's 62
zero-hit queries. Symmetric RRF rescues 16, yet loses 24 prior hit queries and lowers aggregate
recall to 0.749222. This is useful complementarity evidence, not a promotion result.

## Development checks

```bash
uv sync --locked
make smoke
docker compose up -d postgres
DATABASE_URL=postgresql+psycopg://scifact:scifact-local@127.0.0.1:5432/scifact \
  uv run pytest -m integration
```

## Data and model provenance

- SciFact claims/evidence annotations: CC BY 4.0.
- SciFact/S2ORC abstracts: ODC-By 1.0.
- MiniLM and the selected NVIDIA Qwen NVFP4 checkpoint: Apache-2.0.
- The MS MARCO MiniLM L6 cross-encoder checkpoint: Apache-2.0.
- The AnswerAI ColBERT small checkpoint: Apache-2.0.
- RankLLM at the pinned source revision: Apache-2.0.
- The RankZephyr 7B V1 Full checkpoint: MIT.
- Hugging Face Text Embeddings Inference: Apache-2.0.
- vLLM: Apache-2.0. The pinned NVIDIA vLLM container retains NVIDIA's separate container terms.
- FastCoref code and the FCoref checkpoint: MIT.
- pg_tokenizer is Apache-2.0. VectorChord-BM25 is separately dual-licensed under AGPLv3 or Elastic
  License v2 and is copied unmodified from its pinned upstream suite image into the database image.
- Application code is licensed under MIT. Dataset, model, database-extension, and image artifacts
  retain their separate licenses.

See [the composition ADR](docs/adr/0013-scifact-rag-composition-and-runtime.md),
[the modular coreference ADR](docs/adr/0015-modular-coreference-retrieval.md),
[the keyword and RRF ADR](docs/adr/0016-postgresql-keyword-and-rrf.md),
[the VectorChord-BM25 ADR](docs/adr/0017-vectorchord-bm25.md),
[the cross-encoder reranking ADR](docs/adr/0018-msmarco-cross-encoder-reranking.md),
[the pooled-ranking ADR](docs/adr/0020-pooled-ranking-and-projection-alignment.md),
[the robust score-fusion ADR](docs/adr/0021-generic-feature-ranking-and-robust-score-fusion.md),
[the hosted ColBERT ADR](docs/adr/0022-hosted-colbert-late-interaction-scoring.md),
[the semantic-chunking ADR](docs/adr/0023-coreference-aware-semantic-chunking.md),
[the global coreference-interval ADR](docs/adr/0024-global-coreference-interval-packing.md),
[the expanded-pool reranker ADR](docs/adr/0025-expanded-coreference-interval-pool-rerankers.md),
[the title-separated/listwise ADR](docs/adr/0026-title-separated-pooling-and-listwise-reranking.md),
[the Procurement projection crosswalk](docs/architecture/retrieval-projection-crosswalk.md),
[the coreference dependency review](docs/research/scifact-rag-coreference-solutions.md), and
[the BM25 solution assessment](docs/research/scifact-rag-bm25.md),
[the reranking solution assessment](docs/research/scifact-rag-reranking.md), and
[the late-interaction solution assessment](docs/research/scifact-rag-late-interaction.md), and
[the listwise solution assessment](docs/research/scifact-rag-listwise-reranking.md).
