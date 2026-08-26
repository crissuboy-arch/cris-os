"""
ObjetivoRepository — acesso a objetivos (CEO Mode) no SQLite.
"""

import json
from datetime import datetime

from repositories.base import BaseRepository


class ObjetivoRepository(BaseRepository):
    TABELA = "objetivos"
    COLUNAS = ("usuario_id", "objetivo", "tipo", "projeto_id",
               "plano", "status")

    def criar(self, usuario_id: str, objetivo: str, tipo: str = "geral",
              projeto_id: int | None = None, plano: dict | None = None,
              status: str = "planejado") -> int:
        return self.insert(
            usuario_id=usuario_id, objetivo=objetivo, tipo=tipo,
            projeto_id=projeto_id, plano=json.dumps(plano or {}, ensure_ascii=False),
            status=status,
        )

    def por_usuario(self, usuario_id: str) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE usuario_id=? ORDER BY id DESC",
            (usuario_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def abrir(self, id: int) -> dict | None:
        obj = self.get_by_id(id)
        if obj and obj.get("plano"):
            try:
                obj["plano"] = json.loads(obj["plano"])
            except (json.JSONDecodeError, TypeError):
                obj["plano"] = {}
        return obj

    def atualizar_status(self, id: int, status: str) -> bool:
        return self.update(id, status=status,
                           atualizado_em=datetime.now().isoformat())

    def atualizar_plano(self, id: int, plano: dict) -> bool:
        return self.update(id, plano=json.dumps(plano, ensure_ascii=False),
                           atualizado_em=datetime.now().isoformat())
