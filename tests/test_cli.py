from __future__ import annotations

from inspect import signature

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
