from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any

_SCHEMA_VERSION = "generation-run-manifest/v1"
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SOURCE_SPLITS = {"train-development", "train-validation", "test"}


class EvaluationPurpose(StrEnum):
    DEVELOPMENT = "development"
    DEFAULT_SELECTION = "default-selection"
    TEST_CONFIRMATION = "test-confirmation"


@dataclass(frozen=True, slots=True)
class ComponentRevision:
    component: str
    identifier: str
    revision: str

    def __post_init__(self) -> None:
        if not _SAFE_NAME.fullmatch(self.component):
            raise ValueError("component must be a safe non-empty name")
        for field_name in ("identifier", "revision"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"component {field_name} must be non-empty")


@dataclass(frozen=True, slots=True)
class GeneratorSettings:
    temperature: float
    maximum_answer_tokens: int
    thinking_enabled: bool

    def __post_init__(self) -> None:
        if isinstance(self.temperature, bool) or not isinstance(self.temperature, (int, float)):
            raise TypeError("generator temperature must be numeric")
        if not 0.0 <= float(self.temperature) <= 2.0:
            raise ValueError("generator temperature must be between 0 and 2")
        if isinstance(self.maximum_answer_tokens, bool) or not isinstance(
            self.maximum_answer_tokens, int
        ):
            raise TypeError("generator maximum_answer_tokens must be an integer")
        if self.maximum_answer_tokens < 1:
            raise ValueError("generator maximum_answer_tokens must be positive")
        if not isinstance(self.thinking_enabled, bool):
            raise TypeError("generator thinking_enabled must be boolean")


@dataclass(frozen=True, slots=True)
class GenerationRunManifest:
    schema_version: str
    run_id: str
    repository_commit: str
    corpus_sha256: str
    evaluation_manifest_sha256: str
    source_split: str
    purpose: EvaluationPurpose
    retrieval_strategy: str
    context_strategy: str
    retrieval_limit: int
    components: tuple[ComponentRevision, ...]
    generator: GeneratorSettings
    started_at: str
    completed_at: str | None
    host: str
    results_path: str
    test_qrels_inspected: bool

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_SCHEMA_VERSION}")
        if not _SAFE_NAME.fullmatch(self.run_id):
            raise ValueError("run_id must be a safe non-empty name")
        if not _HEX_40.fullmatch(self.repository_commit):
            raise ValueError("repository_commit must be a lowercase 40-character Git commit")
        for field_name in ("corpus_sha256", "evaluation_manifest_sha256"):
            if not _SHA256.fullmatch(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
        if self.source_split not in _SOURCE_SPLITS:
            raise ValueError(f"source_split must be one of {sorted(_SOURCE_SPLITS)}")
        if not isinstance(self.purpose, EvaluationPurpose):
            raise TypeError("purpose must be a recognized evaluation purpose")
        if self.purpose is EvaluationPurpose.DEFAULT_SELECTION and self.source_split == "test":
            raise ValueError("default selection cannot use the inspected test qrels")
        for field_name in ("retrieval_strategy", "context_strategy", "host"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be non-empty")
        if (
            isinstance(self.retrieval_limit, bool)
            or not isinstance(self.retrieval_limit, int)
            or not 1 <= self.retrieval_limit <= 100
        ):
            raise ValueError("retrieval_limit must be between 1 and 100")
        if not self.components:
            raise ValueError("components must not be empty")
        component_names = [component.component for component in self.components]
        if len(component_names) != len(set(component_names)):
            raise ValueError("component names must be unique")
        object.__setattr__(
            self,
            "components",
            tuple(sorted(self.components, key=lambda component: component.component)),
        )
        started = _parse_utc("started_at", self.started_at)
        if self.completed_at is not None:
            completed = _parse_utc("completed_at", self.completed_at)
            if completed < started:
                raise ValueError("completed_at must not precede started_at")
        result_path = PurePosixPath(self.results_path)
        if (
            not self.results_path.strip()
            or result_path.is_absolute()
            or ".." in result_path.parts
            or str(result_path) in ("", ".")
        ):
            raise ValueError("results_path must be a safe repository-relative path")
        if self.test_qrels_inspected is not True:
            raise ValueError("test_qrels_inspected must record the existing inspection as true")

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, serialized: str) -> GenerationRunManifest:
        try:
            raw = json.loads(serialized)
        except json.JSONDecodeError as exc:
            raise ValueError("manifest must be valid JSON") from exc
        if not isinstance(raw, dict):
            raise TypeError("manifest must be a JSON object")
        expected_fields = {field.name for field in fields(cls)}
        if set(raw) != expected_fields:
            raise ValueError("manifest fields do not match the generation-run-manifest/v1 schema")
        raw_components = raw["components"]
        if not isinstance(raw_components, list):
            raise TypeError("components must be a JSON array")
        component_fields = {field.name for field in fields(ComponentRevision)}
        components: list[ComponentRevision] = []
        for raw_component in raw_components:
            if not isinstance(raw_component, dict) or set(raw_component) != component_fields:
                raise ValueError("component fields do not match the schema")
            try:
                components.append(ComponentRevision(**raw_component))
            except TypeError as exc:
                raise ValueError("component values do not match the schema") from exc
        raw_generator = raw["generator"]
        generator_fields = {field.name for field in fields(GeneratorSettings)}
        if not isinstance(raw_generator, dict) or set(raw_generator) != generator_fields:
            raise ValueError("generator fields do not match the schema")
        try:
            generator = GeneratorSettings(**raw_generator)
            purpose = EvaluationPurpose(raw["purpose"])
            values: dict[str, Any] = dict(raw)
            values["components"] = tuple(components)
            values["generator"] = generator
            values["purpose"] = purpose
            return cls(**values)
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith(
                ("schema_version", "run_id", "repository_commit", "corpus_sha256")
            ):
                raise
            raise ValueError(f"manifest values do not match the schema: {exc}") from exc


def _parse_utc(field_name: str, value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field_name} must be an ISO-8601 UTC timestamp ending in Z")
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 UTC timestamp ending in Z") from exc
