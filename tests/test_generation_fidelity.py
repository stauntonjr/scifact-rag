from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

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

FIXTURE = Path(__file__).parent / "fixtures" / "generation_fidelity_challenges.json"


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
        "access_declaration",
        "candidates",
        "cohort",
        "manifest_id",
        "phase",
        "schema_version",
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


def test_manifest_rejects_unknown_or_missing_fields() -> None:
    raw = json.loads(_manifest().to_json())
    raw["question"] = "hidden confirmation content"
    with pytest.raises(ValueError, match="fields do not match"):
        GenerationFidelityManifest.from_json(json.dumps(raw))

    del raw["question"]
    del raw["manifest_id"]
    with pytest.raises(ValueError, match="fields do not match"):
        GenerationFidelityManifest.from_json(json.dumps(raw))


def test_manifest_rejects_non_object_json() -> None:
    with pytest.raises(TypeError, match="JSON object"):
        GenerationFidelityManifest.from_json("[]")


@pytest.mark.parametrize("scheduled_cases", [0, -1, True, 1.5])
def test_cohort_requires_a_positive_integer_case_count(scheduled_cases: object) -> None:
    with pytest.raises(ValueError, match="scheduled_cases"):
        FidelityCohort(
            cohort_id="development-v1",
            cohort_sha256="a" * 64,
            scheduled_cases=scheduled_cases,  # type: ignore[arg-type]
            article_family_sha256s=("b" * 64,),
        )


def test_cohort_requires_sorted_unique_nonempty_family_digests() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        FidelityCohort("cohort", "a" * 64, 1, ())
    with pytest.raises(ValueError, match="unique"):
        FidelityCohort("cohort", "a" * 64, 1, ("b" * 64, "b" * 64))
    with pytest.raises(ValueError, match="sorted"):
        FidelityCohort("cohort", "a" * 64, 1, ("c" * 64, "b" * 64))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("candidate_id", "unsafe/name", "candidate_id"),
        ("product_prompt_sha256", "short", "product_prompt_sha256"),
        ("diagnostic_prompt_id", "", "diagnostic_prompt_id"),
        ("diagnostic_prompt_sha256", "G" * 64, "diagnostic_prompt_sha256"),
    ],
)
def test_candidate_rejects_unsafe_identity_values(
    field: str,
    value: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        replace(_candidate(CandidateRole.BASELINE), **{field: value})


def test_manifest_requires_exactly_one_ordered_candidate_per_role() -> None:
    baseline = _candidate(CandidateRole.BASELINE)
    candidate = _candidate(CandidateRole.CANDIDATE)
    with pytest.raises(ValueError, match="baseline then candidate"):
        replace(_manifest(), candidates=(candidate, baseline))
    with pytest.raises(ValueError, match="baseline then candidate"):
        replace(_manifest(), candidates=(baseline, baseline))


def test_manifest_rejects_duplicate_candidate_and_prompt_identities() -> None:
    baseline = _candidate(CandidateRole.BASELINE)
    candidate = _candidate(CandidateRole.CANDIDATE)
    with pytest.raises(ValueError, match="candidate_id"):
        replace(_manifest(), candidates=(baseline, replace(candidate, candidate_id="baseline-v1")))
    with pytest.raises(ValueError, match="product_prompt_id"):
        replace(
            _manifest(),
            candidates=(
                baseline,
                replace(candidate, product_prompt_id=baseline.product_prompt_id),
            ),
        )
    with pytest.raises(ValueError, match="diagnostic_prompt_id"):
        replace(
            _manifest(),
            candidates=(
                baseline,
                replace(candidate, diagnostic_prompt_id=baseline.diagnostic_prompt_id),
            ),
        )


def test_development_and_stress_reject_seals_or_custodian_access() -> None:
    for phase in (FidelityPhase.DEVELOPMENT, FidelityPhase.STRESS):
        with pytest.raises(ValueError, match="unsealed developer access"):
            _manifest(
                phase=phase,
                access=FidelityAccess.CUSTODIAN_ONLY,
                custodian="custodian",
                sealed_at="2026-09-18T17:00:00Z",
            )


def test_confirmation_rejects_missing_custodian_seal_or_developer_open() -> None:
    with pytest.raises(ValueError, match="named custodian"):
        _manifest(
            phase=FidelityPhase.CONFIRMATION,
            access=FidelityAccess.CUSTODIAN_ONLY,
            sealed_at="2026-09-18T17:00:00Z",
        )
    with pytest.raises(ValueError, match="requires sealed_at"):
        _manifest(
            phase=FidelityPhase.CONFIRMATION,
            access=FidelityAccess.CUSTODIAN_ONLY,
            custodian="custodian",
        )
    with pytest.raises(ValueError, match="unopened by developers"):
        replace(
            _manifest(
                phase=FidelityPhase.CONFIRMATION,
                access=FidelityAccess.CUSTODIAN_ONLY,
                custodian="custodian",
                sealed_at="2026-09-18T17:00:00Z",
            ),
            access_declaration=FidelityAccessDeclaration(
                access=FidelityAccess.CUSTODIAN_ONLY,
                custodian="custodian",
                sealed_at="2026-09-18T17:00:00Z",
                developer_opened_at="2026-09-18T18:00:00Z",
            ),
        )


def test_access_timestamps_require_exact_utc_form() -> None:
    with pytest.raises(ValueError, match="ending in Z"):
        FidelityAccessDeclaration(
            access=FidelityAccess.CUSTODIAN_ONLY,
            custodian="custodian",
            sealed_at="2026-09-18T17:00:00-04:00",
            developer_opened_at=None,
        )


def test_manifest_rejects_unknown_enum_values_from_json() -> None:
    raw = json.loads(_manifest().to_json())
    raw["phase"] = "future-phase"
    with pytest.raises(ValueError, match="manifest values do not match"):
        GenerationFidelityManifest.from_json(json.dumps(raw))


def test_manifest_requires_exact_prompt_hash_mapping() -> None:
    manifest = _manifest()
    manifest.require_prompt_hashes(
        {
            "baseline": ("a" * 64, "c" * 64),
            "candidate": ("b" * 64, "d" * 64),
        }
    )
    with pytest.raises(ValueError, match="baseline and candidate exactly"):
        manifest.require_prompt_hashes({"baseline": ("a" * 64, "c" * 64)})
    with pytest.raises(ValueError, match="baseline product"):
        manifest.require_prompt_hashes(
            {
                "baseline": ("f" * 64, "c" * 64),
                "candidate": ("b" * 64, "d" * 64),
            }
        )
    with pytest.raises(ValueError, match="candidate diagnostic"):
        manifest.require_prompt_hashes(
            {
                "baseline": ("a" * 64, "c" * 64),
                "candidate": ("b" * 64, "f" * 64),
            }
        )


def test_generation_fidelity_challenges_are_complete_and_development_only() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert set(payload) == {"cases", "phase", "schema_version", "synthetic"}
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
            "challenge_id",
            "distinction",
            "evidence",
            "expected_disposition",
            "forbidden_behavior",
            "question",
            "required_behavior",
        }
        assert case["expected_disposition"] in {"answer", "insufficient-evidence"}
        assert case["evidence"] and all(item.strip() for item in case["evidence"])
