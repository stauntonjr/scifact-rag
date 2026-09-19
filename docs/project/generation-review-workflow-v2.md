# Generation-review workflow v2

[Issue #35](https://github.com/stauntonjr/scifact-rag/issues/35) contains the implementation plan.
[ADR-0038](../adr/0038-generation-review-workflow.md) authorizes this successor to the stopped
Issue #28 pilot. The [runtime research](../research/generation-review-runtime-v2.md) and
[report](../reports/generation-review-workflow-v2.md) distinguish software from live qualification.

## Preserved scientific boundary

Use only the original 42 exposed responses in 20 claim/article-family groups: 11 clarification
and 31 assessment. Inventory SHA-256 is
`ea58f7266dc0233cc5d74c79053ed7c560de6f5662937a2b68a4930fe490f9e6`;
selection SHA-256 is `fead52c0a781497e278aec8296a24c6731f0a59a5f4c39d3cef12828cb53cfbc`.
The [v1 protocol](generation-review-pilot-v1.md) remains authoritative for scientific rubric,
category definitions, source identities and reliability/coverage thresholds. No historical label
is sent to a reviewer. No new answer, candidate, corpus, confirmation or model substitution is
included. Existing v1 artifacts retain their original meaning.

R1 is `gpt-5.6-sol`, R2 is `gpt-5.5`, and both adjudication stages use `gpt-5.6-terra`.
Reasoning effort is high. Each request gets only one source case and the applicable rubric;
only final adjudication receives the frozen initial and peer judgments. Each stage uses a fresh
session. Unavailable provider metadata remains null; requested identity is not observed identity.

## Execution and output contracts

The coordinator validates strict model-only JSON, source quotations, exact intervals, adequacy
consistency and case identity before constructing provenance. `adjudicator-final/v2` binds the
initial, R1 and R2 digests, includes a source-valid judgment, and records resolved/unresolved status
and an explanation. First-pass agreement is frozen before adjudication. Adjudication never replaces
first-pass reliability measurements.

Attempt-start records precede dispatch. Successful, malformed, failed, timed-out and unknown
attempts remain attributable and counted. Existing output roots cannot be reused. No semantic
retry, replacement, best-of selection or automatic continuation after an unknown outcome is allowed.
The original budget allowed two fictional rehearsal rounds. The owner later authorized one bounded
transport-troubleshooting revision; the recorded campaign uses at most three rounds and remains
under the unchanged 20 engineering-turn ceiling. The development budget remains 168 turns,
188 combined turns, 10,800 live seconds and 180 seconds per subprocess, one in flight. The two
retained discovery probes already consume two engineering turns; they are not free preparation.

Offline deterministic transports establish coordinator behavior only. Live admission cannot be
asserted through an operator boolean. Runtime admission requires reviewed capability-enforcement evidence and attributable execution;
unavailable provider-returned metadata remains null. No scientific dispatch is authorized by a
successful software test. Qualify the runtime, then run the complete fictional path, before real cases.

## Qualification and reporting

Complete clarification first. At most one documented rubric change is allowed before assessment;
no rubric, model, case or threshold change follows assessment access. Assessment includes every
scheduled response in applicable denominators. Missing and uncertain judgments are non-agreements.
Report positive/negative agreement, all-row agreement, uncertainty, category counts and family
coverage. Undefined binary metrics remain undefined. Answer-adequacy denominators exclude genuinely
inapplicable cases, not merely inconvenient results.

Separate `execution_failed` / `execution_complete` from `not_assessed`,
`insufficient_category_coverage`, `reliability_failed`, and `qualified_development_screening`.
Fictional tests cannot qualify a scientific panel. A completed negative assessment is a valid
scientific outcome; an unexecuted assessment is incomplete and leaves Issue #35 open.

Raw inputs, prompts and judgments stay ignored on the execution host. Public reporting contains
only text-free aggregate counts, implementation identities and artifact digests. The recovered
inventory/selection reproduce the original hashes; they do not restore lost v1 preflight outputs.
Retain this worktree while it holds unique ignored evidence. Confirmation custody remains a
separate, unimplemented boundary and is not established by tool restrictions on a reviewer.


## Operator entry points

Use the repository Python 3.12 environment. Commands are `prepare` / `freeze`, `campaign-init`,
`qualify-runtime`, `rehearse`, `run-development`, and `report`; inspect each command's help for
required paths. `qualify-runtime` takes a discovery object containing the registered `profile_id`,
not an unregistered configuration object or an operator assertion. Campaign initialization binds
both existing discovery-probe directories. Do not create a new campaign to reset spent budget.

The host-specific registered profile lazily loads only its pinned descriptor file and rejects
missing files or digest drift. It cannot admit an arbitrary configuration file. Public checkouts
without ignored evidence can run offline tests; they cannot dispatch this host's live review.

The single authorized development run is now spent. It stopped after two completed calls when the
third call reached the 180-second ceiling. Campaign continuation and replacement development runs
remain fail-closed; a new attempt requires an explicit owner-approved protocol revision.
