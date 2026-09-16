from __future__ import annotations

from collections.abc import Sequence

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    Computed,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    and_,
    create_engine,
    delete,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, insert

from ..domain import CandidateHit, CandidateScore, EvidenceChunk, EvidenceDocument, SearchHit

_DIMENSIONS = 384
_BM25_TOKENIZER = "scifact_bert"
_SEARCH_VECTOR_EXPRESSION = """
setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
setweight(to_tsvector('english', coalesce(text, '')), 'B')
""".strip()
_METADATA = MetaData()
_DOCUMENTS = Table(
    "documents",
    _METADATA,
    Column("doc_id", String, primary_key=True),
    Column("title", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column("embedding", Vector(_DIMENSIONS), nullable=True),
    Column(
        "search_vector",
        TSVECTOR,
        Computed(_SEARCH_VECTOR_EXPRESSION, persisted=True),
        nullable=False,
    ),
)
Index("documents_search_vector_idx", _DOCUMENTS.c.search_vector, postgresql_using="gin")
_REPRESENTATIONS = Table(
    "document_representations",
    _METADATA,
    Column(
        "doc_id",
        String,
        ForeignKey("documents.doc_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("representation", String, primary_key=True),
    Column("ordinal", Integer, primary_key=True),
    Column("text", Text, nullable=False),
    Column("embedding", Vector(_DIMENSIONS), nullable=True),
)
_MAX_BIND_PARAMETERS = 65_535
_MAX_REPRESENTATION_ROWS_PER_INSERT = _MAX_BIND_PARAMETERS // len(_REPRESENTATIONS.columns)


class PostgresEvidenceStore:
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url)

    def initialize(self) -> None:
        with self._engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_tokenizer"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vchord_bm25"))
            _METADATA.create_all(connection)
            connection.execute(text("ALTER TABLE documents ALTER COLUMN embedding DROP NOT NULL"))
            connection.execute(
                text("ALTER TABLE document_representations ALTER COLUMN embedding DROP NOT NULL")
            )
            connection.execute(
                text(
                    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS search_vector tsvector "
                    f"GENERATED ALWAYS AS ({_SEARCH_VECTOR_EXPRESSION}) STORED"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS documents_search_vector_idx "
                    "ON documents USING gin(search_vector)"
                )
            )
            connection.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1
                            FROM tokenizer_catalog.tokenizer
                            WHERE name = 'scifact_bert'
                        ) THEN
                            PERFORM tokenizer_catalog.create_tokenizer(
                                'scifact_bert',
                                'model = "bert_base_uncased"'
                            );
                        END IF;
                    END
                    $$
                    """
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS "
                    "bm25_embedding bm25_catalog.bm25vector"
                )
            )
            connection.execute(
                text(
                    """
                    UPDATE documents
                    SET bm25_embedding = tokenizer_catalog.tokenize(
                        concat_ws(E'\n', title, text), :tokenizer
                    )::bm25_catalog.bm25vector
                    WHERE bm25_embedding IS NULL
                    """
                ),
                {"tokenizer": _BM25_TOKENIZER},
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS documents_bm25_idx "
                    "ON documents USING bm25 "
                    "(bm25_embedding bm25_catalog.bm25_ops)"
                )
            )

    def upsert(
        self,
        documents: Sequence[EvidenceDocument],
        chunks: Sequence[EvidenceChunk],
        embeddings: Sequence[Sequence[float] | None],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunk and embedding counts differ")
        document_ids = {document.doc_id for document in documents}
        if any(chunk.doc_id not in document_ids for chunk in chunks):
            raise ValueError("chunk references a document outside the batch")
        first_embeddings: dict[str, Sequence[float]] = {}
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            if embedding is not None:
                first_embeddings.setdefault(chunk.doc_id, embedding)
        rows = [
            {
                "doc_id": document.doc_id,
                "title": document.title,
                "text": document.text,
                "embedding": (
                    list(first_embeddings[document.doc_id])
                    if document.doc_id in first_embeddings
                    else None
                ),
            }
            for document in documents
        ]
        statement = insert(_DOCUMENTS).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=[_DOCUMENTS.c.doc_id],
            set_={
                "title": statement.excluded.title,
                "text": statement.excluded.text,
                "embedding": func.coalesce(
                    statement.excluded.embedding,
                    _DOCUMENTS.c.embedding,
                ),
            },
            where=or_(
                _DOCUMENTS.c.title.is_distinct_from(statement.excluded.title),
                _DOCUMENTS.c.text.is_distinct_from(statement.excluded.text),
                and_(
                    _DOCUMENTS.c.embedding.is_(None),
                    statement.excluded.embedding.is_not(None),
                ),
            ),
        )
        with self._engine.begin() as connection:
            connection.execute(statement)
            connection.execute(
                text(
                    """
                    WITH tokenized AS MATERIALIZED (
                        SELECT
                            doc_id,
                            tokenizer_catalog.tokenize(
                                concat_ws(E'\n', title, text), :tokenizer
                            )::bm25_catalog.bm25vector AS value
                        FROM documents
                        WHERE doc_id = ANY(CAST(:document_ids AS text[]))
                    )
                    UPDATE documents AS target
                    SET bm25_embedding = tokenized.value
                    FROM tokenized
                    WHERE target.doc_id = tokenized.doc_id
                      AND target.bm25_embedding IS DISTINCT FROM tokenized.value
                    """
                ),
                {
                    "tokenizer": _BM25_TOKENIZER,
                    "document_ids": sorted(document_ids),
                },
            )
            if not chunks:
                return
            represented = {chunk.representation for chunk in chunks}
            connection.execute(
                delete(_REPRESENTATIONS).where(
                    _REPRESENTATIONS.c.doc_id.in_(document_ids),
                    _REPRESENTATIONS.c.representation.in_(represented),
                )
            )
            representation_rows = [
                {
                    "doc_id": chunk.doc_id,
                    "representation": chunk.representation,
                    "ordinal": chunk.ordinal,
                    "text": chunk.text,
                    "embedding": list(embedding) if embedding is not None else None,
                }
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ]
            for start in range(0, len(representation_rows), _MAX_REPRESENTATION_ROWS_PER_INSERT):
                connection.execute(
                    _REPRESENTATIONS.insert().values(
                        representation_rows[
                            start : start + _MAX_REPRESENTATION_ROWS_PER_INSERT
                        ]
                    )
                )

    def search_vector(
        self,
        embedding: Sequence[float],
        limit: int,
        representations: Sequence[str],
    ) -> list[SearchHit]:
        if not representations:
            raise ValueError("at least one representation is required")
        chunk_distance = _REPRESENTATIONS.c.embedding.cosine_distance(list(embedding))
        nearest_chunk = (
            select(
                _REPRESENTATIONS.c.doc_id,
                func.min(chunk_distance).label("distance"),
            )
            .where(_REPRESENTATIONS.c.representation.in_(representations))
            .where(_REPRESENTATIONS.c.embedding.is_not(None))
            .group_by(_REPRESENTATIONS.c.doc_id)
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

    def retrieve_vector_candidates(
        self,
        embedding: Sequence[float],
        limit: int,
        representations: Sequence[str],
    ) -> list[CandidateHit]:
        if not representations:
            raise ValueError("at least one representation is required")
        chunk_distance = _REPRESENTATIONS.c.embedding.cosine_distance(list(embedding))
        ranked_chunks = (
            select(
                _REPRESENTATIONS.c.doc_id,
                _REPRESENTATIONS.c.representation,
                _REPRESENTATIONS.c.ordinal,
                _REPRESENTATIONS.c.text.label("matched_text"),
                chunk_distance.label("distance"),
                func.row_number()
                .over(
                    partition_by=_REPRESENTATIONS.c.doc_id,
                    order_by=(
                        chunk_distance,
                        _REPRESENTATIONS.c.representation,
                        _REPRESENTATIONS.c.ordinal,
                    ),
                )
                .label("position"),
            )
            .where(_REPRESENTATIONS.c.representation.in_(representations))
            .where(_REPRESENTATIONS.c.embedding.is_not(None))
            .subquery()
        )
        statement = (
            select(
                _DOCUMENTS.c.doc_id,
                _DOCUMENTS.c.title,
                _DOCUMENTS.c.text,
                ranked_chunks.c.representation,
                ranked_chunks.c.ordinal,
                ranked_chunks.c.matched_text,
                ranked_chunks.c.distance,
            )
            .join(ranked_chunks, ranked_chunks.c.doc_id == _DOCUMENTS.c.doc_id)
            .where(ranked_chunks.c.position == 1)
            .order_by(ranked_chunks.c.distance, _DOCUMENTS.c.doc_id)
            .limit(limit)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings()
            return [
                CandidateHit(
                    document=EvidenceDocument(
                        doc_id=str(row["doc_id"]),
                        title=str(row["title"]),
                        text=str(row["text"]),
                    ),
                    score=1.0 - float(row["distance"]),
                    representation=str(row["representation"]),
                    chunk_ordinal=int(row["ordinal"]),
                    matched_text=str(row["matched_text"]),
                )
                for row in rows
            ]

    def score_vector_candidates(
        self,
        embedding: Sequence[float],
        document_ids: Sequence[str],
        representations: Sequence[str],
    ) -> list[CandidateScore]:
        if not representations:
            raise ValueError("at least one representation is required")
        if not document_ids:
            return []
        chunk_distance = _REPRESENTATIONS.c.embedding.cosine_distance(list(embedding))
        ranked_chunks = (
            select(
                _REPRESENTATIONS.c.doc_id,
                _REPRESENTATIONS.c.representation,
                _REPRESENTATIONS.c.ordinal,
                _REPRESENTATIONS.c.text.label("matched_text"),
                chunk_distance.label("distance"),
                func.row_number()
                .over(
                    partition_by=_REPRESENTATIONS.c.doc_id,
                    order_by=(
                        chunk_distance,
                        _REPRESENTATIONS.c.representation,
                        _REPRESENTATIONS.c.ordinal,
                    ),
                )
                .label("position"),
            )
            .where(
                _REPRESENTATIONS.c.doc_id.in_(document_ids),
                _REPRESENTATIONS.c.representation.in_(representations),
                _REPRESENTATIONS.c.embedding.is_not(None),
            )
            .subquery()
        )
        statement = (
            select(
                ranked_chunks.c.doc_id,
                ranked_chunks.c.representation,
                ranked_chunks.c.ordinal,
                ranked_chunks.c.matched_text,
                ranked_chunks.c.distance,
            )
            .where(ranked_chunks.c.position == 1)
            .order_by(ranked_chunks.c.doc_id)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings()
            return [
                CandidateScore(
                    doc_id=str(row["doc_id"]),
                    score=1.0 - float(row["distance"]),
                    representation=str(row["representation"]),
                    chunk_ordinal=int(row["ordinal"]),
                    matched_text=str(row["matched_text"]),
                )
                for row in rows
            ]

    def load_chunks(
        self,
        document_ids: Sequence[str],
        representations: Sequence[str],
    ) -> list[EvidenceChunk]:
        if not representations:
            raise ValueError("at least one representation is required")
        if not document_ids:
            return []
        statement = (
            select(
                _REPRESENTATIONS.c.doc_id,
                _REPRESENTATIONS.c.representation,
                _REPRESENTATIONS.c.ordinal,
                _REPRESENTATIONS.c.text,
                _REPRESENTATIONS.c.embedding,
            )
            .where(
                _REPRESENTATIONS.c.doc_id.in_(document_ids),
                _REPRESENTATIONS.c.representation.in_(representations),
            )
            .order_by(
                _REPRESENTATIONS.c.doc_id,
                _REPRESENTATIONS.c.representation,
                _REPRESENTATIONS.c.ordinal,
            )
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings()
            return [
                EvidenceChunk(
                    doc_id=str(row["doc_id"]),
                    ordinal=int(row["ordinal"]),
                    text=str(row["text"]),
                    representation=str(row["representation"]),
                    embedding_required=row["embedding"] is not None,
                )
                for row in rows
            ]

    def search_keyword(self, query: str, limit: int) -> list[SearchHit]:
        statement = text(
            """
            WITH lexemes AS (
                SELECT unnest(
                    tsvector_to_array(to_tsvector('english', :query))
                ) AS lexeme
            ), parsed AS (
                SELECT to_tsquery(
                    'english',
                    string_agg(quote_literal(lexeme), ' | ')
                ) AS value
                FROM lexemes
            )
            SELECT
                documents.doc_id,
                documents.title,
                documents.text,
                ts_rank_cd(documents.search_vector, parsed.value, 1) AS score
            FROM documents
            CROSS JOIN parsed
            WHERE parsed.value IS NOT NULL
              AND documents.search_vector @@ parsed.value
            ORDER BY score DESC, documents.doc_id
            LIMIT :limit
            """
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement, {"query": query, "limit": limit}).mappings()
            return [
                SearchHit(
                    doc_id=str(row["doc_id"]),
                    title=str(row["title"]),
                    text=str(row["text"]),
                    score=float(row["score"]),
                )
                for row in rows
            ]

    def search_bm25(self, query: str, limit: int) -> list[SearchHit]:
        return [
            SearchHit(
                hit.document.doc_id,
                hit.document.title,
                hit.document.text,
                hit.score,
            )
            for hit in self.retrieve_bm25_candidates(query, limit)
        ]

    def retrieve_bm25_candidates(self, query: str, limit: int) -> list[CandidateHit]:
        statement = text(
            """
            WITH query_vector AS (
                SELECT bm25_catalog.to_bm25query(
                    'documents_bm25_idx'::regclass,
                    tokenizer_catalog.tokenize(
                        :query, :tokenizer
                    )::bm25_catalog.bm25vector
                ) AS value
            ), ranked AS (
                SELECT
                    documents.doc_id,
                    documents.title,
                    documents.text,
                    documents.bm25_embedding <&> query_vector.value AS rank
                FROM documents
                CROSS JOIN query_vector
                WHERE documents.bm25_embedding IS NOT NULL
                ORDER BY rank, documents.doc_id
                LIMIT :limit
            )
            SELECT doc_id, title, text, -rank AS score
            FROM ranked
            WHERE rank < 0
            ORDER BY rank, doc_id
            """
        )
        with self._engine.connect() as connection:
            rows = connection.execute(
                statement,
                {
                    "query": query,
                    "tokenizer": _BM25_TOKENIZER,
                    "limit": limit,
                },
            ).mappings()
            return [
                CandidateHit(
                    document=EvidenceDocument(
                        doc_id=str(row["doc_id"]),
                        title=str(row["title"]),
                        text=str(row["text"]),
                    ),
                    score=float(row["score"]),
                    representation="title-abstract",
                )
                for row in rows
            ]

    def score_bm25_candidates(
        self,
        query: str,
        document_ids: Sequence[str],
    ) -> list[CandidateScore]:
        if not document_ids:
            return []
        statement = text(
            """
            WITH query_vector AS (
                SELECT bm25_catalog.to_bm25query(
                    'documents_bm25_idx'::regclass,
                    tokenizer_catalog.tokenize(
                        :query, :tokenizer
                    )::bm25_catalog.bm25vector
                ) AS value
            )
            SELECT
                documents.doc_id,
                -(documents.bm25_embedding <&> query_vector.value) AS score
            FROM documents
            CROSS JOIN query_vector
            WHERE documents.bm25_embedding IS NOT NULL
              AND documents.doc_id = ANY(CAST(:document_ids AS text[]))
            ORDER BY score DESC, documents.doc_id
            """
        )
        with self._engine.connect() as connection:
            rows = connection.execute(
                statement,
                {
                    "query": query,
                    "tokenizer": _BM25_TOKENIZER,
                    "document_ids": list(document_ids),
                },
            ).mappings()
            return [
                CandidateScore(
                    doc_id=str(row["doc_id"]),
                    score=float(row["score"]),
                    representation="title-abstract",
                )
                for row in rows
            ]
