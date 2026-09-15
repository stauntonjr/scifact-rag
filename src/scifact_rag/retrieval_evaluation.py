from __future__ import annotations

import hashlib
import json
import math
import os
import re
import statistics
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile

from .domain import RetrievalMetrics
from .evaluation import ComponentRevision
from .metrics import evaluate_rankings
from .ports import Retriever
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


@dataclass(frozen=True, slots=True)
class RankedRetrievalHit:
    doc_id: str
    score: float

    def __post_init__(self) -> None:
        if not isinstance(self.doc_id, str) or not self.doc_id.isdigit():
            raise ValueError("ranked hit doc_id must be a numeric string")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise TypeError("ranked hit score must be numeric")
        if not math.isfinite(float(self.score)):
            raise ValueError("ranked hit score must be finite")


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationResult:
    schema_version: str
    query_id: str
    strategy: RetrievalStrategyName
    cutoff: int
    latency_ms: float
    hits: tuple[RankedRetrievalHit, ...]
    error_type: str | None
    error_message: str | None

    def __post_init__(self) -> None:
        if self.schema_version != "retrieval-evaluation-result/v1":
            raise ValueError("schema_version must be retrieval-evaluation-result/v1")
        if not isinstance(self.query_id, str) or not self.query_id.isdigit():
            raise ValueError("query_id must be a numeric string")
        if not isinstance(self.strategy, RetrievalStrategyName):
            raise TypeError("strategy must be a RetrievalStrategyName")
        if isinstance(self.cutoff, bool) or not isinstance(self.cutoff, int) or self.cutoff < 1:
            raise ValueError("cutoff must be a positive integer")
        if isinstance(self.latency_ms, bool) or not isinstance(self.latency_ms, (int, float)):
            raise TypeError("latency_ms must be numeric")
        if not math.isfinite(float(self.latency_ms)) or self.latency_ms < 0:
            raise ValueError("latency_ms must be finite and non-negative")
        if not isinstance(self.hits, tuple) or any(
            not isinstance(hit, RankedRetrievalHit) for hit in self.hits
        ):
            raise TypeError("hits must be a tuple of RankedRetrievalHit values")
        if len(self.hits) > self.cutoff:
            raise ValueError("hits must not exceed cutoff")
        doc_ids = [hit.doc_id for hit in self.hits]
        if len(doc_ids) != len(set(doc_ids)):
            raise ValueError("ranked hit doc_ids must be unique")
        if (self.error_type is None) != (self.error_message is None):
            raise ValueError("error_type and error_message must both be set or both be null")
        if self.error_type is not None:
            if not self.error_type.strip() or not self.error_message or not self.error_message.strip():
                raise ValueError("error fields must be non-empty")
            if self.hits:
                raise ValueError("a failed retrieval result must not contain hits")


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationRecord:
    run_id: str
    result: RetrievalEvaluationResult
    schema_version: str = "retrieval-evaluation-record/v1"

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not _SAFE_NAME.fullmatch(self.run_id):
            raise ValueError("run_id must be a safe non-empty name")
        if not isinstance(self.result, RetrievalEvaluationResult):
            raise TypeError("result must be a RetrievalEvaluationResult")
        if self.schema_version != "retrieval-evaluation-record/v1":
            raise ValueError("schema_version must be retrieval-evaluation-record/v1")

    def to_json(self) -> str:
        values = asdict(self)
        values["result"]["strategy"] = self.result.strategy.value
        return json.dumps(values, sort_keys=True, separators=(",", ":")) + "\n"

    @classmethod
    def from_json(cls, serialized: str) -> RetrievalEvaluationRecord:
        try:
            raw = json.loads(serialized)
        except json.JSONDecodeError as exc:
            raise ValueError("retrieval evaluation record must be valid JSON") from exc
        if not isinstance(raw, dict) or set(raw) != {"schema_version", "run_id", "result"}:
            raise ValueError("retrieval evaluation record fields do not match the schema")
        raw_result = raw["result"]
        expected_result_fields = {field.name for field in fields(RetrievalEvaluationResult)}
        if not isinstance(raw_result, dict) or set(raw_result) != expected_result_fields:
            raise ValueError("retrieval evaluation result fields do not match the schema")
        raw_hits = raw_result["hits"]
        expected_hit_fields = {field.name for field in fields(RankedRetrievalHit)}
        if not isinstance(raw_hits, list) or any(
            not isinstance(hit, dict) or set(hit) != expected_hit_fields for hit in raw_hits
        ):
            raise ValueError("ranked retrieval hit fields do not match the schema")
        result_values = dict(raw_result)
        result_values["strategy"] = RetrievalStrategyName(result_values["strategy"])
        result_values["hits"] = tuple(RankedRetrievalHit(**hit) for hit in raw_hits)
        return cls(
            run_id=raw["run_id"],
            result=RetrievalEvaluationResult(**result_values),
            schema_version=raw["schema_version"],
        )


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationExecutionSummary:
    expected_rows: int
    preexisting_rows: int
    written_rows: int
    failed_rows: int


@dataclass(frozen=True, slots=True)
class RetrievalStrategySummary:
    strategy: RetrievalStrategyName
    planned_rows: int
    completed_rows: int
    successful_rows: int
    failed_rows: int
    empty_result_rows: int
    mean_latency_ms: float | None
    median_latency_ms: float | None
    metrics: RetrievalMetrics


@dataclass(frozen=True, slots=True)
class RetrievalQueryTransition:
    query_id: str
    relevant_document_ids_gained: tuple[str, ...]
    relevant_document_ids_lost: tuple[str, ...]
    top_document_changed: bool
    ndcg_delta: float


@dataclass(frozen=True, slots=True)
class RetrievalStrategyComparison:
    baseline: RetrievalStrategyName
    comparator: RetrievalStrategyName
    improved_queries: int
    regressed_queries: int
    tied_queries: int
    transitions: tuple[RetrievalQueryTransition, ...]


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationReport:
    schema_version: str
    run_id: str
    cutoff: int
    query_count: int
    complete: bool
    strategies: tuple[RetrievalStrategySummary, ...]
    comparisons: tuple[RetrievalStrategyComparison, ...]


def read_retrieval_evaluation_records(path: Path) -> tuple[RetrievalEvaluationRecord, ...]:
    if not path.exists():
        return ()
    lines = path.read_text(encoding="utf-8").splitlines()
    if any(not line.strip() for line in lines):
        raise ValueError("retrieval evaluation JSONL must not contain blank rows")
    records: list[RetrievalEvaluationRecord] = []
    for line_number, line in enumerate(lines, start=1):
        try:
            records.append(RetrievalEvaluationRecord.from_json(line))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"retrieval evaluation row {line_number} is invalid: {exc}"
            ) from exc
    return tuple(records)


def _append_retrieval_record(path: Path, record: RetrievalEvaluationRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        output.write(record.to_json())
        output.flush()
        os.fsync(output.fileno())


class RetrievalEvaluationExecutor:
    def __init__(
        self,
        retrievers: Mapping[RetrievalStrategyName, Retriever],
        *,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._retrievers = dict(retrievers)
        self._clock = clock

    def run(
        self,
        *,
        run_id: str,
        queries: Mapping[str, str],
        strategies: Sequence[RetrievalStrategyName],
        cutoff: int,
        output: Path,
    ) -> RetrievalEvaluationExecutionSummary:
        if not isinstance(run_id, str) or not _SAFE_NAME.fullmatch(run_id):
            raise ValueError("run_id must be a safe non-empty name")
        if not isinstance(queries, Mapping) or not queries:
            raise ValueError("queries must be a non-empty mapping")
        if any(
            not isinstance(query_id, str)
            or not query_id.isdigit()
            or not isinstance(query, str)
            or not query.strip()
            for query_id, query in queries.items()
        ):
            raise ValueError("queries require numeric string IDs and non-empty text")
        selected = tuple(strategies)
        if selected != RETRIEVAL_DEFAULT_STRATEGIES:
            raise ValueError("strategies must match the frozen retrieval-default candidates")
        if isinstance(cutoff, bool) or cutoff != 10:
            raise ValueError("cutoff must be 10")
        missing_retrievers = set(selected) - self._retrievers.keys()
        if missing_retrievers:
            raise ValueError(f"retrievers are missing strategies: {sorted(missing_retrievers)}")

        existing_records = read_retrieval_evaluation_records(output)
        existing: dict[tuple[str, RetrievalStrategyName], RetrievalEvaluationRecord] = {}
        for record in existing_records:
            result = record.result
            if record.run_id != run_id:
                raise ValueError("existing retrieval row belongs to another run")
            if result.query_id not in queries:
                raise ValueError("existing retrieval row has an unknown query")
            if result.strategy not in selected:
                raise ValueError("existing retrieval row has an unplanned strategy")
            if result.cutoff != cutoff:
                raise ValueError("existing retrieval row has a mismatched cutoff")
            key = (result.query_id, result.strategy)
            if key in existing:
                raise ValueError("existing retrieval rows contain a duplicate pair")
            existing[key] = record

        written = 0
        for strategy in selected:
            for query_id in sorted(queries, key=int):
                if (query_id, strategy) in existing:
                    continue
                result = self._evaluate(
                    query_id=query_id,
                    query=queries[query_id],
                    strategy=strategy,
                    cutoff=cutoff,
                )
                _append_retrieval_record(output, RetrievalEvaluationRecord(run_id, result))
                written += 1

        all_records = read_retrieval_evaluation_records(output)
        return RetrievalEvaluationExecutionSummary(
            expected_rows=len(queries) * len(selected),
            preexisting_rows=len(existing_records),
            written_rows=written,
            failed_rows=sum(record.result.error_type is not None for record in all_records),
        )

    def _evaluate(
        self,
        *,
        query_id: str,
        query: str,
        strategy: RetrievalStrategyName,
        cutoff: int,
    ) -> RetrievalEvaluationResult:
        started = self._clock()
        retrieved = None
        error: Exception | None = None
        try:
            retrieved = self._retrievers[strategy].search(query, cutoff)
        except Exception as exc:  # noqa: BLE001 - one failure must not suppress other rows
            error = exc
        finally:
            latency_ms = (self._clock() - started) * 1000.0
        if error is not None:
            return RetrievalEvaluationResult(
                schema_version="retrieval-evaluation-result/v1",
                query_id=query_id,
                strategy=strategy,
                cutoff=cutoff,
                latency_ms=latency_ms,
                hits=(),
                error_type=type(error).__name__,
                error_message=str(error) or type(error).__name__,
            )
        if not isinstance(retrieved, list):
            raise TypeError("retriever.search must return a list of SearchHit values")
        return RetrievalEvaluationResult(
            schema_version="retrieval-evaluation-result/v1",
            query_id=query_id,
            strategy=strategy,
            cutoff=cutoff,
            latency_ms=latency_ms,
            hits=tuple(RankedRetrievalHit(hit.doc_id, hit.score) for hit in retrieved),
            error_type=None,
            error_message=None,
        )


def build_retrieval_evaluation_report(
    records: Sequence[RetrievalEvaluationRecord],
    *,
    run_id: str,
    queries: Mapping[str, str],
    qrels: Mapping[str, Mapping[str, int]],
    strategies: Sequence[RetrievalStrategyName],
    cutoff: int,
) -> RetrievalEvaluationReport:
    if not isinstance(run_id, str) or not _SAFE_NAME.fullmatch(run_id):
        raise ValueError("run_id must be a safe non-empty name")
    if not isinstance(queries, Mapping) or not queries:
        raise ValueError("queries must be a non-empty mapping")
    if any(
        not isinstance(query_id, str)
        or not query_id.isdigit()
        or not isinstance(query, str)
        or not query.strip()
        for query_id, query in queries.items()
    ):
        raise ValueError("queries require numeric string IDs and non-empty text")
    canonical_qrels_sha256(qrels)
    if set(queries) != set(qrels):
        raise ValueError("queries and qrels must contain exactly the same query IDs")
    selected = tuple(strategies)
    if selected != RETRIEVAL_DEFAULT_STRATEGIES:
        raise ValueError("strategies must match the frozen retrieval-default candidates")
    if isinstance(cutoff, bool) or not isinstance(cutoff, int) or cutoff < 1:
        raise ValueError("cutoff must be a positive integer")

    by_key: dict[tuple[str, RetrievalStrategyName], RetrievalEvaluationRecord] = {}
    for record in records:
        result = record.result
        if record.run_id != run_id:
            raise ValueError("retrieval report contains a row from another run")
        if result.query_id not in queries:
            raise ValueError("retrieval report contains an unknown query")
        if result.strategy not in selected:
            raise ValueError("retrieval report contains an unplanned strategy")
        if result.cutoff != cutoff:
            raise ValueError("retrieval report contains a mismatched cutoff")
        key = (result.query_id, result.strategy)
        if key in by_key:
            raise ValueError("retrieval report contains a duplicate query-strategy pair")
        by_key[key] = record

    query_ids = tuple(sorted(queries, key=int))
    summaries: list[RetrievalStrategySummary] = []
    rankings_by_strategy: dict[RetrievalStrategyName, dict[str, list[str]]] = {}
    for strategy in selected:
        strategy_records = tuple(
            by_key[(query_id, strategy)]
            for query_id in query_ids
            if (query_id, strategy) in by_key
        )
        successful = tuple(
            record for record in strategy_records if record.result.error_type is None
        )
        rankings = {
            query_id: [
                hit.doc_id
                for hit in by_key[(query_id, strategy)].result.hits
            ]
            if (query_id, strategy) in by_key
            and by_key[(query_id, strategy)].result.error_type is None
            else []
            for query_id in query_ids
        }
        rankings_by_strategy[strategy] = rankings
        latencies = [record.result.latency_ms for record in strategy_records]
        summaries.append(
            RetrievalStrategySummary(
                strategy=strategy,
                planned_rows=len(query_ids),
                completed_rows=len(strategy_records),
                successful_rows=len(successful),
                failed_rows=len(strategy_records) - len(successful),
                empty_result_rows=sum(not record.result.hits for record in successful),
                mean_latency_ms=statistics.fmean(latencies) if latencies else None,
                median_latency_ms=statistics.median(latencies) if latencies else None,
                metrics=evaluate_rankings(qrels, rankings, cutoff),
            )
        )

    baseline = selected[0]
    comparisons: list[RetrievalStrategyComparison] = []
    for comparator in selected[1:]:
        transitions: list[RetrievalQueryTransition] = []
        improved = 0
        regressed = 0
        tied = 0
        for query_id in query_ids:
            baseline_ranking = rankings_by_strategy[baseline][query_id]
            comparator_ranking = rankings_by_strategy[comparator][query_id]
            relevant = {doc_id for doc_id, grade in qrels[query_id].items() if grade > 0}
            baseline_relevant = relevant.intersection(baseline_ranking[:cutoff])
            comparator_relevant = relevant.intersection(comparator_ranking[:cutoff])
            baseline_ndcg = evaluate_rankings(
                {query_id: qrels[query_id]},
                {query_id: baseline_ranking},
                cutoff,
            ).ndcg
            comparator_ndcg = evaluate_rankings(
                {query_id: qrels[query_id]},
                {query_id: comparator_ranking},
                cutoff,
            ).ndcg
            delta = comparator_ndcg - baseline_ndcg
            if math.isclose(delta, 0.0, rel_tol=0.0, abs_tol=1e-12):
                tied += 1
            elif delta > 0:
                improved += 1
            else:
                regressed += 1
            transitions.append(
                RetrievalQueryTransition(
                    query_id=query_id,
                    relevant_document_ids_gained=tuple(
                        sorted(comparator_relevant - baseline_relevant, key=int)
                    ),
                    relevant_document_ids_lost=tuple(
                        sorted(baseline_relevant - comparator_relevant, key=int)
                    ),
                    top_document_changed=(
                        (baseline_ranking[0] if baseline_ranking else None)
                        != (comparator_ranking[0] if comparator_ranking else None)
                    ),
                    ndcg_delta=delta,
                )
            )
        comparisons.append(
            RetrievalStrategyComparison(
                baseline=baseline,
                comparator=comparator,
                improved_queries=improved,
                regressed_queries=regressed,
                tied_queries=tied,
                transitions=tuple(transitions),
            )
        )

    return RetrievalEvaluationReport(
        schema_version="retrieval-evaluation-report/v1",
        run_id=run_id,
        cutoff=cutoff,
        query_count=len(query_ids),
        complete=len(by_key) == len(query_ids) * len(selected),
        strategies=tuple(summaries),
        comparisons=tuple(comparisons),
    )


def write_retrieval_evaluation_report(
    report: RetrievalEvaluationReport,
    destination: Path,
) -> None:
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
            json.dump(asdict(report), staged, indent=2, sort_keys=True)
            staged.write("\n")
            staged.flush()
            os.fsync(staged.fileno())
            staged_path = Path(staged.name)
        os.chmod(staged_path, 0o644)
        staged_path.replace(destination)
    finally:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)


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
