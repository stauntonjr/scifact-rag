# Evidence Inference coordinate qualification

Date: 2026-09-18. Governing work: [Issue #17](https://github.com/stauntonjr/scifact-rag/issues/17).

This is a separate qualification following the [negative admission audit](evidence-inference-admission.md).
The owner authorized testing the proposed coordinate mapping on the same frozen 64 training articles.
The original report, summary, archive and admission code remain unchanged. No model calls or
heldout outcome inspection occurred, and Step 2 remains inactive.

## Publisher evidence and explicit contract

Pinned publisher source: `jayded/evidence-inference@a661e8c14f973398380c8865cf2f27a535aaaf6d`.
Its [text loader](https://github.com/jayded/evidence-inference/blob/a661e8c14f973398380c8865cf2f27a535aaaf6d/evidence_inference/preprocess/preprocessor.py#L87)
uses Python text-mode `open()` with default newline handling. This converts CRLF and lone CR
into LF, as specified by [Python's open documentation](https://docs.python.org/3/library/functions.html#open).
Its [token/sentence representation](https://github.com/jayded/evidence-inference/blob/a661e8c14f973398380c8865cf2f27a535aaaf6d/evidence_inference/preprocess/representations.py#L17)
uses exclusive end offsets. However, the annotation README and
[span verification script](https://github.com/jayded/evidence-inference/blob/a661e8c14f973398380c8865cf2f27a535aaaf6d/verify_span_quality.py#L45)
use inclusive ends; the latter also searches nearby spans and uses edit distance. We do not adopt
those repairs. Token/sentence conventions are not proof of every annotation's convention.

**Qualified representation contract:** decode the immutable source as strict UTF-8; construct an
LF view, retaining a map from every view boundary to the original character and UTF-8 byte
boundaries. Interpret supplied annotation offsets as a nonempty half-open interval only for this
explicit qualification. Require exact equality to the unchanged annotation string and successful
roundtrip through the original source slice. No trimming, Unicode normalization, HTML decoding,
substring relocation, end adjustment per row, or fuzzy equality is accepted.

The LF view alone is lossy; reversibility depends on retaining the original bytes and boundary
map. The mapping changes the representation used to interpret coordinates, not the source data.
All original bytes remain available for citation. Boundaries inside a collapsed CRLF pair are
not separate boundaries in the LF view. Source-byte offsets must not be treated as Unicode or
canonical-view character offsets.

## Frozen scope and reproducibility

Archive SHA-256: `6abe0d4ec0d331834981c0171c3c79d47515761867f82f1dc6066e43863a1586`.
Use only the original 64 article IDs and the 390 rows belonging to them. The public
[summary](evidence-inference-coordinates-summary.json) records aggregate counts; local ignored
artifacts under `artifacts/evidence-inference-v2/coordinate-20260918/` preserve row identifiers,
hashes, mapped coordinates, diagnostics and pinned source-file hashes without committing evidence
text. Read `tools/evidence_inference_coordinates.py --help` for the reproducible command.

This is development qualification on previously inspected training data. It is not independent
confirmation, a corpus-wide quality estimate, or evidence of model performance. Rights and
historical version provenance remain separate from a successful coordinate roundtrip.

## Release-count reconciliation

Identity-only counting resolves the earlier publication discrepancy: 24,686 annotation rows cover
12,616 distinct prompts across 3,346 distinct articles, exactly the published annotated totals.
The prompts table contains 12,865 rows, including 249 IDs without annotations. Available article
texts and split-ID inventories are larger than the annotated corpus. These are different counting
units, not evidence that the publisher supplied a different annotated release. No heldout labels
or outcomes were needed for this reconciliation.

## Qualification result

Of 390 rows, **357 match exactly** under the mapped contract and roundtrip to original bytes;
17 mismatch and 16 have publisher-unavailable offsets. All 33 remain rejected. The 17 mismatches
have the following mutually exclusive diagnostic classifications, evaluated in the documented
priority order rather than counted as independent causes:

| Diagnostic relation | Rows |
|---|---:|
| Whitespace collapse makes the supplied span equal | 8 |
| HTML entity decoding makes the supplied span equal | 4 |
| Unchanged evidence occurs elsewhere at different coordinates | 4 |
| HTML-decoded evidence occurs elsewhere at different coordinates | 1 |

These relations describe strings, not why the annotation was created or whether a medical claim
is valid. None changes inclusion. After the unchanged label, verification and prompt checks,
**351 rows across 195 prompts and 45 articles** are conditionally eligible before rights review.
This is qualification of a traceable representation interface, not admission of the entire corpus.

## Admission boundary

A coordinate-qualified row is not automatically a usable diagnostic prompt. Preserve the previous
requirements for valid labels/reasoning, documented label-code pairs, nonempty ICO roles, publisher
caveats and verified-label agreement. Conditional eligibility still requires article/version rights
and a separately accepted Step 2 protocol. The four label-spelling mismatches are not silently
normalized. The original zero-match result remains correct under its original raw/inclusive
contract; this qualification evaluates a different, explicitly authorized representation contract.

No broader data acquisition or model experiment follows automatically. The useful next decision
is whether to admit a version/provenance-qualified subset and prospectively specify the bounded
fixed-reader experiment. Remaining rejected rows must stay rejected unless a separate source-backed
correction is qualified; their diagnostic categories alone are not repair authority.
