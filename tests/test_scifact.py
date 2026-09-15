from __future__ import annotations

import json
from pathlib import Path

import pytest

from scifact_rag.adapters.scifact import (
    BeirSciFact,
    QrelsSplit,
    SciFactGenerationEvaluationSource,
)
from scifact_rag.evaluation import ScientificStance


def test_beir_scifact_reads_corpus_queries_and_qrels(tmp_path: Path) -> None:
    root = tmp_path / "scifact"
    (root / "qrels").mkdir(parents=True)
    (root / "corpus.jsonl").write_text(
        json.dumps({"_id": "d1", "title": "Title", "text": "Abstract"}) + "\n",
        encoding="utf-8",
    )
    (root / "queries.jsonl").write_text(
        json.dumps({"_id": "q1", "text": "Claim"}) + "\n",
        encoding="utf-8",
    )
    (root / "qrels/test.tsv").write_text(
        "query-id\tcorpus-id\tscore\nq1\td1\t1\n",
        encoding="utf-8",
    )

    corpus = BeirSciFact(root)

    assert next(iter(corpus.documents())).doc_id == "d1"
    assert corpus.queries() == {"q1": "Claim"}
    assert corpus.qrels() == {"q1": {"d1": 1}}


def test_train_qrels_partition_is_deterministic_disjoint_and_complete(tmp_path: Path) -> None:
    root = tmp_path / "scifact"
    (root / "qrels").mkdir(parents=True)
    (root / "corpus.jsonl").write_text(
        json.dumps({"_id": "d1", "title": "Title", "text": "Abstract"}) + "\n",
        encoding="utf-8",
    )
    query_ids = [f"q{index}" for index in range(50)]
    (root / "queries.jsonl").write_text(
        "".join(
            json.dumps({"_id": query_id, "text": f"Claim {query_id}"}) + "\n"
            for query_id in query_ids
        ),
        encoding="utf-8",
    )
    rows = "query-id\tcorpus-id\tscore\n" + "".join(
        f"{query_id}\td1\t1\n" for query_id in query_ids
    )
    (root / "qrels/train.tsv").write_text(rows, encoding="utf-8")

    development = BeirSciFact(root, QrelsSplit.TRAIN_DEVELOPMENT).qrels()
    validation = BeirSciFact(root, QrelsSplit.TRAIN_VALIDATION).qrels()

    assert development
    assert validation
    assert set(development).isdisjoint(validation)
    assert set(development) | set(validation) == set(query_ids)
    assert BeirSciFact(root, QrelsSplit.TRAIN_VALIDATION).qrels() == validation


def _write_generation_sources(
    tmp_path: Path, *, invalid_sentence: bool = False
) -> tuple[Path, Path]:
    beir = tmp_path / "beir"
    original = tmp_path / "original"
    (beir / "qrels").mkdir(parents=True)
    original.mkdir()
    evidence = {"20": [{"sentences": [2 if invalid_sentence else 1], "label": "CONTRADICT"}]}
    (beir / "corpus.jsonl").write_text(
        "\n".join(
            (
                json.dumps({"_id": "10", "title": "Ten", "text": "No evidence here."}),
                json.dumps(
                    {
                        "_id": "20",
                        "title": "Twenty",
                        "text": "Background. Exact contradiction.",
                    }
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    (beir / "queries.jsonl").write_text(
        "\n".join(
            (
                json.dumps({"_id": "0", "text": "Unknown claim.", "metadata": {}}),
                json.dumps({"_id": "2", "text": "Contradicted claim.", "metadata": evidence}),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    (beir / "qrels/train.tsv").write_text(
        "query-id\tcorpus-id\tscore\n0\t10\t1\n2\t20\t1\n",
        encoding="utf-8",
    )
    (original / "claims_train.jsonl").write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "id": 0,
                        "claim": "Unknown claim.",
                        "evidence": {},
                        "cited_doc_ids": [10],
                    }
                ),
                json.dumps(
                    {
                        "id": 2,
                        "claim": "Contradicted claim.",
                        "evidence": evidence,
                        "cited_doc_ids": [20],
                    }
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    (original / "corpus.jsonl").write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "doc_id": 10,
                        "title": "Ten",
                        "abstract": ["No evidence here."],
                        "structured": False,
                    }
                ),
                json.dumps(
                    {
                        "doc_id": 20,
                        "title": "Twenty",
                        "abstract": ["Background.", "Exact contradiction."],
                        "structured": False,
                    }
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return beir, original


def test_generation_evaluation_source_joins_exact_official_rationales(tmp_path: Path) -> None:
    beir_root, original_root = _write_generation_sources(tmp_path)

    evaluation = SciFactGenerationEvaluationSource(
        BeirSciFact(beir_root, QrelsSplit.TRAIN_DEVELOPMENT),
        original_root,
    ).cases()

    assert [case.query_id for case in evaluation.cases] == ["0", "2"]
    assert evaluation.cases[0].expected_stance is ScientificStance.NOT_ENOUGH_INFO
    contradicted = evaluation.cases[1]
    assert contradicted.expected_stance is ScientificStance.CONTRADICT
    assert contradicted.cited_document_ids == ("20",)
    assert contradicted.rationales[0].sentence_indices == (1,)
    assert contradicted.rationales[0].sentences == ("Exact contradiction.",)


def test_generation_evaluation_source_rejects_an_out_of_range_sentence(tmp_path: Path) -> None:
    beir_root, original_root = _write_generation_sources(tmp_path, invalid_sentence=True)

    with pytest.raises(ValueError, match="outside document 20"):
        SciFactGenerationEvaluationSource(
            BeirSciFact(beir_root, QrelsSplit.TRAIN_DEVELOPMENT),
            original_root,
        ).cases()


@pytest.mark.parametrize(
    ("evidence", "message"),
    [
        ([], "evidence must be an object"),
        ({"20": [42]}, "rationale for 20 must be an object"),
    ],
)
def test_generation_evaluation_source_rejects_wrong_source_types(
    tmp_path: Path,
    evidence: object,
    message: str,
) -> None:
    beir_root, original_root = _write_generation_sources(tmp_path)
    claims = [
        json.loads(line) for line in (original_root / "claims_train.jsonl").read_text().splitlines()
    ]
    queries = [json.loads(line) for line in (beir_root / "queries.jsonl").read_text().splitlines()]
    claims[1]["evidence"] = evidence
    queries[1]["metadata"] = evidence
    (original_root / "claims_train.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in claims),
        encoding="utf-8",
    )
    (beir_root / "queries.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in queries),
        encoding="utf-8",
    )

    with pytest.raises(TypeError, match=message):
        SciFactGenerationEvaluationSource(
            BeirSciFact(beir_root, QrelsSplit.TRAIN_DEVELOPMENT),
            original_root,
        ).cases()
