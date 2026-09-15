# Internal SciFact retrieval leaderboard

- Dataset: public BEIR SciFact corpus and qrels
- Corpus size: 5,183 documents
- Evaluation queries: all 300 qrels-backed test claims
- Cutoff: 10
- Embedding model: `sentence-transformers/paraphrase-MiniLM-L6-v2`
- Ranking: strategy-specific PostgreSQL cosine, cover-density, BM25, or reciprocal-rank-fusion score
- Measured: 2026-08-26 on the Docker Compose application path

The table below is retained as exploratory history over the repeatedly inspected 300 test queries.
New architecture selection uses the deterministic 160-query validation partition described later.

## Historical test-set results

| Rank | Strategy | Stored rows | Rows/doc | nDCG@10 | MAP@10 | Recall@10 | Precision@10 | MRR@10 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | BM25 plus nominal coreference RRF | 56,597 | 10.920 | 0.697360 | 0.648547 | 0.836000 | 0.094000 | 0.655964 |
| 2 | BM25 plus coreference-max RRF | 102,764 | 19.827 | 0.694381 | 0.644006 | 0.836000 | 0.094000 | 0.652447 |
| 3 | BM25 plus strict coreference RRF | 56,533 | 10.907 | 0.692333 | 0.642261 | 0.832222 | 0.093667 | 0.650313 |
| 4 | MS MARCO cross-encoder over four-channel union | 122,047 | 23.548 | 0.686962 | 0.642502 | 0.806556 | 0.090333 | **0.658184** |
| 5 | BM25 plus token-window RRF | 24,466 | 4.720 | 0.681985 | 0.627150 | 0.842667 | 0.094333 | 0.634009 |
| 6 | VectorChord-BM25 title plus abstract | 5,183 | 1.000 | 0.681034 | 0.631044 | 0.821889 | 0.091000 | 0.641601 |
| 7 | Strict proper-noun coreference sentences | 51,350 | 9.907 | 0.618163 | 0.561557 | 0.779500 | 0.086000 | 0.574435 |
| 8 | Broader explicit-nominal coreference sentences | 51,414 | 9.920 | 0.617592 | 0.561789 | 0.773944 | 0.085667 | 0.576190 |
| 9 | Max over both coreference policies | 97,581 | 18.827 | 0.613820 | 0.557553 | 0.772833 | 0.085333 | 0.570774 |
| 10 | Strict coreference plus keyword RRF | 56,533 | 10.907 | 0.608786 | 0.558100 | 0.749222 | 0.083000 | 0.572671 |
| 11 | Overlapping token windows | 19,283 | 3.720 | 0.601929 | 0.556945 | 0.727944 | 0.081000 | 0.568218 |
| 12 | Original one-vector baseline | 5,183 | 1.000 | 0.526066 | 0.477665 | 0.661722 | 0.073000 | 0.495447 |
| 13 | PostgreSQL keyword | 5,183 | 1.000 | 0.404084 | 0.359022 | 0.531667 | 0.058667 | 0.369351 |

Ranking uses nDCG@10. BM25 plus nominal coreference leads nDCG and MAP; the MS MARCO reranker leads
MRR. BM25 plus token windows leads recall and precision and retrieves a judged document for 256
queries, rescuing 26 of
strict dense's 62 zero-hit queries while regressing on eight strict hits. The nominal and
coreference-max fusions each retrieve a judged document for 254 queries, with 23 rescues and seven
regressions; strict-coreference fusion reaches 253, with 22 rescues and seven regressions.

The pinned MS MARCO cross-encoder leads MRR at 0.658184 but ranks fourth by nDCG. Relative to
standalone BM25 it changes nDCG by +0.005928, MAP by +0.011458, recall by -0.015333, precision by
-0.000667, and MRR by +0.016583. Relative to the nominal-RRF nDCG leader it changes nDCG by
-0.010398, MAP by -0.006045, recall by -0.029444, precision by -0.003667, and MRR by +0.002220.
Thus the standard reranker improves the first relevant document's typical rank while discarding
too many relevant documents from the top ten to improve overall effectiveness.

The completed Compose evaluation took 87.91 seconds for 300 queries, or 0.293 seconds per query end
to end, through the digest-pinned TEI DGX Spark GPU service. A prior in-process CPU attempt was
interrupted after 417.39 seconds without metrics and is excluded. TEI reports an efficient
GeLU-tanh approximation rather than Transformers' exact GeLU; this is part of the pinned serving
boundary and may cause small score or ordering differences from the in-process implementation.

Standalone BM25 retrieves a judged document for 247 queries, with 25 strict-miss rescues and 16
strict-hit regressions. Max-score fusion across coreference policies remains negative evidence: it
consumes almost twice the
rows of one coreference policy and performs worse than either policy alone.

### Pairwise top-10 hit effects

These counts treat each query as a binary outcome: at least one judged document in the top ten or
none. They complement rank-sensitive aggregate metrics; they do not say where within the top ten a
relevant document appears.

| BM25 fusion | Queries hit | BM25 misses rescued | BM25 hits lost | Net vs BM25 | Strict misses rescued | Strict hits lost | Net vs strict |
|---|---:|---:|---:|---:|---:|---:|---:|
| Token windows | 256 | 13 | 4 | +9 | 26 | 8 | +18 |
| Strict coreference | 253 | 14 | 8 | +6 | 22 | 7 | +15 |
| Nominal coreference | 254 | 14 | 7 | +7 | 23 | 7 | +16 |
| Coreference max | 254 | 14 | 7 | +7 | 23 | 7 | +16 |

The BM25 arithmetic is `247 - hits lost + misses rescued`; the strict arithmetic starts from 238
hit queries. Thus vectors improve net top-10 coverage over BM25 in all four fixed fusions, while
still displacing some queries BM25 retrieved. Token-window fusion's lower MAP and MRR than BM25
show that broader binary coverage can coexist with weaker early-rank placement.

Keyword retrieval is complementary but weak as a standalone ranker. It rescues 13 of the strict
strategy's 62 zero-hit queries. Symmetric RRF rescues 16 but loses 24 queries that strict retrieved,
so it also underperforms strict overall. A diagnostic top-10 union reaches recall 0.825333 over 20
candidates; this is evidence for later candidate reranking, not a top-10 leaderboard entry.

## Fixed Issue #6 retrieval-default comparison

One frozen run compared the three roadmap candidates on the 160-query deterministic validation
partition. That partition had already been inspected, so this is internal comparative evidence,
not pristine validation. No strategy, parameter, model, depth, or data input changed after the
results were opened.

| Strategy | nDCG@10 | MAP@10 | Recall@10 | Precision@10 | MRR@10 | Median latency |
|---|---:|---:|---:|---:|---:|---:|
| DP content-max ColBERT over six-generator pool | **0.742493** | **0.716753** | **0.806250** | **0.092500** | **0.728472** | **638.94 ms** |
| Whole-document ColBERT over six-generator pool | 0.734958 | 0.707396 | 0.800000 | 0.091875 | 0.722569 | 642.45 ms |
| BM25 plus token-window RRF | 0.673519 | 0.630229 | 0.787500 | 0.090625 | 0.647436 | 78.70 ms |

All 480 query-strategy rows completed with no failure or empty ranking. Relative to BM25,
content-max ColBERT improves 39 queries, regresses 13, and ties 108; it gains eight relevant
document IDs and loses five in the top ten. Its 0.068975 absolute nDCG gain comes with about 8.1
times the median latency and a ColBERT GPU-service dependency. Content-max also dominates the
whole-document ColBERT candidate on every reported effectiveness metric and is slightly faster.

ADR-0029 therefore recommends `pooled-coref-interval-content-max-colbert` as the
retrieval-effectiveness default and retains `bm25-token-window-rrf` as the fast/no-ColBERT
alternative. This recommendation does not change the current runtime default. Exact provenance,
artifact hashes, transition counts, and limitations are in
`docs/reports/issue-6-retrieval-default-validation.md`.

## Current title-separated test comparison

The owner authorized one fixed comparison on all 300 test queries after declining the runtime and
distilled-frontier-model approach of RankZephyr. These qrels were already inspected during earlier
architecture work, so the results are exploratory and cannot serve as an untouched estimate. No
parameter, depth, model, prompt, or fusion value changed for this run.

| Strategy | nDCG@10 | MAP@10 | Recall@10 | Precision@10 | MRR@10 | Elapsed |
|---|---:|---:|---:|---:|---:|---:|
| Six-generator pool ranked by AnswerAI ColBERT | **0.744417** | **0.703911** | **0.852667** | **0.095667** | **0.716210** | 165.07 s |
| Six-generator pool ranked by MS MARCO | 0.688308 | 0.642681 | 0.812222 | 0.091333 | 0.657664 | 141.95 s |
| Current BM25 plus abstract-token-window RRF | 0.669962 | 0.616602 | 0.819222 | 0.091667 | 0.629812 | 22.00 s |
| Dedicated-title plus abstract-token-window RRF | 0.548652 | 0.493130 | 0.705167 | 0.078667 | 0.509983 | 28.35 s |

The six-generator pool averages 137.69 unique documents, reaches candidate recall 0.950333 and
query-hit rate 0.953333, and has oracle nDCG@10 0.951169. ColBERT therefore recovers most of the
available ranking quality while retaining materially more relevant top-ten documents than MS
MARCO. It exceeds the current BM25-plus-abstract-token baseline by 0.074454 nDCG and 0.033444
recall. The fixed title-plus-token RRF performs poorly enough that its current default status
should be revisited rather than reinforced from this reused test set.

AnswerAI reports SciFact nDCG@10 0.7477 for full-corpus ColBERT retrieval. The local result is
0.003283 lower. That small difference is encouraging, but it is not a formal reproduction: the
local service reranks a fixed candidate pool through vLLM `HF_ColBERT`, while the published result
uses the model's full-corpus indexing and search stack. The local pool also misses some judged
documents and right-truncates 455 long title-plus-abstract inputs. RankZephyr was not evaluated;
its model and coordinator services were stopped after the earlier validation run projected about
3.4 hours for 160 queries.

## Deterministic train/validation architecture results

The 809 public train-qrels queries are partitioned by SHA-256 query ID into 649 development and 160
validation queries. The partition was introduced after the test qrels had already influenced early
architecture work, and the validation partition was subsequently inspected repeatedly. Both
surfaces are therefore internal comparative evidence, not pristine selection or confirmation sets.

| Strategy | nDCG@10 | MAP@10 | Recall@10 | Precision@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| Pooled AnswerAI ColBERT late interaction | **0.734958** | **0.707396** | 0.800000 | 0.091875 | **0.722569** |
| Expanded interval pool ranked by ColBERT | **0.734958** | **0.707396** | 0.800000 | 0.091875 | **0.722569** |
| BM25 plus token-window RRF | **0.707033** | **0.670174** | **0.809375** | 0.092500 | **0.681111** |
| Expanded interval pool ranked by MS MARCO | 0.701572 | 0.668323 | 0.790625 | 0.090625 | 0.677733 |
| Pooled BM25 + three dense + MS MARCO RRF | 0.699656 | 0.660848 | 0.803125 | 0.092500 | 0.675171 |
| BM25 plus global coreference-interval pack RRF | 0.694759 | 0.657183 | 0.793750 | 0.090625 | 0.670799 |
| BM25 plus greedy coreference pack RRF | 0.694328 | 0.655565 | 0.796875 | 0.091250 | 0.670813 |
| BM25 plus sentence pack RRF | 0.689889 | 0.649854 | 0.796875 | 0.091250 | 0.666081 |
| Pooled BM25 + three dense robust normalized mean | 0.688954 | 0.645051 | 0.806250 | 0.092500 | 0.661119 |
| Pooled BM25 + three dense RRF | 0.683622 | 0.638278 | 0.806250 | 0.092500 | 0.657341 |
| Existing pool + sentence pack RRF | 0.681954 | 0.637997 | 0.800000 | 0.091875 | 0.655605 |
| BM25 plus nominal-coreference RRF | 0.681172 | 0.645154 | 0.778125 | 0.089375 | 0.655685 |
| Existing pool + greedy coreference pack RRF | 0.677932 | 0.634701 | 0.793750 | 0.091250 | 0.651230 |
| Existing pool + global coreference-interval pack RRF | 0.673584 | 0.625490 | 0.806250 | 0.092500 | 0.641959 |
| MiniLM global coreference-interval pack | 0.630108 | 0.581919 | 0.762500 | 0.087500 | 0.596143 |
| MiniLM coreference-aware pack | 0.624108 | 0.577408 | 0.751563 | 0.086250 | 0.592924 |
| MiniLM sentence pack | 0.622347 | 0.578863 | 0.737500 | 0.084375 | 0.596654 |

The pooled surface averages 105.97 unique candidates, reaches candidate recall 0.906250, and has
oracle nDCG@10 0.907664. Robust normalized fusion improves four-channel RRF nDCG by 0.005333 at
unchanged recall, but neither it nor the earlier pooled policies beats the token-window/BM25
validation baseline without recall regression. Hosted ColBERT improves validation nDCG by 0.027925,
MAP by 0.037222, and MRR by 0.041458 over that leader, but lowers recall by 0.009375. The
predeclared recall gate initially prevented a test run or default promotion. This is evidence that
late interaction materially improves ranking while leaving some top-10 coverage loss to analyze;
it is not evidence for adding candidate depth or sweeping fusion parameters. The later
owner-authorized fixed test comparison is reported above and was not used for a parameter sweep.

Sentence packing produced 19,569 chunk rows, greedy proper-noun coreference-aware packing produced
20,329, and global equal-cost coreference-interval packing produced 19,571. The interval optimizer
improves standalone nDCG to 0.630108 and recall to 0.762500, leading both prior packers, while all
three remain below the retained validation leaders. Its BM25 fusion leads the three packing fusions
on nDCG and MAP, but BM25 plus token windows remains stronger.

Each packing was also added separately to the existing four-channel pool, without changing the
top-50 generator depth, complete-rescoring contract, or equal-RRF `k=60` policy:

| Incremental pool | Mean size | Candidate recall | Candidate hit rate | Oracle nDCG@10 | RRF nDCG@10 |
|---|---:|---:|---:|---:|---:|
| Existing four-channel control | 105.97 | 0.906250 | 0.912500 | 0.907664 | **0.683622** |
| + sentence pack | 114.22 | 0.918750 | 0.925000 | 0.920164 | 0.681954 |
| + greedy coreference pack | 114.26 | **0.925000** | **0.931250** | **0.926414** | 0.677932 |
| + global coreference-interval pack | 114.11 | **0.925000** | **0.931250** | **0.926414** | 0.673584 |

The packing channels add relevant candidates and improve the oracle ceiling, but five-channel equal
RRF does not exploit them. This justifies a separately accepted complete-reranker comparison; it
does not justify a weight sweep, test-qrels run, automatic reranking, or default promotion.

The accepted follow-up ranked the global interval pool with each existing neural scorer
independently. Both runs retained mean pool size 114.11, candidate recall 0.925000, query-hit rate
0.931250, and oracle nDCG 0.926414. MS MARCO reached nDCG 0.701572 and recall 0.790625, versus
0.699656 and 0.803125 for the prior five-score MS MARCO fusion; because scorer composition also
changed, that is not a controlled pool-only comparison. ColBERT reached nDCG 0.734958 and recall
0.800000, exactly matching its prior four-generator top-10 result. Only the ColBERT pair isolates
the added generator, and it shows no change in the reported aggregate top-10 effectiveness
metrics; per-query top-ten identities were not retained for this comparison.

## Fixed train-development ColBERT architecture comparison

The raw dual-profile architecture, unchanged prior whole-document ColBERT strategy, and three
fixed-pool scoring ablations were measured over the same 649 deterministic train-development
queries. No run inspected validation or test qrels, varied a weight, or promoted a default.

| Strategy | Mean pool | Candidate recall | Oracle nDCG@10 | nDCG@10 | MAP@10 | Recall@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Six-generator pool, one whole-title-plus-abstract ColBERT score | 137.47 | 0.954289 | 0.955290 | **0.759619** | **0.719683** | **0.869055** | **0.730180** |
| Six-generator pool, raw max-content ColBERT score only | 137.47 | 0.954289 | 0.955290 | 0.755459 | 0.714034 | **0.870853** | 0.724220 |
| Six-generator pool, raw equal-mean ColBERT title/max-content | 137.47 | 0.954289 | 0.955290 | 0.716835 | 0.668757 | 0.847997 | 0.683461 |
| Six-generator pool, robust equal-mean ColBERT title/max-content | 137.47 | 0.954289 | 0.955290 | 0.655268 | 0.604133 | 0.795095 | 0.618217 |
| Four-generator pool, robust equal-mean ColBERT title/max-content | 126.56 | 0.955059 | 0.955886 | 0.657331 | 0.607033 | 0.795095 | 0.620860 |

The control pool uses BM25, title embeddings, token windows, proper-noun coreference sentences,
nominal-coreference sentences, and global interval packs. ColBERT assigns each candidate one raw
score from title plus full abstract, subject to the service's 512-token right-truncation boundary.
The dual-DP pool instead uses BM25, title embeddings, rewritten nominal-coreference sentences, and
raw 112-target/126-hard nominal-coreference-informed DP embeddings. It separately scores the title
and all raw 510-token DP content views, keeps the maximum content score, robust-normalizes both
channels over the candidate set, and uses their equal mean.

On the exact six-generator pool, multiview scoring changes nDCG by -0.104351, MAP by -0.115549,
recall by -0.073960, and MRR by -0.111963. Candidate and oracle metrics are identical by
construction, while the oracle-to-final nDCG gap expands from 0.195671 to 0.300022. This isolates
the measured loss to the complete multiview scoring bundle rather than candidate availability.

Holding that scorer fixed and replacing the six-generator pool with the four-generator DP pool
changes nDCG by +0.002063, MAP by +0.002899, recall by 0, and MRR by +0.002643. Pool composition
therefore explains none of the observed regression on this split. The ablation still combines
content chunking, maximum aggregation, title separation, robust normalization, and equal fusion;
the original fixed-pool result did not identify one component or justify a sweep.

The two later stepwise ablations separate more of that bundle. Adding a raw title channel with an
equal mean to content-max-only changes nDCG by -0.038623, recall by -0.022856, and MRR by -0.040759.
Applying separate robust normalization to those same two channels before the same equal mean
changes nDCG by a further -0.061568, recall by -0.052902, and MRR by -0.065244. Content-max-only is
within -0.004160 nDCG and +0.001798 recall of whole-title-plus-abstract scoring, but that comparison
still couples title omission, chunking, maximum aggregation, and avoided right truncation. It does
not isolate max aggregation alone. The stale-image preflight from the earlier fixed-pool run and
the whole-document control's disclosed output-recovery execution remain documented in their
artifacts. No strategy was promoted.

## Failure requirements exposed by the leaderboard

- Scientific inference can require several sentences or domain knowledge; resolving references
  before sentence splitting does not supply entailment.
- Biomedical synonymy and aliases are not handled by exact PostgreSQL lexemes or within-abstract
  coreference clusters.
- Directional polarity such as increase versus decrease can be overwhelmed by topical similarity.
- Negation and contradiction require stance-aware evidence assessment; retrieving a relevant paper
  does not determine whether it supports or refutes the claim.

BM25 improves corpus-aware lexical ranking but is not expected to solve inference, synonymy,
polarity, or negation. The four BM25 fusions use one predeclared symmetric protocol: top 50 from
each source, RRF `k=60`, no weights, and cutoff 10. No BM25, vector, or fusion parameter was varied.
Because the public qrels have been examined repeatedly, these are exploratory comparisons, not a
validation boundary for tuning or default promotion.

## Strategy definitions

- Strict: resolve each abstract as a whole, rewrite clusters only when a `PROPN` mention is
  available, split the result into sentences, and search those sentences plus the separate title.
- Nominal: the same flow, but a `NOUN` or `PROPN` may supply the explicit replacement.
- Coreference max: search title and both sentence sets together; use the highest similarity found
  for each document. This does not average or calibrate policy scores.
- Sentence pack: keep the title separate; split before a proposed multi-sentence group exceeds 112
  tokens, with a 126-token hard MiniLM limit; use bounded overlapping token fallback only when one
  sentence is too long.
- Coreference-aware pack: use the same limits, but continue across a soft target boundary when a
  strict proper-noun coreference chain has mentions on both sides; canonicalize only after grouping
  from original offsets. The 126-token limit remains absolute.
- Global coreference-interval pack: enumerate contiguous sentence groups under the same hard limit;
  use dynamic programming to minimize equal-cost proper-noun chain cuts, then squared deviation from
  112 tokens, chunk count, and boundary ordinals. Canonicalize rendered candidates after selecting
  from validated original offsets.
- Token windows: overlapping 126-content-token windows with 32-token overlap over abstract text
  only. The title is one separate representation.
- Original baseline: one truncated title-plus-abstract vector per document.
- Keyword: PostgreSQL English lexemes joined by OR; title weight `A`, abstract weight `B`,
  `ts_rank_cd` normalization 1, and a generated-vector GIN index.
- BM25: raw title and abstract joined with a newline, tokenized by pg_tokenizer's
  `bert_base_uncased` model, and ranked through a VectorChord-BM25 native index. Title and abstract
  are not field-weighted.
- Hybrid RRF: top 50 strict coreference and keyword candidates combined with `k=60`. Parameters are
  fixed rather than tuned on the SciFact test qrels.
- BM25 RRF: top 50 BM25 candidates paired separately with the top 50 token-window, strict,
  nominal, coreference-max, sentence-pack, greedy-coreference-pack, or interval-pack vector
  candidates using the same symmetric `k=60` implementation.
- Incremental packing pools: preserve the existing BM25, token-window, strict, and nominal
  generators and complete scorers, then add exactly one packing generator/scorer as a fifth channel.
- MS MARCO reranker: deduplicate top 50 BM25, token-window, strict, and nominal candidates to at
  most 200 documents, then use only the hosted cross-encoder score over raw query and raw title plus
  abstract. The model and TEI image are pinned, inputs auto-truncate at 512 tokens, and equal scores
  break by `doc_id`.
- Pooled ColBERT: reuse that four-generator deduplicated pool, score every raw title plus abstract
  exactly once with `answerdotai/answerai-colbert-small-v1` through vLLM native MaxSim, explicitly
  right-truncate at 512 tokens, and order by the single ColBERT scorer rank. The image and model
  revision are pinned; no retrieval score or second scorer enters the order.
- Expanded interval-pool rerankers: combine six top-50 generators—BM25, title, abstract-token
  windows, strict coreference, nominal coreference, and global coreference-interval packing—then
  independently score the deduplicated pool with only MS MARCO, ColBERT, or the opt-in RankZephyr
  scorer. The strategies share the pool but never combine scorer outputs.

For the individual coreference policies, every document has one title row. Strict stores 46,167
sentence rows and nominal stores 46,231. The combined search spans 5,183 title rows and both
sentence sets, for 97,581 distinct rows.

Fusion row counts describe searchable surfaces: the existing vector representation rows plus 5,183
document lexical vectors. RRF adds no duplicate document table.

Queries are not passed through FastCoref. Each raw claim is embedded once as one normalized MiniLM
vector. Among the 300 evaluated claims, the maximum is 62 content tokens and the 95th percentile is
39; none are truncated by the 126-content-token boundary. This isolates document representation as
the experimental variable. Query-side coreference can be evaluated later as its own strategy.

Across all 5,183 corpus documents, abstract-only MiniLM token lengths have median 293, p90 472,
p95 539, and maximum 1,921. Title-plus-abstract lengths have median 314, p90 500, p95 565.9, and
maximum 1,937. MiniLM's 126-content-token boundary is exceeded by 5,004 abstracts (96.55%) and
5,073 title-plus-abstract inputs (97.88%). ColBERT's 512-token service boundary covers 4,728
title-plus-abstract inputs within 510 content tokens; 455 (8.78%) may be right-truncated. These
facts motivated the fixed semantic-chunk comparison recorded above.

## Reproduction

```bash
docker compose up -d postgres
docker compose run --rm app ingest --strategy token-window --batch-size 64
docker compose run --rm app ingest --strategy coref-max --batch-size 64
docker compose run --rm app evaluate --strategy token-window --cutoff 10
docker compose run --rm app evaluate --strategy coref-propn --cutoff 10
docker compose run --rm app evaluate --strategy coref-nominal --cutoff 10
docker compose run --rm app evaluate --strategy coref-max --cutoff 10
docker compose run --rm app ingest --strategy keyword --batch-size 256
docker compose run --rm app evaluate --strategy keyword --cutoff 10
docker compose run --rm app ingest --strategy bm25 --batch-size 256
docker compose run --rm app evaluate --strategy bm25 --cutoff 10
docker compose run --rm app evaluate --strategy hybrid-rrf --cutoff 10
docker compose run --rm app evaluate --strategy bm25-token-window-rrf --cutoff 10
docker compose run --rm app evaluate --strategy bm25-coref-propn-rrf --cutoff 10
docker compose run --rm app evaluate --strategy bm25-coref-nominal-rrf --cutoff 10
docker compose run --rm app evaluate --strategy bm25-coref-max-rrf --cutoff 10
docker compose up -d reranker
docker compose run --rm app evaluate --strategy rerank-msmarco --cutoff 10
docker compose up -d late-interaction
docker compose run --rm app diagnose-candidates --strategy pooled-colbert \
  --split train-validation --cutoff 10
docker compose run --rm app evaluate --strategy sentence-pack \
  --split train-validation --cutoff 10
docker compose run --rm app evaluate --strategy coref-aware-pack \
  --split train-validation --cutoff 10
docker compose run --rm app ingest --strategy coref-interval-pack --batch-size 64
docker compose run --rm app evaluate --strategy coref-interval-pack \
  --split train-validation --cutoff 10
docker compose run --rm app evaluate --strategy bm25-sentence-pack-rrf \
  --split train-validation --cutoff 10
docker compose run --rm app evaluate --strategy bm25-coref-aware-pack-rrf \
  --split train-validation --cutoff 10
docker compose run --rm app evaluate --strategy bm25-coref-interval-pack-rrf \
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
docker compose run --rm app evaluate --strategy title-token-window-rrf --split test --cutoff 10
docker compose run --rm app evaluate --strategy bm25-token-window-rrf --split test --cutoff 10
docker compose run --rm app diagnose-candidates --strategy pooled-coref-interval-msmarco \
  --split test --cutoff 10
docker compose run --rm app diagnose-candidates --strategy pooled-coref-interval-colbert \
  --split test --cutoff 10
```

The leaderboard compares retrieval effectiveness, not intrinsic coreference accuracy. No winner is
automatically promoted. ADR-0029 and its fixed Issue #6 comparison separately selected
`pooled-coref-interval-content-max-colbert`; Issue #7 applies it as the shared CLI and composition
default. `title-token-window-rrf` remains selectable as the historical control.
