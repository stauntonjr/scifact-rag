# ADR-0016: PostgreSQL keyword retrieval and untuned rank fusion

- Status: accepted for experiment; no default-strategy promotion
- Date: 2026-08-26
- Decider: Jack Rory Staunton
- Governing issue: local retrieval-effectiveness decision; no GitHub repository or Issue exists yet

## Context

Strict coreference-sentence retrieval leads the internal SciFact benchmark at recall@10 0.779500,
but 62 of 300 queries retrieve no judged document in the top ten. Several failures contain exact
scientific identifiers that a lexical method could recover. The project already owns PostgreSQL,
so its native full-text search can test that hypothesis without another service or dependency.

Cosine and text-search ranks are not calibrated to each other. Reciprocal-rank fusion is a
published rank-only method that can combine them without treating either score as a probability.
The owner authorized keyword retrieval first and fusion only if lexical results were complementary.

## Decision

- Add `keyword`, operating on raw canonical titles and abstracts rather than coreference output.
- Store an English `tsvector` as a generated column, weight title lexemes `A` and abstract lexemes
  `B`, and add the preferred GIN index.
- Ask PostgreSQL to normalize query text, combine its surviving lexemes with OR, and rank matching
  documents with `ts_rank_cd` normalization option 1. Do not add a Python query parser.
- Add `hybrid-rrf`, combining the top 50 strict dense and keyword candidates with
  `score(d) = sum(1 / (60 + rank_i(d)))` and returning the ten highest fused ranks.
- Keep strategy scores explicitly strategy-specific while preserving document IDs, result fields,
  citations, and all existing strategies.
- Keep `token-window` as the CLI default. Do not tune fusion on the reported test qrels or promote a
  strategy automatically.

## Consequences

Keyword-only retrieval is inexpensive, interpretable, and rescues 13 strict zero-hit queries, but
its aggregate recall is only 0.531667. RRF confirms complementarity by rescuing 16 strict misses,
but it also loses 24 prior hit queries and lowers recall to 0.749222. The experimental strategies
therefore document a candidate-generation opportunity rather than a ranking improvement.

Canonical document rows may now have a null legacy embedding because active dense retrieval uses
the strategy-aware representation table. Existing embeddings are retained during keyword-only
upserts. The generated text vector and GIN index add storage and PostgreSQL-specific schema, but no
runtime process or package.

The experiment also establishes unresolved requirements rather than assigning them to
coreference: scientific inference across context, biomedical synonym and alias handling,
directional polarity, and explicit negation or contradiction. The current BEIR retrieval metrics
measure whether a judged document is retrieved; they do not prove that the selected evidence
entails rather than contradicts the claim.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| Keep strict dense only | Best current nDCG and recall | Retained, but does not test lexical complementarity |
| Conjunctive PostgreSQL query | Full spike recall 0.069444 | Scientific claims contain too many terms for an all-term match |
| Direct score averaging | Cosine and `ts_rank_cd` have unrelated scales | Would require calibration |
| BM25 extension or standalone implementation | Adds corpus-global term statistics missing from `ts_rank_cd` | Selected as the next lexical baseline, with implementation choice deferred pending a bounded solution assessment |
| Tune RRF weights/depth on SciFact test qrels | Could improve the reported number | Rejected as test-set overfitting |

## Verification and revisit trigger

Run the public 300-query evaluation at cutoff 10 for `keyword` and `hybrid-rrf`, preserve rescue and
regression counts, and keep focused PostgreSQL and deterministic RRF tests. Revisit fusion only with
a separate validation boundary or a new corpus. Revisit the lexical engine if analysis shows that
PostgreSQL normalization—not ranking—is the dominant source of missed scientific identifiers.

The next lexical experiment is independent BM25 over raw titles and abstracts. Benchmark it before
fusion, record which strict misses it rescues, and do not promote or tune it from the public test
qrels alone. Scientific inference, synonymy, polarity, and negation require separate retrieval or
reranking designs and a stance-aware evaluation boundary; BM25 is not treated as their solution.
