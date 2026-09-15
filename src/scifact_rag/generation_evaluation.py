from __future__ import annotations

import time
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from .application import finalize_generated_answer
from .domain import SearchHit
from .evaluation import GenerationEvaluationCase
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
    ) -> tuple[GenerationEvaluationResult, ...]:
        if retrieval_limit < 1:
            raise ValueError("retrieval_limit must be positive")
        retrieval_started = self._clock()
        retrieved = tuple(self._retriever.search(case.claim, retrieval_limit))
        retrieval_latency_ms = (self._clock() - retrieval_started) * 1000.0
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
            for strategy in GenerationContextStrategyName
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
