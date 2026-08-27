# Keyword and rank-fusion solution assessment

- Date: 2026-08-26
- Decision: adapt PostgreSQL full-text search and published reciprocal-rank fusion
- Disposition: adapt
- Trigger: strict coreference retrieval misses 62 of 300 SciFact queries at cutoff 10
- Stop condition: one keyword-only and one untuned hybrid evaluation on the existing benchmark

## Scope and constraints

The experiment asks whether exact lexical evidence complements the existing strict coreference
dense strategy. It must reuse PostgreSQL 17.11, raw SciFact titles and abstracts, the current CLI
and metrics, and the existing Compose service. It must add no search service, runtime dependency,
custom tokenizer, query-side coreference, reranker, or test-set tuning.

Comparison dimensions were retrieval complementarity, implementation and operating cost,
dependency and license impact, scientific-token handling, score compatibility, and evidence
quality. Primary sources were PostgreSQL 17 documentation and the original RRF publication.

## Options

| Option | Evidence | Disposition |
|---|---|---|
| PostgreSQL `tsvector`/`tsquery` and `ts_rank_cd` | Already deployed; weighted fields, English normalization, cover-density ranking, and preferred GIN indexing are built in | Adapt |
| Symmetric reciprocal-rank fusion | Published rank-only fusion avoids calibrating cosine and lexical scores | Adapt as an experiment |
| PostgreSQL conjunctive plain/web query | Inserts AND between surviving terms | Reject after spike: recall@10 0.069444 |
| BM25 implementations | Add corpus-global term statistics missing from `ts_rank_cd`; deployment options are not yet assessed | Select as the next baseline; defer the implementation choice |
| Custom scientific query tokenizer | Could control identifiers and operators, but creates a parser boundary and tuning surface | Defer |
| Keep strict dense only | Best current aggregate result and simplest production candidate | Retain as the leading experimental strategy |

## Spike evidence

The bounded spike normalized the query with PostgreSQL's `english` configuration, joined surviving
lexemes with the native OR operator, weighted titles `A` and abstracts `B`, and ranked with
`ts_rank_cd(..., normalization=1)`. It used precomputed temporary `tsvector` values and a GIN index;
the retained implementation uses an equivalent stored generated column. All 300 public BEIR
SciFact test queries ran at cutoff 10.

- Keyword-only: nDCG 0.404084, MAP 0.359022, recall 0.531667, precision 0.058667,
  MRR 0.369351.
- Keyword retrieves a relevant document for 13 of the strict dense strategy's 62 zero-hit queries.
- Standard symmetric RRF over top-50 candidates with `k=60`: nDCG 0.608786, MAP 0.558100,
  recall 0.749222, precision 0.083000, MRR 0.572671.
- RRF rescues 16 strict zero-hit queries but loses a hit on 24 queries that strict dense retrieved.
- The diagnostic union of each strategy's top 10 reaches recall 0.825333 over 20 candidates,
  confirming complementarity while leaving final top-10 ordering unresolved.

## Decision and limitations

Implement `keyword` and `hybrid-rrf` as independently selectable experimental strategies. Use a
stored generated vector and GIN index because the corpus is searched repeatedly. Build the OR
query from PostgreSQL-produced lexemes, not a Python tokenizer. Keep the RRF parameters at the
published conventional `k=60`, use 50 candidates from each source, and do not tune against the
SciFact test qrels.

PostgreSQL explicitly notes that its built-in rank functions do not use corpus-global information.
This likely contributes to the weak standalone ranking and motivates the bounded BM25 baseline
below. Reopen the wider engine decision if scientific identifiers are systematically lost by the
English configuration, another corpus is introduced, or a proposed fusion method has a validation
set separate from the reported test qrels.

## Unresolved scientific retrieval requirements

The measured failures expose four requirements that neither document-side coreference nor the
current lexical ranker satisfies:

- **Scientific inference:** some claims express a conclusion or mechanism that is supported only
  by combining context across several sentences, or by domain knowledge connecting the claim to
  the paper. Resolving pronouns makes sentences more explicit but does not perform entailment or
  preserve a multi-sentence chain of premises. Sentence retrieval must therefore retain enough
  surrounding context for a later inference-aware ranker or answer verifier.
- **Synonymy and aliases:** exact keyword matching does not connect acronyms, expanded biomedical
  names, gene and protein aliases, drug names, or terminology at different levels of specificity.
  Coreference clusters mentions within one abstract; they are not a corpus-wide scientific
  synonym system. A later strategy must test domain-aware alias expansion or a scientific semantic
  model without silently rewriting the query.
- **Polarity:** directional predicates such as *increase/decrease*, *activate/inhibit*, and
  *promote/prevent* must affect candidate ordering. The diagnostic queries about N-terminal
  cleavage with opposite directional claims produced the same incorrect leading result, showing
  that topical similarity can dominate the direction of the asserted relationship.
- **Negation:** terms such as *not*, *no*, *without*, and *independent of* must survive retrieval and
  reranking. Document relevance alone does not establish whether evidence supports or contradicts
  a claim, so a later stance- or inference-aware boundary is needed in addition to recall metrics.

These are separate from coreference. FastCoref should not be expanded to claim responsibility for
scientific synonym resolution, logical inference, polarity, or contradiction detection.

## Next lexical baseline: BM25

BM25 is the next lexical experiment because it adds corpus-global inverse-document-frequency and
document-length normalization that PostgreSQL `ts_rank_cd` explicitly lacks. It may improve the
ranking of rare scientific identifiers, but it will not by itself solve scientific inference,
synonymy, polarity, or negation.

The BM25 experiment should remain bounded:

1. Rank the same raw title-plus-abstract documents and evaluate BM25 independently on all 300
   queries at cutoff 10.
2. Report nDCG, MAP, recall, precision, MRR, and rescues among the strict strategy's 62 zero-hit
   queries before attempting fusion.
3. Compare its candidate overlap with strict coreference retrieval and PostgreSQL keyword search.
4. Evaluate a predeclared fusion only if BM25 is complementary; do not tune weights or depth on the
   reported SciFact test qrels.
5. Before implementation, assess maintained PostgreSQL-compatible and standalone BM25 options for
   license, AArch64 support, Compose operating cost, and dependency size. Do not assume a new
   extension or service is justified.

## Primary sources

- PostgreSQL 17 text parsing, weighting, and ranking:
  <https://www.postgresql.org/docs/17/textsearch-controls.html>
- PostgreSQL 17 preferred text-search indexes:
  <https://www.postgresql.org/docs/17/textsearch-indexes.html>
- Cormack, Clarke, and Buettcher, “Reciprocal Rank Fusion Outperforms Condorcet and Individual
  Rank Learning Methods” (SIGIR 2009):
  <https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/>
- Robertson, Walker, Jones, Hancock-Beaulieu, and Gatford, “Okapi at TREC-3”:
  <https://www.microsoft.com/en-us/research/publication/okapi-at-trec-3/>
