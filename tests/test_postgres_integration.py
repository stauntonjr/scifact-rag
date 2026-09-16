from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from scifact_rag.adapters import postgres
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
    keyword_marker = f"marker{suffix}"
    first = EvidenceDocument(f"first-{suffix}", "first", keyword_marker)
    second = EvidenceDocument(f"second-{suffix}", "second", "second document")
    seed = uuid.UUID(suffix).bytes
    first_vector = [float(seed[index % len(seed)] - 127.5) for index in range(384)]
    second_vector = [-value for value in first_vector]

    chunks = [
        EvidenceChunk(first.doc_id, 0, "irrelevant first window", "strict"),
        EvidenceChunk(first.doc_id, 1, "relevant second window", "broad"),
        EvidenceChunk(
            first.doc_id,
            0,
            "raw scorer-only view",
            "scorer-only",
            embedding_required=False,
        ),
        EvidenceChunk(second.doc_id, 0, "second document", "strict"),
    ]
    try:
        store.upsert(
            [first, second],
            chunks,
            [second_vector, first_vector, None, first_vector],
        )
        strict_hits = store.search_vector(first_vector, 1, ("strict",))
        fused_hits = store.search_vector(first_vector, 1, ("strict", "broad"))
        keyword_hits = store.search_keyword(keyword_marker, 2)
        bm25_hits = store.search_bm25(keyword_marker, 10)
        vector_candidates = store.retrieve_vector_candidates(
            first_vector,
            2,
            ("strict", "broad"),
        )
        vector_scores = store.score_vector_candidates(
            first_vector,
            (first.doc_id, second.doc_id),
            ("strict", "broad"),
        )
        bm25_scores = store.score_bm25_candidates(
            keyword_marker,
            (first.doc_id, second.doc_id),
        )
        scorer_views = store.load_chunks((first.doc_id,), ("scorer-only",))
        scorer_only_vector_hits = store.search_vector(first_vector, 2, ("scorer-only",))
        with store._engine.connect() as connection:
            tuple_identity_before = {
                str(row.doc_id): (str(row.ctid), str(row.xmin))
                for row in connection.execute(
                    text(
                        "SELECT doc_id, ctid::text AS ctid, xmin::text AS xmin "
                        "FROM documents WHERE doc_id IN (:first, :second)"
                    ),
                    {"first": first.doc_id, "second": second.doc_id},
                )
            }
            extension_versions = dict(
                list(
                    connection.execute(
                        text(
                            "SELECT extname, extversion FROM pg_extension "
                            "WHERE extname IN ('vector', 'pg_tokenizer', 'vchord_bm25')"
                        )
                    ).tuples()
                )
            )

        store.upsert(
            [first, second],
            [
                EvidenceChunk(first.doc_id, 0, "another first representation", "additional"),
                EvidenceChunk(second.doc_id, 0, "another second representation", "additional"),
            ],
            [first_vector, second_vector],
        )
        with store._engine.connect() as connection:
            tuple_identity_after = {
                str(row.doc_id): (str(row.ctid), str(row.xmin))
                for row in connection.execute(
                    text(
                        "SELECT doc_id, ctid::text AS ctid, xmin::text AS xmin "
                        "FROM documents WHERE doc_id IN (:first, :second)"
                    ),
                    {"first": first.doc_id, "second": second.doc_id},
                )
            }
        bm25_hits_after_representation_ingest = store.search_bm25(keyword_marker, 10)

        assert strict_hits[0].doc_id == second.doc_id
        assert fused_hits[0].doc_id == first.doc_id
        assert fused_hits[0].score == pytest.approx(1.0)
        assert keyword_hits[0].doc_id == first.doc_id
        assert bm25_hits[0].doc_id == first.doc_id
        assert bm25_hits[0].score > 0
        assert vector_candidates[0].document.doc_id == first.doc_id
        assert vector_candidates[0].representation == "broad"
        assert vector_candidates[0].chunk_ordinal == 1
        assert vector_candidates[0].matched_text == "relevant second window"
        assert {score.doc_id for score in vector_scores} == {first.doc_id, second.doc_id}
        first_score = next(score for score in vector_scores if score.doc_id == first.doc_id)
        assert first_score.representation == "broad"
        assert first_score.chunk_ordinal == 1
        assert first_score.matched_text == "relevant second window"
        assert {score.doc_id for score in bm25_scores} == {first.doc_id, second.doc_id}
        assert next(score for score in bm25_scores if score.doc_id == first.doc_id).score > 0
        assert scorer_views == [
            EvidenceChunk(
                first.doc_id,
                0,
                "raw scorer-only view",
                "scorer-only",
                embedding_required=False,
            )
        ]
        assert scorer_only_vector_hits == []
        assert tuple_identity_after == tuple_identity_before
        assert bm25_hits_after_representation_ingest[0].doc_id == first.doc_id
        assert extension_versions == {
            "pg_tokenizer": "0.1.1",
            "vchord_bm25": "0.3.0",
            "vector": "0.8.6",
        }
    finally:
        with store._engine.begin() as connection:
            connection.execute(
                text("DELETE FROM documents WHERE doc_id IN (:first, :second)"),
                {"first": first.doc_id, "second": second.doc_id},
            )


@pytest.mark.integration
def test_representation_partition_failure_rolls_back_the_entire_upsert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is not configured")
    store = PostgresEvidenceStore(database_url)
    store.initialize()
    monkeypatch.setattr(postgres, "_MAX_REPRESENTATION_ROWS_PER_INSERT", 2, raising=False)
    doc_id = f"rollback-{uuid.uuid4().hex}"
    document = EvidenceDocument(doc_id, "title", "abstract")
    chunks = [
        EvidenceChunk(doc_id, 0, "first", "raw", embedding_required=False),
        EvidenceChunk(doc_id, 1, "second", "raw", embedding_required=False),
        EvidenceChunk(doc_id, 0, "duplicate", "raw", embedding_required=False),
    ]

    try:
        with pytest.raises(IntegrityError):
            store.upsert([document], chunks, [None, None, None])

        with store._engine.connect() as connection:
            document_count = connection.execute(
                text("SELECT count(*) FROM documents WHERE doc_id = :doc_id"),
                {"doc_id": doc_id},
            ).scalar_one()
            representation_count = connection.execute(
                text("SELECT count(*) FROM document_representations WHERE doc_id = :doc_id"),
                {"doc_id": doc_id},
            ).scalar_one()
        assert document_count == 0
        assert representation_count == 0
    finally:
        with store._engine.begin() as connection:
            connection.execute(
                text("DELETE FROM documents WHERE doc_id = :doc_id"),
                {"doc_id": doc_id},
            )
