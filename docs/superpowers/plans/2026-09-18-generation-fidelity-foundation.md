# Generation-Fidelity Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add strict, model-free contracts for generation-fidelity phases, paired candidate identity, blinded v2 review, and development challenges without changing product generation or opening confirmation data.

**Architecture:** A new framework-free `generation_fidelity` module owns only manifest identity and access-state validation. The existing standalone review tool dispatches by exact schema version so historical v1 artifacts remain unchanged while v2 adds causal, population, and bounded span annotations. A fictional development fixture exercises contract plumbing but is never treated as a semantic quality oracle.

**Tech Stack:** Python 3.12, frozen dataclasses, `StrEnum`, canonical JSON, existing standalone HTML/JavaScript reviewer, pytest, Ruff, Pyright, and the repository engineering loop. No new dependency or service.

**Spec:** `docs/superpowers/specs/2026-09-18-generation-fidelity-foundation-design.md`

## Global Constraints

- Governing Issue: `#26`; engineering-loop run: `20260918T172036Z-0c23bbc2`.
- No model, reranker, database, network, GPU, service-lifecycle, or confirmation-data access.
- Do not change product prompts, defaults, retrieval, context assembly, citation behavior, or public CLI/HTTP/MCP/web contracts.
- Preserve `generation-run-manifest/v1` and `generation-human-review/v1` exactly at their accepted boundaries.
- The fidelity manifest contains identity and access metadata only—never questions, evidence, annotations, answers, outcomes, or source text.
- Use TDD for every behavior change: write one failing test, run it and confirm the expected failure, implement the minimum behavior, then rerun.
- Exactly one `make smoke` may be recorded as the final full gate for the final current attempt.
- Do not access or invent a confirmation cohort. Project-unseen never implies model-unseen.

---

### Task 1: Freeze the normative fidelity protocol

**Files:**
- Create: `docs/project/generation-fidelity-v1.md`
- Modify: `docs/adr/0036-generation-fidelity-evaluation.md`
- Reference: `docs/project/generation-human-review-v1.md`
- Reference: `docs/reports/issue-5-generation-context-validation.md`

**Interfaces:**
- Consumes: accepted ADR-0036 and Issue #26 acceptance criteria.
- Produces: the normative phase, custody, accounting, and interpretation contract used by every later task.

- [ ] **Step 1: Write the protocol with exact authority boundaries**

Create `docs/project/generation-fidelity-v1.md` with these required headings and rules:

```markdown
# Generation fidelity protocol v1

## Purpose and evidence status
The protocol measures whether a candidate preserves material scientific meaning in supplied
evidence. It does not change retrieval, generation, or product defaults. Historical SciFact
outcomes are development evidence and cannot be relabeled as untouched confirmation.

## Phases
- `development`: visible to developers; used for fixture, prompt, and tool development.
- `stress`: visible to developers; enriched for named failure classes and reported separately.
- `confirmation`: held by a named custodian, article-family disjoint from development and stress,
  and opened once only after code, prompts, runtime, analysis, retry, and decision rules freeze.

## Exposure identity
One article family includes preprints, accepted manuscripts, publisher versions, corrections,
paraphrases, and prompts derived from the same scientific result. Family assignment precedes
outcome generation. Exact-text deduplication alone is insufficient.

## Roles and access
The custodian selects, rights-qualifies, annotates, freezes, and executes confirmation cases. The
developer may see only cohort identity, counts, digests, and opaque article-family digests before
unblinding. A manifest declaration is consistency evidence, not proof of human custody.

## Grounding and answerability
Grounding is judged only against supplied context. Full-source and gold annotations separately
measure answerability, retrieval, and assembly. Missing retrieval evidence, removed assembly
evidence, and generation misstatement are distinct failure sources.

## Conservative accounting
All scheduled cases remain in denominators. Missing output, execution failure, unresolved review,
invalid citation, and incorrect abstention are reported separately and count as non-passes in the
conservative quality composite. They are not relabeled as proven hallucinations.

## Review and paired analysis
Baseline and candidate use identical cached contexts. Review identities are opaque and arm labels
remain separate. Article-family—not prompt—is the resampling unit. Primary and enriched stress
cohorts are never pooled into an unweighted population rate.

## Freeze and stop rules
Freeze repository commit, model/runtime revision, prompt digests, decoding, context, request cap,
retry policy, cohort digest, review rules, analysis, and promotion rule before confirmation access.
Stop rather than open confirmation when custody, rights, identity, budget, or power is unresolved.
Once outcomes are inspected, that cohort becomes development evidence.

## Deferred proposed promotion rule
The numerical thresholds in the owner plan are proposals for a later issue. Issue #26 neither
accepts them nor produces evidence against them.
```

- [ ] **Step 2: Confirm ADR acceptance provenance**

Keep ADR-0036 at `Status: accepted` and add this sentence below its header if absent:

```markdown
Owner acceptance: confirmed in the Issue #26 implementation task on 2026-09-18.
```

- [ ] **Step 3: Run documentation static checks**

Run:

```bash
python3 tools/harness_check.py
git diff --check
rg -n 'T[B]D|T[O]DO|implement[ ]later|fill[ ]in[ ]details' \
  docs/project/generation-fidelity-v1.md \
  docs/adr/0036-generation-fidelity-evaluation.md
```

Expected: harness check exits 0; `git diff --check` exits 0; `rg` returns no matches.

- [ ] **Step 4: Record the static check**

Run:

Record `fidelity-protocol-static` with `tools/loop.py record-check`, the exact three commands from
Step 3, their measured elapsed seconds, `tier static`, criteria AC1 and AC5, and evidence text:
`Normative protocol and accepted ADR preserve the model-free phase, custody, accounting, and stop boundaries.`

- [ ] **Step 5: Commit**

```bash
git add docs/project/generation-fidelity-v1.md docs/adr/0036-generation-fidelity-evaluation.md
git commit -m "docs: freeze generation fidelity protocol"
```

---

### Task 2: Implement the strict fidelity manifest

**Files:**
- Create: `src/scifact_rag/generation_fidelity.py`
- Create: `tests/test_generation_fidelity.py`

**Interfaces:**
- Consumes: protocol phase/access rules and frozen prompt identities supplied by a caller.
- Produces: `FidelityPhase`, `FidelityAccess`, `CandidateRole`, `FidelityCandidate`, `FidelityCohort`, `FidelityAccessDeclaration`, and `GenerationFidelityManifest`.

- [ ] **Step 1: Write the first failing round-trip and phase tests**

Create `tests/test_generation_fidelity.py` with imports and this helper:

```python
from __future__ import annotations

import json

import pytest

from scifact_rag.generation_fidelity import (
    CandidateRole,
    FidelityAccess,
    FidelityAccessDeclaration,
    FidelityCandidate,
    FidelityCohort,
    FidelityPhase,
    GenerationFidelityManifest,
)


def _candidate(role: CandidateRole) -> FidelityCandidate:
    return FidelityCandidate(
        role=role,
        candidate_id=f"{role.value}-v1",
        product_prompt_id=f"product-{role.value}-v1",
        product_prompt_sha256=("a" if role is CandidateRole.BASELINE else "b") * 64,
        diagnostic_prompt_id=f"diagnostic-{role.value}-v1",
        diagnostic_prompt_sha256=("c" if role is CandidateRole.BASELINE else "d") * 64,
    )


def _manifest(
    *,
    phase: FidelityPhase = FidelityPhase.DEVELOPMENT,
    access: FidelityAccess = FidelityAccess.DEVELOPER,
    custodian: str | None = None,
    sealed_at: str | None = None,
) -> GenerationFidelityManifest:
    return GenerationFidelityManifest(
        schema_version="generation-fidelity-manifest/v1",
        manifest_id="generation-fidelity-development-v1",
        phase=phase,
        cohort=FidelityCohort(
            cohort_id="development-primary-v1",
            cohort_sha256="e" * 64,
            scheduled_cases=24,
            article_family_sha256s=("1" * 64, "2" * 64),
        ),
        candidates=(
            _candidate(CandidateRole.BASELINE),
            _candidate(CandidateRole.CANDIDATE),
        ),
        access_declaration=FidelityAccessDeclaration(
            access=access,
            custodian=custodian,
            sealed_at=sealed_at,
            developer_opened_at=None,
        ),
    )


def test_fidelity_manifest_round_trips_canonical_identity_only_json() -> None:
    original = _manifest()
    serialized = original.to_json()
    restored = GenerationFidelityManifest.from_json(serialized)
    assert restored == original
    assert serialized.endswith("\n")
    assert set(json.loads(serialized)) == {
        "access_declaration", "candidates", "cohort", "manifest_id", "phase", "schema_version"
    }
    forbidden = {"question", "evidence", "answer", "label", "outcome", "source_text"}
    assert forbidden.isdisjoint(serialized.lower())


def test_confirmation_requires_an_unopened_custodian_seal() -> None:
    confirmed = _manifest(
        phase=FidelityPhase.CONFIRMATION,
        access=FidelityAccess.CUSTODIAN_ONLY,
        custodian="independent-custodian",
        sealed_at="2026-09-18T17:00:00Z",
    )
    assert confirmed.phase is FidelityPhase.CONFIRMATION
    with pytest.raises(ValueError, match="confirmation.*custodian-only"):
        _manifest(phase=FidelityPhase.CONFIRMATION)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
uv run pytest tests/test_generation_fidelity.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'scifact_rag.generation_fidelity'`.

- [ ] **Step 3: Implement enums, dataclasses, and invariant helpers**

Create `src/scifact_rag/generation_fidelity.py` with:

```python
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any

SCHEMA_VERSION = "generation-fidelity-manifest/v1"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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


def _safe_name(field_name: str, value: object) -> None:
    if not isinstance(value, str) or not _SAFE_NAME.fullmatch(value):
        raise ValueError(f"{field_name} must be a safe non-empty identifier")


def _sha256(field_name: str, value: object) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256")


def _utc(field_name: str, value: object) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field_name} must be an ISO-8601 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be an ISO-8601 UTC timestamp ending in Z"
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include timezone information")
```

Implement the seven exact dataclasses from the design. In each `__post_init__`, validate Python
types before values so booleans cannot pass as integers. `GenerationFidelityManifest.__post_init__`
must enforce:

```python
if self.schema_version != SCHEMA_VERSION:
    raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
_safe_name("manifest_id", self.manifest_id)
if tuple(candidate.role for candidate in self.candidates) != (
    CandidateRole.BASELINE,
    CandidateRole.CANDIDATE,
):
    raise ValueError("candidates must contain baseline then candidate exactly once")
if self.phase is FidelityPhase.CONFIRMATION:
    if self.access_declaration.access is not FidelityAccess.CUSTODIAN_ONLY:
        raise ValueError("confirmation phase requires custodian-only access")
    if not self.access_declaration.custodian:
        raise ValueError("confirmation phase requires a named custodian")
    if self.access_declaration.sealed_at is None:
        raise ValueError("confirmation phase requires sealed_at")
    if self.access_declaration.developer_opened_at is not None:
        raise ValueError("confirmation phase must remain unopened by developers")
else:
    if self.access_declaration != FidelityAccessDeclaration(
        access=FidelityAccess.DEVELOPER,
        custodian=None,
        sealed_at=None,
        developer_opened_at=None,
    ):
        raise ValueError("development and stress phases require unsealed developer access")
```

Serialize with `json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"`.

- [ ] **Step 4: Implement strict nested parsing and prompt-hash comparison**

Add a private exact-field helper:

```python
def _exact_object(value: object, cls: type[Any], location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{location} must be a JSON object")
    expected = {field.name for field in fields(cls)}
    if set(value) != expected:
        raise ValueError(f"{location} fields do not match the schema")
    return value
```

`from_json` must parse the top level, cohort, access declaration, and two candidate objects with
this helper; convert enum strings explicitly; convert lists to tuples; and wrap constructor type
errors as `ValueError("manifest values do not match the schema: ...")` without weakening clear
schema-version or digest errors.

Implement prompt verification exactly by candidate role:

```python
def require_prompt_hashes(
    self,
    expected: Mapping[str, tuple[str, str]],
) -> None:
    required = {candidate.role.value for candidate in self.candidates}
    if set(expected) != required:
        raise ValueError("expected prompt identities must name baseline and candidate exactly")
    for candidate in self.candidates:
        product, diagnostic = expected[candidate.role.value]
        if product != candidate.product_prompt_sha256:
            raise ValueError(f"{candidate.role.value} product prompt SHA-256 mismatch")
        if diagnostic != candidate.diagnostic_prompt_sha256:
            raise ValueError(f"{candidate.role.value} diagnostic prompt SHA-256 mismatch")
```

- [ ] **Step 5: Verify GREEN for the first tests**

Run:

```bash
uv run pytest tests/test_generation_fidelity.py -q
```

Expected: the initial round-trip and confirmation-access tests pass.

- [ ] **Step 6: Add refusal tests one behavior at a time**

Add parametrized tests covering:

```python
@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda raw: raw.update({"question": "hidden"}), "fields do not match"),
        (lambda raw: raw["cohort"].update({"scheduled_cases": 0}), "scheduled_cases"),
        (lambda raw: raw["cohort"].update({"article_family_sha256s": ["1" * 64, "1" * 64]}), "unique"),
        (lambda raw: raw["cohort"].update({"article_family_sha256s": ["2" * 64, "1" * 64]}), "sorted"),
        (lambda raw: raw["candidates"].append(raw["candidates"][0]), "baseline then candidate"),
        (lambda raw: raw["access_declaration"].update({"developer_opened_at": "2026-09-18T18:00:00Z"}), "developer access"),
    ],
)
def test_manifest_rejects_identity_and_access_drift(mutation, message) -> None:
    raw = json.loads(_manifest().to_json())
    mutation(raw)
    with pytest.raises((TypeError, ValueError), match=message):
        GenerationFidelityManifest.from_json(json.dumps(raw))
```

Add direct-constructor tests for booleans as counts, malformed identifiers, invalid digests,
duplicate prompt IDs, non-UTC seals, wrong enum Python types, a non-object JSON document, and all
prompt-hash mismatch branches. Run each new test first and confirm it fails for the intended
missing check before adding that check.

- [ ] **Step 7: Run focused static and targeted checks**

Run:

```bash
uv run ruff format --check src/scifact_rag/generation_fidelity.py tests/test_generation_fidelity.py
uv run ruff check src/scifact_rag/generation_fidelity.py tests/test_generation_fidelity.py
uv run pyright src/scifact_rag/generation_fidelity.py tests/test_generation_fidelity.py
uv run pytest tests/test_generation_fidelity.py -q
```

Expected: all commands pass with no warnings or skipped tests.

- [ ] **Step 8: Record checks and commit**

Record Ruff/Pyright as `static` evidence for AC3 and pytest as `targeted` evidence for AC3, using
the exact commands and measured durations. Then:

```bash
git add src/scifact_rag/generation_fidelity.py tests/test_generation_fidelity.py
git commit -m "feat: add generation fidelity manifest"
```

---

### Task 3: Add development-only fidelity challenges

**Files:**
- Modify: `tests/test_generation_fidelity.py`
- Create: `tests/fixtures/generation_fidelity_challenges.json`

**Interfaces:**
- Consumes: active `product-validation-challenges` capability.
- Produces: a fictional deterministic corpus for schema and pipeline regression tests only.

- [ ] **Step 1: Write the failing fixture contract test**

Add:

```python
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "generation_fidelity_challenges.json"


def test_generation_fidelity_challenges_are_complete_and_development_only() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "generation-fidelity-challenges/v1"
    assert payload["phase"] == "development"
    assert payload["synthetic"] is True
    cases = payload["cases"]
    assert len({case["challenge_id"] for case in cases}) == len(cases)
    assert {case["distinction"] for case in cases} == {
        "qualifier-restriction",
        "population-species-boundary",
        "observational-association",
        "non-significant-difference",
        "surrogate-outcome",
        "conflicting-incomplete-evidence",
        "insufficient-evidence",
        "supported-control",
    }
    assert sum(case["distinction"] == "supported-control" for case in cases) >= 2
    for case in cases:
        assert set(case) == {
            "challenge_id", "distinction", "evidence", "expected_disposition",
            "forbidden_behavior", "question", "required_behavior"
        }
        assert case["expected_disposition"] in {"answer", "insufficient-evidence"}
        assert case["evidence"] and all(item.strip() for item in case["evidence"])
```

- [ ] **Step 2: Run and verify RED**

Run `uv run pytest tests/test_generation_fidelity.py::test_generation_fidelity_challenges_are_complete_and_development_only -q`.

Expected: fail because the fixture file does not exist.

- [ ] **Step 3: Create the complete fictional fixture**

Create canonical indented JSON with top-level fields `schema_version`, `phase`, `synthetic`, and
`cases`. Include nine cases: one for each non-control distinction and two supported controls.
Use invented study names and values, never copied project or confirmation cases. Examples must
encode these exact contrasts:

```json
{
  "challenge_id": "observational-association-01",
  "distinction": "observational-association",
  "question": "Does exposure A prevent outcome B?",
  "evidence": ["In a retrospective cohort, exposure A was associated with lower outcome B; residual confounding could not be excluded."],
  "required_behavior": "Describe an association and retain the residual-confounding limitation.",
  "forbidden_behavior": "Claim that exposure A prevents or causes a reduction in outcome B.",
  "expected_disposition": "answer"
}
```

The two controls must contain direct human evidence with no hidden qualifier and require a concise
supported answer, preventing an abstention-only implementation from satisfying the fixture.

- [ ] **Step 4: Verify GREEN and record**

Run `uv run pytest tests/test_generation_fidelity.py -q`. Record it as targeted evidence for AC4
with the exact duration.

- [ ] **Step 5: Commit**

```bash
git add tests/test_generation_fidelity.py tests/fixtures/generation_fidelity_challenges.json
git commit -m "test: add generation fidelity challenges"
```

---

### Task 4: Add strict v2 review validation while preserving v1

**Files:**
- Modify: `tools/generation_review.py`
- Modify: `tests/test_generation_review.py`

**Interfaces:**
- Consumes: exact v1 worksheet contract and v2 annotation design.
- Produces: schema-version-dispatched `validate_worksheet`, `load_worksheet`, and `validate_completed` behavior.

- [ ] **Step 1: Add v2 test builders**

Add helpers without changing `_worksheet` or `_review_values`:

```python
def _v2_review_values(*, complete: bool, material_error: bool = False) -> dict[str, object]:
    values: dict[str, object] = {
        **_review_values("complete" if complete else None),
        "causal_strengthening": "yes" if complete and material_error else ("no" if complete else None),
        "population_generalization": "no" if complete else None,
        "material_errors": [],
    }
    if complete and material_error:
        values["grounded"] = "no"
        values["material_overstatement"] = "present"
        values["material_errors"] = [
            {
                "category": "causal_strengthening",
                "answer_span": {"start": 11, "end": 17},
                "evidence_spans": [{"evidence_index": 0, "start": 15, "end": 30}],
                "evidence_absent": False,
            }
        ]
    return values


def _v2_worksheet(*, complete: bool = False, material_error: bool = False) -> dict[str, object]:
    data = _worksheet(complete=complete)
    data["schema_version"] = "generation-human-review/v2"
    data["selection_protocol"] = "docs/project/generation-fidelity-v1.md"
    for row in data["rows"]:  # type: ignore[index]
        row["review"] = _v2_review_values(complete=complete, material_error=material_error)
    return data
```

- [ ] **Step 2: Write and run a failing v2 validation test**

```python
def test_v2_accepts_bounded_material_error_annotations() -> None:
    module = _tool_module()
    validated = module.validate_worksheet(
        _v2_worksheet(complete=True, material_error=True),
        require_complete=True,
    )
    assert validated["schema_version"] == "generation-human-review/v2"
```

Run the test and confirm RED with `schema_version must be generation-human-review/v1`.

- [ ] **Step 3: Refactor constants into exact versioned contracts**

In `tools/generation_review.py`, retain `SCHEMA_VERSION` as the v1 compatibility alias and add:

```python
SCHEMA_VERSION_V1 = "generation-human-review/v1"
SCHEMA_VERSION_V2 = "generation-human-review/v2"
SCHEMA_VERSION = SCHEMA_VERSION_V1
REVIEW_OPTIONS_V2 = {
    **REVIEW_OPTIONS,
    "causal_strengthening": {"yes", "no", "not_applicable", "uncertain"},
    "population_generalization": {"yes", "no", "not_applicable", "uncertain"},
}
MATERIAL_ERROR_CATEGORIES = {
    "qualifier_loss", "population_generalization", "causal_strengthening", "negation_loss",
    "intervention_change", "comparison_change", "outcome_change", "unsupported_claim",
}
SPAN_FIELDS = {"start", "end"}
EVIDENCE_SPAN_FIELDS = {"evidence_index", "start", "end"}
MATERIAL_ERROR_FIELDS = {
    "answer_span", "category", "evidence_absent", "evidence_spans"
}
```

At the start of `validate_worksheet`, select `review_options` and `review_fields` only after the
top-level object and exact schema value are known. Unknown schema versions must fail before row
validation. Do not mutate global sets at runtime.

- [ ] **Step 4: Implement span and consistency validation**

Add pure helpers:

```python
def _span(
    value: object,
    *,
    text: str,
    location: str,
    errors: list[str],
) -> tuple[int, int] | None:
    _unexpected(value, SPAN_FIELDS, location, errors)
    if not isinstance(value, dict):
        return None
    start, end = value.get("start"), value.get("end")
    if (
        isinstance(start, bool) or isinstance(end, bool)
        or not isinstance(start, int) or not isinstance(end, int)
        or start < 0 or end <= start or end > len(text)
    ):
        errors.append(f"{location} must be a non-empty half-open span within its text")
        return None
    return start, end
```

Add `_validate_v2_material_errors(row, review, location, errors)`. It must:

- require `material_errors` to be a list;
- keep it empty in blank build inputs;
- validate category, answer bounds, evidence index and bounds;
- require `evidence_absent` to be a real boolean;
- enforce XOR between non-empty evidence spans and `evidence_absent=True`;
- reject duplicate `(category, answer_start, answer_end)` tuples; and
- require at least one material-error annotation when completed categorical values establish a
  material non-pass.

The material non-pass predicate is:

```python
review.get("grounded") == "no"
or review.get("material_overstatement") == "present"
or review.get("causal_strengthening") == "yes"
or review.get("population_generalization") == "yes"
or any(review.get(field) == "yes" for field in (
    "negation_omission", "qualifier_omission", "population_omission",
    "intervention_omission", "comparison_omission", "outcome_omission",
))
```

- [ ] **Step 5: Verify GREEN, then add refusal tests**

Run the first v2 test. Then add and red-green each of these cases:

- unknown v2 review field;
- incomplete causal or population judgment;
- answer span outside the answer;
- evidence index outside the row evidence;
- evidence span outside the selected evidence text;
- both evidence spans and `evidence_absent=True`;
- neither evidence spans nor evidence absence;
- duplicate category/answer interval;
- material non-pass without annotation;
- clean pass with an annotation;
- unblinding `candidate_id` at row, review, and top level; and
- existing v1 blank, complete, source-projection, and HTML tests remain byte-semantically unchanged.

- [ ] **Step 6: Run targeted checks and commit validator work**

Run:

```bash
uv run ruff format --check tools/generation_review.py tests/test_generation_review.py
uv run ruff check tools/generation_review.py tests/test_generation_review.py
uv run pyright tools/generation_review.py tests/test_generation_review.py
uv run pytest tests/test_generation_review.py -q
```

Record static and targeted evidence for AC2 and AC5. Then:

```bash
git add tools/generation_review.py tests/test_generation_review.py
git commit -m "feat: validate generation review v2"
```

---

### Task 5: Render and export the offline v2 reviewer

**Files:**
- Modify: `tools/generation_review.py`
- Modify: `tests/test_generation_review.py`

**Interfaces:**
- Consumes: validated blank v2 worksheet.
- Produces: network-disabled HTML that collects the two new categorical fields and structured material-error spans, then exports a source-bound v2 worksheet.

- [ ] **Step 1: Write a failing v2 renderer test**

```python
def test_v2_builder_renders_new_blinded_fields_without_arm_identity(tmp_path: Path) -> None:
    module = _tool_module()
    source = tmp_path / "v2.json"
    output = tmp_path / "v2.html"
    digest = _write_json(source, _v2_worksheet())
    result = module.build_reviewer(source, output, expected_sha256=digest, expected_rows=2)
    rendered = output.read_text(encoding="utf-8")
    assert result["schema_version"] == "generation-human-review/v2"
    assert "Causal strengthening" in rendered
    assert "Population generalization" in rendered
    assert "Material error spans" in rendered
    assert "candidate_id" not in rendered
    assert "context_strategy" not in rendered
    assert "connect-src 'none'" in rendered
```

Run and confirm RED because the current fixed template omits the v2 fields.

- [ ] **Step 2: Parameterize reviewer configuration by exact schema**

Build one JSON-safe `review_config` after validation:

```python
review_config = {
    "categorical_fields": list(review_options),
    "rubric": rubric_for_schema(validated["schema_version"]),
    "material_errors": validated["schema_version"] == SCHEMA_VERSION_V2,
    "material_error_categories": sorted(MATERIAL_ERROR_CATEGORIES),
}
```

Embed it through a new `__REVIEW_CONFIG__` placeholder using `json.dumps(...).replace("</", "<\\/")`.
The v1 configuration must reproduce its existing field order and wording.

- [ ] **Step 3: Add bounded span controls and export normalization**

For v2 only, render a `Material error spans` section with:

- category select;
- answer `start` and `end` integer inputs;
- evidence index plus evidence `start` and `end` integer inputs;
- `evidence absent` checkbox;
- add/remove controls; and
- a read-only preview that slices the answer and selected evidence locally.

JavaScript normalization must keep only integer values, allowed categories, and real booleans.
`rowComplete` for v2 must require all categorical fields and defer final semantic consistency to
the Python validator. Export must call the same normalized v2 field names used by Python.

Do not add external assets, fetch, forms, telemetry, or arm metadata.

- [ ] **Step 4: Add renderer/export regression tests**

Assert:

- the v2 fields and allowed categories appear in embedded config;
- unexpected arm/prompt/result fields do not appear;
- CSP still disables all connections;
- v1 output contains none of the v2 controls;
- source worksheet bytes remain unchanged;
- building refuses an existing output path; and
- source projection detects changes to answers, evidence, response IDs, or schema version while
  allowing only review and completion metadata changes.

Run each new test RED before implementation and GREEN after the smallest renderer change.

- [ ] **Step 5: Run targeted checks and commit**

Run the same Ruff, Pyright, and `tests/test_generation_review.py` commands from Task 4. Record the
targeted evidence for AC2 and AC5. Then:

```bash
git add tools/generation_review.py tests/test_generation_review.py
git commit -m "feat: render generation review v2"
```

---

### Task 6: Reconcile contracts, verify the stable candidate, and report

**Files:**
- Modify: `docs/project/handoff.md`
- Create: `docs/reports/issue-26-generation-fidelity-foundation.md`
- Modify only if the repeatable Git sandbox failure is sanitized: `docs/project/correction-log.md`

**Interfaces:**
- Consumes: all Issue #26 implementation and check evidence.
- Produces: a stable review candidate, independent verdict, truthful handoff, and loop report.

- [ ] **Step 1: Run focused combined checks**

Run:

```bash
uv run pytest tests/test_generation_fidelity.py tests/test_generation_review.py -q
uv run ruff format --check \
  src/scifact_rag/generation_fidelity.py tools/generation_review.py \
  tests/test_generation_fidelity.py tests/test_generation_review.py
uv run ruff check \
  src/scifact_rag/generation_fidelity.py tools/generation_review.py \
  tests/test_generation_fidelity.py tests/test_generation_review.py
uv run pyright \
  src/scifact_rag/generation_fidelity.py tools/generation_review.py \
  tests/test_generation_fidelity.py tests/test_generation_review.py
```

Record exact commands, outcomes, criteria, and durations. These are targeted/static, not the full gate.

- [ ] **Step 2: Run one affected-contract batch**

Run:

```bash
uv run pytest \
  tests/test_evaluation.py \
  tests/test_generation_evaluation.py \
  tests/test_generation_review.py \
  tests/test_generation_fidelity.py \
  tests/test_openai_compatible.py \
  tests/test_application.py \
  tests/test_interface_contracts.py -q
```

Expected: all selected tests pass. Record once as `affected` evidence for AC1–AC5.

- [ ] **Step 3: Finalize durable handoff, implementation report, and correction**

In `docs/project/handoff.md`, state:

- Issue #26 adds model-free fidelity measurement contracts only;
- current product prompt and defaults are unchanged;
- no model request or confirmation case was accessed;
- ADR-0036 and protocol v1 govern later candidate work; and
- cohort acquisition, candidate A/B, latency preflight, and confirmation remain separate owner decisions.

Create `docs/reports/issue-26-generation-fidelity-foundation.md` with the current targeted and
affected commands, counts, criteria mapping, limitations, and exact next boundary. It must say
that final full-gate and independent-review status live in engineering-loop run
`20260918T172036Z-0c23bbc2`; do not predict their outcomes in repository prose.

Append this sanitized correction to `docs/project/correction-log.md`:

```markdown
### Protected linked-worktree Git metadata
- Failed approach: ordinary sandboxed `git worktree add` or `git add` for a linked worktree.
- Error signature: `.git/...lock: Read-only file system`.
- Mutation status: no branch/index mutation occurred on the failed command.
- Corrected path: rerun the exact repository-scoped Git operation through the approved host permission path.
- Verification: branch, worktree, staged paths, and commit identity were re-read after success.
- Durable guard: resolve the exact Git dir and use repository-scoped approval for linked-worktree metadata writes.
```

Run `git diff --check` and `python3 tools/harness_check.py`, then commit the complete repository
candidate before release impact, full verification, or independent review:

```bash
git add \
  docs/project/handoff.md \
  docs/reports/issue-26-generation-fidelity-foundation.md \
  docs/project/correction-log.md
git commit -m "docs: report generation fidelity foundation"
```

- [ ] **Step 4: Record product release impact before the full gate**

Run:

```bash
python3 tools/loop.py record-release-impact \
  --run 20260918T172036Z-0c23bbc2 \
  --level none \
  --reason "Issue #26 adds model-free research/evaluation contracts without changing the product public compatibility contract."
```

- [ ] **Step 5: Run exactly one final full gate**

Run once on the final current attempt:

```bash
make smoke
```

If it fails, record the failure, stop the attempt, use `loop.py new-attempt`, repair through TDD,
rerun affected checks, refresh release impact, and run one full gate for the new final attempt.
Do not repeatedly rerun `make smoke` on a moving candidate.

Record the passing current-attempt command as `tier full` for AC1–AC5 with measured duration.

- [ ] **Step 6: Freeze the candidate and obtain independent review**

Run:

```bash
git diff --check
git status --short
python3 tools/product_version.py
```

Start one engineering-loop review with a verifier identity different from
`codex/01a0b539`. The verifier must remain read-only, inspect all criteria and adjacent risks, run
proportionate checks, collect one deduplicated finding batch, close it once, and record a verdict
bound to the exact commit and working-tree digest.

If findings exist, do not mutate until every finding is dispositioned and the proportionality gate
is complete. Follow the loop's new-attempt or revision transition exactly.

- [ ] **Step 7: Finish the engineering loop without further repository mutation**

Use `python3 tools/loop.py finish --run 20260918T172036Z-0c23bbc2`. If the completion gate refuses,
preserve the exact error and correct evidence/state under the loop contract; never fabricate a
reviewer or weaken a criterion.

Do not close Issue #26, add Project membership, push, create a PR, merge, release, or publish
without the corresponding user authorization and finishing-branch choice.
