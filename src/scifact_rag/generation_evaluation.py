from __future__ import annotations

import json
import os
import re
import statistics
import time
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .application import finalize_generated_answer
from .domain import GeneratedAnswer, SearchHit
from .evaluation import GenerationEvaluationCase, GenerationEvaluationSet, ScientificStance
from .generation import GenerationContextStrategyName
from .ports import (
    AnswerGenerator,
    GenerationContextAssembler,
    MeasuredAnswerGenerator,
    Retriever,
)

GENERATION_EVALUATION_STRATEGIES = (
    GenerationContextStrategyName.WHOLE_DOCUMENT,
    GenerationContextStrategyName.ADAPTIVE,
)


@dataclass(frozen=True, slots=True)
class GenerationEvaluationResult:
    schema_version: str
    query_id: str
    source_split: str
    expected_stance: str
    predicted_stance: str | None
    stance_correct: bool | None
    context_strategy: GenerationContextStrategyName
    retrieval_limit: int
    retrieval_latency_ms: float
    context_assembly_latency_ms: float
    generator_latency_ms: float
    generation_reused_from: str | None
    input_tokens: int | None
    generated_tokens: int | None
    retrieved_parent_ids: tuple[str, ...]
    retrieved_gold_parent_ids: tuple[str, ...]
    relevant_parent_retrieved: bool
    supplied_parent_ids: tuple[str, ...]
    supplied_context_count: int
    supplied_contexts: tuple[SearchHit, ...]
    gold_evidence_sentence_count: int
    matched_gold_evidence_sentence_count: int
    gold_evidence_sentence_recall: float | None
    raw_generated_text: str | None
    answer_text: str | None
    citations: tuple[str, ...]
    citation_valid: bool | None
    generator_model: str
    error_type: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class GenerationEvaluationRecord:
    run_id: str
    result: GenerationEvaluationResult
    schema_version: str = "generation-evaluation-record/v1"

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", self.run_id):
            raise ValueError("run_id must be a safe non-empty name")
        if self.schema_version != "generation-evaluation-record/v1":
            raise ValueError("schema_version must be generation-evaluation-record/v1")

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")) + "\n"

    @classmethod
    def from_json(cls, serialized: str) -> GenerationEvaluationRecord:
        try:
            raw = json.loads(serialized)
        except json.JSONDecodeError as exc:
            raise ValueError("generation evaluation record must be valid JSON") from exc
        if not isinstance(raw, dict) or set(raw) != {"schema_version", "run_id", "result"}:
            raise ValueError("generation evaluation record fields do not match the schema")
        raw_result = raw["result"]
        expected_result_fields = {field.name for field in fields(GenerationEvaluationResult)}
        version_two_result_fields = expected_result_fields - {"generation_reused_from"}
        legacy_result_fields = version_two_result_fields - {"predicted_stance", "stance_correct"}
        if not isinstance(raw_result, dict) or (
            set(raw_result) != expected_result_fields
            and not (
                raw_result.get("schema_version") == "generation-evaluation-result/v1"
                and set(raw_result) == legacy_result_fields
            )
            and not (
                raw_result.get("schema_version") == "generation-evaluation-result/v2"
                and set(raw_result) == version_two_result_fields
            )
        ):
            raise ValueError("generation evaluation result fields do not match the schema")
        raw_result = dict(raw_result)
        if raw_result["schema_version"] == "generation-evaluation-result/v1":
            raw_result["predicted_stance"] = None
            raw_result["stance_correct"] = None
        if raw_result["schema_version"] in {
            "generation-evaluation-result/v1",
            "generation-evaluation-result/v2",
        }:
            raw_result["generation_reused_from"] = None
        contexts = raw_result["supplied_contexts"]
        expected_context_fields = {field.name for field in fields(SearchHit)}
        if not isinstance(contexts, list) or any(
            not isinstance(context, dict) or set(context) != expected_context_fields
            for context in contexts
        ):
            raise ValueError("supplied context fields do not match the schema")
        values: dict[str, Any] = dict(raw_result)
        try:
            values["context_strategy"] = GenerationContextStrategyName(
                raw_result["context_strategy"]
            )
            values["supplied_contexts"] = tuple(SearchHit(**context) for context in contexts)
            for field_name in (
                "retrieved_parent_ids",
                "retrieved_gold_parent_ids",
                "supplied_parent_ids",
                "citations",
            ):
                values[field_name] = tuple(raw_result[field_name])
            result = GenerationEvaluationResult(**values)
            return cls(
                run_id=raw["run_id"],
                result=result,
                schema_version=raw["schema_version"],
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"generation evaluation record values are invalid: {exc}") from exc


def generation_evaluation_expected_rows(
    case_count: int,
    records: Sequence[GenerationEvaluationRecord] = (),
) -> int:
    strategy_count = len(GENERATION_EVALUATION_STRATEGIES)
    if any(
        record.result.context_strategy is GenerationContextStrategyName.TOP_DP_CHUNKS
        for record in records
    ):
        strategy_count += 1
    return case_count * strategy_count


@dataclass(frozen=True, slots=True)
class GenerationEvaluationExecutionSummary:
    expected_rows: int
    preexisting_rows: int
    written_rows: int
    failed_rows: int


@dataclass(frozen=True, slots=True)
class GenerationStrategySummary:
    context_strategy: GenerationContextStrategyName
    rows: int
    successful_rows: int
    failed_rows: int
    relevant_parent_retrieval_rate: float
    mean_conditional_evidence_recall: float | None
    citation_valid_rate: float | None
    insufficient_evidence_rate: float | None
    stance_scored_rows: int
    stance_accuracy: float | None
    median_supplied_contexts: float | None
    median_input_tokens: float | None
    median_generated_tokens: float | None
    median_context_assembly_latency_ms: float | None
    median_generator_latency_ms: float | None


@dataclass(frozen=True, slots=True)
class GenerationEvaluationReport:
    schema_version: str
    run_id: str
    expected_rows: int
    completed_rows: int
    failed_rows: int
    complete: bool
    strategies: tuple[GenerationStrategySummary, ...]


def build_generation_evaluation_report(
    records: Sequence[GenerationEvaluationRecord],
    *,
    run_id: str,
    expected_rows: int,
) -> GenerationEvaluationReport:
    if expected_rows < 1 or len(records) > expected_rows:
        raise ValueError("expected_rows must be positive and cover every completed record")
    if any(record.run_id != run_id for record in records):
        raise ValueError("generation evaluation report records must share the requested run_id")
    keys = {(record.result.query_id, record.result.context_strategy) for record in records}
    if len(keys) != len(records):
        raise ValueError("generation evaluation report records must be unique by query and policy")
    present_strategies = {record.result.context_strategy for record in records}
    report_strategies = tuple(
        strategy
        for strategy in GenerationContextStrategyName
        if strategy in GENERATION_EVALUATION_STRATEGIES or strategy in present_strategies
    )
    summaries: list[GenerationStrategySummary] = []
    for strategy in report_strategies:
        results = [
            record.result for record in records if record.result.context_strategy is strategy
        ]
        successful = [result for result in results if result.error_type is None]
        scored_stances = [
            result.stance_correct for result in successful if result.stance_correct is not None
        ]
        evidence_recalls = [
            result.gold_evidence_sentence_recall
            for result in results
            if result.gold_evidence_sentence_recall is not None
        ]
        citation_validity = [
            result.citation_valid for result in results if result.citation_valid is not None
        ]
        summaries.append(
            GenerationStrategySummary(
                context_strategy=strategy,
                rows=len(results),
                successful_rows=len(successful),
                failed_rows=len(results) - len(successful),
                relevant_parent_retrieval_rate=(
                    sum(result.relevant_parent_retrieved for result in results) / len(results)
                    if results
                    else 0.0
                ),
                mean_conditional_evidence_recall=_mean(evidence_recalls),
                citation_valid_rate=(
                    sum(citation_validity) / len(citation_validity) if citation_validity else None
                ),
                insufficient_evidence_rate=(
                    sum(result.answer_text == "insufficient evidence" for result in successful)
                    / len(successful)
                    if successful
                    else None
                ),
                stance_scored_rows=len(scored_stances),
                stance_accuracy=(
                    sum(scored_stances) / len(scored_stances) if scored_stances else None
                ),
                median_supplied_contexts=_median(
                    [result.supplied_context_count for result in results]
                ),
                median_input_tokens=_median(
                    [result.input_tokens for result in results if result.input_tokens is not None]
                ),
                median_generated_tokens=_median(
                    [
                        result.generated_tokens
                        for result in results
                        if result.generated_tokens is not None
                    ]
                ),
                median_context_assembly_latency_ms=_median(
                    [result.context_assembly_latency_ms for result in results]
                ),
                median_generator_latency_ms=_median(
                    [result.generator_latency_ms for result in results]
                ),
            )
        )
    return GenerationEvaluationReport(
        schema_version="generation-evaluation-report/v2",
        run_id=run_id,
        expected_rows=expected_rows,
        completed_rows=len(records),
        failed_rows=sum(record.result.error_type is not None for record in records),
        complete=len(records) == expected_rows,
        strategies=tuple(summaries),
    )


def _mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _median(values: Sequence[int | float]) -> float | None:
    return float(statistics.median(values)) if values else None


def write_generation_evaluation_report(
    report: GenerationEvaluationReport,
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


class PairedGenerationEvaluator:
    def __init__(
        self,
        *,
        retriever: Retriever,
        assemblers: Mapping[GenerationContextStrategyName, GenerationContextAssembler],
        generator: AnswerGenerator,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._retriever = retriever
        self._assemblers = dict(assemblers)
        self._generator = generator
        self._clock = clock

    def evaluate(
        self,
        case: GenerationEvaluationCase,
        *,
        retrieval_limit: int,
        strategies: Sequence[GenerationContextStrategyName] = GENERATION_EVALUATION_STRATEGIES,
    ) -> tuple[GenerationEvaluationResult, ...]:
        if retrieval_limit < 1:
            raise ValueError("retrieval_limit must be positive")
        requested = set(strategies)
        selected = tuple(
            strategy for strategy in GenerationContextStrategyName if strategy in requested
        )
        if not selected:
            return ()
        retrieval_started = self._clock()
        try:
            retrieved = tuple(self._retriever.search(case.claim, retrieval_limit))
        # A paired run must retain every planned row even when retrieval itself fails.
        except Exception as exc:  # noqa: BLE001
            retrieval_latency_ms = (self._clock() - retrieval_started) * 1000.0
            return tuple(
                self._empty_result(
                    case,
                    strategy,
                    retrieval_limit,
                    retrieval_latency_ms,
                    answer_text=None,
                    citation_valid=None,
                    error=exc,
                )
                for strategy in selected
            )
        retrieval_latency_ms = (self._clock() - retrieval_started) * 1000.0
        if not retrieved:
            return tuple(
                self._empty_result(
                    case,
                    strategy,
                    retrieval_limit,
                    retrieval_latency_ms,
                    answer_text="insufficient evidence",
                    citation_valid=True,
                    error=None,
                )
                for strategy in selected
            )
        retrieved_ids = tuple(hit.doc_id for hit in retrieved)
        if len(retrieved_ids) != len(set(retrieved_ids)):
            raise ValueError("generation evaluation requires unique retrieved parent identifiers")
        allowed = set(retrieved_ids)
        retrieved_gold_ids = tuple(
            doc_id for doc_id in case.cited_document_ids if doc_id in allowed
        )
        generation_cache: dict[
            tuple[str, tuple[SearchHit, ...]],
            tuple[GenerationContextStrategyName, GeneratedAnswer, float],
        ] = {}

        return tuple(
            self._evaluate_policy(
                case,
                strategy,
                retrieved,
                retrieval_limit,
                retrieval_latency_ms,
                retrieved_gold_ids,
                generation_cache,
            )
            for strategy in selected
        )

    def _empty_result(
        self,
        case: GenerationEvaluationCase,
        strategy: GenerationContextStrategyName,
        retrieval_limit: int,
        retrieval_latency_ms: float,
        *,
        answer_text: str | None,
        citation_valid: bool | None,
        error: Exception | None,
    ) -> GenerationEvaluationResult:
        return GenerationEvaluationResult(
            schema_version="generation-evaluation-result/v3",
            query_id=case.query_id,
            source_split=case.source_split,
            expected_stance=case.expected_stance.value,
            predicted_stance=(
                ScientificStance.NOT_ENOUGH_INFO.value
                if error is None and answer_text == "insufficient evidence"
                else None
            ),
            stance_correct=(
                case.expected_stance is ScientificStance.NOT_ENOUGH_INFO
                if error is None and answer_text == "insufficient evidence"
                else None
            ),
            context_strategy=strategy,
            retrieval_limit=retrieval_limit,
            retrieval_latency_ms=retrieval_latency_ms,
            context_assembly_latency_ms=0.0,
            generator_latency_ms=0.0,
            generation_reused_from=None,
            input_tokens=None,
            generated_tokens=None,
            retrieved_parent_ids=(),
            retrieved_gold_parent_ids=(),
            relevant_parent_retrieved=False,
            supplied_parent_ids=(),
            supplied_context_count=0,
            supplied_contexts=(),
            gold_evidence_sentence_count=0,
            matched_gold_evidence_sentence_count=0,
            gold_evidence_sentence_recall=None,
            raw_generated_text=None,
            answer_text=answer_text,
            citations=(),
            citation_valid=citation_valid,
            generator_model=self._generator.model,
            error_type=type(error).__name__ if error is not None else None,
            error_message=str(error) if error is not None else None,
        )

    def _evaluate_policy(
        self,
        case: GenerationEvaluationCase,
        strategy: GenerationContextStrategyName,
        retrieved: tuple[SearchHit, ...],
        retrieval_limit: int,
        retrieval_latency_ms: float,
        retrieved_gold_ids: tuple[str, ...],
        generation_cache: dict[
            tuple[str, tuple[SearchHit, ...]],
            tuple[GenerationContextStrategyName, GeneratedAnswer, float],
        ],
    ) -> GenerationEvaluationResult:
        contexts: tuple[SearchHit, ...] = ()
        context_assembly_latency_ms = 0.0
        generator_latency_ms = 0.0
        input_tokens = None
        generated_tokens = None
        generation_reused_from = None
        try:
            assembly_started = self._clock()
            try:
                contexts = tuple(self._assemblers[strategy].assemble(case.claim, retrieved))
            finally:
                context_assembly_latency_ms = (self._clock() - assembly_started) * 1000.0
            allowed = {hit.doc_id for hit in retrieved}
            if not contexts or any(context.doc_id not in allowed for context in contexts):
                raise ValueError("generation context must contain retrieved parent documents")
            cache_key = (case.claim, contexts)
            cached = generation_cache.get(cache_key)
            if cached is None:
                generation_started = self._clock()
                try:
                    generated = (
                        self._generator.generate_with_metrics(case.claim, contexts)
                        if isinstance(self._generator, MeasuredAnswerGenerator)
                        else GeneratedAnswer(
                            self._generator.generate(case.claim, contexts),
                            None,
                            None,
                        )
                    )
                finally:
                    generator_latency_ms = (self._clock() - generation_started) * 1000.0
                generation_cache[cache_key] = (strategy, generated, generator_latency_ms)
            else:
                source_strategy, generated, generator_latency_ms = cached
                generation_reused_from = source_strategy.value
            raw_generated = generated.text
            input_tokens = generated.input_tokens
            generated_tokens = generated.generated_tokens
            predicted_stance, answer_body = parse_scifact_generated_answer(raw_generated)
            answer_text, citations, citation_valid = finalize_generated_answer(
                answer_body,
                allowed,
            )
            stance_correct = (
                predicted_stance == case.expected_stance.value
                if predicted_stance is not None
                else None
            )
            error_type = None
            error_message = None
        # Every policy must emit a row even when an adapter raises an unexpected error.
        except Exception as exc:  # noqa: BLE001
            raw_generated = None
            answer_text = None
            citations = ()
            citation_valid = None
            predicted_stance = None
            stance_correct = None
            generation_reused_from = None
            error_type = type(exc).__name__
            error_message = str(exc)
        evidence_count, matched_count, evidence_recall = _evidence_sentence_recall(
            case,
            contexts,
            set(retrieved_gold_ids),
        )
        supplied_parent_ids = tuple(dict.fromkeys(context.doc_id for context in contexts))
        return GenerationEvaluationResult(
            schema_version="generation-evaluation-result/v3",
            query_id=case.query_id,
            source_split=case.source_split,
            expected_stance=case.expected_stance.value,
            predicted_stance=predicted_stance,
            stance_correct=stance_correct,
            context_strategy=strategy,
            retrieval_limit=retrieval_limit,
            retrieval_latency_ms=retrieval_latency_ms,
            context_assembly_latency_ms=context_assembly_latency_ms,
            generator_latency_ms=generator_latency_ms,
            generation_reused_from=generation_reused_from,
            input_tokens=input_tokens,
            generated_tokens=generated_tokens,
            retrieved_parent_ids=tuple(hit.doc_id for hit in retrieved),
            retrieved_gold_parent_ids=retrieved_gold_ids,
            relevant_parent_retrieved=bool(retrieved_gold_ids),
            supplied_parent_ids=supplied_parent_ids,
            supplied_context_count=len(contexts),
            supplied_contexts=contexts,
            gold_evidence_sentence_count=evidence_count,
            matched_gold_evidence_sentence_count=matched_count,
            gold_evidence_sentence_recall=evidence_recall,
            raw_generated_text=raw_generated,
            answer_text=answer_text,
            citations=citations,
            citation_valid=citation_valid,
            generator_model=self._generator.model,
            error_type=error_type,
            error_message=error_message,
        )


_SCIFACT_VERDICT = re.compile(r"\AVERDICT: (SUPPORT|CONTRADICT|NOT_ENOUGH_INFO)(?:\r?\n|\Z)")


def parse_scifact_generated_answer(generated: str) -> tuple[str | None, str]:
    """Separate a strict leading SciFact verdict from the product-facing answer body."""
    stripped = generated.strip()
    match = _SCIFACT_VERDICT.match(stripped)
    if match is None:
        return None, stripped
    return match.group(1), stripped[match.end() :].strip()


def _evidence_sentence_recall(
    case: GenerationEvaluationCase,
    contexts: Sequence[SearchHit],
    retrieved_gold_ids: set[str],
) -> tuple[int, int, float | None]:
    eligible_sentences = {
        (rationale.doc_id, index, sentence)
        for rationale in case.rationales
        if rationale.doc_id in retrieved_gold_ids
        for index, sentence in zip(
            rationale.sentence_indices,
            rationale.sentences,
            strict=True,
        )
    }
    if not eligible_sentences:
        return 0, 0, None
    normalized_contexts: dict[str, list[str]] = {}
    for context in contexts:
        normalized_contexts.setdefault(context.doc_id, []).append(_normalize_text(context.text))
    matched = sum(
        any(_normalize_text(sentence) in context for context in normalized_contexts.get(doc_id, ()))
        for doc_id, _, sentence in eligible_sentences
    )
    return len(eligible_sentences), matched, matched / len(eligible_sentences)


def _normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split()).casefold()


class GenerationEvaluationExecutor:
    def __init__(self, evaluator: PairedGenerationEvaluator) -> None:
        self._evaluator = evaluator

    def run(
        self,
        *,
        run_id: str,
        evaluation_set: GenerationEvaluationSet,
        retrieval_limit: int,
        output: Path,
    ) -> GenerationEvaluationExecutionSummary:
        records = read_generation_evaluation_records(output)
        existing: dict[tuple[str, GenerationContextStrategyName], GenerationEvaluationRecord] = {}
        evaluation_query_ids = {case.query_id for case in evaluation_set.cases}
        for record in records:
            if record.run_id != run_id:
                raise ValueError("results file contains a different run_id")
            key = (record.result.query_id, record.result.context_strategy)
            if key in existing:
                raise ValueError("results file contains a duplicate query and policy row")
            if record.result.query_id not in evaluation_query_ids:
                raise ValueError("results file contains a query outside the evaluation set")
            existing[key] = record

        written: list[GenerationEvaluationRecord] = []
        for case in evaluation_set.cases:
            missing = tuple(
                strategy
                for strategy in GENERATION_EVALUATION_STRATEGIES
                if (case.query_id, strategy) not in existing
            )
            if not missing:
                continue
            results = self._evaluator.evaluate(
                case,
                retrieval_limit=retrieval_limit,
                strategies=missing,
            )
            if tuple(result.context_strategy for result in results) != missing or any(
                result.query_id != case.query_id for result in results
            ):
                raise ValueError("evaluator returned rows outside the requested query and policies")
            for result in results:
                record = GenerationEvaluationRecord(run_id=run_id, result=result)
                _append_record(output, record)
                existing[(result.query_id, result.context_strategy)] = record
                written.append(record)

        all_records = tuple(existing.values())
        return GenerationEvaluationExecutionSummary(
            expected_rows=generation_evaluation_expected_rows(
                len(evaluation_set.cases),
                all_records,
            ),
            preexisting_rows=len(records),
            written_rows=len(written),
            failed_rows=sum(record.result.error_type is not None for record in all_records),
        )


def read_generation_evaluation_records(path: Path) -> tuple[GenerationEvaluationRecord, ...]:
    if not path.exists():
        return ()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"could not read generation evaluation results: {exc}") from exc
    if any(not line.strip() for line in lines):
        raise ValueError("generation evaluation results must not contain blank rows")
    return tuple(GenerationEvaluationRecord.from_json(line) for line in lines)


def _append_record(path: Path, record: GenerationEvaluationRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(record.to_json())
        stream.flush()
        os.fsync(stream.fileno())
