from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from .adapters.scifact import BeirSciFact, QrelsSplit
from .composition import build_application
from .generation import GenerationContextStrategyName
from .strategies import RetrievalStrategyName

app = typer.Typer(no_args_is_help=True, help="Grounded retrieval and generation over SciFact.")


def _emit(value: object) -> None:
    typer.echo(json.dumps(value, indent=2, sort_keys=True))


@app.command()
def download(
    data_dir: Annotated[Path, typer.Option(help="Dataset parent directory.")] = Path("data"),
) -> None:
    """Download and verify the public BEIR SciFact dataset."""
    corpus = BeirSciFact.ensure(data_dir)
    _emit({"dataset": str(corpus.root), "status": "ready"})


@app.command()
def ingest(
    data_dir: Annotated[Path, typer.Option(help="Dataset parent directory.")] = Path("data"),
    batch_size: Annotated[int, typer.Option(min=1)] = 64,
    strategy: Annotated[
        RetrievalStrategyName,
        typer.Option(help="Retrieval strategy."),
    ] = RetrievalStrategyName.TITLE_TOKEN_WINDOW_RRF,
) -> None:
    """Index or embed and upsert all SciFact documents."""
    corpus = BeirSciFact.ensure(data_dir)
    _emit(
        asdict(build_application(retrieval_strategy=strategy).ingest(corpus, batch_size=batch_size))
    )


@app.command()
def search(
    query: str,
    limit: Annotated[int, typer.Option(min=1, max=100)] = 5,
    strategy: Annotated[
        RetrievalStrategyName,
        typer.Option(help="Retrieval strategy."),
    ] = RetrievalStrategyName.TITLE_TOKEN_WINDOW_RRF,
) -> None:
    """Return ranked SciFact evidence documents."""
    _emit(
        [
            asdict(hit)
            for hit in build_application(retrieval_strategy=strategy).search(query, limit=limit)
        ]
    )


@app.command()
def ask(
    query: str,
    limit: Annotated[int, typer.Option(min=1, max=20)] = 5,
    strategy: Annotated[
        RetrievalStrategyName,
        typer.Option(help="Retrieval strategy."),
    ] = RetrievalStrategyName.TITLE_TOKEN_WINDOW_RRF,
    context_strategy: Annotated[
        GenerationContextStrategyName,
        typer.Option(help="Generation context strategy."),
    ] = GenerationContextStrategyName.WHOLE_DOCUMENT,
) -> None:
    """Generate a cited answer or an insufficient-evidence result."""
    _emit(
        asdict(
            build_application(
                retrieval_strategy=strategy,
                generation_context_strategy=context_strategy,
            ).ask(query, limit=limit)
        )
    )


@app.command("evaluate")
def evaluate_retrieval(
    data_dir: Annotated[Path, typer.Option(help="Dataset parent directory.")] = Path("data"),
    cutoff: Annotated[int, typer.Option(min=1, max=100)] = 10,
    strategy: Annotated[
        RetrievalStrategyName,
        typer.Option(help="Retrieval strategy."),
    ] = RetrievalStrategyName.TITLE_TOKEN_WINDOW_RRF,
    split: Annotated[
        QrelsSplit,
        typer.Option(help="Qrels evaluation split."),
    ] = QrelsSplit.TEST,
) -> None:
    """Evaluate retrieval with the public BEIR SciFact qrels."""
    corpus = BeirSciFact.ensure(data_dir, split)
    _emit(asdict(build_application(retrieval_strategy=strategy).evaluate(corpus, cutoff=cutoff)))


@app.command("diagnose-candidates")
def diagnose_candidates(
    data_dir: Annotated[Path, typer.Option(help="Dataset parent directory.")] = Path("data"),
    cutoff: Annotated[int, typer.Option(min=1, max=100)] = 10,
    strategy: Annotated[
        RetrievalStrategyName,
        typer.Option(help="Pooled retrieval strategy."),
    ] = RetrievalStrategyName.POOLED_FOUR_CHANNEL_RRF,
    split: Annotated[
        QrelsSplit,
        typer.Option(help="Qrels evaluation split."),
    ] = QrelsSplit.TRAIN_VALIDATION,
) -> None:
    """Report candidate-pool, oracle, channel, and final-ranking diagnostics."""
    corpus = BeirSciFact.ensure(data_dir, split)
    _emit(
        asdict(
            build_application(retrieval_strategy=strategy).diagnose_candidates(
                corpus,
                cutoff=cutoff,
            )
        )
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
