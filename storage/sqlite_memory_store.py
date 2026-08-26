"""
SQLiteMemoryStore — backend da tabela `memoria` com metadados ricos.

Suporta:
  - CRUD completo (criar, ler, atualizar, excluir)
  - Busca textual (FTS5 com fallback LIKE)
  - Filtros por: projeto, cliente, tags, tipo, workspace, utilizador
  - Merge de duplicadas
  - Estatisticas de acesso
  - Isolamento entre workspaces/utilizadores
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from core.models import MemoryItem
from storage._base import SQLiteStore

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memoria (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    workspace TEXT NOT NULL DEFAULT 'default',
    client TEXT NOT NULL DEFAULT '',
    importance INTEGER NOT NULL DEFAULT 0,
    origin TEXT NOT NULL DEFAULT 'telegram',
    date TEXT NOT NULL DEFAULT '',
    agent TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL DEFAULT 'note',
    title TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    project TEXT NOT NULL DEFAULT '',
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mem_user ON memoria(user_id, workspace);
CREATE INDEX IF NOT EXISTS idx_mem_project ON memoria(project);
CREATE INDEX IF NOT EXISTS idx_mem_client ON memoria(client);
CREATE INDEX IF NOT EXISTS idx_mem_agent ON memoria(agent);
CREATE INDEX IF NOT EXISTS idx_mem_type ON memoria(type);
CREATE INDEX IF NOT EXISTS idx_mem_importance ON memoria(importance);
CREATE INDEX IF NOT EXISTS idx_mem_origin ON memoria(origin);
"""

_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS memoria_fts USING fts5(
    content=memoria, content_rowid=rowid,
    title, content, project, client, tags
);
CREATE TRIGGER IF NOT EXISTS memoria_ai AFTER INSERT ON memoria BEGIN
    INSERT INTO memoria_fts(rowid, title, content, project, client, tags)
    VALUES (new.rowid, new.title, new.content, new.project, new.client, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS memoria_ad AFTER DELETE ON memoria BEGIN
    INSERT INTO memoria_fts(memoria_fts, rowid, title, content, project, client, tags)
    VALUES ('delete', old.rowid, old.title, old.content, old.project, old.client, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS memoria_au AFTER UPDATE ON memoria BEGIN
    INSERT INTO memoria_fts(memoria_fts, rowid, title, content, project, client, tags)
    VALUES ('delete', old.rowid, old.title, old.content, old.project, old.client, old.tags);
    INSERT INTO memoria_fts(rowid, title, content, project, client, tags)
    VALUES (new.rowid, new.title, new.content, new.project, new.client, new.tags);
END;
"""


class SQLiteMemoryStore(SQLiteStore):
    """Backend SQLite para a tabela memoria com FTS5."""

    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._init_fts()
        logger.info("Tabela 'memoria' criada/verificada.")

    def _init_fts(self) -> None:
        try:
            self._conn.executescript(_FTS_SCHEMA)
            logger.info("FTS5 para 'memoria' ativado.")
        except sqlite3.OperationalError as e:
            logger.warning("FTS5 nao disponivel: %s. Usando LIKE como fallback.", e)

    # ------------------------------------------------------------------
    #  CRUD
    # ------------------------------------------------------------------

    def _row_to_item(self, r: sqlite3.Row) -> MemoryItem:
        return MemoryItem(
            id=r["id"], user_id=r["user_id"], workspace=r["workspace"],
            client=r["client"], importance=r["importance"], origin=r["origin"],
            date=r["date"], agent=r["agent"], type=r["type"], title=r["title"],
            content=r["content"],
            tags=json.loads(r["tags"]) if isinstance(r["tags"], str) else (r["tags"] or []),
            project=r["project"], access_count=r["access_count"],
            last_accessed=r["last_accessed"], created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def _agora(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _novo_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def create(self, item: MemoryItem) -> MemoryItem:
        now = self._agora()
        if not item.id:
            item.id = self._novo_id()
        if not item.created_at:
            item.created_at = now
        if not item.updated_at:
            item.updated_at = now
        if not item.date:
            item.date = now[:10]
        if not item.workspace:
            item.workspace = "default"

        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO memoria
                (id, user_id, workspace, client, importance, origin, date, agent,
                 type, title, content, tags, project,
                 access_count, last_accessed, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,'',?,?)""",
                (item.id, item.user_id, item.workspace, item.client, item.importance,
                 item.origin, item.date, item.agent, item.type, item.title,
                 item.content, json.dumps(item.tags, ensure_ascii=False),
                 item.project, item.created_at, item.updated_at),
            )
            self._conn.commit()
        logger.info("Memoria criada: id=%s user=%s type=%s title='%s'",
                     item.id, item.user_id, item.type, item.title[:60])
        return item

    def get(self, item_id: str, user_id: str) -> MemoryItem | None:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT * FROM memoria WHERE id=? AND user_id=?",
                (item_id, user_id),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        item = self._row_to_item(row)
        self._increment_access(item_id, user_id)
        return item

    def _increment_access(self, item_id: str, user_id: str) -> None:
        now = self._agora()
        with self._lock:
            self._conn.execute(
                "UPDATE memoria SET access_count = access_count + 1, last_accessed=? WHERE id=? AND user_id=?",
                (now, item_id, user_id),
            )
            self._conn.commit()

    def update(self, item_id: str, user_id: str, **fields) -> MemoryItem | None:
        existing = self.get(item_id, user_id)
        if existing is None:
            return None

        allowed = {"client", "importance", "origin", "date", "agent", "type",
                   "title", "content", "tags", "project", "workspace"}
        updates = {}
        for k, v in fields.items():
            if k in allowed:
                updates[k] = v

        if not updates:
            return existing

        now = self._agora()
        updates["updated_at"] = now
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [item_id, user_id]

        with self._lock:
            self._conn.execute(
                f"UPDATE memoria SET {set_clause} WHERE id=? AND user_id=?",
                values,
            )
            self._conn.commit()

        logger.info("Memoria atualizada: id=%s campos=%s", item_id, list(updates.keys()))
        return self.get(item_id, user_id)

    def delete(self, item_id: str, user_id: str) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM memoria WHERE id=? AND user_id=?",
                (item_id, user_id),
            )
            self._conn.commit()
            deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Memoria excluida: id=%s user=%s", item_id, user_id)
        return deleted

    # ------------------------------------------------------------------
    #  Busca
    # ------------------------------------------------------------------

    def search(self, query: str, user_id: str = "", workspace: str = "",
               project: str = "", client: str = "", tag: str = "",
               type_filter: str = "", limit: int = 20) -> list[MemoryItem]:
        conditions = []
        where_params: list[Any] = []

        if user_id:
            conditions.append("user_id=?")
            where_params.append(user_id)
        if workspace:
            conditions.append("workspace=?")
            where_params.append(workspace)
        if project:
            conditions.append("project LIKE ?")
            where_params.append(f"%{project}%")
        if client:
            conditions.append("client LIKE ?")
            where_params.append(f"%{client}%")
        if tag:
            conditions.append("tags LIKE ?")
            where_params.append(f"%{tag}%")
        if type_filter:
            conditions.append("type=?")
            where_params.append(type_filter)

        base_where = " AND ".join(conditions) if conditions else "1=1"

        # Tenta FTS5 primeiro
        if query and self._has_fts():
            clean_query = query.replace('"', "").replace("'", "")
            fts_params = list(where_params) + [clean_query, limit]
            sql = (
                "SELECT m.* FROM memoria m "
                "INNER JOIN memoria_fts fts ON m.rowid = fts.rowid "
                f"WHERE {base_where} AND memoria_fts MATCH ? "
                "ORDER BY m.importance DESC, m.access_count DESC "
                "LIMIT ?"
            )
            with self._lock:
                cursor = self._conn.execute(sql, fts_params)
                rows = cursor.fetchall()
            results = [self._row_to_item(r) for r in rows]
            if results:
                return results

        # Fallback: LIKE
        if query:
            like = f"%{query}%"
            like_params = list(where_params) + [like, like, like, like, limit]
            sql = (
                "SELECT * FROM memoria "
                f"WHERE {base_where} AND ("
                "  content LIKE ? OR title LIKE ? OR project LIKE ? OR client LIKE ?"
                ") "
                "ORDER BY importance DESC, access_count DESC "
                "LIMIT ?"
            )
        else:
            list_params = list(where_params) + [limit]
            sql = (
                "SELECT * FROM memoria "
                f"WHERE {base_where} "
                "ORDER BY importance DESC, updated_at DESC "
                "LIMIT ?"
            )

        with self._lock:
            cursor = self._conn.execute(sql, like_params if query else list_params)
            rows = cursor.fetchall()
        return [self._row_to_item(r) for r in rows]

    def _has_fts(self) -> bool:
        try:
            cursor = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='virtual_table' AND name='memoria_fts'"
            )
            return cursor.fetchone() is not None
        except sqlite3.OperationalError:
            return False

    # ------------------------------------------------------------------
    #  Utilitarios
    # ------------------------------------------------------------------

    def list_by_user(self, user_id: str, workspace: str = "",
                     limit: int = 50) -> list[MemoryItem]:
        if workspace:
            rows = self._conn.execute(
                "SELECT * FROM memoria WHERE user_id=? AND workspace=? ORDER BY updated_at DESC LIMIT ?",
                (user_id, workspace, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM memoria WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def list_by_project(self, project: str, user_id: str = "",
                        limit: int = 50) -> list[MemoryItem]:
        if user_id:
            rows = self._conn.execute(
                "SELECT * FROM memoria WHERE project LIKE ? AND user_id=? ORDER BY importance DESC LIMIT ?",
                (f"%{project}%", user_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM memoria WHERE project LIKE ? ORDER BY importance DESC LIMIT ?",
                (f"%{project}%", limit),
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def list_by_client(self, client: str, user_id: str = "",
                       limit: int = 50) -> list[MemoryItem]:
        if user_id:
            rows = self._conn.execute(
                "SELECT * FROM memoria WHERE client LIKE ? AND user_id=? ORDER BY importance DESC LIMIT ?",
                (f"%{client}%", user_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM memoria WHERE client LIKE ? ORDER BY importance DESC LIMIT ?",
                (f"%{client}%", limit),
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def list_by_tag(self, tag: str, user_id: str = "",
                    limit: int = 50) -> list[MemoryItem]:
        if user_id:
            rows = self._conn.execute(
                "SELECT * FROM memoria WHERE tags LIKE ? AND user_id=? ORDER BY importance DESC LIMIT ?",
                (f"%{tag}%", user_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM memoria WHERE tags LIKE ? ORDER BY importance DESC LIMIT ?",
                (f"%{tag}%", limit),
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def count(self, user_id: str = "", workspace: str = "") -> int:
        if user_id and workspace:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM memoria WHERE user_id=? AND workspace=?",
                (user_id, workspace),
            ).fetchone()
        elif user_id:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM memoria WHERE user_id=?", (user_id,),
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM memoria").fetchone()
        return row[0] if row else 0

    def merge_duplicates(self, user_id: str, field: str = "content") -> int:
        """Merge duplicadas baseado num campo (content, title). Retorna qtd removida."""
        merged = 0
        with self._lock:
            cursor = self._conn.execute(f"""
                SELECT id FROM memoria
                WHERE user_id=? AND id NOT IN (
                    SELECT MIN(id) FROM memoria WHERE user_id=? GROUP BY {field}
                )
            """, (user_id, user_id))
            dups = [r[0] for r in cursor.fetchall()]
            for dup_id in dups:
                self._conn.execute("DELETE FROM memoria WHERE id=?", (dup_id,))
                merged += 1
            if merged:
                self._conn.commit()
        if merged:
            logger.info("Merge: %d duplicadas removidas para user=%s", merged, user_id)
        return merged

    def delete_all_for_user(self, user_id: str) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM memoria WHERE user_id=?", (user_id,),
            )
            self._conn.commit()
            return cursor.rowcount

    def stats(self, user_id: str = "") -> dict:
        """Estatisticas da memoria."""
        with self._lock:
            if user_id:
                total = self._conn.execute(
                    "SELECT COUNT(*) FROM memoria WHERE user_id=?", (user_id,),
                ).fetchone()[0]
                by_type = self._conn.execute(
                    "SELECT type, COUNT(*) FROM memoria WHERE user_id=? GROUP BY type ORDER BY 2 DESC",
                    (user_id,),
                ).fetchall()
                by_importance = self._conn.execute(
                    "SELECT importance, COUNT(*) FROM memoria WHERE user_id=? GROUP BY importance ORDER BY 1",
                    (user_id,),
                ).fetchall()
                by_origin = self._conn.execute(
                    "SELECT origin, COUNT(*) FROM memoria WHERE user_id=? GROUP BY origin ORDER BY 2 DESC",
                    (user_id,),
                ).fetchall()
                total_access = self._conn.execute(
                    "SELECT COALESCE(SUM(access_count), 0) FROM memoria WHERE user_id=?",
                    (user_id,),
                ).fetchone()[0]
            else:
                total = self._conn.execute(
                    "SELECT COUNT(*) FROM memoria",
                ).fetchone()[0]
                by_type = self._conn.execute(
                    "SELECT type, COUNT(*) FROM memoria GROUP BY type ORDER BY 2 DESC",
                ).fetchall()
                by_importance = self._conn.execute(
                    "SELECT importance, COUNT(*) FROM memoria GROUP BY importance ORDER BY 1",
                ).fetchall()
                by_origin = self._conn.execute(
                    "SELECT origin, COUNT(*) FROM memoria GROUP BY origin ORDER BY 2 DESC",
                ).fetchall()
                total_access = self._conn.execute(
                    "SELECT COALESCE(SUM(access_count), 0) FROM memoria",
                ).fetchone()[0]

        return {
            "total": total,
            "por_tipo": dict(by_type),
            "por_importancia": {str(r[0]): r[1] for r in by_importance},
            "por_origem": dict(by_origin),
            "total_acessos": total_access,
        }
