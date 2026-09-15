from __future__ import annotations

import json
from dataclasses import replace

import pytest

from scifact_rag.domain import EvidenceDocument
from scifact_rag.proposition import (
    GroundedProposition,
    GroundedSpan,
    PropositionPolarity,
    SourceKind,
    source_digest,
)
from scifact_rag.proposition_evaluation import (
    ExtractionStatus,
    Phase3CandidateRecord,
    PropositionEvaluationExecutor,
    PropositionExtractionJournal,
    PropositionExtractionResult,
    build_error_audit,
    build_pair_records,
    build_proposition_report,
    build_source_manifest,
    document_digest,
    score_binary_separation,
)

_RUNTIME = {
    "extractor_model": "qwen-test",
    "prompt_id": "grounded-proposition-extraction-v1",
    "prompt_sha256": "c" * 64,
    "schema_sha256": "d" * 64,
    "seed": 1729,
    "embedding_model": "minilm-test",
}


def _candidate(
    index: int,
    *,
    gold: str,
    predicted: str,
    margin: float,
    query_id: str | None = None,
    document_id: str | None = None,
) -> Phase3CandidateRecord:
    claim_id = query_id or f"q-{index % 2}"
    doc_id = document_id or f"d-{index}"
    title = f"Title {doc_id}"
    text = f"Drug {doc_id} changes outcome."
    return Phase3CandidateRecord(
        candidate_id=f"{index:064x}",
        query_id=claim_id,
        document_id=doc_id,
        claim=f"Claim {claim_id}",
        document_sha256=document_digest(title, text),
        gold_label=gold,
        predicted_label=predicted,
        evidence_margin=margin,
        polarity_margin=-margin,
        colbert_score=margin / 10,
        evidence=(text,),
    )


def test_error_audit_freezes_all_decisive_errors_and_quintile_false_positives() -> None:
    decisive = [
        _candidate(index, gold="entailment", predicted="neutral", margin=float(index))
        for index in range(40)
    ] + [
        _candidate(index + 40, gold="contradiction", predicted="neutral", margin=float(index))
        for index in range(10)
    ]
    neutral_entailment = [
        _candidate(index + 100, gold="neutral", predicted="entailment", margin=float(index))
        for index in range(50)
    ]
    neutral_contradiction = [
        _candidate(index + 200, gold="neutral", predicted="contradiction", margin=float(index))
        for index in range(50)
    ]

    audit = build_error_audit((*decisive, *neutral_entailment, *neutral_contradiction))

    assert len(audit) == 100
    assert {row.candidate_id for row in audit}.issuperset(
        candidate.candidate_id for candidate in decisive
    )
    assert sum(row.stratum == "neutral-to-entailment" for row in audit) == 25
    assert sum(row.stratum == "neutral-to-contradiction" for row in audit) == 25
    assert {row.margin_band for row in audit if row.stratum == "neutral-to-entailment"} == {
        1,
        2,
        3,
        4,
        5,
    }
    assert audit == tuple(sorted(audit, key=lambda row: (row.stratum, row.candidate_id)))

    with pytest.raises(ValueError, match="duplicate candidate"):
        build_error_audit((*decisive, *neutral_entailment, *neutral_contradiction, decisive[0]))
    with pytest.raises(ValueError, match="exactly 50 decisive"):
        build_error_audit((*decisive[:-1], *neutral_entailment, *neutral_contradiction))


def test_source_manifest_contains_only_deduplicated_pool_sources_and_bound_digests() -> None:
    documents = {
        "d-1": EvidenceDocument("d-1", "Title d-1", "Drug d-1 changes outcome."),
        "d-2": EvidenceDocument("d-2", "", "Drug d-2 changes outcome."),
    }
    records = (
        _candidate(
            1, gold="neutral", predicted="neutral", margin=0.0, query_id="q-1", document_id="d-1"
        ),
        _candidate(
            2, gold="neutral", predicted="neutral", margin=0.0, query_id="q-1", document_id="d-2"
        ),
        _candidate(
            3, gold="neutral", predicted="neutral", margin=0.0, query_id="q-2", document_id="d-1"
        ),
    )
    records = tuple(
        replace(
            record,
            claim=f"Claim {record.query_id}",
            document_sha256=document_digest(
                documents[record.document_id].title,
                documents[record.document_id].text,
            ),
        )
        for record in records
    )

    manifest = build_source_manifest(
        run_id="run-1",
        evaluation_sha256="a" * 64,
        phase3_sha256="b" * 64,
        records=records,
        documents=documents,
        **_RUNTIME,
        expected_claims=2,
    )

    assert [(source.kind.value, source.source_id) for source in manifest.sources] == [
        ("claim", "q-1"),
        ("claim", "q-2"),
        ("document", "d-1"),
        ("document", "d-2"),
    ]
    assert manifest.sources[2].text == "Title d-1\nDrug d-1 changes outcome."
    assert manifest.sources[3].text == "Drug d-2 changes outcome."
    assert len(manifest.source_set_sha256) == 64
    assert json.loads(manifest.to_json())["source_set_sha256"] == manifest.source_set_sha256

    mismatched_claim = replace(records[0], claim="Different claim")
    with pytest.raises(ValueError, match="conflicting claim"):
        build_source_manifest(
            run_id="run-1",
            evaluation_sha256="a" * 64,
            phase3_sha256="b" * 64,
            records=(mismatched_claim, *records[1:]),
            documents=documents,
            **_RUNTIME,
            expected_claims=2,
        )
    with pytest.raises(ValueError, match="document digest"):
        build_source_manifest(
            run_id="run-1",
            evaluation_sha256="a" * 64,
            phase3_sha256="b" * 64,
            records=(replace(records[0], document_sha256="0" * 64), *records[1:]),
            documents=documents,
            **_RUNTIME,
            expected_claims=2,
        )


def test_extraction_journal_is_terminal_resumable_and_binary_metrics_are_exact(tmp_path) -> None:
    source = "Aspirin reduces fever."
    proposition = GroundedProposition(
        source_kind=SourceKind.DOCUMENT,
        source_id="d-1",
        source_sha256=source_digest(source),
        sentence=GroundedSpan(0, len(source), source),
        subject=GroundedSpan(0, 7, "Aspirin"),
        predicate=GroundedSpan(8, 15, "reduces"),
        object=GroundedSpan(16, 21, "fever"),
        polarity=PropositionPolarity.POSITIVE,
    )
    path = tmp_path / "extractions.jsonl"
    journal = PropositionExtractionJournal.open(path, "run-1")
    success = PropositionExtractionResult.create(
        "run-1", SourceKind.DOCUMENT, "d-1", source, (proposition,), 10.0
    )
    empty = PropositionExtractionResult.create(
        "run-1", SourceKind.DOCUMENT, "d-2", "No relation.", (), 4.0
    )
    failure = PropositionExtractionResult.create(
        "run-1",
        SourceKind.CLAIM,
        "q-1",
        "Bad claim.",
        (),
        3.0,
        error=("invalid-schema", "schema mismatch"),
    )
    for result in (success, empty, failure):
        journal.append(result)

    reopened = PropositionExtractionJournal.open(path, "run-1")
    assert reopened.completed == {
        (SourceKind.DOCUMENT, "d-1"),
        (SourceKind.DOCUMENT, "d-2"),
        (SourceKind.CLAIM, "q-1"),
    }
    assert reopened.results[(SourceKind.DOCUMENT, "d-1")].status is ExtractionStatus.SUCCESS
    assert len(path.read_text().splitlines()) == 3
    with pytest.raises(ValueError, match="terminal source"):
        reopened.append(success)

    path.write_text(path.read_text() + '{"truncated":', encoding="utf-8")
    with pytest.raises(ValueError, match="row 4"):
        PropositionExtractionJournal.open(path, "run-1")

    metrics = score_binary_separation((True, False, True, False), (0.9, 0.8, 0.7, 0.1))
    assert metrics.roc_auc == pytest.approx(0.75)
    assert metrics.average_precision == pytest.approx((1.0 + 2 / 3) / 2)
    assert metrics.prevalence == 0.5

    documents = {
        "d-10": EvidenceDocument("d-10", "", "Aspirin lowers fever."),
        "d-11": EvidenceDocument("d-11", "", "Aspirin raises fever."),
    }
    records = (
        _candidate(
            1000,
            gold="entailment",
            predicted="entailment",
            margin=0.8,
            query_id="q-10",
            document_id="d-10",
        ),
        _candidate(
            1001,
            gold="neutral",
            predicted="entailment",
            margin=0.7,
            query_id="q-10",
            document_id="d-11",
        ),
    )
    records = tuple(
        replace(
            record,
            claim="Aspirin lowers fever.",
            document_sha256=document_digest(
                documents[record.document_id].title,
                documents[record.document_id].text,
            ),
        )
        for record in records
    )
    manifest = build_source_manifest(
        run_id="pair-run",
        evaluation_sha256="a" * 64,
        phase3_sha256="b" * 64,
        records=records,
        documents=documents,
        **_RUNTIME,
        expected_claims=1,
    )

    class FakeExtractor:
        def __init__(self) -> None:
            self.calls: list[tuple[SourceKind, str]] = []

        def extract(self, source):
            self.calls.append((source.kind, source.source_id))
            words = source.text.split()
            object_text = words[2].rstrip(".")
            object_start = source.text.index(object_text)
            return (
                GroundedProposition(
                    source.kind,
                    source.source_id,
                    source.sha256,
                    GroundedSpan(0, len(source.text), source.text),
                    GroundedSpan(0, len(words[0]), words[0]),
                    GroundedSpan(len(words[0]) + 1, len(words[0]) + 1 + len(words[1]), words[1]),
                    GroundedSpan(object_start, object_start + len(object_text), object_text),
                    PropositionPolarity.POSITIVE,
                ),
            )

    extraction_path = tmp_path / "pair-extractions.jsonl"
    extractor = FakeExtractor()
    executor = PropositionEvaluationExecutor(extractor, timer=lambda: 1.0)
    summary = executor.extract(manifest, extraction_path)
    resumed = executor.extract(manifest, extraction_path)
    assert summary.extracted_sources == 3
    assert resumed.extracted_sources == 0
    assert len(extractor.calls) == 3

    embedded: list[tuple[str, ...]] = []

    class FakeEmbedder:
        def embed(self, texts):
            embedded.append(tuple(texts))
            basis = {
                "Aspirin": [1.0, 0.0],
                "lowers": [0.0, 1.0],
                "raises": [0.0, -1.0],
                "fever": [1.0, 1.0],
            }
            return [basis[text] for text in texts]

    journal = PropositionExtractionJournal.open(extraction_path, "pair-run")
    pairs, coverage = build_pair_records(
        manifest,
        records,
        journal,
        FakeEmbedder(),
        decisive_document_ids={"d-10"},
        audit_document_ids={"d-10", "d-11"},
    )
    assert len(embedded) == 1
    assert set(embedded[0]) == {"Aspirin", "lowers", "raises", "fever"}
    assert coverage.passed
    assert len(pairs) == 2
    assert pairs[0].features.claim_proposition_id
    assert pairs[0].features.proposition_pair_mean > pairs[1].features.proposition_pair_mean
    with pytest.raises(ValueError, match="audit review"):
        build_proposition_report(
            "pair-run",
            pairs,
            coverage,
            extraction_sha256="c" * 64,
            pairs_sha256="d" * 64,
            audit_complete=False,
            expected_decisive=1,
            expected_false_positives=1,
        )
    report = build_proposition_report(
        "pair-run",
        pairs,
        coverage,
        extraction_sha256="c" * 64,
        pairs_sha256="d" * 64,
        audit_complete=True,
        expected_decisive=1,
        expected_false_positives=1,
    )
    assert report.metrics["proposition_pair_mean"].roc_auc == 1.0
    assert report.decision == "graph-next"
