# Generation-review workflow v2: implementation and admission boundary

Date: 2026-09-19. Governing work: [Issue #35](https://github.com/stauntonjr/scifact-rag/issues/35).

**Development execution status: execution_failed. Assessment status: not_assessed. Issue remains
open.** The real 42-case run was attempted once under the frozen protocol. Two development calls
completed, the third reached the 180-second subprocess ceiling, and the coordinator stopped with
zero unknown outcomes. No retry or replacement is authorized. This is not a qualified review panel,
a scientific assessment result, or a claim-answer label. No generation-quality improvement is
established.

## Retained accounting

| Boundary | Attempted | Completed | Failed | Unknown |
|---|---:|---:|---:|---:|
| Fabricated runtime discovery calls | 2 | 2 | 0 | 0 |
| First fictional rehearsal round | 6 | 5 | 1 | 0 |
| Transport troubleshooting round | 2 | 1 | 1 | 0 |
| One bounded transport diagnostic | 1 | 1 | 0 | 0 |
| Final fictional rehearsal round | 8 | 8 | 0 | 0 |
| Scientific development run | 3 | 2 | 1 | 0 |

All attempts are attributable and retained. The campaign consumed 19 engineering turns, 3
development turns, 22 total turns and 514.9947052089483 seconds against the 20-engineering /
168-development / 188-combined-turn and 10,800-second ceilings. There are zero unknown outcomes.
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

The real run used the frozen 42-response population, original inventory and selection hashes,
11/31 split, unchanged rubric, R1 `gpt-5.6-sol`, R2 `gpt-5.5`, and adjudicator
`gpt-5.6-terra`. Attempts 1 and 2 completed. Attempt 3 was attributable to a fresh
`gpt-5.6-sol` session but produced no final judgment or usage before the subprocess was killed at
180.180 seconds; its sanitized failure is `call_timeout`, exit `-9`, `process_exit`. The public
report records 3 attempted, 2 completed, 1 failed, 0 unknown and 165 not attempted turns. The
manifest, report and terminal file SHA-256 values are respectively
`64387310a91aaa1c34c33596187e941a034aa0c932f7be88a84fc552d26f4c63`,
`cde7cbab7f1099b9b58c8aa43ef7b90242fee48471b1d2606a16b6e49f8c756a`, and
`426cd164c31cad719a96481a371bfd33676235ebb3981959b064b7f10d123961`.

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

The pinned capability profile was independently requalified after user-config digest drift. The
retained passing rehearsal was reused only after independent approval of exact run/result digests
and closed scientific, validator, campaign and CLI contract digests. The one permitted development
run then stopped on its third call. Completing the 42-case assessment now requires an explicit
owner-approved contract revision; automatic continuation or a replacement run is forbidden.
No budget increase, alternative models, paid API, new scientific answers, Candidate A, confirmation
acquisition or custody provisioning is authorized here. Confirmation custody remains incomplete.

The focused workflow suite passes 51 tests after final formatting. The current reporting candidate
also passes the full repository gate: 607 tests passed, 3 skipped and 3 deselected, with harness,
formatting, lint, type checking, package smoke and Compose validation all successful. Two earlier
gate invocations exposed missing non-login-shell paths for the project Python and Docker CLI; those
were environment setup failures, not passing gates or product evidence.
