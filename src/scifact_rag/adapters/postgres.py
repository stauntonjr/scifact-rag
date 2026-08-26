from __future__ import annotations

from collections.abc import Sequence

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, MetaData, String, Table, Text, create_engine, select, text
from sqlalchemy.dialects.postgresql import insert

from ..domain import EvidenceDocument, SearchHit

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


class PostgresEvidenceStore:
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url)

    def initialize(self) -> None:
        with self._engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            _METADATA.create_all(connection)

    def upsert(
        self, documents: Sequence[EvidenceDocument], embeddings: Sequence[Sequence[float]]
    ) -> None:
        if len(documents) != len(embeddings):
            raise ValueError("document and embedding counts differ")
        rows = [
            {
                "doc_id": document.doc_id,
                "title": document.title,
                "text": document.text,
                "embedding": list(embedding),
            }
            for document, embedding in zip(documents, embeddings, strict=True)
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

    def search(self, embedding: Sequence[float], limit: int) -> list[SearchHit]:
        distance = _DOCUMENTS.c.embedding.cosine_distance(list(embedding))
        statement = (
            select(
                _DOCUMENTS.c.doc_id,
                _DOCUMENTS.c.title,
                _DOCUMENTS.c.text,
                distance.label("distance"),
            )
            .order_by(distance)
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
