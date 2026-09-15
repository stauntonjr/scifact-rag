from __future__ import annotations

import json
from inspect import signature
from pathlib import Path

from typer.testing import CliRunner

from scifact_rag.cli import app, ask, evaluate_retrieval, ingest, search
from scifact_rag.composition import build_application
from scifact_rag.generation import GenerationContextStrategyName
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
