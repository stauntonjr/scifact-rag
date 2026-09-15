from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from .adapters.scifact import BeirSciFact, QrelsSplit, SciFactGenerationEvaluationSource
from .composition import build_application
from .evaluation import GenerationRunManifest, write_generation_evaluation_set
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


@app.command("generation-eval-dry-run")
def generation_eval_dry_run(
    manifest: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Complete generation-run-manifest/v1 JSON file.",
        ),
    ],
) -> None:
    """Validate and emit a generation run manifest without model or database calls."""
    try:
        validated = GenerationRunManifest.from_json(manifest.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--manifest") from exc
    typer.echo(validated.to_json(), nl=False)


@app.command("build-generation-eval-manifest")
def build_generation_eval_manifest(
    official_data_dir: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Official SciFact release data directory with sentence arrays.",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(help="Destination for canonical generation-evaluation-case/v1 JSONL."),
    ],
    data_dir: Annotated[Path, typer.Option(help="BEIR dataset parent directory.")] = Path("data"),
    split: Annotated[
        QrelsSplit,
        typer.Option(help="Training-derived generation evaluation split."),
    ] = QrelsSplit.TRAIN_VALIDATION,
) -> None:
    """Build a fixed generation-evaluation manifest without database or model calls."""
    if split is QrelsSplit.TEST:
        raise typer.BadParameter(
            "generation evaluation construction cannot use the test split",
            param_hint="--split",
        )
    corpus = BeirSciFact.ensure(data_dir, split)
    evaluation_set = SciFactGenerationEvaluationSource(corpus, official_data_dir).cases()
    summary = asdict(write_generation_evaluation_set(evaluation_set, output))
    summary.update({"output": str(output), "source_split": split.value})
    _emit(summary)


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
