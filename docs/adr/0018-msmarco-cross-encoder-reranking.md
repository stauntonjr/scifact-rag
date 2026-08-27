# ADR-0018: Pinned MS MARCO cross-encoder reranking experiment

- Status: accepted for experiment; no default-strategy promotion
- Date: 2026-08-26
- Decider: Jack Rory Staunton
- Governing issue: local retrieval-effectiveness decision; no GitHub repository or Issue exists yet

## Context

VectorChord-BM25 and the dense representations retrieve complementary SciFact documents. Fixed RRF
improves net top-10 query coverage, but each fusion also loses some queries retrieved by standalone
BM25, and early-rank metrics do not consistently improve. A standard second-stage cross-encoder can
score the broad candidate union directly without introducing graph construction or a new retrieval
service.

The public qrels have already influenced several experiments. The next result is therefore
exploratory. The owner selected the standard MS MARCO MiniLM reranker, required it to be served on
the DGX GPU after an in-process CPU run remained incomplete at 417.39 seconds, and explicitly
deferred graph work.

## Decision

- Add `rerank-msmarco` as a separately selectable ingest, search, ask, and evaluate strategy.
- Reuse top 50 candidates from each existing BM25, token-window, strict-coreference, and
  nominal-coreference retriever. Deduplicate by `doc_id` for a maximum of 200 documents.
- Rank the union only with `cross-encoder/ms-marco-MiniLM-L6-v2`, pinned to immutable revision
  `233902d25c440f23af6f7d6e94d2946bac0bee0a`.
- Serve the model through Hugging Face TEI's digest-pinned DGX Spark `sm_121` ARM64 GPU image and
  native `/rerank` API on a separate Compose service. The application retains only a small HTTP
  adapter and adds no Python dependency.
- Score the raw query paired with raw title plus newline plus abstract. Keep the model's fixed
  512-token boundary, TEI's token-aware batching with a maximum client batch of 256, and
  deterministic `doc_id` tie-breaking.
- Do not combine retrieval scores with cross-encoder scores, calibrate scores, tune candidate depth,
  sweep models, rewrite queries, train a reranker, or promote a new default.
- Keep `token-window` as the default. Defer NER, triple extraction, knowledge-graph construction,
  graph querying, and graph retrieval.

## Consequences

### Positive

- Tests the clearest standard reranking baseline against the broadest already implemented recall
  surface.
- Adds no package, service, database schema, or stored representation beyond those already used.
- Preserves each first-stage retrieval approach as an independent strategy.

### Negative

- Scores up to 200 query-document pairs per request and requires a separately running GPU service.
- A general MS MARCO model may not capture scientific entailment, biomedical synonymy, polarity,
  negation, or contradiction.
- Title-plus-abstract inputs beyond 512 model tokens are truncated rather than chunk-reranked.

### Risks and mitigations

- Repeated public-qrels use can overfit decisions: run once, record the result regardless of
  outcome, and forbid tuning or promotion from this boundary.
- Mutable runtime or model artifacts would weaken reproducibility: pin both the TEI image digest
  and full model revision and record their Apache-2.0 provenance.
- Broader graph work could obscure the reranker result: keep all graph surfaces explicitly
  deferred.

## Measured result

The digest-pinned TEI service loaded `FlashBert` on CUDA and remained healthy. The single completed
300-query run took 87.91 seconds and reported nDCG@10 0.686962, MAP@10 0.642502, recall@10
0.806556, precision@10 0.090333, and MRR@10 0.658184. It establishes a new MRR leader but ranks
fourth by nDCG and lowers recall versus standalone BM25 and all fixed BM25-vector fusions.

This mixed result retains the strategy for comparison but does not promote it. The TEI backend's
logged GeLU-tanh approximation is accepted as part of this pinned serving experiment; comparing an
exact Transformers backend would be a new run and decision.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| MS MARCO MiniLM L6 cross-encoder | Official standard query/passage ranker; small Apache-2.0 checkpoint | Selected |
| Hugging Face TEI | Native rerank API and official DGX Spark ARM64 GPU image | Selected after live compatibility probe |
| Bespoke SentenceTransformers HTTP server | Would reuse the local Python model path | Duplicates maintained TEI serving, batching, and health behavior |
| vLLM | Existing DGX generator-serving pattern | Wrong model class for a BERT sequence-classification reranker |
| MedCPT cross-encoder | Biomedical PubMed search-log training | Defer until a separately justified domain-model comparison |
| BGE or Qwen reranker | Maintained Apache-2.0 models with broader capabilities | Larger and introduces more experimental choices |
| RRF tuning | Existing fixed fusion already measured | Would tune on repeatedly inspected public qrels |
| Graph reranking | Could represent entities and relations | Explicitly deferred; requires new contracts and evaluation |

## Verification and revisit trigger

Focused tests prove composite ingestion, fixed source limits, document deduplication, final score
ordering and validation, and the TEI HTTP contract. A live endpoint probe must show CUDA model
loading, correct relevance ordering, and health before one Compose-path evaluation covers all 300
public queries at cutoff 10 and records elapsed time. Revisit only with an independent evaluation
boundary, a material upstream runtime/model change, a need for long-document handling, or an
owner-approved graph capability decision.
