"""
SQLiteMemory — backend das 4 camadas de memória, num único adaptador coeso.

  L1 conversation  -> conversations
  L1 temporary     -> temporary
  L2 project       -> project_memory   (uma "gaveta" por projeto)
  L3 permanent     -> permanent_memory
  L4 knowledge base-> kb_documents (+ índice FTS5 'kb_fts', com fallback p/ LIKE)

Implementa as portas pequenas e segregadas de core.contracts.memory (ISP). A
busca textual usa FTS5 quando disponível; se o SQLite local não tiver FTS5,
cai para LIKE automaticamente — sem quebrar nada.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

from core.models import KnowledgeItem, Passage
from storage._base import SQLiteStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session);

CREATE TABLE IF NOT EXISTS temporary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL, content TEXT NOT NULL, day TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tmp ON temporary(session, day);

CREATE TABLE IF NOT EXISTS project_memory (
    id TEXT PRIMARY KEY, project TEXT NOT NULL, type TEXT NOT NULL,
    title TEXT NOT NULL, content TEXT NOT NULL, tags TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_proj ON project_memory(project);

CREATE TABLE IF NOT EXISTS permanent_memory (
    id TEXT PRIMARY KEY, type TEXT NOT NULL,
    title TEXT NOT NULL, content TEXT NOT NULL, tags TEXT NOT NULL, created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kb_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL, text TEXT NOT NULL, tags TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteMemory(SQLiteStore):
    """Backend das 4 camadas de memória (cumpre as portas de core.contracts.memory)."""

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._fts = self._try_create_fts()

    def _try_create_fts(self) -> bool:
        """Cria o índice FTS5 da Base de Conhecimento. Retorna False se indisponível."""
        try:
            self._conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(source, text);"
            )
            return True
        except sqlite3.OperationalError:
            return False  # SQLite sem FTS5 -> usaremos LIKE

    # ==================================================================
    # L1 — Conversa
    # ==================================================================
    def add_message(self, session: str, role: str, content: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO conversations(session, role, content, ts) VALUES (?,?,?,?)",
                (session, role, content, _now()),
            )
            self._conn.commit()

    def recent_messages(self, session: str, limit: int) -> list[dict]:
        with self._lock:
            linhas = self._conn.execute(
                "SELECT role, content FROM conversations WHERE session=? "
                "ORDER BY id DESC LIMIT ?",
                (session, max(0, limit)),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(linhas)]

    # ==================================================================
    # L1 — Temporária (itens do dia)
    # ==================================================================
    def add_item(self, session: str, content: str, day: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO temporary(session, content, day) VALUES (?,?,?)",
                (session, content, day),
            )
            self._conn.commit()

    def list_items(self, session: str, day: str) -> list[str]:
        with self._lock:
            linhas = self._conn.execute(
                "SELECT content FROM temporary WHERE session=? AND day=? ORDER BY id",
                (session, day),
            ).fetchall()
        return [r["content"] for r in linhas]

    def clear_before(self, day: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM temporary WHERE day < ?", (day,))
            self._conn.commit()

    # ==================================================================
    # L2 — Memória dos Projetos
    # ==================================================================
    def remember_project(self, project: str, item: KnowledgeItem) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO project_memory"
                "(id, project, type, title, content, tags, created_at) VALUES (?,?,?,?,?,?,?)",
                (item.id, project, item.type, item.title, item.content,
                 json.dumps(item.tags, ensure_ascii=False), item.created_at),
            )
            self._conn.commit()

    def recall_project(self, project: str) -> list[KnowledgeItem]:
        with self._lock:
            linhas = self._conn.execute(
                "SELECT * FROM project_memory WHERE project=? ORDER BY created_at", (project,)
            ).fetchall()
        return [self._linha_item(r) for r in linhas]

    def projects(self) -> list[str]:
        with self._lock:
            linhas = self._conn.execute(
                "SELECT DISTINCT project FROM project_memory ORDER BY project"
            ).fetchall()
        return [r["project"] for r in linhas]

    # ==================================================================
    # L3 — Memória Permanente
    # ==================================================================
    def remember_permanent(self, item: KnowledgeItem) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO permanent_memory"
                "(id, type, title, content, tags, created_at) VALUES (?,?,?,?,?,?)",
                (item.id, item.type, item.title, item.content,
                 json.dumps(item.tags, ensure_ascii=False), item.created_at),
            )
            self._conn.commit()

    def recall_permanent(self, type: str | None = None) -> list[KnowledgeItem]:
        with self._lock:
            if type:
                linhas = self._conn.execute(
                    "SELECT * FROM permanent_memory WHERE type=? ORDER BY created_at", (type,)
                ).fetchall()
            else:
                linhas = self._conn.execute(
                    "SELECT * FROM permanent_memory ORDER BY type, created_at"
                ).fetchall()
        return [self._linha_item(r) for r in linhas]

    def count_permanent(self) -> int:
        with self._lock:
            (n,) = self._conn.execute("SELECT COUNT(*) FROM permanent_memory").fetchone()
        return int(n)

    # ==================================================================
    # L4 — Base de Conhecimento (FTS5 ou LIKE)
    # ==================================================================
    def ingest(self, source: str, text: str, tags: list[str] | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO kb_documents(source, text, tags, created_at) VALUES (?,?,?,?)",
                (source, text, json.dumps(tags or [], ensure_ascii=False), _now()),
            )
            if self._fts:
                self._conn.execute(
                    "INSERT INTO kb_fts(source, text) VALUES (?,?)", (source, text)
                )
            self._conn.commit()

    def search(self, query: str, limit: int = 4) -> list[Passage]:
        termos = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
        if not termos:
            return []

        with self._lock:
            if self._fts:
                match = " OR ".join(f'"{t}"' for t in termos)
                linhas = self._conn.execute(
                    "SELECT source, text, rank FROM kb_fts WHERE kb_fts MATCH ? "
                    "ORDER BY rank LIMIT ?",
                    (match, limit),
                ).fetchall()
                return [Passage(source=r["source"], text=r["text"], score=-float(r["rank"]))
                        for r in linhas]
            # Fallback sem FTS5: LIKE em qualquer termo.
            where = " OR ".join("text LIKE ?" for _ in termos)
            params = [f"%{t}%" for t in termos] + [limit]
            linhas = self._conn.execute(
                f"SELECT source, text FROM kb_documents WHERE {where} LIMIT ?", params
            ).fetchall()
            return [Passage(source=r["source"], text=r["text"]) for r in linhas]

    def count_kb(self) -> int:
        with self._lock:
            (n,) = self._conn.execute("SELECT COUNT(*) FROM kb_documents").fetchone()
        return int(n)

    # ==================================================================
    @staticmethod
    def _linha_item(r: sqlite3.Row) -> KnowledgeItem:
        return KnowledgeItem(
            id=r["id"], type=r["type"], title=r["title"], content=r["content"],
            tags=json.loads(r["tags"]) if r["tags"] else [], created_at=r["created_at"],
        )
