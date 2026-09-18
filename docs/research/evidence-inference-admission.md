# Evidence Inference 2.0 admission

Date: 2026-09-17 (America/New_York). Governing work: [Issue #15](https://github.com/stauntonjr/scifact-rag/issues/15).

**Decision: not admitted under the approved exact-grounding contract.** Step 1 is complete as a
negative admission result; Step 2 is not activated. The sample has zero exact spans under the
archive's documented coordinates. A plausible newline/end-index explanation is retained as a
diagnostic, not silently adopted. No model calls, training, heldout outcome inspection, source
repair, or Lattice changes occurred.

## Source and reproducibility

The [publisher website](https://evidence-inference.ebm-nlp.com/) explicitly links `v2.0.tar.gz`
as its current Evidence Inference 2.0 release. The acquired archive is 36,528,800 bytes, SHA-256
`6abe0d4ec0d331834981c0171c3c79d47515761867f82f1dc6066e43863a1586`.
The archive itself retains a historical README referring to v1.1 patches, so its filename alone
does not reconcile release differences.

Retained local artifacts are ignored under `artifacts/evidence-inference-v2/admission-20260917/`:
archive, every-member hashes and split IDs in `source-manifest.json`, selected IDs, and separate
PMC metadata responses and license audit. No article or evidence text is committed. The published
[summary](evidence-inference-admission-summary.json) contains counts, policy and hashes only.

Run with Python 3.12 from the repository root, after acquiring the exact publisher archive into a
fresh ignored directory and checking its SHA-256:

```bash
python3 tools/evidence_inference_admission.py \
  artifacts/evidence-inference-v2/admission-20260917/v2.0.tar.gz \
  --summary /tmp/evidence-inference-admission-summary.json \
  --manifest /tmp/evidence-inference-source-manifest.json
```

The script reads tar members without extracting paths. It hashes all regular files as bytes,
reads split IDs and merged-CSV identities for inventory, and only inspects outcome fields and
article text for the selected training sample. Because upstream combines splits in CSV files,
CSV parsing transiently traverses other rows; their outcomes are not aggregated, displayed or used
in decisions. Heldout article text is not decoded. Selection is the lowest 64 SHA-256 values of
`ei-admission-v1:<native numeric PMCID>`, before observing content quality.

## Corpus and partition findings

The archive has 4,454 article text files, no XML, and no license/provenance files. Its combined
split lists contain 3,562 train, 443 validation and 449 test IDs, with no duplicate or intersecting
IDs. These lists describe available texts, not necessarily annotated articles.

There are 3,372 prompt-bearing article IDs; 24 have no text, and 1,106 text files have no prompts.
There are 29 prompt rows outside the supplied combined splits. Preserve these exceptions rather
than rebuilding splits. The publication describes 12,616 prompts over 3,346 articles; the acquired
archive differs and must not be presented as a byte-identical realization of those statistics.
[Publication](https://aclanthology.org/2020.bionlp-1.13/).

## Bounded training audit

Of the 64 selected training articles, 47 have prompts and 17 do not; together they contain
209 prompts and 390 annotation rows. Repeated rows from
the same doctor/prompt can represent separate evidence spans; they are not automatically duplicate
labels. The summary retains annotation-level label counts, verification flags, prompt disagreement,
missing evidence, role multiplicity and article lengths separately.

All 64 texts contain CRLF. The release README specifies inclusive start and end offsets and
`-1/-1` for unavailable spans. On unchanged UTF-8 publisher text:

- 374 rows have in-range spans, but none exactly matches the supplied evidence string.
- 16 rows have publisher-unavailable spans.
- Zero prompts satisfy the prospective inclusion policy, even before licensing.

For diagnosis only, replacing CRLF/CR with LF and treating the end as exclusive yields 357 exact
matches among the 374 in-range rows. Either raw-text end convention yields zero; normalized text
with inclusive end also yields zero. This strongly suggests a coordinate-representation mismatch,
but does not qualify the transformation or explain the remaining 17 rows. No substring search,
fuzzy matching or replacement source was admitted.

The CSV also uses Boolean strings where the README describes numeric flags; four labels have
`significantly increase` rather than documented `significantly increased`, while retaining code 1.
Keep those mismatches explicit. Native labels describe comparative effect, not SciFact stance:
`no significant difference` must never be relabeled `insufficient evidence`.

## Rights and provenance audit

The repository's MIT file is not sufficient evidence for licensing all article text in this
separate archive. The archive has no per-article rights metadata. For the same 64 training IDs,
we retrieved only current metadata from PMC's documented public S3 service, preserving responses
and hashes locally. All 64 IDs resolve, with 65 version records: 38 CC BY, 10 CC BY-NC,
4 CC BY-NC-ND, 8 CC BY-NC-SA, and 5 without a license code. These are **version counts**, not
article counts. One transient connection reset was retried once and the original failure retained.

Current metadata cannot establish which historical version produced the benchmark text. No
clinical article body was retrieved from PMC, no current text was substituted, and no article
redistribution permission is asserted. Missing codes and version matching remain unresolved;
noncommercial/no-derivatives conditions cannot be collapsed into an unrestricted license.

PMC retired its legacy OA Web Service in August 2026; use the current metadata service rather
than interpreting an obsolete endpoint failure as an unavailable article.
[Service retirement](https://pmc.ncbi.nlm.nih.gov/tools/oa-service/),
[current metadata access](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/),
[metadata schema](https://pmc-oa-opendata.s3.amazonaws.com/README.txt).

## Inclusion policy and next decision

The unchanged admission policy requires train membership, nonempty ICO, documented label/code,
both native verification flags true, exact inclusive spans, exclusion of publisher-flagged
questionable prompts, and no disagreement among verified native labels for a prompt. A prompt
needs at least one qualifying row; there is no invented majority vote or silent failure deletion.
Article-level provenance and permitted use are separate prerequisites. This sample admits none.

The next useful proposal is a **bounded coordinate-contract qualification**, using only these same
64 training articles: trace the publisher's text-loading/index code, specify a reversible mapping
between published bytes and annotation coordinates, and account for all residual failures. That
would require an explicit amendment to the current no-normalization policy before any transformed
span is accepted. Reconcile archive counts and article-version rights alongside it. This is more
specific than trying another extractor and does not require a model.

Do not start Step 2, build graphs, or silently switch to QASPER. The current negative result concerns
this release's admission contract; it is not evidence that clinical roles cannot inform Lattice,
that the annotations are all semantically wrong, or that a learned-state model would fail.
