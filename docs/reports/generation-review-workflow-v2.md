# Generation-review workflow v2: implementation and admission boundary

Date: 2026-09-19. Governing work: [Issue #35](https://github.com/stauntonjr/scifact-rag/issues/35).

**Execution status: execution_complete. Assessment status: insufficient_category_coverage. Issue
remains open for the 42-case development assessment.** This is a successful fictional workflow
rehearsal and a measured negative coverage result, not a qualified review panel or a claim-answer
label. No generation-quality improvement is established.

## Retained accounting

| Boundary | Attempted | Completed | Failed | Unknown |
|---|---:|---:|---:|---:|
| Fabricated runtime discovery calls | 2 | 2 | 0 | 0 |
| First fictional rehearsal round | 6 | 5 | 1 | 0 |
| Transport troubleshooting round | 2 | 1 | 1 | 0 |
| One bounded transport diagnostic | 1 | 1 | 0 | 0 |
| Final fictional rehearsal round | 8 | 8 | 0 | 0 |
| Scientific development turns | 0 | 0 | 0 | 0 |

All attempts are attributable and retained. The campaign consumed 19 engineering turns and
301.2154211669622 seconds against the 20-engineering / 168-development / 188-combined-turn and
10,800-second ceilings. There are zero unknown outcomes and zero scientific development turns.
The final rehearsal used two fabricated cases and all eight scheduled stages; it is intentionally
too small to qualify the 42-case panel. Its execution report is complete and its assessment result
is `insufficient_category_coverage`.

The first rehearsal's one failure was a strict validation stop: the response marked three material
error flags but supplied only one required annotation category. The troubleshooting round then
had one process exit with no model output. The adapter previously discarded stderr, so it was
repaired to retain only a coarse error class. A new diagnostic under the identical pinned profile
completed with exit 0, a session, valid output and `stderr_without_failure`; the transport failure
did not reproduce as a deterministic launch defect. The final eight-call rehearsal then completed
without transport or validation failures. The
[research record](../research/generation-review-runtime-v2.md) explains the pinned capability
boundary and nullable provider metadata.

## Source recovery and preparation

The Issue #28 worktree was deleted with its ignored artifacts. Original source files survived in
the DGX repository artifact directory. Deterministic repository builders recovered the inventory,
selection and label-free worksheets with the exact previously published SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| Original blank worksheet | `f6a64a24a031ab4cf2cfc3764419ca37276c0d8174581e302d173e3bac72f0d2` |
| Source inventory | `ea58f7266dc0233cc5d74c79053ed7c560de6f5662937a2b68a4930fe490f9e6` |
| Frozen selection | `fead52c0a781497e278aec8296a24c6731f0a59a5f4c39d3cef12828cb53cfbc` |
| Clarification worksheet | `1861db259447548896342e764dcde1a312dde818ac21231e4969f30f7a6ad56c` |
| Assessment worksheet | `2ab31ae8f6549355c97ca20810c4b1765aae1eeaffc582687013d7cc3e83d8b2` |

The 42-response / 20-family population and 11/31 split are unchanged. Recovery restores these input
identities, not deleted preflight raw outputs. Ignored Mac preparation is under
`artifacts/generation-review-workflow-v2/`; a recovered metadata copy also resides outside the
removed worktree on the DGX. The Mac preparation has not been dispatched to a reviewer.

## Implemented boundary and remaining work

The new module and CLI implement strict model judgments, source validation, initial/final
adjudication binding, first-pass agreement, finite scheduling, append-only campaign accounting,
fresh-output protection, subprocess timeout and a conditional subscription adapter. Deterministic
fake transports exercise success and failure paths without model calls. Existing v1 validators and
artifacts remain supported. Public report projection excludes source and judgment text.

The pinned capability profile was independently reviewed and admitted for fictional execution.
The same issue still requires the 11-case clarification stage, the frozen 31-case assessment and
independent result accounting before any development qualification claim.
No budget increase, alternative models, paid API, new scientific answers, Candidate A, confirmation
acquisition or custody provisioning is authorized here. Confirmation custody remains incomplete.

The focused suite passes 71 tests after the transport-observability repair. The locked final
repository gate passed: harness checks, formatting, lint, type checking, 603 non-integration tests
with 3 skips, package smoke, and Docker Compose configuration. A later completed assessment may
validly fail coverage or reliability without being an execution failure.
