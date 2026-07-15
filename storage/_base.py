"""
SQLiteStore — base comum dos backends SQLite do CRIS OS.

Centraliza o boilerplate que estava duplicado em cada store: caminho do arquivo,
criação da pasta, lock de concorrência, conexão (`check_same_thread=False`),
`row_factory`, PRAGMA WAL e o ciclo de vida (`close` / context manager). Cada
subclasse só define o seu schema em `_init_schema()`.

Comportamento idêntico ao que cada store fazia no próprio `__init__` (mesma ordem:
connect -> row_factory -> WAL -> [lock] schema + commit).
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class SQLiteStore:
    """Conexão SQLite com WAL + lock; subclasses implementam `_init_schema`."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        with self._lock:
            self._init_schema()
            self._conn.commit()

    def _init_schema(self) -> None:
        """Cria o schema da subclasse (chamado dentro do lock, antes do commit)."""
        raise NotImplementedError

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "SQLiteStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
