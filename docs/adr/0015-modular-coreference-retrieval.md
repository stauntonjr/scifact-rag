# ADR-0015: Modular coreference-sentence retrieval

- Status: accepted for experiment; no default-strategy promotion
- Date: 2026-08-26
- Decider: Jack Rory Staunton
- Governing issue: local retrieval-effectiveness decision; no GitHub repository or Issue exists yet

## Context

ADR-0014 established overlapping MiniLM token windows as the accepted default after improving the
original one-vector SciFact baseline. The next bounded hypothesis is that resolving references over
an entire abstract before sentence splitting will make individually embedded sentences more
self-contained. The owner requested two canonicalization policies and a max-score comparison,
while preserving each approach as a separately selectable strategy.

Queries remain an independent control: each raw SciFact claim is embedded once by MiniLM and
normalized. Across the 300 evaluated claims, the maximum was 62 content tokens, the 95th percentile
was 39, and none exceeded the 126-content-token boundary. Query-side coreference is therefore not
needed for truncation and is excluded so the experiment changes only document representation.

## Decision

- Add a representation-strategy port and keep `token-window` as the CLI default.
- Add `coref-propn`, which rewrites a cluster only when it contains a proper-noun candidate.
- Add `coref-nominal`, which permits a common noun or proper noun as the explicit candidate.
- Add `coref-max`, which searches title, strict sentences, and nominal sentences together and uses
  the maximum representation similarity as the document score.
- Resolve an abstract once, apply the selected project-owned policy, then split the resolved text
  into sentences. Embed the title independently and retrieve it in parallel with sentences.
- Load FastCoref lazily during coreference ingestion. Existing search and evaluation calls operate
  only on stored vectors.
- Store rows in `document_representations`, keyed by document, representation, and ordinal. Replace
  only the representations being ingested so all strategies can coexist. Preserve the legacy table
  and perform no destructive migration.
- Keep returned results and citations at document granularity.

## Measured result

All measurements use 5,183 SciFact documents, the same MiniLM model, PostgreSQL/pgvector cosine
search, all 300 public BEIR queries, and cutoff 10.

| Strategy | Rows | Rows/doc | nDCG | MAP | Recall | Precision | MRR |
|---|---:|---:|---:|---:|---:|---:|---:|
| `coref-propn` | 51,350 | 9.907 | 0.618163 | 0.561557 | 0.779500 | 0.086000 | 0.574435 |
| `coref-nominal` | 51,414 | 9.920 | 0.617592 | 0.561789 | 0.773944 | 0.085667 | 0.576190 |
| `coref-max` | 97,581 | 18.827 | 0.613820 | 0.557553 | 0.772833 | 0.085333 | 0.570774 |
| `token-window` | 19,283 | 3.720 | 0.601929 | 0.556945 | 0.727944 | 0.081000 | 0.568218 |

Strict proper-noun resolution leads nDCG, recall, and precision. Broader nominal resolution is
close and slightly leads MAP and MRR. Max-score fusion underperforms both, demonstrating that a
maximum over more representations can introduce false-high matches rather than combine evidence.

## Consequences

The coreference strategies materially improve retrieval over token windows, but require roughly
2.7 times as many rows for an individual policy and roughly 5.1 times as many for the fused search.
The lock grows from 75 to 122 packages and the image from 10.69 GB to 11.71 GB. The general-domain
coreference model may also make biomedical errors that aggregate retrieval metrics do not explain.

This result does not promote a new default. `token-window` remains simpler, cheaper, and accepted.
A promotion decision should separately weigh retrieval gain, ingestion cost, search latency,
dependency size, and representative error analysis. Query-side coreference, score calibration,
reranking, and a generic evaluation framework remain out of scope.
