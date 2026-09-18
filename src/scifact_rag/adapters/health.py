from __future__ import annotations

from typing import Any, Protocol

import httpx
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


class SqlConnection(Protocol):
    def execute(self, statement: Any) -> Any: ...


class SqlEngine(Protocol):
    def connect(self) -> Any: ...


class PostgresHealthProbe:
    def __init__(self, engine: SqlEngine) -> None:
        self._engine = engine

    def available(self) -> bool:
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except (OSError, SQLAlchemyError):
            return False
        return True


class HttpHealthProbe:
    def __init__(
        self,
        url: str,
        *,
        client: Any | None = None,
        timeout: float = 0.75,
    ) -> None:
        self._url = url
        self._client = client
        self._timeout = timeout

    def available(self) -> bool:
        try:
            if self._client is not None:
                response = self._client.get(self._url, timeout=self._timeout)
            else:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.get(self._url)
            return 200 <= response.status_code < 300
        except (OSError, TimeoutError, httpx.HTTPError):
            return False
