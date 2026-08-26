from __future__ import annotations

import json
from pathlib import Path

from scifact_rag.adapters.scifact import BeirSciFact


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
