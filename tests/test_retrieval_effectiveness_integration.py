from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

try:
    import pytest
except ModuleNotFoundError:  # The production Compose image runs this file directly.
    pytest = None
else:
    pytestmark = pytest.mark.integration

from scifact_rag.adapters.scifact import BeirSciFact
from scifact_rag.composition import build_application

FIXTURE = Path(__file__).parent / "fixtures/retrieval_challenges.json"


@unittest.skipUnless(os.getenv("DATABASE_URL"), "DATABASE_URL is not configured")
class RetrievalEffectivenessIntegrationTests(unittest.TestCase):
    def test_rescued_retrieval_challenges_remain_in_top_ten(self) -> None:
        challenge = json.loads(FIXTURE.read_text(encoding="utf-8"))
        corpus = BeirSciFact(Path(os.getenv("SCIFACT_DATA_DIR", "data")) / "scifact")
        queries = corpus.queries()
        qrels = corpus.qrels()
        application = build_application()

        failures: list[str] = []
        for query_id in challenge["query_ids"]:
            ranked = {hit.doc_id for hit in application.search(queries[query_id], limit=10)}
            if not ranked.intersection(qrels[query_id]):
                failures.append(query_id)

        self.assertEqual([], failures, f"challenge queries missing relevant documents: {failures}")


if __name__ == "__main__":
    unittest.main()
