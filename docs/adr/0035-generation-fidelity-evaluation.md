# ADR-0035: Sealed generation-fidelity evaluation boundary

- Status: proposed
- Date: 2026-09-18
- Decider: Jack Rory Staunton, human owner
- Governing issue: [#26](https://github.com/stauntonjr/scifact-rag/issues/26)

## Context

The completed SciFact generation-context comparison found 18 of 24 reviewed answers grounded for
each policy and did not support changing the whole-document default. Those rows and the historical
BEIR material are already development evidence. Repartitioning them cannot create an untouched
confirmation set.

The owner approved a new research direction that targets material qualifier loss, population
generalization, and causal strengthening. The first slice must establish truthful measurement and
access boundaries without changing product generation or opening confirmation material.

Observed repository evidence:

- generation manifests and raw-result journals already fail closed on identity drift;
- the v1 human-review tool keeps policy and automatic outcomes out of the reviewer worksheet;
- the active product-validation-challenges capability owns deterministic known-bad examples; and
- the public application response contract must remain unchanged in this slice.

Assumptions remain prospective: a later custodian can select and annotate a rights-qualified,
article-family-disjoint cohort, and a later issue can fund enough cases for a useful decision.

## Decision

- Add a separate `generation-fidelity-manifest/v1` contract rather than changing
  `generation-run-manifest/v1`.
- Represent `development`, `stress`, and `confirmation` phases explicitly. A confirmation
  manifest is valid only with a custodian-only access declaration, a non-empty seal timestamp,
  and no developer-open timestamp.
- Store only cohort identity, digests, counts, opaque article-family digests, candidate prompt
  identities, and access declarations in the manifest. Do not store questions, evidence,
  annotations, answers, or source text.
- Require exactly one baseline and one candidate identity for a paired comparison. Prompt text
  remains outside the manifest; callers verify the recorded prompt digests against independently
  frozen expected identities.
- Add `generation-human-review/v2` without changing v1. V2 retains every v1 categorical field and
  adds explicit causal-strengthening and population-generalization judgments plus structured
  material-error annotations.
- Every V2 material-error annotation names one category and one bounded answer span. It must also
  name one or more bounded evidence spans or explicitly declare that the evidence support is
  absent. This keeps unsupported text and contrasting evidence distinguishable.
- Use development-only deterministic challenge fixtures for plumbing and regression checks.
  Fixture expectations are not an automatic semantic judge and cannot establish quality.
- Keep product prompts, defaults, retrieval, context assembly, citations, and all public
  CLI/HTTP/MCP/web response contracts unchanged.
- Defer cohort acquisition, human annotation, candidate prompt implementation, model requests,
  latency measurement, statistical confirmation, and promotion.

This decision establishes evaluation authority and data semantics only. It does not assert that a
candidate improves generation.

## Consequences

### Positive

- Historical v1 artifacts remain reproducible and interpretable.
- Development tooling cannot truthfully label exposed data as sealed confirmation.
- Article-family dependence and paired candidate identity are preserved before outcomes exist.
- Human findings retain bounded evidence instead of only free-text notes.
- Later candidate work can reuse one explicit contract without changing product interfaces.

### Negative

- A new schema and rubric version increase validator and migration-test surface.
- The manifest can validate a declared access state but cannot prove human custody by itself.
- Human span annotation adds review time and requires a later agreement protocol.
- No user-visible generation improvement occurs in Issue #26.

### Risks and mitigations

- **False seal claim:** a valid JSON declaration could misrepresent actual access. Mitigation:
  require a named custodian and dated access declaration in the later protocol, and describe
  schema validation as consistency evidence rather than proof of custody.
- **V1 regression:** shared review code could reinterpret historical worksheets. Mitigation:
  dispatch validation by exact schema version and retain existing v1 fixtures byte-for-byte.
- **Abstention gaming:** later prompts could reduce unsupported claims by returning nothing.
  Mitigation: the future protocol separately counts adequate grounded answers, incorrect
  abstentions, missing outputs, and a conservative failure composite.
- **Fixture overclaim:** deterministic contrasts could be presented as model-quality evidence.
  Mitigation: fixtures test plumbing only; human review owns semantic judgment.

## Alternatives considered

| Alternative | Evidence | Reason not selected |
|---|---|---|
| Extend generation-run-manifest/v1 in place | Existing schema is strict and historically frozen | Would invalidate or ambiguously reinterpret retained runs. |
| Use the old SciFact validation or test rows | Existing reports contain rich outcomes | Already exposed; cannot support untouched confirmation. |
| Adopt PubMedQA or QASPER | Public scientific QA datasets | Changes the task and still lacks project sealing. |
| Add an LLM-as-judge or autonomous critic now | Could reduce annotation work | Adds a model and validity boundary before the human rubric is stable. |
| Implement the candidate prompt first | Fastest path to visible output | Invites tuning before measurement, exposure, and custody rules are frozen. |

## Verification and revisit trigger

Verification must prove strict round trips, unknown-field refusal, duplicate refusal, phase/access
rules, prompt-digest comparison, V2 span bounds, V1 compatibility, complete challenge-category
coverage, and unchanged product/interface tests. Exactly one final repository smoke gate applies to
the accepted implementation candidate.

Revisit through a superseding ADR before changing the phase/access model, storing hidden case
payloads in the manifest, replacing human review, changing the paired comparison, or promoting a
candidate. Model execution and confirmation access require separate accepted issues even if this
ADR is accepted.

