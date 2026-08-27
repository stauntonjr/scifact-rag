# BM25 solution assessment

- Date: 2026-08-26
- Decision: adapt VectorChord-BM25 into the existing pgvector PostgreSQL image
- Disposition: adapt
- Trigger: measure corpus-aware lexical ranking after native PostgreSQL keyword retrieval
- Stop condition: one independent 300-query evaluation and strict-dense rescue/regression report

## Scope and comparison

The experiment ranks the same 5,183 raw SciFact titles and abstracts at cutoff 10. It must retain
PostgreSQL 17, pgvector 0.8.6, the existing volume, all retrieval strategies, and `token-window` as
the default. It excludes fusion tuning, field weighting, query rewriting, graph retrieval,
scientific inference, reranking, model changes, API/UI work, and a new service.

Options were compared on BM25 semantics, PG17 and AArch64 support, Compose fit, preservation of the
existing database, dependency and license boundary, maintenance evidence, and implementation size.

| Option | Evidence | Disposition |
|---|---|---|
| VectorChord-BM25 plus pg_tokenizer | Native BM25 index, official PG17 multi-architecture suite, English support, current 0.3.0 release | Adapt |
| Direct VectorChord suite replacement | Simplest upstream path, but its pinned release contains pgvector 0.8.2 | Reject because the live database uses 0.8.6 |
| ParadeDB `pg_search` | BM25 plus a broader search engine surface inside PostgreSQL | Defer; disproportionate for one independent ranker |
| PostgreSQL `ts_rank_cd` | Already implemented without another dependency | Retain as `keyword`; it lacks corpus-global statistics |
| Python library or external engine | Many choices exist | Reject for this experiment because it duplicates storage and adds a process boundary |

## Adaptation and provenance

`Dockerfile.postgres` uses two immutable multi-architecture image manifests:

- `pgvector/pgvector:0.8.6-pg17-bookworm@sha256:cf134a767f474095eeba57e0117be8e568e011a63f33fbf252f14c9b760f8e6f`
- `tensorchord/vchord-suite:pg17-20260501@sha256:28a618d3ec820e3e7215b372b69ae9c5d22b5353d1046aa8fc7beb4f14613d74`

Only the pg_tokenizer 0.1.1 and vchord_bm25 0.3.0 libraries and extension SQL/control files are
copied from the suite. The live probe confirmed pgvector remains 0.8.6. The application creates a
single deterministic `bert_base_uncased` tokenizer, tokenizes raw title plus newline plus abstract,
stores one BM25 vector per document, and uses the native index. No corpus-trained tokenizer or
mutable query analyzer was added.

pg_tokenizer is Apache-2.0. VectorChord-BM25 is dual-licensed under AGPLv3 or Elastic License v2.
Both remain external database extensions with separate terms from the MIT application.

## Measured result

The Compose ingest reported 5,183 documents. The pre/post migration counts remained 5,183 canonical
documents and 116,864 dense representation rows, and all 5,183 documents received BM25 vectors.
Across all 300 public BEIR SciFact queries at cutoff 10:

- nDCG: 0.681034
- MAP: 0.631044
- recall: 0.821889
- precision: 0.091000
- MRR: 0.641601
- query-level relevant-document hits: 247; zero hits: 53
- versus strict dense: 25 rescued zero-hit queries and 16 regressed hit queries

This is a strong independent baseline. It does not authorize test-set tuning or automatic default
promotion.

## Fixed fusion follow-up

After reviewing the independent baseline, the owner approved one fusion run with each active
vector approach. The tunable surfaces were explicitly identified before execution:

- BM25 `k1`, `b`, tokenizer, field composition and weighting, and query processing;
- vector model, distance, chunk/window size, overlap, coreference policy, and query processing;
- fusion candidate depth, rank constant, source weights, source set, and output cutoff.

All were frozen. The experiment reused the existing symmetric RRF implementation, top 50
candidates from each source, `k=60`, equal source contribution, and cutoff 10. BM25 configuration,
vector representations, MiniLM, and query processing were unchanged. No grid search or outcome-led
rerun was performed.

| Vector source paired with BM25 | nDCG@10 | MAP@10 | Recall@10 | Precision@10 | MRR@10 | Strict misses rescued | Strict hits lost |
|---|---:|---:|---:|---:|---:|---:|---:|
| Token windows | 0.681985 | 0.627150 | 0.842667 | 0.094333 | 0.634009 | 26 | 8 |
| Strict coreference | 0.692333 | 0.642261 | 0.832222 | 0.093667 | 0.650313 | 22 | 7 |
| Nominal coreference | 0.697360 | 0.648547 | 0.836000 | 0.094000 | 0.655964 | 23 | 7 |
| Coreference max | 0.694381 | 0.644006 | 0.836000 | 0.094000 | 0.652447 | 23 | 7 |

The original table compares each fusion with strict dense retrieval. A separate binary top-10
comparison against standalone BM25 answers whether vector fusion displaces BM25 successes:

| Vector source paired with BM25 | Relevant-query hits | BM25 misses rescued | BM25 hits lost | Net hit change |
|---|---:|---:|---:|---:|
| Token windows | 256 | 13 | 4 | +9 |
| Strict coreference | 253 | 14 | 8 | +6 |
| Nominal coreference | 254 | 14 | 7 | +7 |
| Coreference max | 254 | 14 | 7 | +7 |

Standalone BM25 hits 247 queries. Every frozen fusion therefore improves net top-10 query coverage,
although each loses some queries that BM25 alone retrieves. Token-window fusion is the clearest
ranking tradeoff: it adds nine net hit queries and improves recall, while its lower MAP and MRR
indicate that relevant documents are sometimes placed later.

The results show useful complementarity, but the public qrels have already influenced the sequence
of experiments. They are therefore internal exploratory evidence, not an unbiased validation set.
A parameter change or default promotion requires a new corpus or separately held-out boundary.

## Known limits

BM25 improves term weighting, not scientific reasoning. It does not itself resolve biomedical
synonyms and aliases, combine premises for inference, preserve directional polarity reliably, or
determine whether a document supports versus contradicts a claim. Those requirements remain
separate and need a stance-aware evaluation boundary.

## Primary sources

- VectorChord-BM25 repository, API, limitation, and comparison:
  <https://github.com/supervc-stack/VectorChord-bm25>
- VectorChord-BM25 0.3.0 release:
  <https://github.com/supervc-stack/VectorChord-bm25/releases/tag/0.3.0>
- VectorChord-BM25 dual license:
  <https://github.com/supervc-stack/VectorChord-bm25/blob/main/LICENSE>
- pg_tokenizer repository and Apache-2.0 license:
  <https://github.com/supervc-stack/pg_tokenizer.rs>
- Official suite image build resources and architecture support:
  <https://github.com/tensorchord/VectorChord-images>
