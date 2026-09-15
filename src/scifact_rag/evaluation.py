from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import Any

_SCHEMA_VERSION = "generation-run-manifest/v1"
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SOURCE_SPLITS = {"train-development", "train-validation", "test"}
_GENERATION_EVALUATION_SPLITS = {"train-development", "train-validation"}


class EvaluationPurpose(StrEnum):
    DEVELOPMENT = "development"
    DEFAULT_SELECTION = "default-selection"
    TEST_CONFIRMATION = "test-confirmation"


class ScientificStance(StrEnum):
    SUPPORT = "SUPPORT"
    CONTRADICT = "CONTRADICT"
    NOT_ENOUGH_INFO = "NOT_ENOUGH_INFO"


@dataclass(frozen=True, slots=True)
class GoldRationale:
    doc_id: str
    label: ScientificStance
    sentence_indices: tuple[int, ...]
    sentences: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.doc_id, str) or not self.doc_id.isdigit():
            raise ValueError("rationale doc_id must be a numeric string")
        if not isinstance(self.label, ScientificStance):
            raise TypeError("rationale label must be a ScientificStance")
        if self.label is ScientificStance.NOT_ENOUGH_INFO:
            raise ValueError("a gold rationale cannot have a NOT_ENOUGH_INFO label")
        if not self.sentence_indices or len(self.sentence_indices) != len(self.sentences):
            raise ValueError("sentence indices and texts must have the same non-zero length")
        if any(
            isinstance(index, bool) or not isinstance(index, int) or index < 0
            for index in self.sentence_indices
        ):
            raise ValueError("sentence indices must be non-negative integers")
        if tuple(sorted(set(self.sentence_indices))) != self.sentence_indices:
            raise ValueError("sentence indices must be unique and strictly increasing")
        if any(
            not isinstance(sentence, str) or not sentence.strip() for sentence in self.sentences
        ):
            raise ValueError("rationale sentences must be non-empty")


@dataclass(frozen=True, slots=True)
class GenerationEvaluationCase:
    schema_version: str
    query_id: str
    claim: str
    source_split: str
    expected_stance: ScientificStance
    cited_document_ids: tuple[str, ...]
    rationales: tuple[GoldRationale, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "generation-evaluation-case/v1":
            raise ValueError("schema_version must be generation-evaluation-case/v1")
        if not isinstance(self.query_id, str) or not self.query_id.isdigit():
            raise ValueError("query_id must be a numeric string")
        if not isinstance(self.claim, str) or not self.claim.strip():
            raise ValueError("claim must be non-empty")
        if self.source_split not in _GENERATION_EVALUATION_SPLITS:
            raise ValueError(f"source_split must be one of {sorted(_GENERATION_EVALUATION_SPLITS)}")
        if not isinstance(self.expected_stance, ScientificStance):
            raise TypeError("expected_stance must be a ScientificStance")
        if not self.cited_document_ids:
            raise ValueError("cited_document_ids must not be empty")
        if any(
            not isinstance(doc_id, str) or not doc_id.isdigit()
            for doc_id in self.cited_document_ids
        ):
            raise ValueError("cited document IDs must be numeric strings")
        if len(self.cited_document_ids) != len(set(self.cited_document_ids)):
            raise ValueError("cited document IDs must be unique")
        object.__setattr__(self, "cited_document_ids", tuple(sorted(self.cited_document_ids)))
        if self.expected_stance is ScientificStance.NOT_ENOUGH_INFO:
            if self.rationales:
                raise ValueError("NOT_ENOUGH_INFO cases must not have rationales")
        elif not self.rationales:
            raise ValueError("a SUPPORT or CONTRADICT case requires at least one rationale")
        cited = set(self.cited_document_ids)
        for rationale in self.rationales:
            if rationale.label is not self.expected_stance:
                raise ValueError("rationale label must match the case expected stance")
            if rationale.doc_id not in cited:
                raise ValueError("rationale document must be present in cited_document_ids")
        if len(self.rationales) != len(set(self.rationales)):
            raise ValueError("rationales must be unique")
        object.__setattr__(
            self,
            "rationales",
            tuple(
                sorted(
                    self.rationales,
                    key=lambda rationale: (rationale.doc_id, rationale.sentence_indices),
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class GenerationEvaluationSummary:
    cases: int
    support: int
    contradict: int
    not_enough_info: int
    annotated_cases: int
    rationale_sets: int
    evidence_sentences: int
    sha256: str


@dataclass(frozen=True, slots=True)
class GenerationEvaluationSet:
    cases: tuple[GenerationEvaluationCase, ...]

    def __post_init__(self) -> None:
        if not self.cases:
            raise ValueError("generation evaluation set must not be empty")
        query_ids = [case.query_id for case in self.cases]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("generation evaluation query IDs must be unique")
        splits = {case.source_split for case in self.cases}
        if len(splits) != 1:
            raise ValueError("generation evaluation cases must use one source split")
        object.__setattr__(
            self,
            "cases",
            tuple(sorted(self.cases, key=lambda case: int(case.query_id))),
        )

    def to_jsonl(self) -> str:
        return "".join(
            json.dumps(asdict(case), sort_keys=True, separators=(",", ":")) + "\n"
            for case in self.cases
        )

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.to_jsonl().encode()).hexdigest()

    def summary(self) -> GenerationEvaluationSummary:
        counts = {
            stance: sum(case.expected_stance is stance for case in self.cases)
            for stance in ScientificStance
        }
        rationales = tuple(rationale for case in self.cases for rationale in case.rationales)
        return GenerationEvaluationSummary(
            cases=len(self.cases),
            support=counts[ScientificStance.SUPPORT],
            contradict=counts[ScientificStance.CONTRADICT],
            not_enough_info=counts[ScientificStance.NOT_ENOUGH_INFO],
            annotated_cases=sum(bool(case.rationales) for case in self.cases),
            rationale_sets=len(rationales),
            evidence_sentences=sum(len(rationale.sentences) for rationale in rationales),
            sha256=self.sha256,
        )


def write_generation_evaluation_set(
    evaluation_set: GenerationEvaluationSet,
    destination: Path,
) -> GenerationEvaluationSummary:
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            delete=False,
        ) as staged:
            staged.write(evaluation_set.to_jsonl())
            staged.flush()
            staged_path = Path(staged.name)
        staged_path.replace(destination)
    finally:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)
    return evaluation_set.summary()


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
