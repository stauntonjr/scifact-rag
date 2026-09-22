# ADR-0038: Complete staged development-review execution

- Status: accepted for software implementation; runtime admission remains conditional
- Date: 2026-09-19
- Decider: Jack Rory Staunton, human owner
- Governing issue: [#35](https://github.com/stauntonjr/scifact-rag/issues/35)
- Supersedes: ADR-0037 procedural-only execution restriction and pilot budget for this new revision

The owner approved the six-step repair plan with “do it.” Issue #35 contains its executable plan,
finite accounting and conditional live boundary. Historical Issue #28 results remain unchanged.

Adapt the existing validators into a finite coordinator with source-bound model-only judgments,
coordinator-generated provenance, attempt-start records, failure records, independent initial
adjudication and a final judgment bound to the frozen initial and peer digests. A fresh final-stage
request receives that explicit initial judgment; it does not inherit uncontrolled task context.

Require verified runtime/output controls before real cases. Do not infer enforced isolation from
role names, separate sessions, a prompt instruction or read-only filesystem permissions. Preserve
all attempts, including malformed or unknown outcomes. Prohibit automatic replay or replacement.

For the new revision, reserve at most 20 engineering turns (fabricated probes/rehearsal only), then
168 development turns over the existing 42 responses if admitted. Count both adjudicator stages as
turns. Enforce 188 total turns, one in flight, 180 seconds per subprocess and 10,800 live seconds total.
Freeze assessment once; retain existing reliability and category-coverage thresholds. No measured
outcome is promised by software correctness. After the first fictional rehearsal exposed an
unclassified transport exit, the owner authorized one additional bounded troubleshooting revision;
the total engineering-turn ceiling remains unchanged.

Report execution status separately from qualification outcome. A failed runtime or rehearsal does
not complete this issue: preserve software progress and leave qualification incomplete. Candidate
A, paid APIs, new models, new cases, confirmation acquisition and custody provisioning remain
outside this authority.

Reuse active `role-separated-analysis` and `product-validation-challenges`. A standalone general
agent framework and custom authentication/sandbox are rejected as disproportionate. Confirmation
custody remains specified but unimplemented pending an owner-controlled separate environment.

Verification requires synthetic end-to-end tests, attributable runtime admission evidence,
independent source/denominator accounting and the final repository gate. Revisit this decision if
the installed subscription surface cannot meet the access boundary or the retained frozen source
artifacts cannot be recovered with their original identities.
