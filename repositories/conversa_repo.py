"""
ConversaRepository — acesso a conversas no SQLite.
"""

from repositories.base import BaseRepository


class ConversaRepository(BaseRepository):
    TABELA = "conversas"
    COLUNAS = ("usuario_id", "papel", "conteudo", "agente")

    def adicionar(self, usuario_id: str, papel: str, conteudo: str, agente: str = "") -> int:
        return self.insert(usuario_id=usuario_id, papel=papel, conteudo=conteudo, agente=agente)

    def historico(self, usuario_id: str, limite: int = 20) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE usuario_id=? ORDER BY id DESC LIMIT ?",
            (usuario_id, limite),
        )
        return [dict(r) for r in cur.fetchall()]

    def historico_por_agente(self, usuario_id: str, agente: str, limite: int = 20) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE usuario_id=? AND agente=? ORDER BY id DESC LIMIT ?",
            (usuario_id, agente, limite),
        )
        return [dict(r) for r in cur.fetchall()]

    def limpar(self, usuario_id: str) -> bool:
        cur = self._conn().execute(
            f"DELETE FROM {self.TABELA} WHERE usuario_id=?", (usuario_id,)
        )
        self._conn().commit()
        return cur.rowcount > 0
