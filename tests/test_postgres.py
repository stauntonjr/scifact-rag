from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast

from pytest import MonkeyPatch
from sqlalchemy.sql.dml import Insert

from scifact_rag.adapters import postgres
from scifact_rag.adapters.postgres import PostgresEvidenceStore
from scifact_rag.domain import EvidenceChunk, EvidenceDocument


class _RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    def execute(self, statement: Any, *_args: object, **_kwargs: object) -> None:
        self.statements.append(statement)


class _RecordingEngine:
    def __init__(self) -> None:
        self.connection = _RecordingConnection()
        self.begin_calls = 0

    @contextmanager
    def begin(self) -> Iterator[_RecordingConnection]:
        self.begin_calls += 1
        yield self.connection


def test_upsert_partitions_representation_inserts_inside_one_transaction(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(postgres, "_MAX_REPRESENTATION_ROWS_PER_INSERT", 2, raising=False)
    engine = _RecordingEngine()
    store = PostgresEvidenceStore("postgresql+psycopg://unused")
    store._engine = cast(Any, engine)
    document = EvidenceDocument("doc", "title", "abstract")
    chunks = [
        EvidenceChunk("doc", ordinal, f"chunk {ordinal}", "raw", embedding_required=False)
        for ordinal in range(5)
    ]

    store.upsert([document], chunks, [None] * len(chunks))

    representation_inserts = [
        statement
        for statement in engine.connection.statements
        if isinstance(statement, Insert) and statement.table.name == "document_representations"
    ]
    assert engine.begin_calls == 1
    assert [len(statement.compile().params) for statement in representation_inserts] == [
        10,
        10,
        5,
    ]
