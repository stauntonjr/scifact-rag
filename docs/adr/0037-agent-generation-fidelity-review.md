# ADR-0037: Agent panel for development generation-fidelity review

- Status: accepted
- Date: 2026-09-19
- Decider: Jack Rory Staunton, human owner
- Governing issue: [#28](https://github.com/stauntonjr/scifact-rag/issues/28)
- Supersedes: only the human-staffing and reviewer-authority requirements of ADR-0036

Owner acceptance: the owner supplied and authorized the Issue #28 implementation plan on
2026-09-19. The plan explicitly replaces the earlier multi-human draft with subscription-backed
frontier reviewer agents while retaining the owner as the only required human approver.

## Context

ADR-0036 established the sealed phase boundary, strict review-v2 semantics, and bounded evidence
spans. It deferred replacement of human review. Issue #28 now needs a finite development-only test
of whether a named model panel can apply that rubric consistently to answers already exposed during
development. It does not need a general judge service, a new scientific corpus, or a product prompt
change.

The retained evidence contains 42 distinct responses across 24 claims. Its prior human labels are
useful only for coordinator-side clarification coverage and are not population estimates or gold
labels. Two model sessions seeing the same training distribution or provider are not statistically
independent merely because their names or conversations differ.

## Decision

- Activate the existing `role-separated-analysis` capability for this bounded workflow. R1 and R2
  own separate first-pass artifacts; A owns evidence-first and post-peer adjudication artifacts;
  the coordinator owns source identity, packaging, validation, and aggregation; the human owner
  alone approves promotion or release claims.
- Use subscription-backed OpenAI Codex agents already available to the project. Freeze R1 as
  `gpt-5.6-sol`, R2 as `gpt-5.5`, and A as `gpt-5.6-terra`, each at high reasoning effort. Exact
  provider revisions, request IDs, token counts, and latency are recorded as unavailable when the
  subscription surface does not expose them. Model labels and session identities remain mandatory.
- Give each scoring session only one opaque case, the frozen rubric, and its role prompt. Sessions
  must not browse the repository, web, retained labels, other task history, automatic outcomes, or
  peer judgments. This is a procedural restriction: the current agent runtime does not expose a
  tool-denial control, so the report must not claim enforced sandbox isolation.
- Preserve every original first-pass judgment. The adjudicator first judges the case from source
  evidence, freezes that output, then receives R1 and R2 outputs in the same bounded task and emits
  a final disposition. Agreement cases receive the same scrutiny as disagreements. Unresolved
  cases remain unresolved.
- Store model output in `generation-agent-review-envelope/v1`. Strictly validate its identity,
  provenance, exact quotations, bounded spans, review-v2 projection, and separate adequacy
  judgment against the immutable source row before aggregation. Malformed output receives no
  semantic retry or replacement.
- Limit work to at most 60 exposed responses, 120 first-pass tasks, 60 adjudication tasks, and six
  fictional preflight tasks. The current inventory uses 42 responses: 11 clarification and 31
  assessment. Clarification cannot contribute to the readiness denominator.
- Apply the prospectively frozen Issue #28 thresholds once. A truthful no-go or
  insufficient-evidence result completes the issue; it does not authorize a new model, larger
  sample, changed rubric, or relaxed threshold.

This panel can at most qualify a frozen automated workflow for provisional Candidate A development
screening. It cannot establish human-calibrated accuracy, objective scientific correctness,
statistical independence, better generation, or confirmation performance.

## Preserved ADR-0036 boundaries

The following remain unchanged:

- development, stress, and untouched confirmation are separate phases;
- exposed development evidence cannot become untouched confirmation evidence;
- confirmation content cannot enter this issue;
- review-v1 and review-v2 historical meanings remain unchanged;
- article-family grouping, paired candidate identity, sealed manifests, and access declarations
  remain mandatory;
- product prompts, defaults, retrieval, context assembly, citations, and public interfaces remain
  unchanged; and
- candidate implementation and confirmation execution require separate accepted issues.

## Consequences

### Positive

- The operational judge boundary is explicit, versioned, attributable, and fail-closed.
- Different model families reduce one obvious source of correlated presentation behavior without
  being mislabeled as independence.
- Review-v2 remains the semantic projection while adequacy stays a separate immutable companion.
- Historical human attestations are not overwritten with model identities.

### Negative

- Model-panel agreement can be consistently wrong and is not accuracy.
- The subscription runtime exposes model labels but not immutable revisions or enforceable
  per-session tool denial.
- Fresh sessions increase coordination cost and do not remove pretraining or infrastructure
  overlap.
- A failed task remains visible and can force insufficient evidence because semantic retries are
  prohibited.

## Alternatives considered

| Alternative | Benefit | Reason not selected |
|---|---|---|
| Recruit multiple human scientists now | Stronger calibration prospect | The owner explicitly chose a development-only agent-panel pilot and remains the sole required human. |
| Use one model as judge | Lower execution cost | Does not exercise disagreement, staged adjudication, or role-separated artifacts. |
| Build a hosted judge service or framework | Reusable invocation surface | Expands dependency, security, and operational scope beyond 42 retained responses. |
| Treat prior human labels as gold | Enables apparent accuracy estimates | One historical reviewed subset is not a representative or independently calibrated reference. |
| Run Candidate A first | Produces product outputs sooner | Would tune generation before the review boundary and custody rules are qualified. |

## Verification and revisit trigger

Verification must cover exact schema fields, source-bound quotations and spans, output digests,
adequacy applicability, missing/reordered/repeated IDs, label-free worksheets, connected
article-family grouping, uncertainty denominators, and immutable first-pass/adjudication exports.
Fictional preflight proves only transport and validation. The final report must keep observed,
inferred, and unsupported claims separate.

Revisit this ADR before changing the model panel, role isolation, retry policy, rubric, readiness
thresholds, adjudication order, confirmation authority, or human-calibration claim. A provider model
identity change during frozen assessment stops that revision.
