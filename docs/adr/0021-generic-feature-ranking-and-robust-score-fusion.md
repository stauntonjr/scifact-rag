# ADR-0021: Generic feature ranking and robust score fusion

- Status: accepted
- Date: 2026-08-26
- Decider: Jack Rory Staunton, human owner
- Governing issue: local retrieval-effectiveness decision; no GitHub repository or Issue exists

## Context

ADR-0020 separated candidate generation, complete candidate scoring, and rank aggregation. The
first aggregator used only scorer ranks through equal reciprocal-rank fusion. It deliberately
discarded incomparable raw-score magnitudes, but the frozen validation result left a large gap
between actual and oracle nDCG. The owner requested a generic scoring architecture and robust
normalized score fusion without special handling for SciFact content.

Observed evidence is limited to the existing four complete corpus-global score channels over one
deduplicated candidate pool. Their raw BM25 and cosine scores have different scales and
distributions. The 160-query validation partition is frozen; the repeatedly inspected 300-query
test qrels are not a selection boundary. No evidence supports learned weights, calibration as
probabilities, or a new retrieval channel.

## Decision

- Materialize every completely scored pool as an immutable candidate feature matrix. Each row
  contains one feature per scorer channel with raw score, scorer rank, representation, matched
  passage, and passage ordinal. Generation signals remain separate provenance and never enter the
  matrix.
- Separate feature-matrix construction, score normalization, and setwise ranking policy behind
  application ports. Existing RRF consumes the same complete matrix without normalization.
- Add one query-local robust normalizer. For each channel:
  - a constant channel maps every value to `0.5`;
  - otherwise compute median `m` and median absolute deviation `MAD`;
  - when `MAD > 0`, transform `z = 0.6744897501960817 * (score - m) / MAD` through the logistic
    function;
  - when `MAD = 0` but values differ, use a deterministic tied-midrank empirical CDF in `[0, 1]`.
- Add an equal-score fusion policy that averages every channel's normalized score. It has no
  weights, threshold, learned parameter, corpus statistic, or domain-specific feature.
- Expose only `pooled-four-channel-robust-sum`, using the existing BM25, token-window,
  strict-coreference, and nominal-coreference generators and complete scorers.
- Keep all existing strategies and the `token-window` default unchanged. Do not add an MS MARCO
  normalized variant, train a learning-to-rank model, sweep normalization choices, access the test
  qrels, or promote the strategy when the frozen gate is not met.

The normalized values are bounded comparison features, not relevance probabilities or confidence
calibration.

## Consequences

### Positive

- Future graph, late-interaction, learned-sparse, or stance scorers can add a provenance-bearing
  feature without changing candidate generation or the ranking-policy contract.
- Fixed fusion policies, future learned ranking, and diagnostics can inspect the same explicit
  feature rows.
- The robust transform retains score magnitude when median dispersion exists while bounding
  outliers and handling sparse or constant channels deterministically.
- Existing RRF behavior remains available through the same feature matrix.

### Negative

- Query-local normalization makes a document's normalized score dependent on the candidate pool.
- The empirical-CDF fallback preserves order rather than magnitude when more than half the channel
  values collapse at the median.
- Equal normalized fusion still assumes every channel deserves one equal contribution.
- The feature matrix duplicates a small amount of in-memory scorer provenance for at most 200
  candidates per query.

### Risks and mitigations

- An incomplete row could silently bias fusion: the matrix builder and every ranking policy reject
  missing, duplicate, non-finite, non-positive-rank, or duplicate-document features.
- Generation scores could be counted again: only non-generation scorer signals become features.
- Bounded scores could be mistaken for probabilities: code and documentation call them normalized
  features and make no probability or calibration claim.
- Generic architecture could expand ahead of product evidence: this slice adds one normalizer, one
  policy, and one opt-in composition without a dependency, schema, service, model, or new channel.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| Keep RRF only | Stable and scale-independent | Discards all score-spacing information |
| Min-max normalization | Dependency-free and bounded | One outlier controls the full channel range |
| Mean and standard-deviation normalization | Familiar | Sensitive to the score outliers this experiment is intended to bound |
| Rank-percentile fusion only | Deterministic | Repeats RRF's loss of magnitude whenever dispersion is usable |
| LambdaMART now | General learning-to-rank architecture | Requires a separate training, feature-governance, and overfitting decision |
| Add a normalized MS MARCO variant | Existing scorer is available | Expands the fixed experiment and GPU/model boundary without owner request |

## Measured validation result

On the frozen 160-query validation partition, robust four-channel fusion reached nDCG@10
`0.688954`, MAP@10 `0.645051`, recall@10 `0.806250`, precision@10 `0.092500`, and MRR@10
`0.661119`. It improves the same pool's equal RRF nDCG from `0.683622` without changing recall, but
does not beat the BM25-plus-token-window leader at nDCG `0.707033` and recall `0.809375`.

The promotion gate therefore rejects a test confirmation and default change. The architecture and
negative result remain useful for later independent scoring policies.

## Verification and revisit trigger

Focused tests must cover complete feature provenance, exclusion of generation signals, unchanged
RRF ordering, median/MAD logistic behavior, zero-MAD and constant fallbacks, equal averaging,
invalid-matrix rejection, strategy selection, and the repository gate. Independent review must
confirm the frozen validation evidence and absence of excluded changes.

Revisit the normalization contract only with a separately declared comparison; revisit equal
fusion when a learned ranker or calibrated scorer has a protected training/validation design; and
supersede this ADR if future scorers require cross-candidate features that cannot be represented by
the current immutable matrix.
