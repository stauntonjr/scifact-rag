# Generation-fidelity foundation design

- Date: 2026-09-18
- Governing issue: [#26](https://github.com/stauntonjr/scifact-rag/issues/26)
- Engineering-loop run: `20260918T172036Z-0c23bbc2`
- Owner-approved boundary: model-free measurement foundation only

## Goal

Create the smallest fail-closed foundation needed to measure a later generation-fidelity
candidate while preserving the completed SciFact product, historical evaluation artifacts, and a
future sealed confirmation boundary.

The implementation does not improve generation. It makes later improvement claims testable.

## Scope and authority

Included:

- a versioned fidelity protocol and prior-art record;
- a proposed architecture decision;
- a model-free candidate/cohort manifest and validator;
- a backward-compatible v2 blinded-review format;
- deterministic development-only fidelity challenges; and
- focused, affected-contract, independent, and full verification evidence.

Excluded:

- any generator or reranker request;
- prompt, retrieval, context, citation, or default changes;
- confirmation cohort acquisition, inspection, annotation, or execution;
- service or GPU lifecycle changes;
- quality, latency, power, or promotion claims; and
- Project membership, release, deployment, or external notification.

Any excluded need is a scope-revision trigger, not an implementation convenience.

## Architecture

### 1. Fidelity manifest module

Create `src/scifact_rag/generation_fidelity.py` as a focused, framework-free contract. It does not
depend on the application composition root or any transport.

Public types:

```python
class FidelityPhase(StrEnum):
    DEVELOPMENT = "development"
    STRESS = "stress"
    CONFIRMATION = "confirmation"

class FidelityAccess(StrEnum):
    DEVELOPER = "developer"
    CUSTODIAN_ONLY = "custodian-only"

class CandidateRole(StrEnum):
    BASELINE = "baseline"
    CANDIDATE = "candidate"

@dataclass(frozen=True, slots=True)
class FidelityCandidate:
    role: CandidateRole
    candidate_id: str
    product_prompt_id: str
    product_prompt_sha256: str
    diagnostic_prompt_id: str
    diagnostic_prompt_sha256: str

@dataclass(frozen=True, slots=True)
class FidelityCohort:
    cohort_id: str
    cohort_sha256: str
    scheduled_cases: int
    article_family_sha256s: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class FidelityAccessDeclaration:
    access: FidelityAccess
    custodian: str | None
    sealed_at: str | None
    developer_opened_at: str | None

@dataclass(frozen=True, slots=True)
class GenerationFidelityManifest:
    schema_version: str
    manifest_id: str
    phase: FidelityPhase
    cohort: FidelityCohort
    candidates: tuple[FidelityCandidate, FidelityCandidate]
    access_declaration: FidelityAccessDeclaration

    @classmethod
    def from_json(cls, serialized: str) -> "GenerationFidelityManifest": ...
    def to_json(self) -> str: ...
    def require_prompt_hashes(
        self,
        expected: Mapping[str, tuple[str, str]],
    ) -> None: ...
```

The serialized schema is exact: unknown, missing, or mistyped fields fail. Identifiers use the
repository's conservative safe-name convention and all digests are lowercase SHA-256.

Invariants:

- exactly two candidates exist, one per role;
- candidate IDs and every prompt ID are unique within their relevant namespace;
- `scheduled_cases` is positive;
- article-family digests are non-empty, unique, and sorted;
- development and stress require `developer` access and prohibit seal/open timestamps;
- confirmation requires `custodian-only`, a nonblank custodian, a timezone-aware `sealed_at`, and
  no `developer_opened_at`;
- manifests never contain source text, questions, evidence, labels, answers, or review outcomes;
  strict unknown-field rejection enforces that serialization boundary; and
- `require_prompt_hashes` compares each role's product and diagnostic digests against separately
  supplied frozen identities and fails on missing, foreign, or mismatched entries.

This contract validates internal consistency. It does not prove that a person honored the access
declaration.

### 2. Generation review v2

Extend `tools/generation_review.py` through exact schema-version dispatch. Keep all v1 functions,
HTML behavior, categorical fields, error messages relied on by tests, and frozen source checks.

V2 rows retain `response_id`, `claim`, `evidence`, `answer`, and `review`. V2 review retains every
v1 field and adds:

```json
{
  "causal_strengthening": "yes | no | not_applicable | uncertain",
  "population_generalization": "yes | no | not_applicable | uncertain",
  "material_errors": [
    {
      "category": "qualifier_loss | population_generalization | causal_strengthening | negation_loss | intervention_change | comparison_change | outcome_change | unsupported_claim",
      "answer_span": {"start": 0, "end": 12},
      "evidence_spans": [
        {"evidence_index": 0, "start": 5, "end": 21}
      ],
      "evidence_absent": false
    }
  ]
}
```

Span intervals are half-open Unicode-code-point offsets into the exact displayed strings.
`start < end`, indices must be in bounds, and an error must have either one or more evidence spans
or `evidence_absent=true`, never both. Categories may not repeat with the same answer interval.

V2 consistency rules:

- a clean grounded review has no material errors;
- any `grounded=no`, `material_overstatement=present`, causal strengthening, population
  generalization, or other material omission requires at least one matching material-error row;
- `uncertain` remains a non-pass but does not invent a definitive category;
- completed exports require all categorical fields and valid annotations;
- source validation ignores only review content and completion metadata, exactly as v1 does; and
- reviewer HTML contains no arm, prompt, expected label, automatic score, aggregate, or mapping
  field.

The v2 browser UI adds the two categorical questions and bounded span inputs. It continues to use
local storage only and emits no network request.

### 3. Fidelity protocol

Create `docs/project/generation-fidelity-v1.md` as the normative human protocol. It defines:

- historical SciFact rows as development/regression evidence;
- article-family exposure identity across paraphrases, preprints, and publication versions;
- distinct representative-primary and enriched-stress cohorts;
- custodian and developer responsibilities;
- source/evidence/answerability versus supplied-context grounding;
- conservative accounting for missing, failed, unresolved, and abstaining outputs;
- paired denominators and article-family analysis;
- the future freeze and one-time-open rule; and
- explicit stop conditions before any confirmation access.

The protocol records proposed later promotion thresholds as unaccepted future criteria, not Issue
#26 acceptance.

### 4. Development challenges

Create `tests/fixtures/generation_fidelity_challenges.json` with schema
`generation-fidelity-challenges/v1`. Each fictional, development-only case contains:

- stable `challenge_id`;
- one `distinction`;
- `question` and one or more evidence passages;
- `required_behavior` and `forbidden_behavior`; and
- `expected_disposition` of `answer` or `insufficient-evidence`.

Required distinctions are qualifier restriction, population/species boundary, observational
association, non-significant difference, surrogate outcome, conflicting/incomplete evidence,
insufficient evidence, and supported control. Tests enforce schema, uniqueness, complete category
coverage, and at least two supported controls. They do not call a model or score semantics.

The active `product-validation-challenges` capability owns this fixture. No inactive capability is
activated.

## Data flow

```text
protocol + frozen prompt identities
                |
                v
      strict fidelity manifest -----> model execution (later issue only)
                |                                  |
                |                                  v
                +------------------------> blinded v2 worksheet
                                                     |
                                                     v
                                          source-bound validation
                                                     |
                                                     v
                                        paired analysis (later issue)
```

Issue #26 implements only the left-hand contracts and model-free worksheet validation. It creates
no arrow into model execution.

## Failure behavior

- Parse and validate complete inputs in memory before writing outputs.
- Reject existing output paths rather than overwrite retained evidence.
- Reject unknown schema fields and versions.
- Reject duplicate identities and unsorted family digests.
- Reject phase/access contradictions and all confirmation developer-open declarations.
- Reject prompt identity drift before an executor could be constructed.
- Reject altered reviewer-facing source content, unblinding fields, invalid spans, incomplete
  categories, and inconsistent material-error annotations.
- Never repair, coerce, truncate, remap, or silently drop invalid evidence.

## Verification design

TDD is mandatory. Every new behavior begins with a focused failing test.

Targeted checks:

- `tests/test_generation_fidelity.py` for manifest round trips and all refusal paths;
- `tests/test_generation_review.py` for v2 rendering, validation, span bounds, consistency, and
  unchanged v1 behavior; and
- fixture-schema/category tests without any model endpoint.

Affected-contract checks cover evaluation, generation review, application, generator adapter, and
interface contracts. Product prompt constants and current defaults are compared directly where
useful. Exactly one `make smoke` runs on the final current attempt after release-impact recording.

An independent verifier who did not author the change reviews the stable candidate. Findings are
collected as one batch before any repair.

## Files and ownership

| Path | Responsibility |
|---|---|
| `src/scifact_rag/generation_fidelity.py` | Strict model-free fidelity manifest types and validation |
| `tools/generation_review.py` | Exact v1/v2 blinded worksheet dispatch, rendering, and validation |
| `tests/test_generation_fidelity.py` | Manifest and challenge contract tests |
| `tests/test_generation_review.py` | V1 compatibility and V2 review tests |
| `tests/fixtures/generation_fidelity_challenges.json` | Development-only semantic contrasts |
| `docs/project/generation-fidelity-v1.md` | Normative measurement, custody, and interpretation protocol |
| `docs/research/generation-fidelity-existing-solutions.md` | Prior-art and dataset disposition |
| `docs/adr/0036-generation-fidelity-evaluation.md` | Proposed durable architecture decision |
| `docs/project/handoff.md` | Current state and next authority boundary |
| `docs/reports/issue-26-generation-fidelity-foundation.md` | Final accepted evidence summary |

## Implementation order

1. Freeze protocol and exact schemas in an implementation plan.
2. Add manifest refusal tests, observe failure, then implement the focused module.
3. Add challenge-fixture tests, observe failure, then add the fixture.
4. Add v2 review tests one behavior at a time, preserving v1 after every cycle.
5. Run targeted and affected checks.
6. Record release impact, run the one final full gate, and stabilize the candidate.
7. Obtain independent review and reconcile findings under the engineering-loop contract.
8. Update handoff/report and finish the loop without starting candidate or confirmation work.
