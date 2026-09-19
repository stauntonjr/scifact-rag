# Generation-fidelity reviewer pilot and custody plan

**Proposed issue title:** Qualify the generation-fidelity review process on development evidence

**Goal:** Qualify a bounded frontier-agent review panel for consistent, evidence-attributed development screening, and specify how a future confirmation cohort will be held separately from developer agents. Agreement does not establish scientific correctness.

**Architecture:** Reuse Issue #26's review-v2 worksheets, validators, fidelity contracts, and existing local reviewer. Keep the agent-review pilot, custody specification, and subsequent generation experiments as distinct evidence boundaries. The user is the sole required human: owner and final decision-maker.

**Execution:** Follow the repository engineering loop for the accepted bounded issue. This document is a planning deliverable outside the repository checkout; this update does not create an issue, run agents, or establish reviewer qualification. The user has selected frontier-agent review; execution must bind the available subscription-backed models and finite budget before dispatch.

**Authority:** User's requested scope and the accepted `docs/adr/0036-generation-fidelity-evaluation.md` and `docs/project/generation-fidelity-v1.md`, verified during the preceding review. Reconcile current main before implementation. The user has explicitly replaced the multi-human staffing assumption with frontier-agent delegation. Preserve historical contracts and artifacts; reconcile this changed scientific authority into a new accepted ADR and protocol revision during execution. Do not describe automated review as compliant with the old two-human confirmation requirement without that amendment. The prior staffing draft is retained beside this file as `2026-09-19-reviewer-pilot-and-custody.human-draft.md` and is superseded, not an executable alternative.

## Scope and budget

- Include real exposed-answer selection, two independently collected frontier-agent reviews, agent adjudication, one rubric-clarification round, a frozen development assessment, and a confirmation-custody specification.
- Exclude candidate generation, product model/runtime changes, new frameworks, confirmation source acquisition or selection, hidden-content access, and generation-quality claims. Reviewer-model calls are explicitly in scope.
- Use frontier agents available through the owner's existing subscriptions; introduce no separately billed APIs, new subscriptions, or paid services. Verify that the required models are actually callable through that access. If unavailable, record the limitation instead of silently switching billing routes. No LangSmith, LangGraph, Semantica, or other evaluation-framework adoption in this issue.
- At most 60 distinct existing responses across the entire pilot, each reviewed by both reviewer agents. Allocate at most 12 responses to clarification and 48 to the frozen assessment. Each reviewer assesses each response once per stage; no response crosses stages. Repeated copies cannot increase coverage.
- One clarification round and one frozen assessment. A failed or underpowered assessment ends this issue with no-go or insufficient evidence; no open-ended rubric tuning.
- Preserve historical artifacts byte-for-byte. Do not edit synced `sources/` material.

**Build/adopt/adapt/defer:** Adapt the existing reviewer and strict contracts, using a versioned machine-review envelope rather than impersonating a human reviewer. Use active `product-validation-challenges` for plumbing checks; use the application-composition capability only if tooling wiring requires it. Defer ledger and observability capabilities. Recheck the inactive `role-separated-analysis` capability during implementation: this agent-panel design proposes its activation if its claimed orchestration responsibilities apply. Record real model/session identities, role boundaries, handoffs, and checks in that capability instead of creating parallel orchestration. The user's delegation instruction supplies the role-design direction; repository activation must be reconciled explicitly.

### Agent execution and isolation contract

- Maximum scoring workload: 120 first-pass reviews (two per response) plus 60 adjudication tasks, totaling 180 case-level tasks. Clarification and frozen assessment share this ceiling. No semantic retries, best-of sampling, or automatic replacement after a failed task. Transport failures or malformed output remain explicit non-passes. Freeze an additional coordination token/turn and wall-time allocation from the actual available subscription allowance before execution; no unlimited coordinator loop is permitted.
- Any preflight uses fictional fixtures only, with at most six additional scoring tasks. Fixtures verify tooling, not qualification. Total scoring-task ceiling including preflight: 186. Count actual model requests/continuations where observable; task count is not a claim that the platform makes exactly one inference per task. Record opaque platform usage as unavailable rather than exact.
- R1/R2 get only the frozen rubric and one opaque case package. Deny repository browsing, web research, other task history, existing labels, candidate identities, peer results, and external tools. The adjudicator's staged inputs must preserve its evidence-first judgment before peer-review access. A coordinator that sees labels must not become a reviewer by reusing its own conversation.
- Distinct agent names or sessions do not guarantee isolation or statistical independence. Validate case packaging and tool permissions with dummy content; record shared model family, infrastructure, and any inaccessible-to-measure training overlap.
- Every definitive judgment includes a brief evidence-linked rationale, including clean judgments; require bounded spans or exact quotations with document attribution. Resolve quotations deterministically. Ambiguous matches, absent required support, malformed fields, or inconsistent labels produce an unresolved result, not an invented span or clean pass. Preserve the existing explicit evidence-absent mode when no supporting passage exists.
- Retain raw outputs and immutable identities. If a provider changes model identity during the assessment, stop that revision. If an exact revision is unavailable, record the provider label, date window, settings, and limitation; do not claim exact replay reproducibility.
- The owner approves the report and dispositions; full human annotation is not required. Offer a compact packet of consequential disagreements and unanimous-but-weakly-supported judgments for optional owner spot checks. Such checks remain separately labeled and cannot be promoted into human-gold calibration.

## 1. Establish ownership and verify usable evidence

- [ ] Assign the user as owner/release approver. Assign two frontier reviewer agents (R1/R2), a separate frontier adjudicator agent (A), and coordinator/custodian agent roles. These are agent roles, not requests for additional humans. Record actual callable models, providers, session IDs, available version identifiers, prior exposure, and role overlaps. Prefer different model families for R1/R2 when available at no extra cost; never claim cross-family independence when both use the same family.
- [ ] A assesses each case from evidence first, freezes that judgment, then sees the two retained reviews and adjudicates in the same bounded assessment task. Preserve the initial judgment and final explanation. Agreement cases receive scrutiny too; majority vote alone is not adjudication. Unresolved cases stay unresolved. A separate session is required; model diversity is preferred but does not prove independent errors.
- [ ] Inventory the 42 historical distinct responses and their original evidence, source IDs, hashes, and existing labels. Do not expose historical labels to reviewers. Use fresh sessions without inherited task history, prior labels, shared memory, or peer messages. Record residual model/pretraining exposure; a fresh session is not a fresh model.
- [ ] Inventory additional already-exposed real answers only if needed for coverage. Each additional response needs a retained raw artifact, exact supplied context, source identity, and dated exposure evidence. Do not generate new answers or acquire new scientific sources to fill gaps.
- [ ] Group related records by claim and by connected article family: if responses share any source article family, keep them together. Preserve every context-policy variant within its group. Exclude records whose provenance cannot be established, with reasons retained.

**Exit:** Named reviewers and an auditable eligible inventory. If callable reviewer roles or usable artifacts are unavailable, report the exact dependency and stop pilot execution; custody documentation can continue independently.

## 2. Freeze the pilot protocol before reviews

- [ ] The coordinator selects up to 12 clarification responses, aiming to exercise the three target errors, grounded controls, and insufficiency. Use historical labels for coordinator-only coverage planning, never as review-v2 reference truth.
- [ ] Allocate the remaining eligible article-family groups to an assessment pool, up to 48 responses, with a documented deterministic order and no outcome-driven additions after assessment starts. Keep both stages entirely within already-exposed development evidence.
- [ ] Describe the selection as a diagnostic pilot, not a representative estimate of deployed error rates. Preserve separate results for any deliberately error-enriched subset.
- [ ] Randomize opaque worksheet IDs and presentation order. Hide previous labels, context-policy names, generator/prompt identities, automatic scores, and the other reviewer's judgments. Reviewers receive the question, exact supplied evidence and IDs, and the answer.
- [ ] Freeze the operational gate below, selection rule, review instructions, adequacy fields, handling of uncertainty, and artifact paths before the first review. Also freeze R1/R2/A prompts, model identifiers, input packaging, decoding controls where exposed, tool permissions, request ceilings, and failure policy.

### Judgments and evidence boundary

Retain all review-v2 fields and span annotations. Require separate judgments for qualifier loss, population generalization, causal strengthening, groundedness, and answer adequacy. Define materiality as a change that alters the answer's scientific scope, direction, strength, or applicability; stylistic shortening alone is not an error.

Add an immutable companion adequacy worksheet rather than silently extending strict review-v2 JSON:

- `response_id`: references the frozen review-v2 row.
- `supplied_context_answerability`: `answerable`, `not_answerable`, or `uncertain`.
- `answer_adequacy`: `adequate`, `inadequate`, or `uncertain`, assessed only when context is answerable; otherwise record `not_applicable`.
- `insufficiency_handling`: `appropriate`, `inappropriate`, `not_applicable`, or `uncertain`.
- `rationale`: brief source-bound justification for any non-pass or uncertainty.
- Agent role, provider/model and available revision, session/request IDs, UTC submission time, rubric/prompt version and digest, source worksheet/input digest, raw-output digest, and usage/latency when available. Explicitly mark unavailable runtime fields; never invent an immutable revision for a subscription UI model.

The instructions must cover subgroup/dose/time restrictions, species transfer, association versus causation, non-significance versus equivalence, surrogate versus clinical outcomes, mixed evidence, and supported narrower answers. Broader source answerability is a separate diagnostic after blind judgments are frozen; it does not change grounding against supplied context.

## 3. Run one clarification round

- [ ] Each reviewer independently completes the clarification worksheets before seeing the other's results.
- [ ] Save original attributable, timestamped agent outputs and immutable exports; do not call these human-signed reviews. Validate IDs, content identity, categorical completeness, and bounded spans before joining results.
- [ ] Have the adjudicator and coordinator analyze disagreements and record the original judgments, evidence, adjudicated label or unresolved status, and specific wording change. Do not overwrite first-pass labels.
- [ ] Freeze a new rubric version and examples drawn only from the clarification portion. Do not inspect assessment labels or answers to refine the wording during this stage.

**Exit:** A frozen rubric, clarification log, and validated independent review artifacts. Clarification-stage agreement does not count toward qualification.

## 4. Assess the frozen rubric once

- [ ] R1 and R2 independently score all frozen assessment responses in isolated case sessions. Freeze both exports before discussion or adjudication.
- [ ] Report per-category confusion tables, exact agreement, positive and negative agreement, uncertainty, and unresolved counts. For binary target-error tables, let a be both-positive, d both-negative, and b/c the discordant counts. Positive agreement is `2a/(2a+b+c)` and negative agreement is `2d/(2d+b+c)`; report undefined values explicitly.
- [ ] Keep `uncertain` and missing judgments visible. In the gate, they are non-agreements even if both reviewers chose uncertainty. Do not remove them from the all-scheduled denominator. Report binary agreement on resolved rows separately with its coverage.
- [ ] Report the number of distinct claims and connected article-family groups. Display raw counts beside percentages; any exploratory uncertainty analysis resamples these groups rather than treating every response as independent. This issue does not estimate population-wide reviewer accuracy.
- [ ] Adjudicate after the independent-agreement report is frozen. Preserve disagreements; consensus labels cannot replace the pre-adjudication agreement calculation.

### Proposed operational readiness gate

These are explicit engineering thresholds for agent-reviewed development comparisons, not published scientific standards, human calibration, or evidence that reviewers are objectively correct. Accept them before the pilot; never relax them after seeing results.

- Every scheduled response has two independently completed, source-validated reviews.
- For each target category, the frozen assessment has at least five adjudicated positive and five adjudicated negative examples, each class spanning at least three distinct article-family groups. Overlapping categories are allowed and reported.
- For each target category, at least 80% exact agreement across all scheduled assessment responses, with positive and negative agreement each at least 75% on resolved binary judgments.
- Groundedness, supplied-context answerability, and answer adequacy each achieve at least 80% agreement on their defined assessment denominator. Adequacy also needs at least five adequate and five inadequate adjudicated answers spanning at least three families per class; inapplicable cases cannot inflate its agreement.
- For every assessed dimension, uncertainty/missing judgments affect at most 10% of its denominator. After adjudication, no material disagreement used to justify readiness remains unresolved.
- All substantive rubric changes occur before assessment. Any new change required by assessment leads to no-go for this revision and a separate future reassessment.

**Decision:** `go-agent-reviewed-development` if all conditions pass; `no-go-rubric-revision` if adequate coverage exists but reliability fails; `insufficient-evidence` if coverage, model access, or isolation cannot support the assessment. Passing qualifies only this frozen panel for provisional development screening. Agent-adjudicated positive/negative counts are panel labels, not independent gold. The modest category counts and correlated-model risk limit all claims.

## 5. Specify confirmation custody without choosing confirmation content

This documentation can proceed alongside the agent pilot. It must name the accountable human owner, actual agent/model roles, and the proposed storage/access environment before being marked specified.

- [ ] Name the owner-controlled custodian agent, two confirmation reviewer agents, adjudicator agent, developer agents, and the user as release approver. A custodian cannot also act as a candidate developer. Confirmation reviewers must use fresh sessions and the frozen panel protocol. The owner controls access grants and release; agents cannot self-authorize exposure.
- [ ] Define future source eligibility, permitted-use verification, sampling frame, article-family grouping, and exclusion against every development/stress source. Include preprints, corrected versions, shared studies, paraphrases, and derived prompts. Perform no actual candidate-source selection in this issue.
- [ ] Specify separate custodian-controlled storage and credentials, developer-denied content access, separate review access, protected mapping files, and restricted exports. Cover shared disks, backups, browser storage, logs, tracing, and model-call records. If developer administrators can read the storage, record that residual access and do not claim enforced separation.
- [ ] Ordinary subagents in a shared workspace do not establish sealed custody. Use a separately permissioned environment/account with no developer-agent tool or credential route to the content. Coordinator and custodian roles may share a model family, but must not share a conversation or readable storage once real custody begins. If this cannot be enforced, custody remains incomplete and actual confirmation acquisition stays blocked.
- [ ] Use fabricated sentinel files to rehearse allowed/denied access, reviewer export, and release approval under representative credentials. This tests custody controls, not scientific review. No real confirmation material enters the rehearsal.
- [ ] Define sealing: immutable content and inclusion manifests, hashes, timestamp, custody/access declarations, and a developer-visible manifest containing only permitted opaque IDs, counts, and digests. Hashes demonstrate identity, not secrecy; do not treat a public source-ID hash as guaranteed anonymization.
- [ ] Define future sample-size calculation using development estimates of paired discordance and article-family dependence. Power every binding decision criterion, including answer-adequacy preservation, under prospectively accepted effect sizes and margins. Freeze the computed size and budget before confirmation outcomes exist; if unaffordable, stop or revise prospectively.
- [ ] Define the one-run boundary: freeze candidate and baseline, protocol, software/runtime, analysis, thresholds, failure/retry handling, and request budget before confirmation execution. Keep all outputs and aggregates unavailable to developers until reviews and adjudication are locked.
- [ ] Define incidents: stop access/run on an unexpected disclosure, retain access logs, mark affected families exposed, and report whether the entire cohort is compromised. No silent substitution or continued use under an untouched label.

**Future confirmation claim:** After a separately approved real run, the strongest intended claim is “improvement on a development-unexposed cohort under the frozen automated review protocol.” Report model-panel bias and uncalibrated scientific accuracy as limitations. Do not call the result independently human-confirmed fidelity or silently carry over the old human-review authority. The amended ADR must specify agent adjudication, unresolved handling, and owner promotion authority before any confirmation execution.

**Custody status:** `specified` when assignments and procedures are complete; `operationally-rehearsed` only after the dummy access/export checks pass; otherwise `incomplete` with named missing prerequisites. None means that a real cohort exists or is ready to run.

## 6. Deliver the decision and successor boundaries

Proposed execution artifacts, relative to the repository:

- A new ADR at the next available number: supersede only the human-staffing and reviewer-authority requirements, preserve phase separation and exposure rules, and explicitly describe automated-review limitations.
- `docs/project/generation-review-pilot-v1.md`: frozen protocol, rubric supplement, thresholds, and version history.
- `docs/project/generation-confirmation-custody-v1.md`: named custody assignments, controls, source rules, sealing, and future run gates.
- `docs/reports/generation-review-pilot-v1.md`: inventory/exclusions, category coverage, independent agreement, adjudication, limitations, and decision.
- Fresh ignored `artifacts/generation-review-pilot-v1/`: source inventory, separate opaque mappings, attributable agent review exports, adequacy companions, clarification history, and dummy custody evidence. Preserve prior artifacts.

Use the existing validators and local inspection tool. Add a versioned agent-review envelope carrying machine provenance and a strict projection into review-v2 fields; retain the adequacy companion. Do not populate human-review attestations with model identities or silently change v1/v2 historical semantics. A narrow agent invocation/export helper is sufficient; do not build a new UI or a general judge service. If a validator or analysis helper is necessary, limit it to these artifact contracts and test missing/reordered IDs, altered evidence, repeated rows, inapplicable adequacy, uncertainty accounting, and group-aware denominators. Any repository implementation follows its focused checks and final gate; do not claim code tests or cross-agent agreement establish scientific correctness.

The final report must state independently:

1. Review-process readiness and the exact supported use: Candidate A development comparison under this frozen automated review panel, without human-calibrated accuracy claims.
2. Custody status and unresolved operational dependencies.
3. No generation improvement, human-gold calibration, or untouched confirmation result was established. State exactly what operational agent-panel qualification was established, if any.

**Successors:** A separate accepted issue can implement/run Candidate A after review readiness passes and the custody/exclusion specification is complete. Operational custody rehearsal is mandatory before acquiring real confirmation content, not a reason to block unrelated development tooling. This pilot is the bounded qualification of the chosen agent panel; no additional judge framework or separately hosted judge qualification is required. A later confirmation preparation/run issue requires an operational custodian, eligible sealed cohort, powered protocol, and frozen candidate.

**Completion rule:** A truthful no-go or insufficient-evidence report completes this pilot issue. It does not authorize a larger sample, new model, repeated assessment, or relaxed threshold. Those require a separately scoped decision.

## Plan self-review

- Scientific boundary: bounded reviewer-agent calls only; no new candidate answers or confirmation-content access.
- Selection leakage: related claims/source families stay within one pilot stage; no assessment-driven additions.
- Qualification: independent original judgments, fixed operational criteria, category coverage, and explicit uncertainty handling.
- Custody: actual agent/runtime identities and denied-access rehearsal distinguish a document or agent instruction from enforced separation.
- Delivery: useful negative outcomes close the issue; Candidate A and confirmation remain separate successor issues.
