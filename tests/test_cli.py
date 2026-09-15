from __future__ import annotations

import json
from inspect import signature
from pathlib import Path

import pytest
from typer.testing import CliRunner

from scifact_rag import cli as cli_module
from scifact_rag.adapters.openai_compatible import (
    SCIFACT_EVALUATION_PROMPT_ID,
    SCIFACT_EVALUATION_PROMPT_SHA256,
    SCIFACT_EVALUATION_SEED,
)
from scifact_rag.adapters.scifact import QrelsSplit
from scifact_rag.cli import app, ask, evaluate_retrieval, ingest, search
from scifact_rag.composition import build_application
from scifact_rag.evaluation import (
    ComponentRevision,
    EvaluationPurpose,
    GenerationEvaluationCase,
    GenerationEvaluationSet,
    GenerationRunManifest,
    GeneratorSettings,
    ScientificStance,
)
from scifact_rag.generation import GenerationContextStrategyName
from scifact_rag.generation_evaluation import (
    GenerationEvaluationExecutionSummary,
    GenerationEvaluationReport,
)
from scifact_rag.retrieval_evaluation import (
    RETRIEVAL_DEFAULT_STRATEGIES,
    RetrievalEvaluationExecutionSummary,
    RetrievalRunManifest,
    canonical_qrels_sha256,
    sha256_file,
)
from scifact_rag.strategies import RetrievalStrategyName


def test_cli_exposes_the_first_five_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("download", "ingest", "search", "ask", "evaluate"):
        assert command in result.stdout


def test_generation_evaluation_dry_run_canonicalizes_a_complete_manifest(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.json"
    payload = {
        "schema_version": "generation-run-manifest/v1",
        "run_id": "validation-run",
        "repository_commit": "a" * 40,
        "corpus_sha256": "b" * 64,
        "evaluation_manifest_sha256": "c" * 64,
        "source_split": "train-validation",
        "purpose": "default-selection",
        "retrieval_strategy": "pooled-coref-interval-colbert",
        "context_strategy": "adaptive",
        "retrieval_limit": 10,
        "components": [
            {
                "component": "generator-model",
                "identifier": "qwen",
                "revision": "qwen-revision",
            },
            {
                "component": "embedding-model",
                "identifier": "minilm",
                "revision": "minilm-revision",
            },
        ],
        "generator": {
            "temperature": 0.1,
            "maximum_answer_tokens": 512,
            "thinking_enabled": False,
        },
        "started_at": "2026-09-14T12:00:00Z",
        "completed_at": None,
        "host": "spark-3a8f",
        "results_path": "artifacts/validation-run/results.jsonl",
        "test_qrels_inspected": True,
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["generation-eval-dry-run", "--manifest", str(manifest)],
        env={
            "DATABASE_URL": "invalid://must-not-be-opened",
            "GENERATOR_BASE_URL": "http://must-not-be-called.invalid/v1",
            "LATE_INTERACTION_BASE_URL": "http://must-not-be-called.invalid",
        },
    )

    assert result.exit_code == 0
    normalized = json.loads(result.stdout)
    assert normalized["run_id"] == "validation-run"
    assert [component["component"] for component in normalized["components"]] == [
        "embedding-model",
        "generator-model",
    ]


def _retrieval_manifest(**overrides: object) -> RetrievalRunManifest:
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
            ComponentRevision("vector-model", "minilm", "revision"),
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


def test_retrieval_eval_dry_run_canonicalizes_without_composition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(_retrieval_manifest().to_json(), encoding="utf-8")

    def unexpected_call(*args, **kwargs):
        raise AssertionError("dry-run must not construct the corpus or application")

    monkeypatch.setattr(cli_module, "build_application", unexpected_call)
    monkeypatch.setattr(cli_module.BeirSciFact, "ensure", unexpected_call)

    result = CliRunner().invoke(
        app,
        ["retrieval-eval-dry-run", "--manifest", str(manifest)],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == json.loads(_retrieval_manifest().to_json())


def test_retrieval_eval_dry_run_rejects_invalid_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    payload = json.loads(_retrieval_manifest().to_json())
    payload["cutoff"] = 20
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["retrieval-eval-dry-run", "--manifest", str(manifest)],
    )

    assert result.exit_code == 2
    assert "cutoff must be 10" in result.stderr


_RETRIEVAL_COMPONENTS = (
    "application-image",
    "postgres-image",
    "embedding-model",
    "colbert-model",
    "colbert-tokenizer",
    "pg-tokenizer-extension",
    "pgvector-extension",
    "vchord-bm25-extension",
)


class FakeRetrievalCorpus:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._queries = {"1": "first", "2": "second"}
        self._qrels = {"1": {"10": 1}, "2": {"20": 1}}

    def queries(self):
        return self._queries

    def qrels(self):
        return self._qrels


def _retrieval_cli_fixture(tmp_path: Path) -> tuple[Path, Path, FakeRetrievalCorpus]:
    data_dir = tmp_path / "data"
    root = data_dir / "scifact"
    (root / "qrels").mkdir(parents=True)
    (root / "corpus.jsonl").write_bytes(b'{"_id":"10","text":"body"}\n')
    (root / "queries.jsonl").write_bytes(b'{"_id":"1","text":"first"}\n')
    (root / "qrels/train.tsv").write_text(
        "query-id\tcorpus-id\tscore\n1\t10\t1\n",
        encoding="utf-8",
    )
    corpus = FakeRetrievalCorpus(root)
    components = tuple(
        ComponentRevision(component, component, f"{component}-revision")
        for component in _RETRIEVAL_COMPONENTS
    )
    manifest = _retrieval_manifest(
        corpus_sha256=sha256_file(root / "corpus.jsonl"),
        queries_sha256=sha256_file(root / "queries.jsonl"),
        qrels_sha256=canonical_qrels_sha256(corpus.qrels()),
        components=components,
    )
    manifest_path = tmp_path / "retrieval-manifest.json"
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")
    return manifest_path, data_dir, corpus


def test_run_retrieval_eval_verifies_boundary_and_builds_frozen_strategies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, data_dir, corpus = _retrieval_cli_fixture(tmp_path)
    observed: dict[str, object] = {"built": []}

    class FakeApplication:
        def __init__(self, strategy: RetrievalStrategyName) -> None:
            self.strategy = strategy
            self.calls: list[tuple[str, int]] = []

        def search(self, query: str, *, limit: int):
            self.calls.append((query, limit))
            return []

    applications: dict[RetrievalStrategyName, FakeApplication] = {}

    def fake_ensure(actual_data_dir: Path, split: QrelsSplit):
        observed["ensure"] = (actual_data_dir, split)
        return corpus

    def fake_build(*, retrieval_strategy: RetrievalStrategyName):
        observed["built"].append(retrieval_strategy)  # type: ignore[union-attr]
        application = FakeApplication(retrieval_strategy)
        applications[retrieval_strategy] = application
        return application

    class FakeExecutor:
        def __init__(self, retrievers) -> None:
            assert tuple(retrievers) == RETRIEVAL_DEFAULT_STRATEGIES
            retrievers[RETRIEVAL_DEFAULT_STRATEGIES[0]].search("probe", 10)

        def run(self, **kwargs):
            observed["executor"] = kwargs
            return RetrievalEvaluationExecutionSummary(6, 1, 5, 0)

    raw_records = (object(),)
    report = object()

    def fake_read(path: Path):
        observed["read_path"] = path
        return raw_records

    def fake_report_builder(records, **kwargs):
        observed["report_records"] = records
        observed["report_kwargs"] = kwargs
        return report

    def fake_report_writer(actual_report, path: Path):
        observed["report"] = actual_report
        observed["report_path"] = path

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module.BeirSciFact, "ensure", fake_ensure)
    monkeypatch.setattr(cli_module, "build_application", fake_build)
    monkeypatch.setattr(cli_module, "RetrievalEvaluationExecutor", FakeExecutor, raising=False)
    monkeypatch.setattr(cli_module, "read_retrieval_evaluation_records", fake_read, raising=False)
    monkeypatch.setattr(
        cli_module, "build_retrieval_evaluation_report", fake_report_builder, raising=False
    )
    monkeypatch.setattr(
        cli_module, "write_retrieval_evaluation_report", fake_report_writer, raising=False
    )

    result = CliRunner().invoke(
        app,
        ["run-retrieval-eval", "--manifest", str(manifest_path), "--data-dir", str(data_dir)],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "expected_rows": 6,
        "failed_rows": 0,
        "preexisting_rows": 1,
        "report_path": "artifacts/retrieval-validation-1/results.report.json",
        "written_rows": 5,
    }
    assert observed["ensure"] == (data_dir, QrelsSplit.TRAIN_VALIDATION)
    assert observed["built"] == list(RETRIEVAL_DEFAULT_STRATEGIES)
    assert applications[RETRIEVAL_DEFAULT_STRATEGIES[0]].calls == [("probe", 10)]
    assert observed["executor"] == {
        "run_id": "retrieval-validation-1",
        "queries": corpus.queries(),
        "strategies": RETRIEVAL_DEFAULT_STRATEGIES,
        "cutoff": 10,
        "output": Path("artifacts/retrieval-validation-1/results.jsonl"),
    }
    assert observed["read_path"] == Path("artifacts/retrieval-validation-1/results.jsonl")
    assert observed["report_records"] is raw_records
    assert observed["report_kwargs"] == {
        "run_id": "retrieval-validation-1",
        "queries": corpus.queries(),
        "qrels": corpus.qrels(),
        "strategies": RETRIEVAL_DEFAULT_STRATEGIES,
        "cutoff": 10,
    }
    assert observed["report"] is report
    assert observed["report_path"] == Path("artifacts/retrieval-validation-1/results.report.json")


def test_run_retrieval_eval_stops_before_composition_on_digest_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, data_dir, corpus = _retrieval_cli_fixture(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["corpus_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(cli_module.BeirSciFact, "ensure", lambda *args: corpus)

    def unexpected_build(**kwargs):
        raise AssertionError("digest mismatch must stop before composition")

    monkeypatch.setattr(cli_module, "build_application", unexpected_build)

    result = CliRunner().invoke(
        app,
        ["run-retrieval-eval", "--manifest", str(manifest_path), "--data-dir", str(data_dir)],
    )

    assert result.exit_code == 2
    assert "corpus SHA-256" in result.stderr


def test_run_retrieval_eval_requires_every_runtime_component(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, data_dir, corpus = _retrieval_cli_fixture(tmp_path)
    complete = json.loads(manifest_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(cli_module.BeirSciFact, "ensure", lambda *args: corpus)

    def unexpected_build(**kwargs):
        raise AssertionError("missing components must stop before composition")

    monkeypatch.setattr(cli_module, "build_application", unexpected_build)

    for missing in _RETRIEVAL_COMPONENTS:
        payload = dict(complete)
        payload["components"] = [
            component for component in complete["components"] if component["component"] != missing
        ]
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")

        result = CliRunner().invoke(
            app,
            [
                "run-retrieval-eval",
                "--manifest",
                str(manifest_path),
                "--data-dir",
                str(data_dir),
            ],
        )

        assert result.exit_code == 2
        compact_error = "".join(result.stderr.split())
        assert "missingrequiredcomponent:" in compact_error
        assert missing in compact_error


def test_build_generation_evaluation_manifest_writes_exact_official_evidence(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "datasets"
    beir = data_dir / "scifact"
    official = tmp_path / "official"
    (beir / "qrels").mkdir(parents=True)
    official.mkdir()
    evidence = {"20": [{"sentences": [1], "label": "SUPPORT"}]}
    (beir / "corpus.jsonl").write_text(
        json.dumps({"_id": "20", "title": "Title", "text": "Background. Exact support."}) + "\n",
        encoding="utf-8",
    )
    (beir / "queries.jsonl").write_text(
        json.dumps({"_id": "7", "text": "Supported claim.", "metadata": evidence}) + "\n",
        encoding="utf-8",
    )
    (beir / "qrels/train.tsv").write_text(
        "query-id\tcorpus-id\tscore\n7\t20\t1\n",
        encoding="utf-8",
    )
    (official / "claims_train.jsonl").write_text(
        json.dumps(
            {
                "id": 7,
                "claim": "Supported claim.",
                "evidence": evidence,
                "cited_doc_ids": [20],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (official / "corpus.jsonl").write_text(
        json.dumps(
            {
                "doc_id": 20,
                "title": "Title",
                "abstract": ["Background.", "Exact support."],
                "structured": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "artifacts" / "validation.jsonl"

    result = CliRunner().invoke(
        app,
        [
            "build-generation-eval-manifest",
            "--data-dir",
            str(data_dir),
            "--official-data-dir",
            str(official),
            "--split",
            "train-validation",
            "--output",
            str(output),
        ],
        env={
            "DATABASE_URL": "invalid://must-not-be-opened",
            "GENERATOR_BASE_URL": "http://must-not-be-called.invalid/v1",
        },
    )

    assert result.exit_code == 0
    summary = json.loads(result.stdout)
    assert summary["cases"] == 1
    assert summary["support"] == 1
    assert summary["contradict"] == 0
    assert summary["not_enough_info"] == 0
    assert summary["source_split"] == "train-validation"
    assert summary["output"] == str(output)
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["rationales"][0]["sentences"] == ["Exact support."]


def test_cli_and_composition_default_to_equal_title_token_window_rrf() -> None:
    assert (
        signature(build_application).parameters["retrieval_strategy"].default
        is RetrievalStrategyName.TITLE_TOKEN_WINDOW_RRF
    )

    for command in (ingest, search, ask, evaluate_retrieval):
        assert (
            signature(command).parameters["strategy"].default
            is RetrievalStrategyName.TITLE_TOKEN_WINDOW_RRF
        )

    assert (
        signature(build_application).parameters["generation_context_strategy"].default
        is GenerationContextStrategyName.WHOLE_DOCUMENT
    )
    assert (
        signature(ask).parameters["context_strategy"].default
        is GenerationContextStrategyName.WHOLE_DOCUMENT
    )


def test_ask_cli_exposes_all_generation_context_strategies() -> None:
    result = CliRunner().invoke(app, ["ask", "--help"], env={"COLUMNS": "240"})

    assert result.exit_code == 0
    for strategy in GenerationContextStrategyName:
        assert strategy.value in result.stdout


def test_run_generation_evaluation_uses_manifest_boundary_and_results_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluation_set = GenerationEvaluationSet(
        (
            GenerationEvaluationCase(
                schema_version="generation-evaluation-case/v1",
                query_id="7",
                claim="Unresolved claim.",
                source_split="train-development",
                expected_stance=ScientificStance.NOT_ENOUGH_INFO,
                cited_document_ids=("20",),
                rationales=(),
            ),
        )
    )
    evaluation_path = tmp_path / "input.jsonl"
    evaluation_path.write_text(evaluation_set.to_jsonl(), encoding="utf-8")
    manifest = GenerationRunManifest(
        schema_version="generation-run-manifest/v1",
        run_id="development-1",
        repository_commit="a" * 40,
        corpus_sha256="b" * 64,
        evaluation_manifest_sha256=evaluation_set.sha256,
        source_split="train-development",
        purpose=EvaluationPurpose.DEVELOPMENT,
        retrieval_strategy=RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT.value,
        context_strategy="paired",
        retrieval_limit=5,
        components=(
            ComponentRevision("generator-model", "qwen", "revision"),
            ComponentRevision(
                "generator-prompt",
                SCIFACT_EVALUATION_PROMPT_ID,
                SCIFACT_EVALUATION_PROMPT_SHA256,
            ),
            ComponentRevision(
                "generator-seed",
                "fixed-per-request",
                str(SCIFACT_EVALUATION_SEED),
            ),
        ),
        generator=GeneratorSettings(0.1, 512, False),
        started_at="2026-09-14T12:00:00Z",
        completed_at=None,
        host="spark-3a8f",
        results_path="artifacts/results.jsonl",
        test_qrels_inspected=True,
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")
    built: dict[str, object] = {}
    evaluator = object()

    def fake_build(*, retrieval_strategy):
        built["retrieval_strategy"] = retrieval_strategy
        return evaluator

    class FakeExecutor:
        def __init__(self, actual_evaluator) -> None:
            assert actual_evaluator is evaluator

        def run(self, **kwargs):
            built.update(kwargs)
            return GenerationEvaluationExecutionSummary(2, 0, 2, 0)

    report = GenerationEvaluationReport(
        "generation-evaluation-report/v2",
        "development-1",
        2,
        2,
        0,
        True,
        (),
    )

    def fake_write(actual_report, destination):
        built["report"] = actual_report
        built["report_path"] = destination

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "build_generation_evaluator", fake_build)
    monkeypatch.setattr(cli_module, "GenerationEvaluationExecutor", FakeExecutor)
    monkeypatch.setattr(
        cli_module,
        "read_generation_evaluation_records",
        lambda path: (),
        raising=False,
    )
    monkeypatch.setattr(
        cli_module,
        "build_generation_evaluation_report",
        lambda records, **kwargs: report,
        raising=False,
    )
    monkeypatch.setattr(
        cli_module,
        "write_generation_evaluation_report",
        fake_write,
        raising=False,
    )

    result = CliRunner().invoke(
        app,
        [
            "run-generation-eval",
            "--manifest",
            str(manifest_path),
            "--evaluation-set",
            str(evaluation_path),
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "expected_rows": 2,
        "failed_rows": 0,
        "preexisting_rows": 0,
        "report_path": "artifacts/results.report.json",
        "written_rows": 2,
    }
    assert built["retrieval_strategy"] is RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT
    assert built["run_id"] == "development-1"
    assert built["evaluation_set"] == evaluation_set
    assert built["retrieval_limit"] == 5
    assert built["output"] == Path("artifacts/results.jsonl")
    assert built["report"] is report
    assert built["report_path"] == Path("artifacts/results.report.json")
