# Issue #26: generation-fidelity evaluation foundation

Date: 2026-09-18

Governing issue: [#26](https://github.com/stauntonjr/scifact-rag/issues/26)

## 1. Outcome and why it matters

`VERIFIED`: The repository now has a model-free foundation for evaluating whether generated
scientific answers preserve material qualifiers, populations or species, and causal strength. It
can freeze candidate identities and prompt digests, declare development versus confirmation
access, validate blinded review-v2 artifacts, and exercise known failure families without calling
a model.

`VERIFIED`: The foundation fails closed on unknown fields, invalid phase/access combinations,
foreign prompt hashes, malformed spans, ambiguous evidence attribution, duplicate annotations,
and inconsistent clean/non-pass reviews. Existing review-v1 artifacts remain valid.

## 2. Planned versus completed

`VERIFIED`: Issue #26's five acceptance criteria are implemented: the protocol and exposure
boundary are durable; review v2 supports material scientific judgments and bounded annotations;
the candidate/cohort/access manifest is strict; deterministic development challenges cover the
required families; and compatibility plus static/targeted verification are present.

`VERIFIED`: The implementation follows the approved first slice. It does not execute either a
baseline or candidate, acquire confirmation data, annotate a scientific cohort, or alter product
generation behavior.

## 3. User-visible and scientific-semantic changes

`VERIFIED`: Review v2 adds causal-strengthening and population-generalization judgments. Material
errors carry a category, half-open Unicode-code-point answer interval, and either one or more
bounded evidence intervals or an explicit evidence-absent declaration.

`VERIFIED`: The offline reviewer derives its controls from the worksheet schema. A v1 worksheet
retains the previous rubric. A v2 worksheet adds structured local-only error controls while keeping
candidate, prompt, context strategy, expected label, automatic score, and aggregate result absent.

## 4. Architecture, schema, dependency, data, and interface changes

`VERIFIED`: `src/scifact_rag/generation_fidelity.py` defines immutable candidate, cohort, access,
and manifest contracts with exact JSON parsing and prompt-hash checks. It adds no dependency and
does not connect to a model or network service.

`VERIFIED`: `generation-human-review/v2` is an additive schema selected by exact version dispatch
inside the existing standalone review tool. The accepted v1 constant and behavior remain
available. Review HTML remains self-contained, uses local browser storage, and retains a
deny-by-default content-security policy.

`VERIFIED`: The development challenge fixture contains nine fictional cases spanning qualifier
loss, population/species generalization, observational association, non-significance, surrogate
outcome, conflicting evidence, insufficiency, and supported controls. It is not confirmation data
and no result derived from it is a product-quality estimate.

## 5. Existing-solutions and capability disposition

`VERIFIED`: The existing-solutions note evaluates PubMedQA, QASPER, and SciFact as useful public
development precedents but rejects them as substitutes for an untouched custodian-owned
confirmation cohort. Cluster-level reporting precedent is adapted without importing a new
evaluation framework.

`VERIFIED`: Active application composition and product-validation challenge capabilities are
reused where applicable. No inactive capability is duplicated or activated, and no new service,
workflow, or planning authority is introduced.

## 6. Verification evidence and boundary proven

`VERIFIED`: Manifest tests cover exact fields, unique roles and IDs, sorted family digests,
phase/access rules, and separately supplied prompt-hash identities. Challenge tests cover fixture
schema and all required families. Review tests cover v1 compatibility, v2 completeness,
unblinding rejection, bounded offsets, evidence modes, duplicates, clean/non-pass consistency,
and schema-specific rendering.

`VERIFIED`: The affected generation-fidelity boundary passes 46 tests with clean formatting, Ruff,
and Pyright. The authoritative final full-gate command and elapsed time are recorded in engineering
loop `20260918T172036Z-0c23bbc2`; this source report does not claim evidence collected after its own
revision.

## 7. Acceptance-criterion coverage and waivers

- AC1: covered by the frozen protocol, access declarations, denominator rules, and accepted ADR.
- AC2: covered by strict review-v2 validation and the schema-aware blinded offline renderer.
- AC3: covered by the immutable manifest contract and prompt-digest verification tests.
- AC4: covered by the nine-case deterministic development fixture and category tests.
- AC5: covered by retained v1 tests, static/type checks, affected tests, and the final repository
  gate recorded in the engineering loop.

No criterion is waived. Independent review and the revision-bound verdict remain engineering-loop
evidence and must precede integration.

The first independent review reproduced three AC2 defects: category-mismatched annotations were
accepted, browser completion did not apply annotation invariants, and the HTML builder overwrote a
retained destination. Attempt 2 repairs all three with focused Python and executable JavaScript
regressions plus v1/v2 retained-path tests. A fresh independent verdict on the repaired candidate
is still required; the superseded revise verdict remains preserved in the loop record.

## 8. Baseline-relative write scope and violations

`VERIFIED`: The loop began at clean commit `0c23bbc2` in isolated branch
`codex/generation-fidelity-foundation`. Durable changes are limited to the accepted ADR, protocol,
research/design/plan/report/handoff/correction documentation, one source module, the existing
review tool, focused tests, and one fixture. The loop recovery check reports no scope violation.

## 9. GitHub Issue, Project, PR, and release state

`VERIFIED`: Issue #26 is open with the M2 milestone and `enhancement` label. Project #17 membership
was previewed but not applied because that external planning write was not authorized.

`VERIFIED`: No pull request, merge, push, tag, GitHub Release, package publication, deployment,
model request, or confirmation run is claimed. Release impact is expected to be `none` because the
slice adds research/evaluation tooling without changing the public application contract; the final
recommendation is recorded in the loop.

## 10. Risks, limitations, and unverified claims

`VERIFIED`: Schema validity cannot prove that a reviewer or custodian honored the declared access
boundary. The challenge corpus proves deterministic contract behavior only. Public benchmarks are
exposed development material, and no generated-answer quality improvement is established.

`VERIFIED`: The browser UI collects structured offsets but Python validation remains the authority
for bounds and semantic consistency. Human usability and agreement require a separately authorized
development pilot before confirmation.

## 11. Decisions or authorization needed

A future confirmation loop requires owner approval for the custodian, untouched cohort source,
access transfer, baseline/candidate identities, prompt digests, request budget, stopping rules, and
result-release boundary. None is inferred from Issue #26.

## 12. Recommended next loop

After this foundation is integrated, prepare a custodian-owned confirmation protocol and a bounded
development-only reviewer pilot as separate authorized work. Do not acquire or expose confirmation
content during candidate development.
