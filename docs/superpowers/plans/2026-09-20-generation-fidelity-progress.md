# Generation fidelity progress implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make one defensible baseline-versus-Candidate A development comparison targeting material qualifier loss, population transfer or causal strengthening while preserving useful answers.

**Architecture:** Use the existing cached-context generation runner, source-bound review contracts and reporting tools. Repair the measurement instructions for the chosen decision, use agents as assisted reviewers with explicit unresolved outcomes, and keep automatic qualification and confirmation separate. Adapt the current workflow rather than building another evaluator.

**Tech Stack:** Existing Python/uv generation and review tooling, the project's configured generator service, retained context manifests, versioned Markdown rubric and JSON artifacts.

**Spec:** docs/project/generation-fidelity-v1.md; ADR-0036 and ADR-0037 explain the original purpose and existing restrictions. The evidence-reuse plan supplies concrete failure cases. This is a proposed scope revision: Candidate A execution remains a separate authorization under the current accepted contract.

## Global constraints

- Do not repeat the historical 168-judgment assessment.
- Use original scientific objectives: preserve qualifiers, population applicability and causal strength; preserve adequate substantive answers.
- Existing 42 responses are development evidence, never confirmation.
- No automatic pass or promotion based only on reviewer agreement or a clean schema.
- No new numerical gate without a stated decision, error tolerance and sample-size/uncertainty rationale.
- Baseline and candidate use identical contexts and generator settings except the named candidate change.
- Reuse active review and deterministic challenge capabilities; no general orchestration framework.
- Do not change product defaults, invoke paid APIs, or access confirmation content as part of this plan.

## Review focus

- Explicitly faithful answers may legitimately omit nonessential comparator wording.
- Negation, non-significance and equivalence are distinct meanings.
- Population/causal overlap must not cause accidental duplicate error counts.
- A shorter or abstaining answer must not win simply by making fewer claims.
- A reviewer can agree with its peers and still contradict the source.

## Task 1: Define the actual decision and repair its rubric

**Files:** create docs/project/generation-fidelity-development-v2.md and a separately versioned reviewer instruction alongside the current protocol. Preserve historical prompt bytes. Amend ADR-0037 through a new explicit decision if assisted review replaces its universal qualification prerequisite.

- [ ] Use the evidence-reuse brief to select one observed mechanism and one Candidate A intervention; do not optimize a generic list of error labels.
- [ ] State the next decision: retain or reject this candidate for further development. Product promotion and automatic reviewer qualification are not that decision.
- [ ] For every field retained in the evaluation, provide definition, applicability, yes/no/uncertain boundaries, source-support requirements and overlapping-category rules.
- [ ] Define comparison omission explicitly: a missing or changed comparator is material only when the answer consequently asserts a different contrast or a broader effect than the supplied evidence supports. Comparator silence that preserves the supported proposition is not automatically an error. Specify no versus not-applicable and preserve uncertainty for unresolved cases.
- [ ] Include source/answer examples with an explanation for positive, negative and boundary cases for each primary target. Label fabricated contrasts as instruction tests, never natural error prevalence.
- [ ] Choose one count per material proposition for the primary error summary, with additional category tags retained; keep adequacy and incorrect abstention separate.
- [ ] Freeze the exact serialized reviewer payload and review it for semantic completeness, including the schema's descriptions. A document definition absent from the delivered payload does not count.
- [ ] Record an assisted-review decision rule: every apparent win/regression and unresolved material judgment receives source-based review; unresolved cases cannot justify a win. Do not label this automated qualification.

**Acceptance:** Someone reading only the delivered payload can apply each field without repository knowledge. A bounded independent design review checks definitions, applicability, source examples and the match between the intended decision and available evidence. Resolve material interpretation questions before calls.

## Task 2: Verify instruction behavior on new diagnostic contrasts

**Inputs:** the frozen rubric and source-based contrasts written before judge outputs are observed.

- [ ] Construct positive and negative contrasts for the primary mechanism and controls for useful answers and appropriate abstention. Include at least one applicability boundary and one overlapping-category case.
- [ ] Record expected decisions and source-based rationales before invocation. Obtain an independent reference review; disputed references remain diagnostic ambiguities and cannot become a qualification denominator.
- [ ] Reserve contrasts that were not used as instruction examples. Do not evaluate memorized examples as held-out performance.
- [ ] Exercise the actual prompt/schema/runtime once on this bounded diagnostic set, with declared models, call count, retry handling and elapsed-time budget.
- [ ] Compare outputs to the prewritten reference rationales, not just to one another. Fix demonstrable instruction defects before freezing the candidate comparison.
- [ ] If the judges still misapply a critical rule, route that rule to explicit source review in the development comparison. Do not start another broad qualification campaign.

**Acceptance:** The evaluator can expose the intended defect and recognize preserved meaning on diagnostic contrasts, or its remaining limitation has a concrete review fallback. This is instruction verification, not a statistical accuracy claim.

## Task 3: Specify and run one paired Candidate A development comparison

**Files:** versioned candidate prompt and evaluation manifest using existing generation-evaluation tooling; docs/reports/generation-fidelity-candidate-a-development.md.

- [ ] Derive the smallest intervention from the evidence brief: for example, require the answer to retain the studied population and uncertainty where they limit the principal assertion. The final text must address the actual inspected mechanism.
- [ ] Build a coverage matrix before generation: each primary mechanism has source-verified natural cases and clean/adequacy controls. Show distinct article families and include every eligible case under the declared inclusion rule.
- [ ] Use the historical inventory only as development. If a target has no eligible natural examples, limit claims for that target; do not disguise fabricated or enriched cases as a representative population.
- [ ] Freeze baseline and candidate prompts, source/context digests, case list, models, settings, request budget, stop/recovery rules and paired reporting before dispatch.
- [ ] Reuse a baseline output only if its exact prompt, context, generator/settings identity and applicability match. Where identity cannot be established, run a new matched baseline and candidate pair rather than claiming a matched comparison.
- [ ] Generate Candidate A once per planned case, retaining all failed attempts and uncertain outcomes. Judge changed outputs with the revised instruction; historical old-rubric labels are not interchangeable with new-rubric labels.
- [ ] Blind arm identity. Source-check each apparent improvement or regression and all unresolved material cases; inspect a prespecified sample of unchanged/jointly clean outputs for shared errors.
- [ ] Report paired transitions: error corrected, error introduced, adequate answer preserved/lost, incorrect abstention introduced/removed, unresolved and failed outputs. Show cases and families beside counts; keep stress contrasts separate.
- [ ] Assess whether observed improvements address the original mechanism without sacrificing usefulness. If evidence is too sparse or mixed, report that and name the remaining question instead of manufacturing a pass.

**Acceptance:** One concrete generator change has a traceable paired result, cost/latency accounting and an explicit retain/reject/unresolved development decision. This is actual product-relevant evidence; it is not a confirmation or default-change authorization.

## Task 4: Decide whether a further validation investment is warranted

- [ ] If Candidate A has no credible development benefit, reject it and preserve the diagnostic result; do not build a larger evaluator to rescue it.
- [ ] If the result supports further development, specify a single next validation question and the error costs that determine required precision.
- [ ] Only if automated gating is needed, construct a separate independently referenced judge benchmark with planned positive/negative coverage, held-out families and sample size justified by that automation decision. Measure correctness against references as well as agreement.
- [ ] Only if product promotion is sought, use a separately authorized confirmation design and custody process. Define the promotion margin, adequacy guard, statistical method and budget before acquisition or unblinding.
- [ ] Publish clear boundaries between instruction checks, exploratory development comparison, judge validation and product confirmation.

**Done:** The project has advanced from judging old answers to testing a concrete generation improvement, with the remaining uncertainty stated. No automatic qualification gate has been silently weakened.

## Execution order and cost controls

Complete the evidence-reuse plan first: zero calls. Complete Task 1 offline next. Before Tasks 2 and 3, present their concrete manifests and total generation/judge budgets for the separate execution authorization required by the current protocol. Do not request approval for routine reading, artifact indexing or drafting. Do not execute Tasks 2–4 as part of a request to make plans.

## Complete definitions and delivery requirement

Use docs/project/generation-review-rubric-v3-draft.md as the concrete prospective instruction text. It defines corpus terms, scientific concepts, stance distinctions, every review field and allowed value, error categories, annotation fields and adjudication. Review it before freezing; do not retrospectively substitute it into historical requests. Every future judge must receive the complete approved content in the actual serialized request. Verify inclusion against the frozen rubric bytes and digest. Field-name coverage is not semantic validation.
