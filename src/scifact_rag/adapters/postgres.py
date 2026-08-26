from __future__ import annotations

from collections.abc import Sequence

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import insert

from ..domain import EvidenceChunk, EvidenceDocument, SearchHit

_DIMENSIONS = 384
_METADATA = MetaData()
_DOCUMENTS = Table(
    "documents",
    _METADATA,
    Column("doc_id", String, primary_key=True),
    Column("title", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column("embedding", Vector(_DIMENSIONS), nullable=False),
)
_CHUNKS = Table(
    "document_chunks",
    _METADATA,
    Column(
        "doc_id",
        String,
        ForeignKey("documents.doc_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer, primary_key=True),
    Column("text", Text, nullable=False),
    Column("embedding", Vector(_DIMENSIONS), nullable=False),
)


class PostgresEvidenceStore:
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url)

    def initialize(self) -> None:
        with self._engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            _METADATA.create_all(connection)

    def upsert(
        self,
        documents: Sequence[EvidenceDocument],
        chunks: Sequence[EvidenceChunk],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunk and embedding counts differ")
        document_ids = {document.doc_id for document in documents}
        if any(chunk.doc_id not in document_ids for chunk in chunks):
            raise ValueError("chunk references a document outside the batch")
        first_embeddings: dict[str, Sequence[float]] = {}
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            first_embeddings.setdefault(chunk.doc_id, embedding)
        if set(first_embeddings) != document_ids:
            raise ValueError("every document must have at least one chunk")
        rows = [
            {
                "doc_id": document.doc_id,
                "title": document.title,
                "text": document.text,
                "embedding": list(first_embeddings[document.doc_id]),
            }
            for document in documents
        ]
        statement = insert(_DOCUMENTS).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=[_DOCUMENTS.c.doc_id],
            set_={
                "title": statement.excluded.title,
                "text": statement.excluded.text,
                "embedding": statement.excluded.embedding,
            },
        )
        with self._engine.begin() as connection:
            connection.execute(statement)
            connection.execute(delete(_CHUNKS).where(_CHUNKS.c.doc_id.in_(document_ids)))
            connection.execute(
                _CHUNKS.insert().values(
                    [
                        {
                            "doc_id": chunk.doc_id,
                            "ordinal": chunk.ordinal,
                            "text": chunk.text,
                            "embedding": list(embedding),
                        }
                        for chunk, embedding in zip(chunks, embeddings, strict=True)
                    ]
                )
            )

    def search(self, embedding: Sequence[float], limit: int) -> list[SearchHit]:
        chunk_distance = _CHUNKS.c.embedding.cosine_distance(list(embedding))
        nearest_chunk = (
            select(
                _CHUNKS.c.doc_id,
                func.min(chunk_distance).label("distance"),
            )
            .group_by(_CHUNKS.c.doc_id)
            .subquery()
        )
        statement = (
            select(
                _DOCUMENTS.c.doc_id,
                _DOCUMENTS.c.title,
                _DOCUMENTS.c.text,
                nearest_chunk.c.distance,
            )
            .join(nearest_chunk, nearest_chunk.c.doc_id == _DOCUMENTS.c.doc_id)
            .order_by(nearest_chunk.c.distance, _DOCUMENTS.c.doc_id)
            .limit(limit)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings()
            return [
                SearchHit(
                    doc_id=str(row["doc_id"]),
                    title=str(row["title"]),
                    text=str(row["text"]),
                    score=1.0 - float(row["distance"]),
                )
                for row in rows
            ]
