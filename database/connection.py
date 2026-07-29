"""
Conexao SQLite do CRIS OS.

Banco local em data/cris_os.db (mesmo diretorio do banco existente).
Cria o diretorio data/ se necessario.
"""

import os
import sqlite3
import threading
from pathlib import Path

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

RAIZ = Path(__file__).resolve().parent.parent
DB_DIR = RAIZ / "data"
DB_PATH = DB_DIR / "cris_os.db"


def get_connection() -> sqlite3.Connection:
    """Retorna conexao unica (singleton thread-safe)."""
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                DB_DIR.mkdir(parents=True, exist_ok=True)
                _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
                _conn.row_factory = sqlite3.Row
                _conn.execute("PRAGMA journal_mode=WAL")
                _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


def close_connection() -> None:
    """Fecha a conexao com o banco."""
    global _conn
    with _lock:
        if _conn:
            _conn.close()
            _conn = None
