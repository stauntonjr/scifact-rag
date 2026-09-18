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
        raise ValueError(f"{field_name} must be an ISO-8601 UTC timestamp ending in Z") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include timezone information")


def _exact_object(value: object, cls: type[Any], location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{location} must be a JSON object")
    expected = {field.name for field in fields(cls)}
    if set(value) != expected:
        raise ValueError(f"{location} fields do not match the schema")
    return value


@dataclass(frozen=True, slots=True)
class FidelityCandidate:
    role: CandidateRole
    candidate_id: str
    product_prompt_id: str
    product_prompt_sha256: str
    diagnostic_prompt_id: str
    diagnostic_prompt_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, CandidateRole):
            raise TypeError("role must be a CandidateRole")
        _safe_name("candidate_id", self.candidate_id)
        _safe_name("product_prompt_id", self.product_prompt_id)
        _sha256("product_prompt_sha256", self.product_prompt_sha256)
        _safe_name("diagnostic_prompt_id", self.diagnostic_prompt_id)
        _sha256("diagnostic_prompt_sha256", self.diagnostic_prompt_sha256)


@dataclass(frozen=True, slots=True)
class FidelityCohort:
    cohort_id: str
    cohort_sha256: str
    scheduled_cases: int
    article_family_sha256s: tuple[str, ...]

    def __post_init__(self) -> None:
        _safe_name("cohort_id", self.cohort_id)
        _sha256("cohort_sha256", self.cohort_sha256)
        if (
            isinstance(self.scheduled_cases, bool)
            or not isinstance(self.scheduled_cases, int)
            or self.scheduled_cases < 1
        ):
            raise ValueError("scheduled_cases must be a positive integer")
        if not isinstance(self.article_family_sha256s, tuple):
            raise TypeError("article_family_sha256s must be a tuple")
        if not self.article_family_sha256s:
            raise ValueError("article_family_sha256s must not be empty")
        for digest in self.article_family_sha256s:
            _sha256("article_family_sha256", digest)
        if len(self.article_family_sha256s) != len(set(self.article_family_sha256s)):
            raise ValueError("article_family_sha256s must be unique")
        if self.article_family_sha256s != tuple(sorted(self.article_family_sha256s)):
            raise ValueError("article_family_sha256s must be sorted")


@dataclass(frozen=True, slots=True)
class FidelityAccessDeclaration:
    access: FidelityAccess
    custodian: str | None
    sealed_at: str | None
    developer_opened_at: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.access, FidelityAccess):
            raise TypeError("access must be a FidelityAccess")
        if self.custodian is not None and (
            not isinstance(self.custodian, str) or not self.custodian.strip()
        ):
            raise ValueError("custodian must be non-empty text or null")
        if self.sealed_at is not None:
            _utc("sealed_at", self.sealed_at)
        if self.developer_opened_at is not None:
            _utc("developer_opened_at", self.developer_opened_at)


@dataclass(frozen=True, slots=True)
class GenerationFidelityManifest:
    schema_version: str
    manifest_id: str
    phase: FidelityPhase
    cohort: FidelityCohort
    candidates: tuple[FidelityCandidate, FidelityCandidate]
    access_declaration: FidelityAccessDeclaration

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        _safe_name("manifest_id", self.manifest_id)
        if not isinstance(self.phase, FidelityPhase):
            raise TypeError("phase must be a FidelityPhase")
        if not isinstance(self.cohort, FidelityCohort):
            raise TypeError("cohort must be a FidelityCohort")
        if not isinstance(self.candidates, tuple):
            raise TypeError("candidates must be a tuple")
        if not all(isinstance(candidate, FidelityCandidate) for candidate in self.candidates):
            raise TypeError("candidates must contain FidelityCandidate values")
        if tuple(candidate.role for candidate in self.candidates) != (
            CandidateRole.BASELINE,
            CandidateRole.CANDIDATE,
        ):
            raise ValueError("candidates must contain baseline then candidate exactly once")
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_id values must be unique")
        product_prompt_ids = [candidate.product_prompt_id for candidate in self.candidates]
        if len(product_prompt_ids) != len(set(product_prompt_ids)):
            raise ValueError("product_prompt_id values must be unique")
        diagnostic_prompt_ids = [candidate.diagnostic_prompt_id for candidate in self.candidates]
        if len(diagnostic_prompt_ids) != len(set(diagnostic_prompt_ids)):
            raise ValueError("diagnostic_prompt_id values must be unique")
        if not isinstance(self.access_declaration, FidelityAccessDeclaration):
            raise TypeError("access_declaration must be a FidelityAccessDeclaration")
        if self.phase is FidelityPhase.CONFIRMATION:
            if self.access_declaration.access is not FidelityAccess.CUSTODIAN_ONLY:
                raise ValueError("confirmation phase requires custodian-only access")
            if not self.access_declaration.custodian:
                raise ValueError("confirmation phase requires a named custodian")
            if self.access_declaration.sealed_at is None:
                raise ValueError("confirmation phase requires sealed_at")
            if self.access_declaration.developer_opened_at is not None:
                raise ValueError("confirmation phase must remain unopened by developers")
        elif self.access_declaration != FidelityAccessDeclaration(
            access=FidelityAccess.DEVELOPER,
            custodian=None,
            sealed_at=None,
            developer_opened_at=None,
        ):
            raise ValueError("development and stress phases require unsealed developer access")

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, serialized: str) -> GenerationFidelityManifest:
        try:
            raw = json.loads(serialized)
        except json.JSONDecodeError as exc:
            raise ValueError("manifest must be valid JSON") from exc
        values = _exact_object(raw, cls, "manifest")
        cohort_raw = _exact_object(values["cohort"], FidelityCohort, "cohort")
        family_digests = cohort_raw["article_family_sha256s"]
        if not isinstance(family_digests, list):
            raise TypeError("article_family_sha256s must be a JSON array")
        candidates_raw = values["candidates"]
        if not isinstance(candidates_raw, list):
            raise TypeError("candidates must be a JSON array")
        access_raw = _exact_object(
            values["access_declaration"],
            FidelityAccessDeclaration,
            "access_declaration",
        )
        try:
            cohort = FidelityCohort(
                cohort_id=cohort_raw["cohort_id"],
                cohort_sha256=cohort_raw["cohort_sha256"],
                scheduled_cases=cohort_raw["scheduled_cases"],
                article_family_sha256s=tuple(family_digests),
            )
            parsed_candidates = tuple(
                FidelityCandidate(
                    **{
                        **_exact_object(item, FidelityCandidate, f"candidates[{index}]"),
                        "role": CandidateRole(item["role"]),
                    }
                )
                for index, item in enumerate(candidates_raw)
            )
            access = FidelityAccessDeclaration(
                **{
                    **access_raw,
                    "access": FidelityAccess(access_raw["access"]),
                }
            )
            if len(parsed_candidates) != 2:
                raise ValueError("candidates must contain baseline then candidate exactly once")
            candidates = (parsed_candidates[0], parsed_candidates[1])
            return cls(
                schema_version=values["schema_version"],
                manifest_id=values["manifest_id"],
                phase=FidelityPhase(values["phase"]),
                cohort=cohort,
                candidates=candidates,
                access_declaration=access,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"manifest values do not match the schema: {exc}") from exc

    def require_prompt_hashes(
        self,
        expected: Mapping[str, tuple[str, str]],
    ) -> None:
        required = {candidate.role.value for candidate in self.candidates}
        if set(expected) != required:
            raise ValueError("expected prompt identities must name baseline and candidate exactly")
        for candidate in self.candidates:
            prompt_hashes = expected[candidate.role.value]
            if not isinstance(prompt_hashes, tuple) or len(prompt_hashes) != 2:
                raise ValueError("expected prompt identities must contain product and diagnostic")
            product, diagnostic = prompt_hashes
            if product != candidate.product_prompt_sha256:
                raise ValueError(f"{candidate.role.value} product prompt SHA-256 mismatch")
            if diagnostic != candidate.diagnostic_prompt_sha256:
                raise ValueError(f"{candidate.role.value} diagnostic prompt SHA-256 mismatch")
