# ADR-0022: Hosted ColBERT late-interaction scoring

- Status: accepted for experiment; no default-strategy promotion
- Date: 2026-08-26
- Decider: Jack Rory Staunton, human owner
- Governing issue: local retrieval-effectiveness decision; no GitHub repository or Issue exists

## Context

ADR-0020 established a broad, feature-preserving candidate pool. ADR-0021 showed that robust
normalization recovers only a small fraction of the gap between actual and oracle nDCG. The owner
then selected late interaction as the next generic scoring family.

The existing pool averages 105.97 documents, reaches validation recall 0.906250, and has oracle
nDCG@10 0.907664. A ColBERT-style scorer preserves contextual token vectors and uses MaxSim at
scoring time, offering more query-document interaction than one-vector MiniLM without the full
joint encoding cost of a cross-encoder.

The selected model and serving boundary are ecosystem-provided. Implementing token projection,
masking, query expansion, MaxSim, batching, or a model server in this application would be
disproportionate.

## Decision

- Add `pooled-colbert` as an opt-in strategy over the unchanged top-50 BM25, token-window,
  strict-coreference, and nominal-coreference generators.
- Score every deduplicated candidate exactly once using only
  `answerdotai/answerai-colbert-small-v1`, pinned to revision
  `c72aa89bc61afdd85373643f3a1a75b2aad6e0fe`.
- Serve the checkpoint through native vLLM `HF_ColBERT` MaxSim scoring in the digest-pinned NVIDIA
  26.06 ARM64 image on loopback port 8082. The application adds only an HTTP adapter and no Python
  dependency.
- Send the unchanged query and raw title plus abstract. Explicitly right-truncate at the model's
  512-token boundary; do not silently claim full-abstract coverage.
- Preserve the ColBERT raw score in the complete feature matrix. Use the existing one-channel RRF
  rank policy for final ordering; because there is one scorer, it is monotonic with ColBERT rank
  and mixes no retrieval score.
- Keep `token-window` as the default. Do not add a ColBERT index, fusion variant, learned weight,
  model sweep, training run, test-qrels run, graph channel, or semantic chunker in this decision.

## Consequences

### Positive

- Adds a materially different generic scorer without changing candidate generation or storage.
- Reuses maintained model and serving implementations rather than recreating MaxSim.
- Leaves raw scorer provenance available to later diagnostics and ranking policies.
- The selected 33.4M-parameter model is small relative to the active generator and coexists on the
  DGX in the measured environment.

### Negative

- Requires a third local model service and scores roughly 106 full documents per query.
- Explicit right truncation can lose tail evidence for 455 of 5,183 title-plus-abstract inputs.
- Single-channel RRF exposes a rank-derived result score even though ColBERT raw scores remain in
  the internal feature matrix.
- Stronger nDCG does not eliminate failures involving scientific entailment, polarity, negation,
  contradiction, or multi-sentence inference.

### Risks and mitigations

- Mutable artifacts could invalidate comparison: pin both the image digest and model revision and
  verify live identity, architecture, model length, and health.
- Long abstracts could be rejected or silently truncated: send explicit 512-token right truncation
  and report the measured length distribution.
- Repeated evaluation could tune the benchmark: use one model and one frozen validation result,
  with no parameter sweep or test confirmation when the recall guardrail fails.
- A new scorer could trigger unbounded fusion work: retain it independently and require a separate
  decision for any fusion.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| AnswerAI ColBERT small through vLLM | Native MaxSim serving, Apache-2.0 model, 33.4M parameters, published SciFact 0.7477 | Selected |
| Canonical ColBERTv2 | Mature reference implementation | Larger and lower published SciFact score |
| Sentence Transformers 6 in-process | First-party `MultiVectorEncoder` implementation | Requires an unrelated Transformers 5 application migration |
| TEI or Infinity token embeddings | Maintained serving projects | No selected native scorer contract comparable to vLLM `/rerank` |
| Bespoke server or MaxSim implementation | Full local control | Duplicates maintained model semantics and serving behavior |
| Semantic chunking first | Could improve coherent context and long-document coverage | Valuable next experiment, but does not test the requested scoring family |
| Keep prior rankers only | Lowest complexity | Leaves the measured ranking bottleneck unaddressed |

## Measured result

The live service loaded vLLM 0.22.1, resolved `HF_ColBERT`, used float16 on CUDA, reported a
512-token model length, and returned the expected relevance order. On the frozen 160-query
validation partition, `pooled-colbert` reached nDCG@10 0.734958, MAP@10 0.707396, recall@10
0.800000, precision@10 0.091875, and MRR@10 0.722569.

It leads validation nDCG, MAP, and MRR, but recall falls 0.009375 below the BM25-plus-token-window
guardrail. The strategy remains selectable; the default and test split remain unchanged.

## Verification and revisit trigger

Focused checks cover request contents, response reordering and validation, one complete ColBERT
feature per pooled candidate, independent strategy selection, and unchanged existing rankers. Live
checks verify image/model identity, `HF_ColBERT`, health, MaxSim ordering, and the frozen validation
result. The repository full gate and independent review bind the final candidate.

Revisit after a separately specified semantic-chunk comparison, a held-out fusion design, a model
or runtime revision, material GPU contention, or evidence that long-document tail loss explains
the recall regression.
