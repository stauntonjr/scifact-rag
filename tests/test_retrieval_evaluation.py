from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from scifact_rag.domain import SearchHit
from scifact_rag.evaluation import ComponentRevision
from scifact_rag.metrics import evaluate_rankings
from scifact_rag.retrieval_evaluation import (
    RETRIEVAL_DEFAULT_STRATEGIES,
    RankedRetrievalHit,
    RetrievalEvaluationExecutor,
    RetrievalEvaluationRecord,
    RetrievalEvaluationResult,
    RetrievalRunManifest,
    build_retrieval_evaluation_report,
    canonical_qrels_sha256,
    read_retrieval_evaluation_records,
    sha256_file,
    write_retrieval_evaluation_report,
)
from scifact_rag.strategies import RetrievalStrategyName


def _manifest(**overrides: object) -> RetrievalRunManifest:
    values: dict[str, object] = {
        "schema_version": "retrieval-run-manifest/v1",
        "run_id": "retrieval-validation-1",
        "repository_commit": "a" * 40,
        "corpus_sha256": "b" * 64,
        "queries_sha256": "c" * 64,
        "qrels_sha256": "d" * 64,
        "source_split": "train-validation",
        "evidence_class": "internal-comparative",
        "strategies": RETRIEVAL_DEFAULT_STRATEGIES,
        "cutoff": 10,
        "components": (
            ComponentRevision("vector-model", "minilm", "1"),
            ComponentRevision("application-image", "scifact-rag", "sha256:123"),
        ),
        "started_at": "2026-09-15T12:00:00Z",
        "completed_at": None,
        "host": "spark-3a8f",
        "results_path": "artifacts/retrieval-validation-1/results.jsonl",
        "test_qrels_inspected": True,
    }
    values.update(overrides)
    return RetrievalRunManifest(**values)  # type: ignore[arg-type]


def test_retrieval_run_manifest_emits_canonical_frozen_boundary() -> None:
    payload = json.loads(_manifest().to_json())

    assert set(payload) == {
        "schema_version",
        "run_id",
        "repository_commit",
        "corpus_sha256",
        "queries_sha256",
        "qrels_sha256",
        "source_split",
        "evidence_class",
        "strategies",
        "cutoff",
        "components",
        "started_at",
        "completed_at",
        "host",
        "results_path",
        "test_qrels_inspected",
    }
    assert payload["schema_version"] == "retrieval-run-manifest/v1"
    assert payload["source_split"] == "train-validation"
    assert payload["evidence_class"] == "internal-comparative"
    assert payload["strategies"] == [strategy.value for strategy in RETRIEVAL_DEFAULT_STRATEGIES]
    assert payload["cutoff"] == 10
    assert [item["component"] for item in payload["components"]] == [
        "application-image",
        "vector-model",
    ]
    assert _manifest().to_json().endswith("\n")


def test_retrieval_run_manifest_round_trips_canonical_json() -> None:
    manifest = _manifest(completed_at="2026-09-15T12:30:00Z")

    assert RetrievalRunManifest.from_json(manifest.to_json()) == manifest


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "retrieval-run-manifest/v2"),
        ("run_id", "../escape"),
        ("repository_commit", "A" * 40),
        ("corpus_sha256", "b" * 63),
        ("queries_sha256", "C" * 64),
        ("qrels_sha256", "not-a-digest"),
        ("source_split", "test"),
        ("evidence_class", "confirmation"),
        ("strategies", tuple(reversed(RETRIEVAL_DEFAULT_STRATEGIES))),
        ("cutoff", 20),
        ("components", ()),
        ("started_at", "2026-09-15 12:00:00"),
        ("completed_at", "2026-09-15T11:59:59Z"),
        ("host", "  "),
        ("results_path", "/tmp/results.jsonl"),
        ("results_path", "artifacts/../results.jsonl"),
        ("results_path", "artifacts/results.json"),
        ("test_qrels_inspected", False),
    ],
)
def test_retrieval_run_manifest_rejects_boundary_drift(field: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _manifest(**{field: value})


def test_retrieval_run_manifest_rejects_duplicate_components() -> None:
    component = ComponentRevision("application-image", "scifact-rag", "sha256:123")

    with pytest.raises(ValueError, match="unique"):
        _manifest(components=(component, replace(component, revision="sha256:456")))


@pytest.mark.parametrize("serialized", ["[]", "{}", '{"schema_version":"unknown"}'])
def test_retrieval_run_manifest_rejects_invalid_json_shape(serialized: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        RetrievalRunManifest.from_json(serialized)


def test_retrieval_run_manifest_rejects_unknown_strategy_on_parse() -> None:
    payload = json.loads(_manifest().to_json())
    payload["strategies"][0] = "unknown"

    with pytest.raises(ValueError):
        RetrievalRunManifest.from_json(json.dumps(payload))


def test_frozen_strategy_order_names_the_three_default_candidates() -> None:
    assert RETRIEVAL_DEFAULT_STRATEGIES == (
        RetrievalStrategyName.BM25_TOKEN_WINDOW_RRF,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT,
        RetrievalStrategyName.POOLED_COREF_INTERVAL_CONTENT_MAX_COLBERT,
    )


def test_qrels_digest_is_stable_across_mapping_order() -> None:
    left = {"2": {"20": 1, "10": 2}, "1": {"30": 1}}
    right = {"1": {"30": 1}, "2": {"10": 2, "20": 1}}

    assert canonical_qrels_sha256(left) == canonical_qrels_sha256(right)


def test_qrels_digest_preserves_relevance_grades() -> None:
    assert canonical_qrels_sha256({"1": {"10": 1}}) != canonical_qrels_sha256(
        {"1": {"10": 2}}
    )


@pytest.mark.parametrize(
    "qrels",
    [
        {},
        {"": {"10": 1}},
        {1: {"10": 1}},
        {"1": {"": 1}},
        {"1": {10: 1}},
        {"1": {"10": True}},
        {"1": {"10": 1.0}},
        {"1": {"10": -1}},
    ],
)
def test_qrels_digest_rejects_invalid_boundaries(qrels: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        canonical_qrels_sha256(qrels)  # type: ignore[arg-type]


def test_sha256_file_hashes_exact_bytes(tmp_path: Path) -> None:
    source = tmp_path / "data.jsonl"
    source.write_bytes(b"one\ntwo\n")

    assert sha256_file(source) == hashlib.sha256(b"one\ntwo\n").hexdigest()


def _result(**overrides: object) -> RetrievalEvaluationResult:
    values: dict[str, object] = {
        "schema_version": "retrieval-evaluation-result/v1",
        "query_id": "17",
        "strategy": RetrievalStrategyName.BM25_TOKEN_WINDOW_RRF,
        "cutoff": 10,
        "latency_ms": 12.5,
        "hits": (RankedRetrievalHit("2", 0.7), RankedRetrievalHit("1", 0.6)),
        "error_type": None,
        "error_message": None,
    }
    values.update(overrides)
    return RetrievalEvaluationResult(**values)  # type: ignore[arg-type]


def test_retrieval_record_round_trips_ordered_hits_and_scores() -> None:
    record = RetrievalEvaluationRecord("retrieval-validation-1", _result())

    assert RetrievalEvaluationRecord.from_json(record.to_json()) == record
    assert [hit.doc_id for hit in record.result.hits] == ["2", "1"]
    assert [hit.score for hit in record.result.hits] == [0.7, 0.6]


@pytest.mark.parametrize(
    ("doc_id", "score"),
    [("not-numeric", 0.5), ("1", float("nan")), ("1", float("inf"))],
)
def test_ranked_retrieval_hit_rejects_invalid_values(doc_id: str, score: float) -> None:
    with pytest.raises((TypeError, ValueError)):
        RankedRetrievalHit(doc_id, score)


@pytest.mark.parametrize(
    "overrides",
    [
        {"schema_version": "retrieval-evaluation-result/v2"},
        {"query_id": "not-numeric"},
        {"strategy": "bm25-token-window-rrf"},
        {"cutoff": 0},
        {"latency_ms": -0.1},
        {"latency_ms": float("nan")},
        {"hits": (RankedRetrievalHit("1", 0.7), RankedRetrievalHit("1", 0.6))},
        {"hits": tuple(RankedRetrievalHit(str(index), 0.1) for index in range(11))},
        {"hits": (), "error_type": "TimeoutError"},
        {"hits": (), "error_message": "timed out"},
        {"error_type": "TimeoutError", "error_message": "timed out"},
    ],
)
def test_retrieval_result_rejects_invalid_boundaries(overrides: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        _result(**overrides)


def test_retrieval_result_accepts_a_failure_without_hits() -> None:
    result = _result(hits=(), error_type="TimeoutError", error_message="timed out")

    assert result.error_type == "TimeoutError"
    assert result.hits == ()


@pytest.mark.parametrize(
    ("run_id", "schema_version"),
    [("../escape", "retrieval-evaluation-record/v1"), ("run", "unknown")],
)
def test_retrieval_record_rejects_invalid_envelope(run_id: str, schema_version: str) -> None:
    with pytest.raises(ValueError):
        RetrievalEvaluationRecord(run_id, _result(), schema_version)


def test_retrieval_record_rejects_unknown_fields() -> None:
    payload = json.loads(RetrievalEvaluationRecord("run-1", _result()).to_json())
    payload["unexpected"] = True

    with pytest.raises(ValueError, match="fields"):
        RetrievalEvaluationRecord.from_json(json.dumps(payload))


class RecordingRetriever:
    def __init__(self, responses: dict[str, list[SearchHit] | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, limit: int) -> list[SearchHit]:
        self.calls.append((query, limit))
        response = self.responses[query]
        if isinstance(response, Exception):
            raise response
        return response


class IncrementingClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        self.value += 0.01
        return self.value


def _retrievers() -> dict[RetrievalStrategyName, RecordingRetriever]:
    return {
        RetrievalStrategyName.BM25_TOKEN_WINDOW_RRF: RecordingRetriever(
            {
                "first": [
                    SearchHit("2", "Second", "body", 0.7),
                    SearchHit("1", "First", "body", 0.6),
                ],
                "second": [],
            }
        ),
        RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT: RecordingRetriever(
            {
                "first": TimeoutError("late interaction timed out"),
                "second": [SearchHit("3", "Third", "body", 0.8)],
            }
        ),
        RetrievalStrategyName.POOLED_COREF_INTERVAL_CONTENT_MAX_COLBERT: RecordingRetriever(
            {
                "first": [SearchHit("4", "Fourth", "body", 0.9)],
                "second": [SearchHit("5", "Fifth", "body", 0.5)],
            }
        ),
    }


def test_retrieval_executor_writes_every_pair_in_canonical_order(tmp_path: Path) -> None:
    retrievers = _retrievers()
    output = tmp_path / "results.jsonl"

    summary = RetrievalEvaluationExecutor(retrievers, clock=IncrementingClock()).run(
        run_id="retrieval-validation-1",
        queries={"2": "second", "1": "first"},
        strategies=RETRIEVAL_DEFAULT_STRATEGIES,
        cutoff=10,
        output=output,
    )

    assert summary.expected_rows == 6
    assert summary.preexisting_rows == 0
    assert summary.written_rows == 6
    assert summary.failed_rows == 1
    assert [retriever.calls for retriever in retrievers.values()] == [
        [("first", 10), ("second", 10)],
        [("first", 10), ("second", 10)],
        [("first", 10), ("second", 10)],
    ]
    records = read_retrieval_evaluation_records(output)
    assert [(record.result.strategy, record.result.query_id) for record in records] == [
        (strategy, query_id)
        for strategy in RETRIEVAL_DEFAULT_STRATEGIES
        for query_id in ("1", "2")
    ]
    assert records[0].result.hits == (
        RankedRetrievalHit("2", 0.7),
        RankedRetrievalHit("1", 0.6),
    )
    assert records[1].result.hits == ()
    assert records[2].result.error_type == "TimeoutError"
    assert records[2].result.error_message == "late interaction timed out"


def test_retrieval_executor_resumes_only_missing_pairs(tmp_path: Path) -> None:
    output = tmp_path / "results.jsonl"
    output.write_text(
        RetrievalEvaluationRecord("retrieval-validation-1", _result(query_id="1")).to_json(),
        encoding="utf-8",
    )
    retrievers = {
        strategy: RecordingRetriever(
            {
                "first": [SearchHit("1", "First", "body", 1.0)],
                "second": [SearchHit("2", "Second", "body", 1.0)],
            }
        )
        for strategy in RETRIEVAL_DEFAULT_STRATEGIES
    }

    summary = RetrievalEvaluationExecutor(retrievers, clock=IncrementingClock()).run(
        run_id="retrieval-validation-1",
        queries={"2": "second", "1": "first"},
        strategies=RETRIEVAL_DEFAULT_STRATEGIES,
        cutoff=10,
        output=output,
    )

    assert summary.expected_rows == 6
    assert summary.preexisting_rows == 1
    assert summary.written_rows == 5
    assert len(read_retrieval_evaluation_records(output)) == 6
    assert retrievers[RetrievalStrategyName.BM25_TOKEN_WINDOW_RRF].calls == [("second", 10)]


@pytest.mark.parametrize(
    "existing",
    [
        "not json\n",
        RetrievalEvaluationRecord("another-run", _result(query_id="1")).to_json(),
        RetrievalEvaluationRecord("retrieval-validation-1", _result(query_id="1")).to_json()
        * 2,
        RetrievalEvaluationRecord("retrieval-validation-1", _result(query_id="9")).to_json(),
        RetrievalEvaluationRecord(
            "retrieval-validation-1",
            _result(query_id="1", strategy=RetrievalStrategyName.BM25),
        ).to_json(),
        RetrievalEvaluationRecord(
            "retrieval-validation-1", _result(query_id="1", cutoff=9)
        ).to_json(),
    ],
)
def test_retrieval_executor_rejects_invalid_existing_file_before_search(
    tmp_path: Path,
    existing: str,
) -> None:
    output = tmp_path / "results.jsonl"
    output.write_text(existing, encoding="utf-8")
    retrievers = _retrievers()

    with pytest.raises(ValueError):
        RetrievalEvaluationExecutor(retrievers).run(
            run_id="retrieval-validation-1",
            queries={"2": "second", "1": "first"},
            strategies=RETRIEVAL_DEFAULT_STRATEGIES,
            cutoff=10,
            output=output,
        )

    assert all(not retriever.calls for retriever in retrievers.values())


def _record(
    query_id: str,
    strategy: RetrievalStrategyName,
    hits: tuple[RankedRetrievalHit, ...] = (),
    *,
    latency_ms: float = 10.0,
    error: Exception | None = None,
    run_id: str = "retrieval-validation-1",
    cutoff: int = 2,
) -> RetrievalEvaluationRecord:
    return RetrievalEvaluationRecord(
        run_id,
        RetrievalEvaluationResult(
            schema_version="retrieval-evaluation-result/v1",
            query_id=query_id,
            strategy=strategy,
            cutoff=cutoff,
            latency_ms=latency_ms,
            hits=hits if error is None else (),
            error_type=type(error).__name__ if error is not None else None,
            error_message=str(error) if error is not None else None,
        ),
    )


def _report_records() -> tuple[RetrievalEvaluationRecord, ...]:
    baseline, colbert, content_max = RETRIEVAL_DEFAULT_STRATEGIES
    return (
        _record(
            "1",
            baseline,
            (RankedRetrievalHit("10", 0.9), RankedRetrievalHit("99", 0.8)),
            latency_ms=10.0,
        ),
        _record("2", baseline, latency_ms=30.0, error=TimeoutError("timed out")),
        _record(
            "1",
            colbert,
            (RankedRetrievalHit("99", 0.9), RankedRetrievalHit("10", 0.8)),
            latency_ms=20.0,
        ),
        _record("2", colbert, (RankedRetrievalHit("20", 0.7),), latency_ms=40.0),
        _record("1", content_max, (RankedRetrievalHit("10", 0.7),), latency_ms=50.0),
    )


def test_retrieval_report_penalizes_failed_and_missing_rows_as_empty_rankings() -> None:
    qrels = {"1": {"10": 1}, "2": {"20": 1}}

    report = build_retrieval_evaluation_report(
        _report_records(),
        run_id="retrieval-validation-1",
        queries={"1": "first", "2": "second"},
        qrels=qrels,
        strategies=RETRIEVAL_DEFAULT_STRATEGIES,
        cutoff=2,
    )

    baseline = report.strategies[0]
    assert baseline.metrics == evaluate_rankings(
        qrels,
        {"1": ["10", "99"], "2": []},
        cutoff=2,
    )
    assert (
        baseline.planned_rows,
        baseline.completed_rows,
        baseline.successful_rows,
        baseline.failed_rows,
        baseline.empty_result_rows,
    ) == (2, 2, 1, 1, 0)
    assert baseline.mean_latency_ms == 20.0
    assert baseline.median_latency_ms == 20.0

    content_max = report.strategies[2]
    assert content_max.metrics == evaluate_rankings(
        qrels,
        {"1": ["10"], "2": []},
        cutoff=2,
    )
    assert content_max.completed_rows == 1
    assert content_max.successful_rows == 1
    assert content_max.failed_rows == 0
    assert report.complete is False


def test_retrieval_report_marks_complete_when_every_planned_row_exists() -> None:
    records = _report_records() + (
        _record("2", RETRIEVAL_DEFAULT_STRATEGIES[2]),
    )

    report = build_retrieval_evaluation_report(
        records,
        run_id="retrieval-validation-1",
        queries={"1": "first", "2": "second"},
        qrels={"1": {"10": 1}, "2": {"20": 1}},
        strategies=RETRIEVAL_DEFAULT_STRATEGIES,
        cutoff=2,
    )

    assert report.complete is True
    assert report.strategies[2].empty_result_rows == 1


def test_write_retrieval_report_emits_canonical_json(tmp_path: Path) -> None:
    report = build_retrieval_evaluation_report(
        _report_records(),
        run_id="retrieval-validation-1",
        queries={"1": "first", "2": "second"},
        qrels={"1": {"10": 1}, "2": {"20": 1}},
        strategies=RETRIEVAL_DEFAULT_STRATEGIES,
        cutoff=2,
    )
    destination = tmp_path / "report.json"

    write_retrieval_evaluation_report(report, destination)

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "retrieval-evaluation-report/v1"
    assert payload["run_id"] == "retrieval-validation-1"
    assert destination.read_text(encoding="utf-8").endswith("\n")


@pytest.mark.parametrize(
    "mutation",
    ["foreign-run", "duplicate", "qrels-mismatch", "cutoff", "unplanned"],
)
def test_retrieval_report_rejects_inconsistent_raw_evidence(mutation: str) -> None:
    records = list(_report_records())
    queries = {"1": "first", "2": "second"}
    qrels = {"1": {"10": 1}, "2": {"20": 1}}
    if mutation == "foreign-run":
        records[0] = _record(
            "1", RETRIEVAL_DEFAULT_STRATEGIES[0], run_id="another-run"
        )
    elif mutation == "duplicate":
        records.append(records[0])
    elif mutation == "qrels-mismatch":
        qrels = {"1": {"10": 1}}
    elif mutation == "cutoff":
        records[0] = _record("1", RETRIEVAL_DEFAULT_STRATEGIES[0], cutoff=3)
    elif mutation == "unplanned":
        records[0] = _record("1", RetrievalStrategyName.BM25)

    with pytest.raises(ValueError):
        build_retrieval_evaluation_report(
            records,
            run_id="retrieval-validation-1",
            queries=queries,
            qrels=qrels,
            strategies=RETRIEVAL_DEFAULT_STRATEGIES,
            cutoff=2,
        )


def test_retrieval_report_describes_baseline_transitions_for_each_comparator() -> None:
    baseline, colbert, content_max = RETRIEVAL_DEFAULT_STRATEGIES
    qrels = {"1": {"10": 1}, "2": {"20": 1}, "3": {"30": 1}}
    rankings = {
        baseline: {"1": ("99",), "2": ("20",), "3": ("30",)},
        colbert: {"1": ("10",), "2": ("99",), "3": ("30",)},
        content_max: {"1": ("99",), "2": ("20",), "3": ("30",)},
    }
    records = tuple(
        _record(
            query_id,
            strategy,
            tuple(RankedRetrievalHit(doc_id, 1.0) for doc_id in rankings[strategy][query_id]),
        )
        for strategy in RETRIEVAL_DEFAULT_STRATEGIES
        for query_id in ("1", "2", "3")
    )

    report = build_retrieval_evaluation_report(
        records,
        run_id="retrieval-validation-1",
        queries={"1": "first", "2": "second", "3": "third"},
        qrels=qrels,
        strategies=RETRIEVAL_DEFAULT_STRATEGIES,
        cutoff=2,
    )

    assert [comparison.comparator for comparison in report.comparisons] == [
        colbert,
        content_max,
    ]
    comparison = report.comparisons[0]
    assert comparison.baseline is baseline
    assert comparison.comparator is colbert
    assert (
        comparison.improved_queries,
        comparison.regressed_queries,
        comparison.tied_queries,
    ) == (1, 1, 1)
    assert [transition.query_id for transition in comparison.transitions] == ["1", "2", "3"]
    assert comparison.transitions[0].relevant_document_ids_gained == ("10",)
    assert comparison.transitions[0].relevant_document_ids_lost == ()
    assert comparison.transitions[0].top_document_changed is True
    assert comparison.transitions[0].ndcg_delta == 1.0
    assert comparison.transitions[1].relevant_document_ids_gained == ()
    assert comparison.transitions[1].relevant_document_ids_lost == ("20",)
    assert comparison.transitions[1].top_document_changed is True
    assert comparison.transitions[1].ndcg_delta == -1.0
    assert comparison.transitions[2].top_document_changed is False
    assert comparison.transitions[2].ndcg_delta == 0.0
    assert (
        report.comparisons[1].improved_queries,
        report.comparisons[1].regressed_queries,
        report.comparisons[1].tied_queries,
    ) == (0, 0, 3)
