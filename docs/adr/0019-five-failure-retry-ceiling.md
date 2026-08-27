# ADR-0019: Five-failure engineering-loop retry ceiling

- Status: accepted
- Date: 2026-08-26
- Deciders: Jack Rory Staunton, human owner
- Governing issue: owner-authorized harness policy correction
- Supersedes: the three-failure retry ceiling in ADR-0007

## Context

The MS MARCO reranker candidate was technically complete, but evidence-ordering repairs exhausted
the three-failure engineering-loop ceiling. The owner then had to authorize a new evidence revision
even though the product candidate did not require another implementation revision. This showed
that three attempts were too sensitive for a loop that also validates the ordering, freshness, and
identity of its own evidence.

The retry ceiling is an engineering-loop recovery policy. It is separate from Pi's ceiling of three
consecutive unavailable-tool calls, which protects a different runtime boundary and remains
unchanged. Existing run records bind their retry policy when created and retain that recorded value.

## Decision

New engineering-loop runs bind a ceiling of five consecutive failed repair attempts. Failures one
through four create attempts two through five. The fifth failure blocks the run at attempt five and
does not create attempt six.

Retry exhaustion continues to preserve partial work. Continuing a blocked run still requires a
structured handoff explicitly reviewed by a `human:IDENTITY`, and resume still starts a new evidence
revision at attempt one. This decision changes neither Pi's unavailable-tool policy nor historical
run records.

## Consequences

### Positive

- Agents have two additional bounded repair cycles for evidence and integration faults.
- Technically sound product work is less likely to require owner intervention solely because of
  harness bookkeeping.
- Recovery remains finite, explicit, and auditable.

### Negative

- A genuinely unproductive repair path can consume two more cycles before it blocks.
- Documentation, fixtures, generated plugin artifacts, and runtime defaults must remain aligned.

### Risks and mitigations

- Repeated repairs could drift from the objective. The independent proportionality review after a
  second failed repair remains mandatory.
- An agent could confuse this limit with Pi's runtime protection. Both policies are documented as
  separate limits, and the Pi adapter remains unchanged.
- Existing runs could silently change semantics. Each run stores its bound retry ceiling, so this
  policy applies only to newly started runs.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| Retain three failures | Reranker completion needed a human resume for evidence-ordering repairs | Too sensitive for the current evidence model |
| Remove the ceiling | Would avoid retry exhaustion | Unbounded retries weaken escalation and proportionality controls |
| Change Pi's tool limit too | Both limits currently use the number three | The Pi limit governs unavailable tool calls, not engineering repairs |

## Verification and revisit trigger

`python3 tools/recovery_scenarios.py --fixture R005` must block at attempt five without creating
attempt six. `R006` must resume only from a human-reviewed structured handoff into revision two,
attempt one. Plugin synchronization, harness validation, and the repository smoke gate must pass.

Revisit this decision if observed runs routinely need all five attempts, if the independent
proportionality review fails to stop unproductive work, or if evidence bookkeeping is simplified
enough that a lower limit no longer interrupts sound product delivery.
