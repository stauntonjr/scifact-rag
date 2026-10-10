# Local scientific-review diagnostic implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Complete checkboxes in order.

**Goal:** Determine which local reviewer can detect the specified scientific meaning changes and preserve adequate answers, while keeping every currently loaded model available.

**Architecture:** Adapt existing source-bound judgment validation and append-only accounting to a local HTTP transport. Compare the existing Qwen endpoint and a separately hosted Qwen3.8 FP8 checkpoint on the same 24 referenced diagnostic cases. No artificial multi-role panel or final adjudicator is needed.

**Tech Stack:** Python/uv, existing vLLM services, an isolated compatible ARM64 evaluation image if needed, strict JSON schema, immutable JSON artifacts.

**Spec:** Owner's September 22 request; docs/project/generation-review-rubric-v3-draft.md; docs/superpowers/plans/2026-09-20-generation-fidelity-progress.md. This is a plan, not evidence of a completed trial.

## Constraints and intended decision

- Keep every model loaded at execution start and its endpoint/configuration intact. Never stop, restart, unload, replace or reconfigure an existing serving process to accommodate the trial.
- Preserve all other running containers, including apparently idle SparkRun containers. Names and container IDs are not stable authority; capture their current identities.
- Existing generator remains nvidia/Qwen3.6-35B-A3B-NVFP4; generation defaults are unchanged.
- No historic 42-case rerun, new candidate generation, paid API, Jev call, confirmation access or product promotion.
- All 24 cases are explicitly fabricated scientific contrasts, not a representative corpus sample or a powered qualification set.
- The decision is assisted-review suitability per capability: eligible for bounded source-reviewed development, limited to suggested annotations, or unsuitable pending repair. It is not autonomous scientific qualification.
- Disposition: adapt current validators, transport interface, artifact identities and report helpers; use active role-separated-analysis and product-validation-challenges. No new general evaluation framework.

## Observed host state, 2026-09-22

Read-only checks found 121 GiB total unified memory, 57 GiB available, 64 GiB used and 4.9 GiB swap in use. Memory availability is a snapshot, not an allocation guarantee.

Confirmed model endpoints:
- Port 8000: nvidia/Qwen3.6-35B-A3B-NVFP4, 32,768-token limit.
- Loopback port 8082: answerdotai/answerai-colbert-small-v1, 512-token limit. This is a retrieval scorer, not an eligible generative judge; keep it available.
- Two SparkRun containers and other application/database services were running. Preserve all of them whether or not a model is visible in the endpoint inventory.

## Models

M1: the existing Qwen3.6 endpoint, no server changes. Trial-specific prompt and decoding settings go only in evaluation requests.

M2: Qwen/Qwen3.8-27B-FP8, the official checkpoint, pinned to an immutable revision during preparation. Run only if a separate service can fit with the preservation rules. Official availability was rechecked: https://huggingface.co/Qwen/Qwen3.8-27B-FP8.

Proposed M2 endpoint: 127.0.0.1:18080, after checking it is unused. Use a new named trial container, isolated environment, bounded cache, concurrency one, and initial context ceiling 16,384 tokens. Never upgrade a package inside an existing serving environment. A model name alone does not pin weights, tokenizer, chat template, serving image or quantization behavior; record all of them.

Do not substitute another quantization or smaller model silently. If M2 cannot coexist, report that condition and complete only the admitted M1 arm. Do not free capacity by evicting existing models.

## Task 1: Establish service preservation and admission

**Output:** ignored artifacts/local-review-diagnostic-v1/preflight.json, service-baseline.json and service-after.json.

- [ ] Inventory all model-serving processes, endpoint model IDs, container IDs/images, process start times and current health before any launch. Enumerate listeners rather than guessing ports.
- [ ] Observe memory and existing request queues for five minutes. Proceed only during a quiet window; do not enqueue diagnostic requests behind live service demand.
- [ ] Budget M2 for at most 36 GiB incremental resident memory including cache/workspace, leaving at least 16 GiB host MemAvailable during trial operation. These are conservative operational reserves, not scientific acceptance thresholds.
- [ ] Verify that the chosen runtime can bound total evaluation allocation, including load-time and graph-capture peaks. A GPU-memory-utilization fraction alone is insufficient; it must not assume the whole shared machine is disposable.
- [ ] If load peaks cannot be safely bounded within headroom, do not launch M2. A memory monitor cannot guarantee protection from instantaneous shared-memory exhaustion.
- [ ] Monitor host memory, swap activity, service health and request queues during loading and calls. Sustained new swap-out, falling below the reserve, or any existing service becoming unhealthy stops new diagnostic dispatch immediately.
- [ ] Keep at most one diagnostic request in flight across both models. If external demand appears, let the admitted request drain, then yield. Never cancel another user's request.
- [ ] Any cleanup targets only the new trial-owned container after checking its captured ID. Existing endpoints must retain their model IDs and process start identities afterwards.
- [ ] Record contention and pauses. Loaded availability can be preserved; unchanged latency cannot be guaranteed on one shared GPU. If strict latency isolation is needed, defer to a quieter window.

**Acceptance:** Existing services remain loaded and healthy. Model admission is denied rather than trading away that requirement.

## Task 2: Build and independently review the 24 references

**Files:** create tests/fixtures/local_review_diagnostic_v1.json and docs/project/local-review-diagnostic-v1.md. References and target categories are coordinator-only; exclude them from model inputs.

Each case contains opaque ID, claim, exact answer, evidence with opaque document IDs, expected values for every field, expected material-error spans and a concise reference explanation. Also record a contrast-pair ID and target capability in hidden metadata.

Use these eight distinct contrast pairs (16 cases). The source/claim is identical within each pair; change the answer only:

| IDs | Target | Source proposition | Error answer | Faithful answer |
|---|---|---|---|---|
| Q01–Q02 | qualifier_omission | Observed improvement was limited to a four-week follow-up; later persistence was not evaluated. | Benefit persists long-term. | Benefit was observed at four weeks; later persistence is unknown. |
| Q03–Q04 | population_omission | A result is reported only for adults with a specified advanced condition. | Unrestricted statement about patients, with no scoped referent. | Explicitly retains the studied adults and condition. |
| Q05–Q06 | population_generalization | A response was observed in cultured cells; no animal or human outcomes were studied. | The treatment works in humans. | Describes the cultured-cell observation only. |
| Q07–Q08 | intervention_omission | The reported result used a combination of two named interventions. | Attributes it to one intervention alone. | Preserves the combination. |
| Q09–Q10 | comparison_omission | The study compared an intervention against placebo only. | Asserts superiority over standard treatment. | States the observed placebo comparison. |
| Q11–Q12 | outcome_omission | A laboratory marker changed; clinical endpoint was not assessed. | Asserts improvement in that clinical endpoint. | States the laboratory-marker result and its limit. |
| Q13–Q14 | negation_omission | Exposure did not increase the measured endpoint. | Says exposure increased it. | Preserves did not increase. |
| Q15–Q16 | causal_strengthening | An observational study reports association without causal identification. | Says the exposure causes the endpoint. | Preserves associated with. |

Write original sentences and domain labels rather than copying the instruction examples. Add exact quantitative/context details only when needed to make the intended judgment determinate; do not require external scientific knowledge.

Eight boundary cases:
- Q17: a short answer with comparator unambiguously established by the question; faithful omission must not be penalized.
- Q18: non-significant difference rewritten as equivalence; expected qualifier error, not automatic negation loss.
- Q19: two equally applicable conflicting passages with no resolution; expected uncertainty on a proposition that cannot be decided, with field-specific explanation.
- Q20: appropriate insufficiency-only response to genuinely non-answerable context; adequacy not_applicable, applicable granular labels explicitly defined.
- Q21: unnecessary refusal despite a direct supported answer; inadequate and inappropriate insufficiency handling.
- Q22: narrow, useful substantive answer retaining a stated limit; adequate, not penalized for failing to endorse the broader claim.
- Q23: one assertion both broadens population and strengthens causality; both tags, one proposition-level error.
- Q24: faithful supported contradiction of the question's claim; grounded and adequate despite not agreeing with the claim.

- [ ] Write complete reference records before any candidate judge sees these cases. Coverage is designed, not inferred from judge output.
- [ ] Have a reviewer who did not author the records check every reference against the complete rubric and source. A disputed determinate reference is fixed before freeze; an intentionally ambiguous case has uncertainty as its explicit target.
- [ ] Check there are 24 unique cases, eight contrast pairs, eight boundary cases, and all eight granular fields have a positive and a faithful contrast.
- [ ] Freeze source, expected labels, intervals, order and rubric digests. Do not change references after seeing model outputs.
- [ ] Preserve reference limitations: these are independently reviewed synthetic decisions, not human-calibrated natural science ground truth.

**Acceptance:** Every reference is justified by visible source text and the defined rubric, including applicability and adequacy. No category depends on an unexplained term.

## Task 3: Prepare the actual request and bounded transport

**Files:** adapt src/scifact_rag/generation_review_workflow.py transport boundary if appropriate; keep Codex admission intact. Add a narrow tools/local_review_diagnostic.py and focused tests/test_local_review_diagnostic.py only as required. Reuse pilot validators rather than reproducing them.

- [ ] Include the entire approved rubric, claim, answer, all passages and strict judgment schema in each request. Exclude expected answers, target labels, pair identity, other cases and prior outputs.
- [ ] Verify exact rubric bytes/digest in serialized payloads. Count tokens using each checkpoint's tokenizer; input plus output reserve must fit. Do not truncate definitions or source text.
- [ ] Freeze one supported reasoning mode and sampling setting per model using its own template capabilities. Use bounded thinking; do not imply numerical decoding settings make different models identical. No setting sweep.
- [ ] Limit total generated tokens to 8,192 per request, including reasoning and final output; 120-second request timeout. If complete input plus reserve exceeds 16K, deny M2 admission unless a larger cache still meets the same preservation budget.
- [ ] Keep reasoning content separate from final JSON. Retain final output and concise reference-linked rationale, not private reasoning transcripts.
- [ ] Preserve the raw source-validation result. No post-result quote normalization to rescue labels in this trial.
- [ ] Validate exact quotations and source intervals. If intervals fail but labels are readable, report scientific label diagnostics separately; the record still fails the usable-output criterion.
- [ ] Test hidden-reference exclusion, complete rubric inclusion, nonfresh-root rejection, attempt-start persistence, timeout/unknown handling, output validation and service-identity protection using fake transport.
- [ ] Run two additional, unscored fictional transport checks per admitted model: one clean and one annotated-error output. They are distinct from the 24 scored cases.

**Acceptance:** Complete semantic instructions actually reach the model, and structural failures remain distinguishable from semantic errors.

## Task 4: Execute once with a finite budget

- [ ] Use the same frozen randomized order for both arms, alternating models by case when both are available. Score one independent response per model/case; no adjudicator and no semantic retry.
- [ ] Budget: 48 scored requests plus four unscored checks = 52 maximum model requests. If only M1 is admitted, at most 26. Health GETs are not model requests.
- [ ] Maximum summed live request time: 104 minutes (52 × 120 seconds). Allow at most 30 minutes for one M2 load attempt; download time is reported separately. These ceilings are cost controls, not predicted runtime.
- [ ] After a timeout, determine whether server work ended before dispatching more requests. Never assume closing HTTP cancels server inference. If completion cannot be established, stop that arm and preserve unknown status.
- [ ] A malformed but attributable response is a recorded failure; continue remaining cases within budget. Runtime/service-preservation failures stop admission. Do not restart or unload an existing model to recover.
- [ ] Retain attempted, completed, failed, skipped and unknown counts with a terminal record. No success-only denominator.

## Task 5: Interpret and advance generation work

**Output:** docs/reports/local-review-diagnostic-v1.md plus ignored raw artifacts and a per-case matrix.

- [ ] Report errors per defined capability against the independent references, false positives on faithful answers, applicability/uncertainty decisions, and adequate-answer/abstention behavior.
- [ ] Separate schema failure, exact-source failure, timeout and semantic disagreement. Show numerator/denominator for every result; do not call 24 examples an accuracy estimate for the corpus.
- [ ] Report pair sensitivity: did the model change the target label appropriately when only the material answer content changed?
- [ ] Show median and maximum full-request latency, token counts, peak incremental memory and any impact observed on existing endpoints. With 24 calls, do not oversell tail estimates.
- [ ] Select an assisted-review role only where errors are understood. Any missed definite error in the three primary objectives or a false positive on its faithful contrast means that capability cannot be delegated without source review. This is a diagnostic alarm tied to a demonstrated counterexample, not a statistical qualification threshold.
- [ ] If either model handles the diagnostic distinctions, use it in the planned baseline-versus-Candidate A development comparison with source review of apparent improvements/regressions and unresolved cases.
- [ ] If both fail, preserve those exact examples, repair the instructions or restrict automation, and proceed with source-reviewed candidate development rather than opening another broad judge qualification campaign.
- [ ] Record final service inventory: all preexisting models remain loaded and reachable; any new M2 remains separately managed according to the explicit execution decision.

## Review focus

- Complete definitions absent from serialized input: reject before calls.
- Role repetition mistaken for independent models: this is a two-checkpoint comparison, not a panel vote.
- Synthetic coverage mistaken for natural prevalence: label all cases and conclusions appropriately.
- Timeouts mistaken for cancellation: verify completion before further dispatch.
- Model loading or GPU contention degrading existing services: preservation outranks completing the second arm.

## Scope of this planning request

This document is the deliverable. No model download, launch, service change, inference call or assessment execution is performed while preparing it.
