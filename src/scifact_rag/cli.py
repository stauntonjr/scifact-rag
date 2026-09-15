from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from .adapters.openai_compatible import (
    SCIFACT_EVALUATION_PROMPT_ID,
    SCIFACT_EVALUATION_PROMPT_SHA256,
    SCIFACT_EVALUATION_SEED,
)
from .adapters.proposition_extraction import (
    PROPOSITION_PROMPT_ID,
    PROPOSITION_PROMPT_SHA256,
    PROPOSITION_SCHEMA_SHA256,
    PROPOSITION_SEED,
)
from .adapters.scifact import BeirSciFact, QrelsSplit, SciFactGenerationEvaluationSource
from .application import RagApplication
from .composition import (
    Settings,
    build_application,
    build_generation_evaluator,
    build_proposition_evaluator,
    build_scientific_inference_executor,
)
from .domain import EvidenceDocument, SearchHit
from .evaluation import (
    GenerationEvaluationSet,
    GenerationRunManifest,
    GeneratorSettings,
    write_generation_evaluation_set,
)
from .generation import GenerationContextStrategyName
from .generation_evaluation import (
    GenerationEvaluationExecutor,
    build_generation_evaluation_report,
    generation_evaluation_expected_rows,
    read_generation_evaluation_records,
    write_generation_evaluation_report,
)
from .proposition import SourceKind
from .proposition_evaluation import (
    Phase3CandidateRecord,
    PropositionExtractionJournal,
    PropositionSourceManifest,
    build_error_audit,
    build_pair_records,
    build_proposition_report,
    build_source_manifest,
    phase3_candidate_records,
    read_audit,
    read_audit_reviews,
    write_immutable,
)
from .retrieval_evaluation import (
    RetrievalEvaluationExecutor,
    RetrievalRunManifest,
    build_retrieval_evaluation_report,
    canonical_qrels_sha256,
    read_retrieval_evaluation_records,
    sha256_file,
    write_retrieval_evaluation_report,
)
from .scientific_inference_evaluation import (
    ScientificInferenceJournal,
    ScientificInferenceRunManifest,
    build_scientific_inference_report,
    write_scientific_inference_failures,
    write_scientific_inference_report,
)
from .strategies import DEFAULT_RETRIEVAL_STRATEGY, RetrievalStrategyName

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
    ] = DEFAULT_RETRIEVAL_STRATEGY,
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
    ] = DEFAULT_RETRIEVAL_STRATEGY,
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
    ] = DEFAULT_RETRIEVAL_STRATEGY,
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


@app.command("retrieval-eval-dry-run")
def retrieval_eval_dry_run(
    manifest: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Complete retrieval-run-manifest/v1 JSON file.",
        ),
    ],
) -> None:
    """Validate and emit a retrieval run manifest without service or dataset calls."""
    try:
        validated = RetrievalRunManifest.from_json(manifest.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--manifest") from exc
    typer.echo(validated.to_json(), nl=False)


@app.command("scientific-inference-eval-dry-run")
def scientific_inference_eval_dry_run(
    manifest: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Complete scientific-inference-run-manifest/v1 JSON file.",
        ),
    ],
) -> None:
    """Validate an inference manifest without constructing data or model services."""
    try:
        validated = ScientificInferenceRunManifest.from_json(manifest.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--manifest") from exc
    typer.echo(validated.to_json(), nl=False)


class _ApplicationSearchRetriever:
    def __init__(self, application: RagApplication) -> None:
        self._application = application

    def search(self, query: str, limit: int) -> list[SearchHit]:
        return self._application.search(query, limit=limit)


@app.command("run-retrieval-eval")
def run_retrieval_eval(
    manifest: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Complete retrieval-run-manifest/v1 JSON file.",
        ),
    ],
    data_dir: Annotated[Path, typer.Option(help="BEIR dataset parent directory.")] = Path("data"),
) -> None:
    """Run or resume the fixed retrieval-default comparison."""
    try:
        run_manifest = RetrievalRunManifest.from_json(manifest.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--manifest") from exc

    corpus = BeirSciFact.ensure(data_dir, QrelsSplit.TRAIN_VALIDATION)
    qrels = corpus.qrels()
    digest_checks = (
        (
            "corpus SHA-256",
            run_manifest.corpus_sha256,
            sha256_file(corpus.root / "corpus.jsonl"),
        ),
        (
            "queries SHA-256",
            run_manifest.queries_sha256,
            sha256_file(corpus.root / "queries.jsonl"),
        ),
        ("qrels SHA-256", run_manifest.qrels_sha256, canonical_qrels_sha256(qrels)),
    )
    for name, expected, actual in digest_checks:
        if actual != expected:
            raise typer.BadParameter(
                f"{name} does not match the run manifest",
                param_hint="--manifest",
            )
    if len(qrels) != 160:
        raise typer.BadParameter(
            "validation qrels must contain exactly 160 queries",
            param_hint="--data-dir",
        )
    all_queries = corpus.queries()
    missing_query_ids = sorted(set(qrels) - set(all_queries), key=int)
    if missing_query_ids:
        raise typer.BadParameter(
            f"validation qrels query {missing_query_ids[0]} is missing from queries.jsonl",
            param_hint="--data-dir",
        )
    queries = {query_id: all_queries[query_id] for query_id in qrels}

    components = {component.component: component for component in run_manifest.components}
    required_components = (
        "application-image",
        "postgres-image",
        "embedding-model",
        "colbert-model",
        "colbert-tokenizer",
        "pg-tokenizer-extension",
        "pgvector-extension",
        "vchord-bm25-extension",
    )
    for component_name in required_components:
        if component_name not in components:
            raise typer.BadParameter(
                f"missing required component: {component_name}",
                param_hint="--manifest",
            )

    retrievers = {
        strategy: _ApplicationSearchRetriever(build_application(retrieval_strategy=strategy))
        for strategy in run_manifest.strategies
    }
    results_path = Path(run_manifest.results_path)
    summary = RetrievalEvaluationExecutor(retrievers).run(
        run_id=run_manifest.run_id,
        queries=queries,
        strategies=run_manifest.strategies,
        cutoff=run_manifest.cutoff,
        output=results_path,
    )
    report_path = results_path.with_suffix(".report.json")
    records = read_retrieval_evaluation_records(results_path)
    report = build_retrieval_evaluation_report(
        records,
        run_id=run_manifest.run_id,
        queries=queries,
        qrels=qrels,
        strategies=run_manifest.strategies,
        cutoff=run_manifest.cutoff,
    )
    write_retrieval_evaluation_report(report, report_path)
    response = asdict(summary)
    response["report_path"] = str(report_path)
    _emit(response)


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


@app.command("run-generation-eval")
def run_generation_eval(
    manifest: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Complete paired generation-run-manifest/v1 JSON file.",
        ),
    ],
    evaluation_set: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Canonical generation-evaluation-case/v1 JSONL input.",
        ),
    ],
) -> None:
    """Run or resume the three paired generation-context policies."""
    try:
        run_manifest = GenerationRunManifest.from_json(manifest.read_text(encoding="utf-8"))
        cases = GenerationEvaluationSet.from_jsonl(evaluation_set.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if run_manifest.context_strategy != "paired":
        raise typer.BadParameter("context_strategy must be paired", param_hint="--manifest")
    if run_manifest.evaluation_manifest_sha256 != cases.sha256:
        raise typer.BadParameter(
            "evaluation manifest SHA-256 does not match the run manifest",
            param_hint="--evaluation-set",
        )
    source_split = {case.source_split for case in cases.cases}
    if source_split != {run_manifest.source_split}:
        raise typer.BadParameter(
            "evaluation source split does not match the run manifest",
            param_hint="--evaluation-set",
        )
    required_generator = GeneratorSettings(0.1, 512, False)
    if run_manifest.generator != required_generator:
        raise typer.BadParameter(
            "generator settings must remain fixed at temperature 0.1, 512 tokens, thinking false",
            param_hint="--manifest",
        )
    components = {component.component: component for component in run_manifest.components}
    required_components = {
        "generator-prompt": (
            SCIFACT_EVALUATION_PROMPT_ID,
            SCIFACT_EVALUATION_PROMPT_SHA256,
        ),
        "generator-seed": ("fixed-per-request", str(SCIFACT_EVALUATION_SEED)),
    }
    for component_name, (identifier, revision) in required_components.items():
        component = components.get(component_name)
        if component is None or (component.identifier, component.revision) != (
            identifier,
            revision,
        ):
            raise typer.BadParameter(
                f"{component_name} must record {identifier} at revision {revision}",
                param_hint="--manifest",
            )
    try:
        retrieval_strategy = RetrievalStrategyName(run_manifest.retrieval_strategy)
    except ValueError as exc:
        raise typer.BadParameter(
            "retrieval_strategy is not implemented",
            param_hint="--manifest",
        ) from exc
    evaluator = build_generation_evaluator(retrieval_strategy=retrieval_strategy)
    results_path = Path(run_manifest.results_path)
    summary = GenerationEvaluationExecutor(evaluator).run(
        run_id=run_manifest.run_id,
        evaluation_set=cases,
        retrieval_limit=run_manifest.retrieval_limit,
        output=results_path,
    )
    report_path = results_path.with_suffix(".report.json")
    records = read_generation_evaluation_records(results_path)
    report = build_generation_evaluation_report(
        records,
        run_id=run_manifest.run_id,
        expected_rows=generation_evaluation_expected_rows(len(cases.cases), records),
    )
    write_generation_evaluation_report(report, report_path)
    response = asdict(summary)
    response["report_path"] = str(report_path)
    _emit(response)


@app.command("run-scientific-inference-eval")
def run_scientific_inference_eval(
    manifest: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Complete scientific-inference-run-manifest/v1 JSON file.",
        ),
    ],
    evaluation_set: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Canonical generation-evaluation-case/v1 JSONL input.",
        ),
    ],
) -> None:
    """Run or inspect the fixed, resumable scientific-inference diagnostic."""
    try:
        run_manifest = ScientificInferenceRunManifest.from_json(
            manifest.read_text(encoding="utf-8")
        )
        cases = GenerationEvaluationSet.from_jsonl(evaluation_set.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if run_manifest.evaluation_manifest_sha256 != cases.sha256:
        raise typer.BadParameter(
            "evaluation manifest SHA-256 does not match the run manifest",
            param_hint="--evaluation-set",
        )
    if {case.source_split for case in cases.cases} != {"train-validation"}:
        raise typer.BadParameter(
            "scientific inference requires the train-validation split",
            param_hint="--evaluation-set",
        )
    if len(cases.cases) != 160:
        raise typer.BadParameter(
            "scientific inference evaluation must contain exactly 160 cases",
            param_hint="--evaluation-set",
        )
    components = {component.component: component for component in run_manifest.components}
    required_components = (
        "application-image",
        "postgres-image",
        "colbert-model",
        "colbert-tokenizer",
        "deberta-model",
        "deberta-tokenizer",
        "transformers",
        "inference-container",
    )
    for component_name in required_components:
        if component_name not in components:
            raise typer.BadParameter(
                f"missing required component: {component_name}",
                param_hint="--manifest",
            )

    results_path = Path(run_manifest.results_path)
    summary = build_scientific_inference_executor(run_manifest).run(
        run_id=run_manifest.run_id,
        evaluation_set=cases,
        retrieval_limit=run_manifest.ranking_cutoff,
        output=results_path,
    )
    state = ScientificInferenceJournal.open(results_path, run_manifest.run_id).state
    records = tuple(state.results.values())
    report = build_scientific_inference_report(
        records,
        evaluation_set=cases,
        run_id=run_manifest.run_id,
        expected_candidates=summary.expected_candidates,
        outcome_unknown_candidates=len(state.outcome_unknown),
    )
    report_path = results_path.with_suffix(".report.json")
    failures_path = results_path.with_suffix(".failures.jsonl")
    write_scientific_inference_report(report, report_path)
    write_scientific_inference_failures(records, failures_path)
    response = asdict(summary)
    response.update({"report_path": str(report_path), "failures_path": str(failures_path)})
    _emit(response)


def _load_proposition_boundary(
    phase3_manifest_path: Path,
    phase3_results_path: Path,
    evaluation_path: Path,
    data_dir: Path,
) -> tuple[
    tuple[Phase3CandidateRecord, ...],
    dict[str, EvidenceDocument],
    str,
    str,
]:
    phase3 = ScientificInferenceRunManifest.from_json(
        phase3_manifest_path.read_text(encoding="utf-8")
    )
    evaluation = GenerationEvaluationSet.from_jsonl(evaluation_path.read_text(encoding="utf-8"))
    if (
        phase3.evaluation_manifest_sha256 != evaluation.sha256
        or len(evaluation.cases) != 160
        or {case.source_split for case in evaluation.cases} != {"train-validation"}
    ):
        raise ValueError("Phase 3 evaluation does not match the fixed 160-query boundary")
    journal = ScientificInferenceJournal.open(phase3_results_path, phase3.run_id)
    if journal.state.outcome_unknown:
        raise ValueError("Phase 3 journal contains outcome-unknown attempts")
    records = phase3_candidate_records(tuple(journal.state.results.values()))
    decisive = sum(item.gold_label in {"entailment", "contradiction"} for item in records)
    false_positives = sum(
        item.gold_label == "neutral" and item.predicted_label in {"entailment", "contradiction"}
        for item in records
    )
    if len(records) != 21_711 or decisive != 120 or false_positives != 4_316:
        raise ValueError("Phase 3 results do not match the fixed candidate comparison")
    corpus = BeirSciFact(data_dir / "scifact", QrelsSplit.TRAIN_VALIDATION)
    documents = {document.doc_id: document for document in corpus.documents()}
    return records, documents, evaluation.sha256, sha256_file(phase3_results_path)


def _derive_proposition_manifest(
    run_id: str,
    records: tuple[Phase3CandidateRecord, ...],
    documents: dict[str, EvidenceDocument],
    evaluation_sha256: str,
    phase3_sha256: str,
) -> PropositionSourceManifest:
    settings = Settings.from_environment()
    return build_source_manifest(
        run_id=run_id,
        evaluation_sha256=evaluation_sha256,
        phase3_sha256=phase3_sha256,
        records=records,
        documents=documents,
        extractor_model=settings.generator_model,
        prompt_id=PROPOSITION_PROMPT_ID,
        prompt_sha256=PROPOSITION_PROMPT_SHA256,
        schema_sha256=PROPOSITION_SCHEMA_SHA256,
        seed=PROPOSITION_SEED,
        embedding_model=settings.embedding_model,
    )


def _proposition_inputs(
    phase3_manifest: Path,
    phase3_results: Path,
    evaluation_set: Path,
    data_dir: Path,
    run_id: str,
) -> tuple[PropositionSourceManifest, tuple[Phase3CandidateRecord, ...], str]:
    records, documents, evaluation_sha256, phase3_sha256 = _load_proposition_boundary(
        phase3_manifest, phase3_results, evaluation_set, data_dir
    )
    manifest = _derive_proposition_manifest(
        run_id, records, documents, evaluation_sha256, phase3_sha256
    )
    audit = build_error_audit(records)
    return manifest, records, "".join(row.to_json() + "\n" for row in audit)


@app.command("prepare-proposition-pair-eval")
def prepare_proposition_pair_eval(
    phase3_manifest: Annotated[Path, typer.Option(exists=True, readable=True)],
    phase3_results: Annotated[Path, typer.Option(exists=True, readable=True)],
    evaluation_set: Annotated[Path, typer.Option(exists=True, readable=True)],
    data_dir: Annotated[Path, typer.Option()] = Path("data"),
    output_dir: Annotated[Path, typer.Option()] = Path("artifacts/proposition-pair-v1"),
    run_id: Annotated[str, typer.Option()] = "proposition-pair-v1",
) -> None:
    """Freeze the fixed source manifest and 100-row audit before extraction."""
    try:
        manifest, _records, audit = _proposition_inputs(
            phase3_manifest, phase3_results, evaluation_set, data_dir, run_id
        )
        write_immutable(output_dir / "manifest.json", manifest.to_json())
        write_immutable(output_dir / "audit.jsonl", audit)
    except (OSError, TypeError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    _emit(
        {
            "run_id": run_id,
            "sources": len(manifest.sources),
            "claims": sum(source.kind is SourceKind.CLAIM for source in manifest.sources),
            "documents": sum(source.kind is SourceKind.DOCUMENT for source in manifest.sources),
            "audit_rows": 100,
            "output_dir": str(output_dir),
        }
    )


@app.command("proposition-pair-eval-dry-run")
def proposition_pair_eval_dry_run(
    manifest: Annotated[Path, typer.Option(exists=True, readable=True)],
    audit: Annotated[Path, typer.Option(exists=True, readable=True)],
    phase3_manifest: Annotated[Path, typer.Option(exists=True, readable=True)],
    phase3_results: Annotated[Path, typer.Option(exists=True, readable=True)],
    evaluation_set: Annotated[Path, typer.Option(exists=True, readable=True)],
    data_dir: Annotated[Path, typer.Option()] = Path("data"),
) -> None:
    """Re-derive the frozen boundary without loading Qwen or MiniLM."""
    try:
        frozen = PropositionSourceManifest.from_json(manifest.read_text(encoding="utf-8"))
        expected, _records, expected_audit = _proposition_inputs(
            phase3_manifest,
            phase3_results,
            evaluation_set,
            data_dir,
            frozen.run_id,
        )
        if frozen.to_json() != expected.to_json():
            raise ValueError("source manifest does not match the re-derived boundary")
        audit_text = audit.read_text(encoding="utf-8")
        read_audit(audit_text)
        if audit_text != expected_audit:
            raise ValueError("audit does not match the re-derived boundary")
    except (OSError, TypeError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    _emit({"run_id": frozen.run_id, "sources": len(frozen.sources), "audit_rows": 100})


@app.command("run-proposition-pair-eval")
def run_proposition_pair_eval(
    manifest: Annotated[Path, typer.Option(exists=True, readable=True)],
    audit: Annotated[Path, typer.Option(exists=True, readable=True)],
    phase3_manifest: Annotated[Path, typer.Option(exists=True, readable=True)],
    phase3_results: Annotated[Path, typer.Option(exists=True, readable=True)],
    evaluation_set: Annotated[Path, typer.Option(exists=True, readable=True)],
    data_dir: Annotated[Path, typer.Option()] = Path("data"),
    audit_review: Annotated[Path | None, typer.Option(exists=True, readable=True)] = None,
) -> None:
    """Extract, resume, gate, and score the fixed proposition-pair diagnostic."""
    try:
        frozen = PropositionSourceManifest.from_json(manifest.read_text(encoding="utf-8"))
        expected, records, expected_audit = _proposition_inputs(
            phase3_manifest,
            phase3_results,
            evaluation_set,
            data_dir,
            frozen.run_id,
        )
        audit_text = audit.read_text(encoding="utf-8")
        audit_rows = read_audit(audit_text)
        if frozen.to_json() != expected.to_json() or audit_text != expected_audit:
            raise ValueError("frozen proposition artifacts do not match their source boundary")
        executor, embedder = build_proposition_evaluator(frozen)
        output_dir = manifest.parent
        extraction_path = output_dir / "extractions.jsonl"
        extraction = executor.extract(frozen, extraction_path)
        journal = PropositionExtractionJournal.open(extraction_path, frozen.run_id)
        pairs, coverage = build_pair_records(
            frozen,
            records,
            journal,
            embedder,
            decisive_document_ids={
                item.document_id
                for item in records
                if item.gold_label in {"entailment", "contradiction"}
            },
            audit_document_ids={item.document_id for item in audit_rows},
        )
        write_immutable(
            output_dir / "coverage.json",
            json.dumps(asdict(coverage), indent=2, sort_keys=True) + "\n",
        )
        response = {**asdict(extraction), "coverage_passed": coverage.passed}
        if coverage.passed:
            pair_text = "".join(item.to_json() + "\n" for item in pairs)
            pairs_path = output_dir / "pairs.jsonl"
            write_immutable(pairs_path, pair_text)
            response["scored_pairs"] = len(pairs)
            if audit_review is None:
                response["status"] = "awaiting-audit-review"
            else:
                read_audit_reviews(audit_review.read_text(encoding="utf-8"), audit_rows)
                report = build_proposition_report(
                    frozen.run_id,
                    pairs,
                    coverage,
                    extraction_sha256=sha256_file(extraction_path),
                    pairs_sha256=sha256_file(pairs_path),
                    audit_complete=True,
                )
                write_immutable(output_dir / "report.json", report.to_json())
                response.update({"status": "complete", "decision": report.decision})
        else:
            response["status"] = "stopped-extraction-coverage"
    except (OSError, TypeError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    _emit(response)


@app.command("evaluate")
def evaluate_retrieval(
    data_dir: Annotated[Path, typer.Option(help="Dataset parent directory.")] = Path("data"),
    cutoff: Annotated[int, typer.Option(min=1, max=100)] = 10,
    strategy: Annotated[
        RetrievalStrategyName,
        typer.Option(help="Retrieval strategy."),
    ] = DEFAULT_RETRIEVAL_STRATEGY,
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
