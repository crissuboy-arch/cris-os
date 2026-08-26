"""
LembreteRepository — acesso a lembretes no SQLite.
"""

from repositories.base import BaseRepository


class LembreteRepository(BaseRepository):
    TABELA = "lembretes"
    COLUNAS = ("usuario_id", "titulo", "data_hora", "recorrencia",
               "tarefa_id", "status")

    def criar(self, usuario_id: str, titulo: str, data_hora: str,
              recorrencia: str = "", tarefa_id: int | None = None,
              status: str = "ativo") -> int:
        return self.insert(
            usuario_id=usuario_id, titulo=titulo, data_hora=data_hora,
            recorrencia=recorrencia, tarefa_id=tarefa_id, status=status,
        )

    def ativos(self, usuario_id: str) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE usuario_id=? AND status='ativo' "
            f"ORDER BY data_hora ASC",
            (usuario_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def devidos(self, usuario_id: str, ate: str) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE usuario_id=? AND status='ativo' "
            f"AND data_hora <= ? ORDER BY data_hora ASC",
            (usuario_id, ate),
        )
        return [dict(r) for r in cur.fetchall()]

    def cancelar(self, id: int) -> bool:
        return self.update(id, status="cancelado")
