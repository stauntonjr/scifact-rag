# ADR-0014: Bounded token-window retrieval

- Status: accepted
- Date: 2026-08-26
- Decider: Jack Rory Staunton
- Governing issue: local retrieval-effectiveness decision; no GitHub Issue exists yet

## Context

The first SciFact implementation embedded each title and abstract as one normalized MiniLM vector.
`paraphrase-MiniLM-L6-v2` accepts at most 128 tokens, while almost every relevant SciFact abstract
exceeds that limit. The public 300-query BEIR evaluation established this baseline at cutoff 10:

- nDCG: 0.526066
- MAP: 0.477665
- recall: 0.661722
- precision: 0.073000
- MRR: 0.495447

A read-only experiment compared that baseline with overlapping token windows using the same model,
corpus, queries, qrels, and cosine scoring. It encoded at most 126 content tokens per window with a
32-token overlap and used the best window score as the document score. The experiment improved
nDCG to 0.601929 and recall to 0.727944. It rescued 32 baseline misses at cutoff 10 and regressed
13 baseline hits, so the full benchmark—not selected examples—remains the acceptance oracle.

## Decision

- Split title-plus-abstract text into 126-token windows with a 32-token overlap inside the MiniLM
  adapter. The adapter owns this boundary because tokenization and maximum input length are
  model-specific.
- Store windows in a `document_chunks` table keyed by document ID and ordinal while preserving one
  canonical document row for returned title, abstract, and citation identity.
- Rank documents by the minimum cosine distance across their windows. Return each document at most
  once and keep the existing document ID as the citation contract.
- Re-ingestion replaces every chunk belonging to each ingested document, so configuration changes
  cannot leave stale windows for that document.
- Activate `product-validation-challenges` with 12 public-qrels queries that the baseline missed
  and the accepted window strategy retrieved at cutoff 10. The complete 300-query evaluation stays
  authoritative and guards against tuning only to those cases.
- Keep MiniLM, pgvector, the CLI, composition root, generator, and dependency set unchanged.

This supersedes ADR-0013 only where it selected one vector per abstract and kept product challenges
inactive. Its interface, composition, grounding, and generator decisions remain accepted.

## Consequences

### Positive

- Later abstract content can affect retrieval instead of being silently truncated.
- The measured pgvector path improves every reported retrieval metric at cutoff 10.
- Search and answer results remain document-level, so existing citations and CLI JSON retain their
  meaning.
- The challenge corpus is small, deterministic, and derived from real benchmark failures.

### Negative

- The SciFact corpus grows from 5,183 document vectors to 19,283 chunk vectors, an average of 3.72
  vectors per document.
- Ingestion embeds more text and exact search aggregates more rows.
- Max-window scoring can promote a locally similar passage even when the full abstract is less
  relevant; the 13 observed regressions remain visible in full-benchmark evidence.

## Alternatives considered

| Alternative | Disposition |
|---|---|
| Keep one truncated vector | Rejected because the measured window strategy materially improves nDCG and recall |
| Sentence splitting | Deferred because token windows match the model limit directly without a new sentence-boundary dependency |
| Hybrid lexical/vector retrieval | Deferred until token windows stop producing useful gains |
| Cross-encoder reranking or a new embedding model | Deferred because it adds model and runtime scope before the existing MiniLM boundary is exhausted |

## Verification and revisit trigger

The actual Compose/PostgreSQL path contains 5,183 documents and 19,283 chunks. Evaluation over all
300 BEIR test queries at cutoff 10 reports nDCG 0.601929, MAP 0.556945, recall 0.727944, precision
0.081000, and MRR 0.568218. All 12 retained challenge queries retrieve at least one qrel document
in the top ten.

Revisit if a later full benchmark loses recall, the average exceeds four chunks per document,
latency becomes material, or a proposed retrieval model makes this model-specific windowing
unnecessary.
