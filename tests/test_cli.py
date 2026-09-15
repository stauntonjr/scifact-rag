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
            return GenerationEvaluationExecutionSummary(3, 0, 3, 0)

    report = GenerationEvaluationReport(
        "generation-evaluation-report/v2",
        "development-1",
        3,
        3,
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
        "expected_rows": 3,
        "failed_rows": 0,
        "preexisting_rows": 0,
        "report_path": "artifacts/results.report.json",
        "written_rows": 3,
    }
    assert built["retrieval_strategy"] is RetrievalStrategyName.POOLED_COREF_INTERVAL_COLBERT
    assert built["run_id"] == "development-1"
    assert built["evaluation_set"] == evaluation_set
    assert built["retrieval_limit"] == 5
    assert built["output"] == Path("artifacts/results.jsonl")
    assert built["report"] is report
    assert built["report_path"] == Path("artifacts/results.report.json")
