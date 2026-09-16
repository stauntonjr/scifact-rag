from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from scifact_rag.domain import GeneratedAnswer, SearchHit
from scifact_rag.evaluation import (
    GenerationEvaluationCase,
    GenerationEvaluationSet,
    GoldRationale,
    ScientificStance,
)
from scifact_rag.generation import GenerationContextStrategyName
from scifact_rag.generation_evaluation import (
    GenerationEvaluationExecutor,
    GenerationEvaluationRecord,
    GenerationEvaluationReport,
    PairedGenerationEvaluator,
    build_generation_evaluation_report,
    generation_evaluation_expected_rows,
    write_generation_evaluation_report,
)


class RecordingRetriever:
    def __init__(self, hits: Sequence[SearchHit]) -> None:
        self.hits = list(hits)
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, limit: int) -> list[SearchHit]:
        self.calls.append((query, limit))
        return self.hits[:limit]


class FailingRetriever:
    def search(self, query: str, limit: int) -> list[SearchHit]:
        raise TimeoutError("retrieval timed out")


class RecordingAssembler:
    def __init__(
        self,
        contexts: Sequence[SearchHit] = (),
        *,
        error: Exception | None = None,
    ) -> None:
        self.contexts = list(contexts)
        self.error = error
        self.calls: list[tuple[str, list[SearchHit]]] = []

    def assemble(self, query: str, evidence: Sequence[SearchHit]) -> list[SearchHit]:
        self.calls.append((query, list(evidence)))
        if self.error is not None:
            raise self.error
        return list(self.contexts)


class RecordingGenerator:
    model = "test-generator"

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, list[SearchHit]]] = []

    def generate(self, query: str, evidence: Sequence[SearchHit]) -> str:
        self.calls.append((query, list(evidence)))
        return self.responses[evidence[0].text]


class MeasuredRecordingGenerator(RecordingGenerator):
    def generate_with_metrics(
        self,
        query: str,
        evidence: Sequence[SearchHit],
    ) -> GeneratedAnswer:
        return GeneratedAnswer(
            text=self.generate(query, evidence),
            input_tokens=137,
            generated_tokens=9,
        )


def _case() -> GenerationEvaluationCase:
    return GenerationEvaluationCase(
        schema_version="generation-evaluation-case/v1",
        query_id="17",
        claim="Drug A lowers marker B.",
        source_split="train-development",
        expected_stance=ScientificStance.SUPPORT,
        cited_document_ids=("1",),
        rationales=(
            GoldRationale(
                doc_id="1",
                label=ScientificStance.SUPPORT,
                sentence_indices=(1,),
                sentences=("Drug A lowers marker B.",),
            ),
        ),
    )


def test_cli_acceptance_fixture_freezes_representative_public_cases() -> None:
    fixture = Path(__file__).parent / "fixtures" / "cli_acceptance_cases.jsonl"

    evaluation_set = GenerationEvaluationSet.from_jsonl(
        fixture.read_text(encoding="utf-8")
    )

    assert tuple(case.query_id for case in evaluation_set.cases) == (
        "30",
        "40",
        "622",
        "1084",
    )
    assert tuple(case.expected_stance for case in evaluation_set.cases) == (
        ScientificStance.SUPPORT,
        ScientificStance.CONTRADICT,
        ScientificStance.NOT_ENOUGH_INFO,
        ScientificStance.SUPPORT,
    )
    qualified = evaluation_set.cases[-1]
    assert "associated with the highest adjusted hazard ratios" in (
        qualified.rationales[0].sentences[0]
    )


def test_paired_evaluator_retrieves_once_and_preserves_parent_order_for_every_policy() -> None:
    parents = [
        SearchHit("2", "Second", "Other evidence.", 0.9),
        SearchHit("1", "First", "Drug A lowers marker B.", 0.8),
    ]
    retriever = RecordingRetriever(parents)
    assemblers = {
        GenerationContextStrategyName.WHOLE_DOCUMENT: RecordingAssembler(
            [SearchHit("2", "Second", "whole", 0.9)]
        ),
        GenerationContextStrategyName.TOP_DP_CHUNKS: RecordingAssembler(
            [SearchHit("1", "First", "top dp", 0.8)]
        ),
        GenerationContextStrategyName.ADAPTIVE: RecordingAssembler(
            [SearchHit("1", "First", "adaptive", 0.8)]
        ),
    }
    generator = RecordingGenerator(
        {
            "whole": "Whole answer [2]",
            "top dp": "DP answer [1]",
            "adaptive": "Adaptive answer [1]",
        }
    )
    evaluator = PairedGenerationEvaluator(
        retriever=retriever,
        assemblers=assemblers,
        generator=generator,
    )

    results = evaluator.evaluate(_case(), retrieval_limit=2)

    assert retriever.calls == [("Drug A lowers marker B.", 2)]
    assert [result.context_strategy for result in results] == [
        GenerationContextStrategyName.WHOLE_DOCUMENT,
        GenerationContextStrategyName.ADAPTIVE,
    ]
    assert assemblers[GenerationContextStrategyName.WHOLE_DOCUMENT].calls == [
        ("Drug A lowers marker B.", parents)
    ]
    assert assemblers[GenerationContextStrategyName.TOP_DP_CHUNKS].calls == []
    assert assemblers[GenerationContextStrategyName.ADAPTIVE].calls == [
        ("Drug A lowers marker B.", parents)
    ]
    assert all(result.retrieved_parent_ids == ("2", "1") for result in results)


def test_paired_evaluator_records_raw_answer_citations_and_normalized_evidence_recall() -> None:
    parents = [SearchHit("1", "Study", "Complete abstract.", 1.0)]
    contexts = [
        SearchHit("1", "Study", "Drug A\n  LOWERS marker B.", 1.0),
        SearchHit("1", "Study", "Additional context.", 1.0),
    ]
    assembler = RecordingAssembler(contexts)
    evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever(parents),
        assemblers={strategy: assembler for strategy in GenerationContextStrategyName},
        generator=RecordingGenerator(
            {"Drug A\n  LOWERS marker B.": "The result supports the claim [1] [1]"}
        ),
    )

    result = evaluator.evaluate(_case(), retrieval_limit=5)[0]

    assert result.relevant_parent_retrieved is True
    assert result.retrieved_gold_parent_ids == ("1",)
    assert result.supplied_parent_ids == ("1",)
    assert result.supplied_context_count == 2
    assert result.gold_evidence_sentence_count == 1
    assert result.matched_gold_evidence_sentence_count == 1
    assert result.gold_evidence_sentence_recall == 1.0
    assert result.raw_generated_text == "The result supports the claim [1] [1]"
    assert result.answer_text == "The result supports the claim [1] [1]"
    assert result.citations == ("1",)
    assert result.citation_valid is True
    assert result.error_type is None
    assert result.error_message is None


def test_paired_evaluator_parses_and_scores_an_explicit_scifact_verdict() -> None:
    parent = SearchHit("1", "Study", "Drug A lowers marker B.", 1.0)
    assembler = RecordingAssembler([parent])
    evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever([parent]),
        assemblers={strategy: assembler for strategy in GenerationContextStrategyName},
        generator=RecordingGenerator(
            {parent.text: "VERDICT: SUPPORT\nThe evidence supports the claim [1]"}
        ),
    )

    result = evaluator.evaluate(_case(), retrieval_limit=1)[0]

    assert result.raw_generated_text == "VERDICT: SUPPORT\nThe evidence supports the claim [1]"
    assert result.answer_text == "The evidence supports the claim [1]"
    assert result.predicted_stance == "SUPPORT"
    assert result.stance_correct is True
    assert result.citation_valid is True


def test_paired_evaluator_reuses_one_generation_for_byte_identical_contexts() -> None:
    parent = SearchHit("1", "Study", "Drug A lowers marker B.", 1.0)
    assembler = RecordingAssembler([parent])
    generator = RecordingGenerator(
        {parent.text: "VERDICT: SUPPORT\nThe evidence supports the claim [1]"}
    )
    evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever([parent]),
        assemblers={strategy: assembler for strategy in GenerationContextStrategyName},
        generator=generator,
    )

    results = evaluator.evaluate(_case(), retrieval_limit=1)

    assert len(generator.calls) == 1
    assert len({result.raw_generated_text for result in results}) == 1
    assert results[0].generation_reused_from is None
    assert results[1].generation_reused_from == "whole-document"


def test_paired_evaluator_retains_policy_failure_and_continues_other_policies() -> None:
    parents = [SearchHit("1", "Study", "Drug A lowers marker B.", 1.0)]
    failing = RecordingAssembler(error=ValueError("missing DP views"))
    succeeding = RecordingAssembler(parents)
    evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever(parents),
        assemblers={
            GenerationContextStrategyName.WHOLE_DOCUMENT: succeeding,
            GenerationContextStrategyName.TOP_DP_CHUNKS: failing,
            GenerationContextStrategyName.ADAPTIVE: succeeding,
        },
        generator=RecordingGenerator({"Drug A lowers marker B.": "Supported [1]"}),
    )

    results = evaluator.evaluate(
        _case(),
        retrieval_limit=1,
        strategies=tuple(GenerationContextStrategyName),
    )

    failed = results[1]
    assert failed.context_strategy is GenerationContextStrategyName.TOP_DP_CHUNKS
    assert failed.raw_generated_text is None
    assert failed.answer_text is None
    assert failed.citation_valid is None
    assert failed.error_type == "ValueError"
    assert failed.error_message == "missing DP views"
    assert results[0].answer_text == "Supported [1]"
    assert results[2].answer_text == "Supported [1]"


def test_paired_evaluator_preserves_raw_invalid_citation_and_applies_product_fallback() -> None:
    parent = SearchHit("1", "Study", "Drug A lowers marker B.", 1.0)
    assembler = RecordingAssembler([parent])
    evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever([parent]),
        assemblers={strategy: assembler for strategy in GenerationContextStrategyName},
        generator=RecordingGenerator({parent.text: "Unsupported citation [999]"}),
    )

    result = evaluator.evaluate(_case(), retrieval_limit=1)[0]

    assert result.raw_generated_text == "Unsupported citation [999]"
    assert result.answer_text == "insufficient evidence"
    assert result.citations == ("999",)
    assert result.citation_valid is False


def test_paired_evaluator_runs_only_requested_policies_in_canonical_order() -> None:
    parent = SearchHit("1", "Study", "Drug A lowers marker B.", 1.0)
    assemblers = {
        strategy: RecordingAssembler([parent]) for strategy in GenerationContextStrategyName
    }
    evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever([parent]),
        assemblers=assemblers,
        generator=RecordingGenerator({parent.text: "Supported [1]"}),
    )

    results = evaluator.evaluate(
        _case(),
        retrieval_limit=1,
        strategies=(
            GenerationContextStrategyName.ADAPTIVE,
            GenerationContextStrategyName.TOP_DP_CHUNKS,
        ),
    )

    assert [result.context_strategy for result in results] == [
        GenerationContextStrategyName.TOP_DP_CHUNKS,
        GenerationContextStrategyName.ADAPTIVE,
    ]
    assert assemblers[GenerationContextStrategyName.WHOLE_DOCUMENT].calls == []


def test_generation_evaluation_record_round_trips_canonical_json() -> None:
    parent = SearchHit("1", "Study", "Drug A lowers marker B.", 1.0)
    assembler = RecordingAssembler([parent])
    evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever([parent]),
        assemblers={strategy: assembler for strategy in GenerationContextStrategyName},
        generator=RecordingGenerator({parent.text: "Supported [1]"}),
    )
    result = evaluator.evaluate(_case(), retrieval_limit=1)[0]
    record = GenerationEvaluationRecord(run_id="development-1", result=result)

    serialized = record.to_json()

    assert serialized.endswith("\n")
    assert GenerationEvaluationRecord.from_json(serialized) == record


def test_generation_evaluation_executor_resumes_only_missing_policy_rows(
    tmp_path: Path,
) -> None:
    parent = SearchHit("1", "Study", "Drug A lowers marker B.", 1.0)
    seed_assembler = RecordingAssembler([parent])
    seed_evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever([parent]),
        assemblers={strategy: seed_assembler for strategy in GenerationContextStrategyName},
        generator=RecordingGenerator({parent.text: "Supported [1]"}),
    )
    seed = seed_evaluator.evaluate(
        _case(),
        retrieval_limit=1,
        strategies=(GenerationContextStrategyName.WHOLE_DOCUMENT,),
    )[0]
    output = tmp_path / "results.jsonl"
    output.write_text(
        GenerationEvaluationRecord(run_id="development-1", result=seed).to_json(),
        encoding="utf-8",
    )
    retriever = RecordingRetriever([parent])
    assemblers = {
        strategy: RecordingAssembler([parent]) for strategy in GenerationContextStrategyName
    }
    evaluator = PairedGenerationEvaluator(
        retriever=retriever,
        assemblers=assemblers,
        generator=RecordingGenerator({parent.text: "Supported [1]"}),
    )

    summary = GenerationEvaluationExecutor(evaluator).run(
        run_id="development-1",
        evaluation_set=GenerationEvaluationSet((_case(),)),
        retrieval_limit=1,
        output=output,
    )

    assert summary.expected_rows == 2
    assert summary.preexisting_rows == 1
    assert summary.written_rows == 1
    assert summary.failed_rows == 0
    assert retriever.calls == [("Drug A lowers marker B.", 1)]
    assert assemblers[GenerationContextStrategyName.WHOLE_DOCUMENT].calls == []
    records = [
        GenerationEvaluationRecord.from_json(line)
        for line in output.read_text(encoding="utf-8").splitlines()
    ]
    assert [(record.result.query_id, record.result.context_strategy) for record in records] == [
        ("17", GenerationContextStrategyName.WHOLE_DOCUMENT),
        ("17", GenerationContextStrategyName.ADAPTIVE),
    ]


def test_generation_evaluation_executor_rejects_results_from_another_run(
    tmp_path: Path,
) -> None:
    parent = SearchHit("1", "Study", "Drug A lowers marker B.", 1.0)
    assembler = RecordingAssembler([parent])
    evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever([parent]),
        assemblers={strategy: assembler for strategy in GenerationContextStrategyName},
        generator=RecordingGenerator({parent.text: "Supported [1]"}),
    )
    result = evaluator.evaluate(_case(), retrieval_limit=1)[0]
    output = tmp_path / "results.jsonl"
    output.write_text(
        GenerationEvaluationRecord(run_id="other-run", result=result).to_json(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="different run_id"):
        GenerationEvaluationExecutor(evaluator).run(
            run_id="development-1",
            evaluation_set=GenerationEvaluationSet((_case(),)),
            retrieval_limit=1,
            output=output,
        )


def test_paired_evaluator_retains_retrieval_failure_for_every_requested_policy() -> None:
    assemblers = {strategy: RecordingAssembler() for strategy in GenerationContextStrategyName}
    evaluator = PairedGenerationEvaluator(
        retriever=FailingRetriever(),
        assemblers=assemblers,
        generator=RecordingGenerator({}),
    )

    results = evaluator.evaluate(_case(), retrieval_limit=5)

    assert len(results) == 2
    assert all(result.error_type == "TimeoutError" for result in results)
    assert all(result.error_message == "retrieval timed out" for result in results)
    assert all(result.retrieved_parent_ids == () for result in results)
    assert all(result.supplied_contexts == () for result in results)
    assert all(assembler.calls == [] for assembler in assemblers.values())


def test_paired_evaluator_records_no_retrieval_as_valid_insufficient_evidence() -> None:
    assemblers = {strategy: RecordingAssembler() for strategy in GenerationContextStrategyName}
    generator = RecordingGenerator({})
    evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever([]),
        assemblers=assemblers,
        generator=generator,
    )

    results = evaluator.evaluate(_case(), retrieval_limit=5)

    assert len(results) == 2
    assert all(result.raw_generated_text is None for result in results)
    assert all(result.answer_text == "insufficient evidence" for result in results)
    assert all(result.citation_valid is True for result in results)
    assert all(result.error_type is None for result in results)
    assert all(assembler.calls == [] for assembler in assemblers.values())
    assert generator.calls == []


def test_paired_evaluator_separates_assembly_and_generator_time_and_token_usage() -> None:
    parent = SearchHit("1", "Study", "Drug A lowers marker B.", 1.0)
    clock_values = iter((0.0, 0.1, 0.1, 0.12, 0.12, 0.32))
    evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever([parent]),
        assemblers={
            GenerationContextStrategyName.WHOLE_DOCUMENT: RecordingAssembler([parent]),
        },
        generator=MeasuredRecordingGenerator({parent.text: "Supported [1]"}),
        clock=lambda: next(clock_values),
    )

    result = evaluator.evaluate(
        _case(),
        retrieval_limit=1,
        strategies=(GenerationContextStrategyName.WHOLE_DOCUMENT,),
    )[0]

    assert result.retrieval_latency_ms == pytest.approx(100.0)
    assert result.context_assembly_latency_ms == pytest.approx(20.0)
    assert result.generator_latency_ms == pytest.approx(200.0)
    assert result.input_tokens == 137
    assert result.generated_tokens == 9


def test_generation_evaluation_report_aggregates_each_policy_without_dropping_failures() -> None:
    parent = SearchHit("1", "Study", "Drug A lowers marker B.", 1.0)
    assembler = RecordingAssembler([parent])
    evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever([parent]),
        assemblers={strategy: assembler for strategy in GenerationContextStrategyName},
        generator=RecordingGenerator({parent.text: "Supported [1]"}),
    )
    base = evaluator.evaluate(
        _case(),
        retrieval_limit=1,
        strategies=tuple(GenerationContextStrategyName),
    )
    records = (
        GenerationEvaluationRecord(
            "development-1",
            replace(
                base[0],
                input_tokens=100,
                generated_tokens=10,
                generator_latency_ms=100.0,
                context_assembly_latency_ms=2.0,
            ),
        ),
        GenerationEvaluationRecord(
            "development-1",
            replace(
                base[1],
                input_tokens=50,
                generated_tokens=9,
                generator_latency_ms=80.0,
                context_assembly_latency_ms=20.0,
                answer_text="insufficient evidence",
                citation_valid=False,
            ),
        ),
        GenerationEvaluationRecord(
            "development-1",
            replace(
                base[2],
                raw_generated_text=None,
                answer_text=None,
                citations=(),
                citation_valid=None,
                input_tokens=None,
                generated_tokens=None,
                error_type="TimeoutError",
                error_message="generation timed out",
            ),
        ),
    )

    report = build_generation_evaluation_report(
        records,
        run_id="development-1",
        expected_rows=3,
    )

    assert report.completed_rows == 3
    assert report.failed_rows == 1
    assert report.complete is True
    assert [summary.context_strategy for summary in report.strategies] == list(
        GenerationContextStrategyName
    )
    whole, top_dp, adaptive = report.strategies
    assert whole.successful_rows == 1
    assert whole.stance_scored_rows == 0
    assert whole.stance_accuracy is None
    assert whole.median_input_tokens == 100
    assert whole.mean_conditional_evidence_recall == 1.0
    assert top_dp.insufficient_evidence_rate == 1.0
    assert top_dp.citation_valid_rate == 0.0
    assert adaptive.failed_rows == 1
    assert adaptive.median_input_tokens is None


def test_generation_evaluation_expected_rows_recognizes_legacy_three_policy_records() -> None:
    parent = SearchHit("1", "Study", "Drug A lowers marker B.", 1.0)
    assembler = RecordingAssembler([parent])
    evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever([parent]),
        assemblers={strategy: assembler for strategy in GenerationContextStrategyName},
        generator=RecordingGenerator({parent.text: "Supported [1]"}),
    )
    results = evaluator.evaluate(
        _case(),
        retrieval_limit=1,
        strategies=tuple(GenerationContextStrategyName),
    )
    records = tuple(GenerationEvaluationRecord("development-1", result) for result in results)

    assert generation_evaluation_expected_rows(1, records[:1]) == 2
    assert generation_evaluation_expected_rows(1, records) == 3


def test_generation_evaluation_report_aggregates_only_parseable_stance_predictions() -> None:
    parent = SearchHit("1", "Study", "Drug A lowers marker B.", 1.0)
    assembler = RecordingAssembler([parent])
    evaluator = PairedGenerationEvaluator(
        retriever=RecordingRetriever([parent]),
        assemblers={strategy: assembler for strategy in GenerationContextStrategyName},
        generator=RecordingGenerator(
            {parent.text: "VERDICT: SUPPORT\nThe evidence supports the claim [1]"}
        ),
    )
    result = evaluator.evaluate(
        _case(),
        retrieval_limit=1,
        strategies=(GenerationContextStrategyName.WHOLE_DOCUMENT,),
    )[0]

    report = build_generation_evaluation_report(
        (GenerationEvaluationRecord("development-1", result),),
        run_id="development-1",
        expected_rows=2,
    )

    assert [summary.context_strategy for summary in report.strategies] == [
        GenerationContextStrategyName.WHOLE_DOCUMENT,
        GenerationContextStrategyName.ADAPTIVE,
    ]
    whole = report.strategies[0]
    assert whole.stance_scored_rows == 1
    assert whole.stance_accuracy == 1.0


def test_generation_evaluation_report_writes_canonical_json_atomically(tmp_path: Path) -> None:
    report = GenerationEvaluationReport(
        schema_version="generation-evaluation-report/v2",
        run_id="development-1",
        expected_rows=3,
        completed_rows=0,
        failed_rows=0,
        complete=False,
        strategies=(),
    )
    destination = tmp_path / "nested" / "results.report.json"

    write_generation_evaluation_report(report, destination)

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "generation-evaluation-report/v2"
    assert payload["run_id"] == "development-1"
    assert payload["complete"] is False
    assert destination.stat().st_mode & 0o777 == 0o644
