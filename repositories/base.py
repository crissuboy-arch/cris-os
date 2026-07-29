"""
BaseRepository — classe base com metodos CRUD comuns.
"""

import sqlite3
from typing import Any

from database.connection import get_connection


class BaseRepository:
    TABELA: str = ""
    COLUNAS: tuple[str, ...] = ()

    def _conn(self) -> sqlite3.Connection:
        return get_connection()

    def insert(self, **kwargs) -> int:
        cols = ", ".join(kwargs)
        placeholders = ", ".join("?" for _ in kwargs)
        sql = f"INSERT INTO {self.TABELA} ({cols}) VALUES ({placeholders})"
        cur = self._conn().execute(sql, tuple(kwargs.values()))
        self._conn().commit()
        return cur.lastrowid

    def update(self, id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        sets = ", ".join(f"{k}=?" for k in kwargs)
        sql = f"UPDATE {self.TABELA} SET {sets} WHERE id=?"
        cur = self._conn().execute(sql, tuple(kwargs.values()) + (id,))
        self._conn().commit()
        return cur.rowcount > 0

    def delete(self, id: int) -> bool:
        cur = self._conn().execute(
            f"DELETE FROM {self.TABELA} WHERE id=?", (id,)
        )
        self._conn().commit()
        return cur.rowcount > 0

    def get_by_id(self, id: int) -> dict[str, Any] | None:
        cur = self._conn().execute(
            f"SELECT * FROM {self.TABELA} WHERE id=?", (id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def list_all(self, order_by: str = "id DESC") -> list[dict[str, Any]]:
        cur = self._conn().execute(
            f"SELECT * FROM {self.TABELA} ORDER BY {order_by}"
        )
        return [dict(r) for r in cur.fetchall()]

    def list_by_usuario(
        self, usuario_id: str, order_by: str = "id DESC"
    ) -> list[dict[str, Any]]:
        cur = self._conn().execute(
            f"SELECT * FROM {self.TABELA} WHERE usuario_id=? ORDER BY {order_by}",
            (usuario_id,),
        )
        return [dict(r) for r in cur.fetchall()]
