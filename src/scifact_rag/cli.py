from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from .adapters.scifact import BeirSciFact
from .composition import build_application

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
) -> None:
    """Embed and upsert all SciFact documents."""
    corpus = BeirSciFact.ensure(data_dir)
    _emit(asdict(build_application().ingest(corpus, batch_size=batch_size)))


@app.command()
def search(query: str, limit: Annotated[int, typer.Option(min=1, max=100)] = 5) -> None:
    """Return the nearest SciFact evidence documents."""
    _emit([asdict(hit) for hit in build_application().search(query, limit=limit)])


@app.command()
def ask(query: str, limit: Annotated[int, typer.Option(min=1, max=20)] = 5) -> None:
    """Generate a cited answer or an insufficient-evidence result."""
    _emit(asdict(build_application().ask(query, limit=limit)))


@app.command("evaluate")
def evaluate_retrieval(
    data_dir: Annotated[Path, typer.Option(help="Dataset parent directory.")] = Path("data"),
    cutoff: Annotated[int, typer.Option(min=1, max=100)] = 10,
) -> None:
    """Evaluate retrieval with the public BEIR SciFact qrels."""
    corpus = BeirSciFact.ensure(data_dir)
    _emit(asdict(build_application().evaluate(corpus, cutoff=cutoff)))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
