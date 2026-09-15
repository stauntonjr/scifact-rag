from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path, PurePosixPath

from .evaluation import ComponentRevision
from .strategies import RetrievalStrategyName

_SCHEMA_VERSION = "retrieval-run-manifest/v1"
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

RETRIEVAL_DEFAULT_STRATEGIES = (
    RetrievalStrategyName.BM25_TOKEN_WINDOW_RRF,
    RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT,
    RetrievalStrategyName.POOLED_COREF_INTERVAL_CONTENT_MAX_COLBERT,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_qrels_sha256(qrels: Mapping[str, Mapping[str, int]]) -> str:
    if not isinstance(qrels, Mapping) or not qrels:
        raise ValueError("qrels must be a non-empty mapping")
    rows: list[dict[str, object]] = []
    for query_id, relevance in qrels.items():
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError("qrels query IDs must be non-empty strings")
        if not isinstance(relevance, Mapping):
            raise TypeError("qrels relevance values must be mappings")
        canonical_relevance: list[tuple[str, int]] = []
        for doc_id, grade in relevance.items():
            if not isinstance(doc_id, str) or not doc_id.strip():
                raise ValueError("qrels document IDs must be non-empty strings")
            if isinstance(grade, bool) or not isinstance(grade, int):
                raise TypeError("qrels relevance grades must be integers")
            if grade < 0:
                raise ValueError("qrels relevance grades must be non-negative")
            canonical_relevance.append((doc_id, grade))
        rows.append(
            {
                "query_id": query_id,
                "relevance": sorted(canonical_relevance),
            }
        )
    rows.sort(key=lambda row: str(row["query_id"]))
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _parse_utc_timestamp(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field_name} must be an ISO 8601 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO 8601 UTC timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return parsed


@dataclass(frozen=True, slots=True)
class RetrievalRunManifest:
    schema_version: str
    run_id: str
    repository_commit: str
    corpus_sha256: str
    queries_sha256: str
    qrels_sha256: str
    source_split: str
    evidence_class: str
    strategies: tuple[RetrievalStrategyName, ...]
    cutoff: int
    components: tuple[ComponentRevision, ...]
    started_at: str
    completed_at: str | None
    host: str
    results_path: str
    test_qrels_inspected: bool

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_SCHEMA_VERSION}")
        if not isinstance(self.run_id, str) or not _SAFE_NAME.fullmatch(self.run_id):
            raise ValueError("run_id must be a safe non-empty name")
        if not isinstance(self.repository_commit, str) or not _HEX_40.fullmatch(
            self.repository_commit
        ):
            raise ValueError("repository_commit must be a lowercase 40-character Git commit")
        for field_name in ("corpus_sha256", "queries_sha256", "qrels_sha256"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not _SHA256.fullmatch(value):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
        if self.source_split != "train-validation":
            raise ValueError("source_split must be train-validation")
        if self.evidence_class != "internal-comparative":
            raise ValueError("evidence_class must be internal-comparative")
        if not isinstance(self.strategies, tuple) or self.strategies != RETRIEVAL_DEFAULT_STRATEGIES:
            raise ValueError("strategies must match the frozen retrieval-default candidates")
        if isinstance(self.cutoff, bool) or self.cutoff != 10:
            raise ValueError("cutoff must be 10")
        if not isinstance(self.components, tuple) or not self.components:
            raise ValueError("components must be a non-empty tuple")
        if any(not isinstance(component, ComponentRevision) for component in self.components):
            raise TypeError("components must contain ComponentRevision values")
        component_names = [component.component for component in self.components]
        if len(component_names) != len(set(component_names)):
            raise ValueError("component names must be unique")
        object.__setattr__(
            self,
            "components",
            tuple(sorted(self.components, key=lambda component: component.component)),
        )
        started_at = _parse_utc_timestamp(self.started_at, "started_at")
        if self.completed_at is not None:
            completed_at = _parse_utc_timestamp(self.completed_at, "completed_at")
            if completed_at < started_at:
                raise ValueError("completed_at must not precede started_at")
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("host must be non-empty")
        if not isinstance(self.results_path, str) or not self.results_path:
            raise ValueError("results_path must be a safe repository-relative JSONL path")
        path = PurePosixPath(self.results_path)
        if (
            path.is_absolute()
            or path.suffix != ".jsonl"
            or any(part in {"", ".", ".."} for part in self.results_path.split("/"))
            or "\\" in self.results_path
        ):
            raise ValueError("results_path must be a safe repository-relative JSONL path")
        if self.test_qrels_inspected is not True:
            raise ValueError("test_qrels_inspected must be true")

    def to_json(self) -> str:
        values = asdict(self)
        values["strategies"] = [strategy.value for strategy in self.strategies]
        return json.dumps(values, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, serialized: str) -> RetrievalRunManifest:
        raw = json.loads(serialized)
        if not isinstance(raw, dict):
            raise TypeError("manifest must be a JSON object")
        if set(raw) != {field.name for field in fields(cls)}:
            raise ValueError("manifest fields do not match retrieval-run-manifest/v1")
        if not isinstance(raw["strategies"], list):
            raise TypeError("manifest strategies must be a JSON array")
        if not isinstance(raw["components"], list):
            raise TypeError("manifest components must be a JSON array")
        component_fields = {field.name for field in fields(ComponentRevision)}
        components: list[ComponentRevision] = []
        for value in raw["components"]:
            if not isinstance(value, dict) or set(value) != component_fields:
                raise ValueError("manifest component fields do not match ComponentRevision")
            components.append(ComponentRevision(**value))
        raw["strategies"] = tuple(
            RetrievalStrategyName(value) for value in raw["strategies"]
        )
        raw["components"] = tuple(components)
        return cls(**raw)
