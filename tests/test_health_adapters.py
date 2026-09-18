from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import httpx

from scifact_rag.adapters.health import HttpHealthProbe, PostgresHealthProbe


class RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: Any) -> None:
        self.statements.append(str(statement))


class RecordingEngine:
    def __init__(self) -> None:
        self.connection = RecordingConnection()

    @contextmanager
    def connect(self):
        yield self.connection


def test_postgres_health_probe_executes_only_select_one() -> None:
    engine = RecordingEngine()

    assert PostgresHealthProbe(engine).available() is True
    assert engine.connection.statements == ["SELECT 1"]


class Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class RecordingClient:
    def __init__(self, response: Response | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, *, timeout: float) -> Response:
        self.calls.append((url, timeout))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_http_health_probe_uses_fixed_timeout_and_does_not_read_body() -> None:
    client = RecordingClient(Response(204))

    assert HttpHealthProbe("http://health/health", client=client).available() is True
    assert client.calls == [("http://health/health", 0.75)]


def test_http_health_probe_fails_closed_for_non_success_and_transport_errors() -> None:
    assert (
        HttpHealthProbe("http://health/health", client=RecordingClient(Response(503))).available()
        is False
    )
    assert (
        HttpHealthProbe(
            "http://health/health",
            client=RecordingClient(httpx.ConnectError("secret")),
        ).available()
        is False
    )
