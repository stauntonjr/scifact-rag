from __future__ import annotations

import json
from pathlib import Path

from scifact_rag.adapters.scifact import BeirSciFact, QrelsSplit


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
