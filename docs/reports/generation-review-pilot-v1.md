# Generation review pilot v1 report

Date: 2026-09-19

Governing issue: [#28](https://github.com/stauntonjr/scifact-rag/issues/28)

Decision: **`insufficient-evidence`**

## Executive result

The agent-panel review process is **not qualified** for Candidate A development comparison in this
revision. The six-task fictional preflight reached its prospective ceiling with only two strict
passes. No attributable valid adjudicator envelope was retained; two coordinator-assigned raw
blobs were malformed, so staged evidence-first adjudication was not validated. The protocol
prohibits more preflight tasks,
semantic retries, replacement outputs, or relaxing the schema after seeing those results.

No retained development response was sent to a reviewer model. Therefore this report contains no
scientific category agreement, no adjudicated positive or negative coverage, and no readiness-gate
result that can be compared with the numerical thresholds. Stopping before the 42-response run
prevents invalid judge artifacts from being laundered into a reliability result.

Confirmation custody is **incomplete**. Its procedures are specified, but no separately
permissioned owner-controlled environment or dummy access rehearsal exists. Candidate A was not
implemented or run. No generation improvement, human-gold calibration, model independence, or
untouched confirmation result was established.

## Verified source inventory and frozen selection

The new reconciler verified all 42 historical responses against the retained opaque mapping and
raw result stream. It accepts only the exact product answer or the exact verdict-stripped raw
generation defined by the historical review protocol, and it requires every evidence title, text,
and document ID to equal the mapped supplied contexts.

| Item | Verified result |
|---|---:|
| Eligible already-exposed responses | 42 |
| Distinct claims | 24 |
| Connected claim/article-family groups | 20 |
| Clarification selection | 11 responses, 3 whole groups |
| Frozen assessment pool | 31 responses, 17 whole groups |
| Excluded for provenance failure | 0 |
| Newly generated scientific answers | 0 |

The inventory SHA-256 is
`ea58f7266dc0233cc5d74c79053ed7c560de6f5662937a2b68a4930fe490f9e6`; the group-contained
selection SHA-256 is
`fead52c0a781497e278aec8296a24c6731f0a59a5f4c39d3cef12828cb53cfbc`. Historical labels were used
only to choose clarification coverage and were never supplied to reviewer sessions or treated as
gold.

## Implementation result

`generation-agent-review-envelope/v1` now fails closed on:

- unknown or missing fields and invalid categorical values;
- response identity drift, altered source content, missing/reordered/repeated rows;
- non-exact answer/evidence quotations, invalid document attribution, and out-of-bounds spans;
- contradictory `evidence_absent` and evidence-span modes;
- invalid adequacy applicability;
- altered raw-output digests or incomplete runtime provenance; and
- uncertainty removal or denominator rewriting during agreement calculation.

Valid envelopes project into unchanged `generation-human-review/v2`; adequacy remains a separate
`generation-agent-adequacy/v1` artifact. Seventeen focused contract tests cover the repaired strict
projection, source/raw/panel identity binding, and earlier inventory/agreement behavior. This
establishes software behavior only, not judge quality.

## Fictional preflight

The coordinator reports six fresh subscription-backed tasks: R1, R2, and evidence-first A on each
of two fictional fixtures. Only fixture 2 R1/R2 have independently attributable envelopes. The
other four artifacts are malformed raw blobs without recoverable prompt, model, session, input, or
validation-error manifests; their task/model assignments below are coordinator-reported, not
independently verified:

| Assigned role | Reported model label | Fixture 1 | Fixture 2 |
|---|---|---|---|
| R1 | `gpt-5.6-sol` | rejected | accepted |
| R2 | `gpt-5.5` | rejected | accepted |
| Coordinator-assigned A | `gpt-5.6-terra` | rejected | rejected |

Observed strict failures:

- Fixture 1 R1 encoded `evidence_absent` as explanatory text and used an invalid insufficiency
  value.
- Fixture 1 R2 simultaneously declared evidence absent and supplied evidence spans, and used an
  invalid insufficiency value.
- The coordinator-assigned fixture 1 A blob used invalid adequacy enums.
- The coordinator-assigned fixture 2 A blob omitted the required top-level rationale and nested an
  object where adequacy requires plain text.

Fixture 2 R1 and R2 were source-valid and retained as attributable envelopes. They disagreed on
whether unrelated context is `not_answerable` or `answerable` merely because it supports an
insufficiency response. Before any real review, the rubric was clarified to define answerability as
support for a responsible substantive answer; an insufficiency-only case is `not_answerable` and
has `answer_adequacy=not_applicable`. No remaining fictional task was available to validate that
wording or a final adjudication artifact boundary, which was neither implemented nor exercised.

Raw-output SHA-256 digests are retained under ignored
`artifacts/generation-review-pilot-v1/preflight/`:

| Task | Raw-output SHA-256 |
|---|---|
| Fixture 1 R1 | `c96a052e185e96979f145696839b608447b5bee673f051104c2561de243851a5` |
| Fixture 1 R2 | `23491ad49fb8b8fe893339b3c158a8eca8352c6f0a89e4fd8a3c6d883425f2b8` |
| Coordinator-assigned fixture 1 A | `57a6ca17a50d7ffd1abdeba096182528eb3391ac90787c978bbd57c2fcfe2827` |
| Fixture 2 R1 | `2f2e8c7389e4dee83222531d3ffa26f9de9145cdb59202a6bb6a5cbd97dde683` |
| Fixture 2 R2 | `c029f214a4b95a719a632fff703e36b8844b2a2c00467b63b660fdc65244ab18` |
| Coordinator-assigned fixture 2 A | `7dd71233a46efa2719da4408b8c7751fcd3503d0adbcbc65212fb1e54fdd11e0` |

The accepted R1 and R2 canonical envelope digests are
`6d2aa8c11b9435c40d9509226e649d27ff3a7c3609f5933e059d0487cbb096d8` and
`b2b7be57ca8b5d01a6d61f594ff30e808f9c1e82c65ad4683a6a32f338e866ae` respectively.
Subscription usage, immutable provider revisions, request IDs, decoding controls, and provider-side
latency were unavailable and were not invented. Coordinator receipt time was retained as the
available submission timestamp.

The raw text does not cite tool-derived material, but four failures lack attributable prompt/task
records and the runtime did not expose enforceable per-agent tool denial. The preflight therefore
cannot independently establish fresh-session execution, tool isolation, exact panel identity, or
statistical independence for those failures.

## Gate accounting

| Quantity | Frozen allowance | Executed |
|---|---:|---:|
| Fictional scoring tasks | 6 | 6 coordinator-reported; 2 attributable |
| Development first-pass tasks | 120 maximum | 0 |
| Development adjudication tasks | 60 maximum | 0 |
| Real development responses judged | 60 maximum | 0 |

Because complete validated dual review and staged adjudication were unavailable, the first binding
readiness condition failed before assessment. Per-category agreement, positive/negative agreement,
uncertainty rates, adequacy coverage, and unresolved material counts are **not computed**, not zero.

## Decision and successor boundary

The exact decision is `insufficient-evidence`: usable exposed artifacts and callable first-pass
reviewer roles exist, but the frozen preflight did not validate the adjudicator artifact boundary
or resolve the answerability instruction within its run budget. This outcome completes the bounded
pilot without qualifying the panel.

Candidate A remains blocked on a separately accepted reviewer-panel revision. Such a revision must
prospectively choose one of these materially different remedies rather than silently retrying:

1. obtain a structured-output surface that enforces the JSON schema;
2. accept a new fictional preflight budget and versioned prompt/schema revision; or
3. replace staged model adjudication with an explicitly authorized human adjudication boundary.

The current issue does not authorize any option. A later confirmation preparation issue also
requires the missing custody environment, successful sentinel rehearsal, powered sample-size
calculation, sealed eligible cohort, frozen candidate, and owner-approved one-run budget.

## Claim boundary

Verified: strict source/provenance tooling, a 42-response/20-group eligible inventory, a frozen
11/31 group-contained split, two attributable valid fictional first-pass envelopes, and four
malformed unattributed raw outputs.

Inferred: clearer schema wording may reduce malformed output, but this was not tested within the
frozen budget.

Not established: reliable scientific judgment, human agreement, independent model errors,
development-review readiness, better generation, operational custody, or confirmation performance.

## Release impact

Recommended impact: **none**. This development-only pilot changes no public CLI, HTTP, MCP, web,
package, or product-generation compatibility contract.
