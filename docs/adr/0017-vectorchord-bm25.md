# ADR-0017: VectorChord-BM25 as an independent PostgreSQL strategy

- Status: accepted for experiment; no default-strategy promotion
- Date: 2026-08-26
- Decider: Jack Rory Staunton
- Governing issue: local retrieval-effectiveness decision; no GitHub repository or Issue exists yet

## Context

PostgreSQL keyword retrieval rescues exact lexical matches but lacks corpus-global term statistics
and reaches only 0.531667 recall@10. The owner selected VectorChord-BM25 after asking for a
maintained PostgreSQL BM25 option compatible with one AArch64 DGX Spark and Docker Compose.

The existing database is PostgreSQL 17 with pgvector 0.8.6 and a populated named volume. The
current official VectorChord suite image includes pg_tokenizer 0.1.1 and VectorChord-BM25 0.3.0,
but also pgvector 0.8.2. Replacing the image directly would silently downgrade an installed
extension and was rejected.

## Decision

- Build a pinned multi-stage PostgreSQL image from the existing pgvector 0.8.6 PostgreSQL 17 base.
- Copy only the pg_tokenizer 0.1.1 and VectorChord-BM25 0.3.0 extension artifacts from the pinned
  official multi-architecture VectorChord suite image. Do not install VectorChord's dense index or
  replace pgvector.
- Preserve the existing Compose volume and PostgreSQL major version. Initialize both extensions,
  one `bert_base_uncased` tokenizer, a document BM25 vector, and a native BM25 index idempotently.
- Add `bm25` as an independent strategy over unweighted raw title plus abstract. It does not load
  MiniLM or FastCoref and does not alter keyword, dense, or RRF behavior.
- Convert VectorChord's negative lower-is-better rank to a positive application relevance score;
  filter zero-score nonmatches.
- Keep `token-window` as the CLI default. The initial BM25 run remains independent.
- After the independent result, add four owner-approved pairwise RRF experiments against the active
  vector strategies. Freeze the existing implementation at top 50 candidates per source, `k=60`,
  equal source contribution, and cutoff 10; do not run a parameter sweep.

## Consequences

The populated database retained 5,183 documents, 116,864 dense representation rows, and pgvector
0.8.6. All documents now also have BM25 vectors. The 300-query evaluation reports nDCG@10
0.681034, MAP@10 0.631044, recall@10 0.821889, precision@10 0.091000, and MRR@10 0.641601. BM25
rescues 25 strict-dense zero-hit queries and regresses on 16 strict-dense hit queries.

The application remains MIT. pg_tokenizer is separately Apache-2.0. VectorChord-BM25 is separately
dual-licensed under AGPLv3 or Elastic License v2. Copying their unmodified binaries into the
database image does not relicense those extensions as MIT; image use and distribution must comply
with the selected upstream terms.

The fixed BM25-plus-nominal fusion leads nDCG@10 at 0.697360, while BM25 plus token windows leads
recall@10 at 0.842667. Repeated evaluation on public qrels is not a separate tuning boundary, so
these results remain exploratory and do not promote a default. Fusion parameter changes, field
weighting, tokenizer changes, and scientific query expansion require new decisions. BM25 does not
establish scientific entailment or handle
synonymy, polarity, negation, or contradiction.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| Direct official suite image | Maintained, multi-architecture, all extensions included | Would downgrade pgvector 0.8.6 to 0.8.2 |
| Custom image copying two official extension packages | Preserves the populated PG17/pgvector contract with a narrow dependency boundary | Selected |
| ParadeDB `pg_search` | Broader Elasticsearch-like PostgreSQL search surface | More capability and migration than the independent BM25 experiment needs |
| Native PostgreSQL keyword | No new dependency and already measured | Retained; lacks corpus-global BM25 statistics |
| Python BM25 implementation or separate service | Avoids a PostgreSQL extension | Duplicates indexing/storage and violates the single-Compose-database constraint |

## Verification and revisit trigger

The live integration test checks all three extension versions, preserves pgvector ranking, and
proves BM25 ranking and positive score conversion. The Compose CLI ingests all 5,183 documents and
evaluates all 300 queries at cutoff 10. The four fusion runs change only the selected vector source.
Revisit only for an upstream extension/image upgrade, a PostgreSQL-major migration, a separately
validated parameter or promotion proposal, or evidence that tokenizer behavior is the dominant
failure source.
