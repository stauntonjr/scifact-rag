from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from .application import finalize_generated_answer
from .domain import SearchHit
from .evaluation import GenerationEvaluationCase, GenerationEvaluationSet
from .generation import GenerationContextStrategyName
from .ports import AnswerGenerator, GenerationContextAssembler, Retriever


@dataclass(frozen=True, slots=True)
class GenerationEvaluationResult:
    schema_version: str
    query_id: str
    source_split: str
    expected_stance: str
    context_strategy: GenerationContextStrategyName
    retrieval_limit: int
    retrieval_latency_ms: float
    generation_latency_ms: float
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
        if not isinstance(raw_result, dict) or set(raw_result) != expected_result_fields:
            raise ValueError("generation evaluation result fields do not match the schema")
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


@dataclass(frozen=True, slots=True)
class GenerationEvaluationExecutionSummary:
    expected_rows: int
    preexisting_rows: int
    written_rows: int
    failed_rows: int


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
        strategies: Sequence[GenerationContextStrategyName] = tuple(GenerationContextStrategyName),
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

        return tuple(
            self._evaluate_policy(
                case,
                strategy,
                retrieved,
                retrieval_limit,
                retrieval_latency_ms,
                retrieved_gold_ids,
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
            schema_version="generation-evaluation-result/v1",
            query_id=case.query_id,
            source_split=case.source_split,
            expected_stance=case.expected_stance.value,
            context_strategy=strategy,
            retrieval_limit=retrieval_limit,
            retrieval_latency_ms=retrieval_latency_ms,
            generation_latency_ms=0.0,
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
    ) -> GenerationEvaluationResult:
        started = self._clock()
        contexts: tuple[SearchHit, ...] = ()
        try:
            contexts = tuple(self._assemblers[strategy].assemble(case.claim, retrieved))
            allowed = {hit.doc_id for hit in retrieved}
            if not contexts or any(context.doc_id not in allowed for context in contexts):
                raise ValueError("generation context must contain retrieved parent documents")
            raw_generated = self._generator.generate(case.claim, contexts)
            answer_text, citations, citation_valid = finalize_generated_answer(
                raw_generated,
                allowed,
            )
            error_type = None
            error_message = None
        # Every policy must emit a row even when an adapter raises an unexpected error.
        except Exception as exc:  # noqa: BLE001
            raw_generated = None
            answer_text = None
            citations = ()
            citation_valid = None
            error_type = type(exc).__name__
            error_message = str(exc)
        latency_ms = (self._clock() - started) * 1000.0
        evidence_count, matched_count, evidence_recall = _evidence_sentence_recall(
            case,
            contexts,
            set(retrieved_gold_ids),
        )
        supplied_parent_ids = tuple(dict.fromkeys(context.doc_id for context in contexts))
        return GenerationEvaluationResult(
            schema_version="generation-evaluation-result/v1",
            query_id=case.query_id,
            source_split=case.source_split,
            expected_stance=case.expected_stance.value,
            context_strategy=strategy,
            retrieval_limit=retrieval_limit,
            retrieval_latency_ms=retrieval_latency_ms,
            generation_latency_ms=latency_ms,
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
        records = _read_records(output)
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
                for strategy in GenerationContextStrategyName
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
            expected_rows=len(evaluation_set.cases) * len(GenerationContextStrategyName),
            preexisting_rows=len(records),
            written_rows=len(written),
            failed_rows=sum(record.result.error_type is not None for record in all_records),
        )


def _read_records(path: Path) -> tuple[GenerationEvaluationRecord, ...]:
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
