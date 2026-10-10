# Generation-review workflow v2: completed development assessment

Date: 2026-09-20. Governing work: [Issue #35](https://github.com/stauntonjr/scifact-rag/issues/35).

**Execution complete: 42 cases and all 168 scheduled judgments. Assessment result: `insufficient_category_coverage`.** The real assessment ran; the panel did not qualify for development screening. This is a measured negative qualification result, not another unexecuted assessment or transport stop.

## Measured result

The original 42 responses, 20 article families, 11 clarification / 31 assessment split, rubric, model assignments and qualification thresholds are retained. R1 is `gpt-5.6-sol`, R2 is `gpt-5.5`, and initial/final adjudication use `gpt-5.6-terra`. All 42 final adjudications are resolved. Every case has two independent reviews, an independent initial adjudication and a final adjudication bound to the preceding record digests.

Eight positive error categories fail the required minimum of five cases spanning three families:

| Positive category | Cases | Families |
|---|---:|---:|
| causal_strengthening | 2 | 1 |
| comparison_omission | 3 | 2 |
| intervention_omission | 2 | 2 |
| negation_omission | 0 | 0 |
| outcome_omission | 2 | 2 |
| population_generalization | 3 | 2 |
| population_omission | 2 | 1 |
| qualifier_omission | 4 | 3 |

Aggregate agreement does not cure this coverage failure. Several dimension-specific positive agreements also fall below the 75% threshold. For example, groundedness exact agreement is 29/31 (93.55%), material-overstatement exact agreement is 30/31 (96.77%), but comparison-omission positive agreement is 0%. Answer-adequacy exact agreement is 21/26 (80.77%) on the applicable first-review denominator; inadequate agreement is 71.43%. The full [text-free aggregate results](generation-review-workflow-v2-results.json) retain every dimension and its denominator.

## Complete accounting

| Accounting view | Count |
|---|---:|
| Scheduled cases | 42 |
| Selected valid judgments | 168 |
| Physical development calls | 202 |
| Originally recorded completed / failed calls | 167 / 35 |
| Current-validation selected / duplicate / invalid calls | 168 / 5 / 29 |
| Engineering calls, all retained | 19 |
| Total campaign calls | 221 |
| Unknown outcomes / missing judgments | 0 / 0 |

The 35 original failure records remain unchanged. Corrected validation and explicitly recorded normalization produce the separate 29-invalid accounting view; these numbers must not be conflated. All 202 physical development calls are counted, including failures and duplicates. Cumulative live execution was 9,224.469735545 seconds (153.74 minutes), within the retained 10,800-second ceiling. Execution remained sequential and used the existing subscription runtime.

## Recovery and claim boundary

The owner instructed completion through recoverable failures, superseding the earlier single-retry stop rule. The [recovery protocol](../project/generation-review-recovery.md) records the operational revision, five-attempt per-slot retry policy and inherited maximum-attempt guard. The [original stopped report](generation-review-workflow-v2-initial-stop.md) remains historical evidence.

Recovery repaired three operational defects: recursive continuation bookkeeping lost physical-call counts; exact-quote validation discarded earlier excerpts sharing a document ID; and runtime admission pinned a user configuration file that the actual launch explicitly ignores. Effective runtime controls, binary/evidence checks and system configuration checks remain enforced.

Of the 168 selected records, 17 contain explicitly audited ASCII quote-delimiter normalization and one contains the later missing-slot quote-syntax repair. Every normalized quote is an exact unique source substring; raw model outputs remain intact. The later completion preserved all 166 already selected records and added the missing initial judgment plus a newly dispatched final judgment bound to it. Retried outputs and mixed normalization-policy provenance are disclosed; this is not a claim that all original raw outputs passed a single frozen acceptance policy.

No cases, source text, labels, spans, model assignments or scientific thresholds were repaired to force qualification. The result establishes neither judge accuracy, clinical correctness, human calibration, model-error independence nor generation-quality improvement. Candidate A and confirmation work remain separate and unauthorized; confirmation custody remains incomplete.

## Independent verification and delivery

Independent reviewer `/root/assess_recovery` reproduced all eight source-run terminal and attempt chains, 42 judgments per role, the 11/31 split, input/request/schema/model identities, peer exclusion, stage ordering, all final dependency digests, unchanged prior selections, normalization traces, campaign counts, agreement tables and the coverage decision. Verdict: complete execution verified; panel not qualified.

The final implementation checks passed: 622 tests, 3 skipped, 3 deselected; harness, formatting, lint, type checking, package smoke and Compose validation. Product release impact: none. This is assessment tooling and evidence, not a product change.

## Evidence identities

The retained final run is `artifacts/generation-review-workflow-v2/development-recovery-005/`. Raw artifacts remain local and ignored; this report publishes aggregates and hashes only.

| Artifact | SHA-256 |
|---|---|
| Original inventory | `ea58f7266dc0233cc5d74c79053ed7c560de6f5662937a2b68a4930fe490f9e6` |
| Original selection | `fead52c0a781497e278aec8296a24c6731f0a59a5f4c39d3cef12828cb53cfbc` |
| manifest.json | `75cb28ce2174d1db2969e9ca692aa363fc91d1b23dd94c83d3ccf73fa3eda757` |
| report.json | `4cc900ee2a860b496185410ac322cfb39bfa09bbb6944d898d04ae7f8b01f14b` |
| selected-judgments.json | `b93933f553eede8ada2e9791cec44ab2c7a5d0dcbc7b41057d95caaa2fd04883` |
| late-normalization.json | `ce1afe1c7e2d9a9800f127e73c5b73383188848bb25e76273ec87da123214d25` |
| revalidation.json | `43e00b47babe589f7589cbaacaa985f690ac855dca762682cd6ed82f00667f26` |
