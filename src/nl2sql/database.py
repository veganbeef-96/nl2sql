"""Read-only access layer for the SQLite database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


class DatabaseError(Exception):
    """Raised for any database access failure (missing file, query error, write rejection)."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]

    @property
    def is_empty(self) -> bool:
        return len(self.rows) == 0


class Database:
    def __init__(self, path: str):
        self._path = Path(path)
        if not self._path.is_file():
            raise DatabaseError(f"Database file not found: {path}")

    def _connect(self) -> sqlite3.Connection:
        uri = f"file:{self._path}?mode=ro"
        try:
            return sqlite3.connect(uri, uri=True)
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to open database: {e}") from e

    def execute(self, sql: str, params: tuple | dict | None = None) -> QueryResult:
        conn = self._connect()
        try:
            cursor = conn.execute(sql, params or ())
            columns = [d[0] for d in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return QueryResult(columns=columns, rows=rows)
        except sqlite3.Error as e:
            raise DatabaseError(f"Query failed: {e}") from e
        finally:
            conn.close()

    def schema_text(self) -> str:
        result = self.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
        return "\n\n".join(row[0] for row in result.rows if row[0])
