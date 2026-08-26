from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text

from scifact_rag.adapters.postgres import PostgresEvidenceStore
from scifact_rag.domain import EvidenceChunk, EvidenceDocument


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

    chunks = [
        EvidenceChunk(first.doc_id, 0, "irrelevant first window"),
        EvidenceChunk(first.doc_id, 1, "relevant second window"),
        EvidenceChunk(second.doc_id, 0, "second document"),
    ]
    try:
        store.upsert(
            [first, second],
            chunks,
            [second_vector, first_vector, second_vector],
        )
        hits = store.search(first_vector, 1)

        assert hits[0].doc_id == first.doc_id
        assert hits[0].score == pytest.approx(1.0)
    finally:
        with store._engine.begin() as connection:
            connection.execute(
                text("DELETE FROM documents WHERE doc_id IN (:first, :second)"),
                {"first": first.doc_id, "second": second.doc_id},
            )
