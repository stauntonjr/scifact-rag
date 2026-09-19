# Generation review pilot v1

## Status and authority

This is the frozen Issue #28 protocol for a development-only LLM-as-judge pilot. The human owner
and release approver is Jack Rory Staunton. ADR-0037 authorizes three agent roles and preserves the
phase and exposure rules of ADR-0036.

Passing this protocol qualifies only the exact frozen panel for provisional development comparison
of the current prompt and Candidate A. It does not establish human calibration, scientific
correctness, independent errors, better generation, or an untouched confirmation result.

## Frozen evidence and selection

The eligible population is the 42 distinct, already-exposed responses retained by the Issue #5
review. Immutable copies live under ignored `artifacts/generation-review-pilot-v1/source/`.

| Artifact | SHA-256 |
|---|---|
| Blank historical worksheet | `f6a64a24a031ab4cf2cfc3764419ca37276c0d8174581e302d173e3bac72f0d2` |
| Opaque response map | `436de342736b264b4c7e21faa33e7df8c1b90e702750e764502bfb9e60f87372` |
| Completed historical review | `8388c3da046a9ec4d671b4230168b29fcd7208d55353ba0f84a700e37d16d62b` |
| Generation manifest | `7348418473ec279c840561862475d9dca73a6f91db239f7fadb5e23ea9422882` |
| Raw result stream | `006b88286e24efc5b6b1a66f23f3e88a814048a4cb06c8cee1336d24728c7aec` |

The strict reconciler admitted all 42 responses and grouped them into 20 connected components by
shared claim or supplied source-document identity. Context-policy variants remain in their group.
No row with unknown provenance was admitted and no additional answer was generated.

Coordinator-only historical labels were used to choose clarification groups `afg-001`, `afg-008`,
and `afg-019`. Their 11 responses include insufficiency, clean controls, qualifier loss,
population transfer, species transfer, and association/causation wording. Those labels are neither
reviewer inputs nor reference truth. The other 17 whole groups and 31 responses form the assessment
pool. No assessment-driven addition is permitted.

The frozen ignored artifacts are:

| Artifact | SHA-256 |
|---|---|
| Reconciled source inventory | `ea58f7266dc0233cc5d74c79053ed7c560de6f5662937a2b68a4930fe490f9e6` |
| Group-contained selection | `fead52c0a781497e278aec8296a24c6731f0a59a5f4c39d3cef12828cb53cfbc` |
| Shuffled clarification worksheet | `448c12fedb2554ff606ef1a523c0d807820fbe3392f82ae5367327513fb428b8` |
| Shuffled assessment worksheet | `649271d9ac7964797534a9f179504d4c744893086cf1f99a0c98eceb84824cf3` |

Ordering seeds are `issue-28-clarification-v1` and `issue-28-assessment-v1`. Opaque historical
response IDs are retained. Reviewers see only one row's opaque ID, claim, answer, and exact supplied
evidence with document IDs; they do not see stage membership, query ID, policy, prompt/generator,
automatic metrics, historical labels, or peer output.

## Roles, models, and isolation

| Role | Frozen callable model | Reasoning | Artifact ownership |
|---|---|---|---|
| R1 | OpenAI `gpt-5.6-sol` through the existing Codex subscription | high | first-pass envelope only |
| R2 | OpenAI `gpt-5.5` through the existing Codex subscription | high | first-pass envelope only |
| A | OpenAI `gpt-5.6-terra` through the existing Codex subscription | high | evidence-first and final adjudication only |
| Coordinator | current Issue #28 Codex task | n/a | identity, packaging, validation, aggregation |
| Owner | Jack Rory Staunton | human | approval, risk acceptance, release authority |

Each case uses fresh sessions with no inherited task turns. R1 and R2 never receive peer output. A
receives the source first, returns and freezes an initial judgment, then receives the two retained
reviews in the same bounded case task. The current runtime cannot technically remove repository and
web tools from a spawned session, so prompts prohibit tool calls and outputs must show no reliance
on external material. This is procedural separation, not an enforced sandbox or proof of
independence. Session IDs and observable role/model labels are recorded; immutable model revisions,
provider request IDs, usage, and latency are `null` when unavailable.

If a role reports a different model label, uses an external tool, sees a historical label or peer
result prematurely, or receives more than one case, stop the revision. A malformed or transport-
failed task remains a non-pass; there is no semantic retry, best-of selection, or replacement.

## Frozen reviewer instruction

The following instruction is identical in semantic content for R1 and R2; only the role name and
prompt version differ.

> You are the named first-pass scientific fidelity reviewer. Judge only the supplied claim,
> answer, and evidence. Do not use tools, browse, inspect files, infer hidden labels, or rely on
> outside knowledge. Treat the supplied context as the complete grounding boundary. Return exactly
> the requested JSON judgment. For every judgment, quote exact answer text and exact evidence text
> with its document ID. Mark uncertainty when the boundary cannot support a definite judgment.
> Material means changing scientific scope, direction, strength, or applicability; stylistic
> shortening is not material. Do not reward fluency.

Apply these rules:

- `grounded=yes` only if every material answer claim is directly supported by supplied context.
- Qualifier loss includes omitted uncertainty, statistical significance, dose, time, subgroup,
  study-design, or limitation language that materially strengthens the answer.
- Population generalization includes age, disease status, geography, species, cell/animal-to-human,
  or selected-cohort transfer.
- Causal strengthening includes changing association or prediction into causation, prevention, or
  treatment effect. Causal study language can support causality only within its actual design and
  population.
- Non-significance does not establish equivalence or no effect. Surrogate outcomes do not establish
  clinical outcomes. Mixed evidence must remain mixed unless the supplied context resolves it.
- A supported answer may be narrower than the claim. Judge its actual text, not whether it repeats
  the claim. `insufficient evidence` is appropriate when the supplied context cannot responsibly
  answer; it is inadequate when a material supported answer is available.
- `supplied_context_answerability` asks whether the supplied evidence can support a responsible
  substantive or insufficiency answer. Assess `answer_adequacy` only when answerability is
  `answerable`; otherwise it must be `not_applicable`.
- A material error requires a bounded answer span and either bounded contrasting evidence spans or
  explicit `evidence_absent=true`. Clean results contain no material-error annotation.

The adjudicator receives the same scientific rules. Its first turn adds: “Judge the case before
peer access and return the requested initial JSON.” Its second turn adds: “The following are frozen
R1/R2 artifacts. Reconcile them against your retained initial judgment and the supplied evidence;
majority vote is not authority. Return the final label or `unresolved`, preserving the initial and
explaining any change.”

Prompt versions are `reviewer-r1/v1`, `reviewer-r2/v1`, `adjudicator-initial/v1`, and
`adjudicator-final/v1`. Their exact serialized prompts and SHA-256 digests are retained beside run
artifacts before fictional preflight. Decoding controls are unavailable on this subscription
surface and are recorded as such.

## Artifact contract

`generation-agent-review-envelope/v1` contains exactly:

- `response_id`, `role`, `review_v2`, `adequacy`, `rationale`, and `provenance`;
- every strict review-v2 judgment and material-error span;
- adequacy fields `supplied_context_answerability`, `answer_adequacy`,
  `insufficiency_handling`, and source-bound `rationale`;
- exact answer quotations and evidence quotations carrying document IDs; and
- provider/model label, nullable revision and request ID, session ID, UTC submission time,
  rubric/prompt versions and digests, exact input and raw-output digests, raw output, nullable usage,
  and nullable latency.

The validator resolves quotations and span offsets against the exact source row, verifies the raw
output digest, refuses unknown fields, and projects only valid ordered envelopes into unchanged
`generation-human-review/v2`. Adequacy is exported separately as
`generation-agent-adequacy/v1`; model identities are never written into human-review attestations.

## Execution and budget

1. Run at most six fictional scoring tasks to verify case packaging, output parsing, provenance,
   and staged adjudication. Fictional output is excluded from qualification.
2. Run R1, R2, and staged A on the 11 clarification rows. Preserve all originals, analyze wording
   disagreements, and freeze one rubric update before opening assessment outputs. Clarification
   contributes no readiness result.
3. Run R1 and R2 once on each of the 31 assessment rows. Freeze both exports and the independent
   agreement report before adjudication.
4. Run staged A once on every assessment row, including R1/R2 agreements. Preserve its initial and
   final outputs and unresolved cases.
5. Apply the frozen gate without adding cases, changing models, retrying semantic judgments, or
   relaxing a threshold.

Ceilings are 120 first-pass and 60 adjudication case tasks across clarification and assessment,
plus six fictional preflight tasks: 186 total case tasks. This inventory schedules 84 first-pass
and 42 adjudication case tasks. A's evidence-first continuation is counted and reported as an
observable additional model turn, although it remains one adjudication case task. Coordination is
limited to this issue and one pass through each stage; there is no open-ended repair loop.

## Frozen analysis and readiness gate

For every dimension, report scheduled count, exact agreements, exact agreement, uncertainty or
missing count, and resolved-binary coverage. `uncertain` and missing are non-agreements in the
all-scheduled denominator even when both reviewers are uncertain. For binary target fields, with
`a` both-positive, `d` both-negative, and `b/c` discordant:

- positive agreement is `2a / (2a + b + c)`;
- negative agreement is `2d / (2d + b + c)`; and
- a zero denominator is reported as undefined, never zero or one.

Report distinct claims and article-family groups. Display counts beside percentages. Any
exploratory interval resamples whole article-family groups and cannot become a population estimate.
Adjudication never replaces pre-adjudication agreement.

`go-agent-reviewed-development` requires every condition:

- two complete source-valid reviews for every scheduled assessment response;
- for each target category, at least five adjudicated positive and five negative examples, each
  class spanning at least three article-family groups;
- for each target category, at least 80% exact all-row agreement and at least 75% positive and
  negative agreement on resolved binary rows;
- groundedness, supplied-context answerability, and answer adequacy each at least 80% agreement on
  their defined denominator;
- answer adequacy has at least five adequate and five inadequate adjudicated answers, each class
  spanning at least three groups, without inapplicable inflation;
- uncertainty or missing judgments at most 10% for every assessed dimension;
- no unresolved material disagreement supporting readiness; and
- no substantive rubric change after assessment begins.

Otherwise choose `no-go-rubric-revision` when coverage exists but reliability fails, or
`insufficient-evidence` when coverage, access, source validation, or isolation cannot support the
assessment. The owner may inspect a compact packet of consequential disagreements and unanimous
weak rationales, but those observations are separately labeled and are not human-gold calibration.

## Reproduction commands

The narrow helper supports immutable inventory, group-contained selection, label-free worksheet
creation, envelope validation, and strict projection. Use a task-specific writable uv cache in the
isolated worktree. Source artifacts are ignored and never committed.

```text
python tools/generation_review_pilot.py inventory ...
python tools/generation_review_pilot.py select ...
python tools/generation_review_pilot.py worksheet ...
python tools/generation_review_pilot.py validate ...
python tools/generation_review_pilot.py project ...
```

The 14 focused tests and fictional preflight establish only implementation behavior. They do not
prove scientific judgment quality.
