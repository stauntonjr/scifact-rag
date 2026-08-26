from __future__ import annotations

import os
import uuid

import pytest

from scifact_rag.adapters.postgres import PostgresEvidenceStore
from scifact_rag.domain import EvidenceDocument


@pytest.mark.integration
def test_pgvector_round_trip() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is not configured")
    assert database_url is not None
    store = PostgresEvidenceStore(database_url)
    store.initialize()
    suffix = uuid.uuid4().hex
    first = EvidenceDocument(f"first-{suffix}", "first", "first document")
    second = EvidenceDocument(f"second-{suffix}", "second", "second document")
    seed = uuid.UUID(suffix).bytes
    first_vector = [float(seed[index % len(seed)] - 127.5) for index in range(384)]
    second_vector = [-value for value in first_vector]

    store.upsert([first, second], [first_vector, second_vector])
    hits = store.search(first_vector, 1)

    assert hits[0].doc_id == first.doc_id
    assert hits[0].score == pytest.approx(1.0)
