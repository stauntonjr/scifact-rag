# Evidence Inference source and rights qualification

Date: 2026-09-18. Governing work: [Issue #19](https://github.com/stauntonjr/scifact-rag/issues/19).

This bounded audit follows the [coordinate qualification](evidence-inference-coordinates.md).
It examines only its 45 candidate training articles, 195 prompts and 351 qualifying annotation
rows. It changes neither the original admission result nor the coordinate contract. No new
sample, heldout outcome inspection, model call, training or Lattice change occurred.

## What the provenance establishes

The benchmark archive remains SHA-256
`6abe0d4ec0d331834981c0171c3c79d47515761867f82f1dc6066e43863a1586`.
The publisher repository is pinned to
`a661e8c14f973398380c8865cf2f27a535aaaf6d`. Its
[annotation documentation](https://github.com/jayded/evidence-inference/blob/a661e8c14f973398380c8865cf2f27a535aaaf6d/annotations/README.md)
declares XML and TXT representations paired by PMCID, with TXT produced by preprocessing XML.
All 45 candidate pairs were acquired from that revision and hashed. No publisher code was executed.

None of the 45 archive TXT files equals the paired repository TXT in raw bytes. **38 match
exactly in the already qualified LF coordinate view; seven do not.** All 45 XML records contain
the expected PMCID. The audit checks acquired file hashes, sizes, paths and pinned URLs; it also
checks the frozen archive, coordinate manifest and candidate-ID digests before classifying rights.
It never accepts whitespace folding, Unicode normalization, fuzzy equality or relocation.

For the 38 matching texts, the evidence supports **publisher-declared pairing with exact
coordinate-view identity**. It does not establish an exact historical PMC version or a reproduced
XML-to-TXT extraction. The historical extraction involves upstream text-repair dependencies whose
exact generating runtime has not been established. A PMCID and current PMC metadata alone cannot
fill that gap. The seven remaining text differences are source-linkage failures, regardless of
what license their paired XML declares; no license is transferred to them by guesswork.

## Rights screen and reuse scope

The screen reads article-level permissions from `front/article-meta`, including nested license
links and explicit versioned Creative Commons URLs in prose. It retains attribution metadata,
copyright statements, complete permission statements, source hashes and links in an ignored local
manifest. A data-only CC0 clause does not relicense the article and is kept separate from its
article license. Missing, custom or conflicting terms do not become an unrestricted grant.

The first proposed subset uses only versioned CC BY article terms with the matching publisher-pair
provenance above. For example, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) allows sharing
and adaptation subject to attribution, license linkage and change notices; earlier license versions
are retained as written, not silently upgraded. Any later distributed fixture must carry the
applicable author/title/source, copyright and license notices, describe representation changes,
and respect separately credited third-party exclusions. This report publishes counts and source
identities, not article text or a newly licensed corpus.

Noncommercial and ShareAlike cases remain a separate conditional pool. NoDerivatives, custom,
missing and conflicting terms remain unresolved in this screen. These are conservative project
selection rules, not a claim that such articles forbid every local research use. In particular,
[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) restricts distribution of
modified material; its terms should not be paraphrased as a blanket ban on analysis.

The publisher's [MIT software license](https://github.com/jayded/evidence-inference/blob/a661e8c14f973398380c8865cf2f27a535aaaf6d/LICENSE)
does not replace third-party article terms. This issue screens article sources; it makes no new
blanket licensing claim for benchmark annotations or extracted evidence quotations.

## Result

The classifications below are mutually exclusive. Source-linkage failures take precedence over
rights categories. Article counts sum to 45, prompts to 195 and qualifying rows to 351.

| Candidate classification | Articles | Prompts | Rows |
|---|---:|---:|---:|
| Versioned CC BY and matching publisher-pair provenance | 20 | 101 | 181 |
| Conditional noncommercial terms, including ShareAlike | 12 | 47 | 91 |
| Custom or missing terms | 4 | 26 | 48 |
| NoDerivatives terms | 2 | 7 | 11 |
| Unresolved text/source linkage | 7 | 14 | 20 |

**20 articles and 101 prompts form the proposed first pool.** No model-performance labels were
used to rank candidates or enlarge that pool. The detailed local manifest retains exact article
and prompt IDs for every classification, including all excluded cases. The seven mismatched
articles and 18 other rights-constrained articles remain outside the first pool.

## Reproduction and retained evidence

The [machine-readable summary](evidence-inference-provenance-summary.json) is generated by
`tools/evidence_inference_provenance.py`. All inputs and the detailed attribution/decision manifest
remain under ignored `artifacts/evidence-inference-v2/`; public output contains no article text.
The acquisition manifest records each pinned URL, SHA-256 and byte count. Reproduction uses:

```sh
python3 tools/evidence_inference_provenance.py \
  artifacts/evidence-inference-v2/admission-20260917/v2.0.tar.gz \
  --coordinates artifacts/evidence-inference-v2/coordinate-20260918/coordinate-manifest.json \
  --source-dir artifacts/evidence-inference-v2/provenance-20260918 \
  --summary /tmp/evidence-inference-provenance-summary.json \
  --manifest /tmp/evidence-inference-provenance-manifest.json
```

## Decision and next boundary

The useful next step is a prospective Step 2 protocol built from the attribution-only candidate
pool, accepting its explicitly limited publisher-pair provenance. It must freeze article-grouped
prompt IDs, reader/runtime identity, three context arms, output validation, metrics and a concrete
compute cap before dispatch. No new sample is needed simply to fill the earlier maximum of 128
prompts; a smaller defensible pool is preferable to silently relaxing inclusion.

This audit is training-side development qualification, not confirmation, a corpus-wide rights
determination or a result about scientific inference. A later experiment can inform Lattice's
evidence/role fidelity hypothesis, but it does not alter Lattice's active native baseline or establish
learned latent state. Step 2 remains a separate accepted protocol and execution decision.
