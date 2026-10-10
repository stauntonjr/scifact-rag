# Assessment evidence reuse implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Turn the completed assessment into an actionable source-grounded error and measurement-design analysis without repeating generation or judging.

**Architecture:** Adapt existing artifact readers, review projections and agreement functions. Preserve all original attempts, selections and reported gate outcomes; produce a separate explanatory audit with direct artifact references. Do not build another coordinator.

**Tech Stack:** Existing Python/uv tooling, retained JSON artifacts and Markdown.

**Spec:** The owner's September 20 request for a plan to use the assessment information; docs/project/generation-fidelity-v1.md defines the underlying fidelity objective. This document proposes work; it does not execute it or supersede accepted decisions.

## Global constraints

- Zero new model requests and zero regeneration of the 42 historical answers.
- Keep the 11 clarification / 31 assessment distinction and article-family dependencies visible.
- Existing adjudications are judgments, not independent reference truth.
- Preserve raw outputs, 202 physical development attempts, selected records and normalization provenance.
- Keep source-bearing packets local; publish aggregate findings and source artifact hashes only.
- Reuse active role-separated-analysis and product-validation-challenges; no new framework.
- Original qualification outcome remains recorded; clarify its limited interpretation in a separate audit.

## Review focus

- A unanimous label can be wrong: inspect source support rather than treating agreement as truth.
- A categorical disagreement can reflect missing definitions or applicability rules: identify that separately.
- Repeated answers or related article families cannot inflate distinct evidence.
- Quote normalization and retries cannot silently disappear from provenance.
- Good fidelity achieved through unnecessary abstention is not a useful-answer improvement.

## Task 1: Assemble a complete evidence index

**Inputs:** artifacts/generation-review-workflow-v2/development-recovery-005/{manifest.json,selected-judgments.json,report.json,revalidation.json,late-normalization.json}; recovered-source inventory/selection; original source-run artifacts referenced by recovery.json.

**Outputs:** ignored artifacts/generation-review-workflow-v2/evidence-audit-001/case-index.json and disagreement-matrix.json. Use existing readers in generation_review_recovery.py and agreement helpers; no changes to scoring behavior.

- [ ] Record input hashes before reading; record the audit's own inputs and code identity.
- [ ] Join all 42 response IDs to cohort, article family, exact source/answer, all four selected judgments, source-run attempt IDs and normalization policy.
- [ ] For each dimension, enumerate yes/yes, no/no, discordant, not-applicable and uncertain combinations; show counts and case IDs.
- [ ] Verify 42 unique response rows, 168 judgment references, 11/31 split, and final dependency identities. Check published aggregates against the index.
- [ ] Preserve disagreements involving not-applicable; do not silently remove them when discussing positive agreement.

**Acceptance:** Every selected judgment resolves to its immutable input and physical attempt; aggregates reconcile without new judging. Any mismatch is reported before interpretation.

## Task 2: Explain the observed disagreements and candidate failure mechanisms

**Outputs:** local source-linked case packets and docs/reports/generation-review-assessment-design-audit.md.

- [ ] Examine every assessment case with any first-pass disagreement; include relevant clarification cases as development evidence only.
- [ ] Also inspect unanimous material-error cases and unanimous cases labeled inadequate. Examine a deterministic one-per-family sample of the remaining unanimous clean cases to check for obvious shared blind spots; report sampling limitations.
- [ ] For each examined case, separate directly observable source differences from interpretive judgments. Use categories: missing/ambiguous rubric rule; applicability mismatch; explicit source contradiction; supported scope loss; insufficient supplied evidence; unresolved.
- [ ] For comparison omission specifically, identify the source comparator, what the answer actually says, whether its omission changes the claim, and whether the field should be applicable. Report each reviewer/adjudicator position without treating the majority as authority.
- [ ] Trace relevant upstream causes using retained contexts/results: distinguish missing retrieval or assembly evidence from generation misstatement. Mark unavailable full-source evidence as unavailable.
- [ ] Rank the three original fidelity targets—qualifier loss, population transfer and causal strengthening—by distinct affected cases/families, consequence and confidence. Counts describe this inventory only.

**Acceptance:** Each proposed defect or ambiguity cites a specific answer/evidence pair and its provenance. Unresolved interpretations stay unresolved. The audit produces concrete candidate requirements, not a model ranking.

## Task 3: Correct the interpretation and preserve reusable tests

**Files:** docs/reports/generation-review-assessment-design-audit.md; proposed amendments to docs/project/handoff.md and the existing report; existing challenge fixtures/tests only when an objective invariant is available.

- [ ] State that insufficient category coverage reflects an inventory/gate mismatch and that underspecified instructions confound attribution of disagreement to the panel.
- [ ] Retain the original numerical result and distinguish completed execution, observed agreement, reference accuracy not measured, and qualification not established.
- [ ] Turn objective escaped defects into minimal deterministic fixtures: multiple same-document excerpts, exact quote occurrence, unchanged prior selection and honest accounting. Reuse existing tests where they already cover these cases.
- [ ] Do not encode disputed scientific judgments as expected labels without a separately documented reference decision.
- [ ] Produce a short decision brief: highest-confidence generation defects; rubric defects; evidence gaps; a single recommended Candidate A change.
- [ ] Review the interpretation independently against the retained artifacts; run focused tests only if implementation changes, then the required repository gate on the final changed candidate.

**Done:** A source-grounded decision brief and reusable case index exist; the owner can see which failure mechanism the next candidate addresses. No historical model call was repeated.

## Complete definitions and delivery requirement

Use docs/project/generation-review-rubric-v3-draft.md as the concrete prospective instruction text. It defines corpus terms, scientific concepts, stance distinctions, every review field and allowed value, error categories, annotation fields and adjudication. Review it before freezing; do not retrospectively substitute it into historical requests. Every future judge must receive the complete approved content in the actual serialized request. Verify inclusion against the frozen rubric bytes and digest. Field-name coverage is not semantic validation.
