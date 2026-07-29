"""
ConfigRepository — acesso a configuracoes no SQLite.
"""

from repositories.base import BaseRepository


class ConfigRepository(BaseRepository):
    TABELA = "configuracoes"
    COLUNAS = ("usuario_id", "chave", "valor")

    def definir(self, usuario_id: str, chave: str, valor: str) -> int:
        conn = self._conn()
        existente = conn.execute(
            f"SELECT id FROM {self.TABELA} WHERE usuario_id=? AND chave=?",
            (usuario_id, chave),
        ).fetchone()
        if existente:
            self.update(existente["id"], valor=valor)
            return existente["id"]
        return self.insert(usuario_id=usuario_id, chave=chave, valor=valor)

    def obter(self, usuario_id: str, chave: str, padrao: str = "") -> str:
        conn = self._conn()
        row = conn.execute(
            f"SELECT valor FROM {self.TABELA} WHERE usuario_id=? AND chave=?",
            (usuario_id, chave),
        ).fetchone()
        return row["valor"] if row else padrao

    def listar_por_usuario(self, usuario_id: str) -> list[dict]:
        return self.list_by_usuario(usuario_id, "chave ASC")

    def resetar(self, usuario_id: str) -> bool:
        cur = self._conn().execute(
            f"DELETE FROM {self.TABELA} WHERE usuario_id=?", (usuario_id,)
        )
        self._conn().commit()
        return True
