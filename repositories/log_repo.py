"""
LogRepository — acesso a logs de atividade no SQLite.
"""

from repositories.base import BaseRepository


class LogRepository(BaseRepository):
    TABELA = "logs_atividade"
    COLUNAS = ("usuario_id", "agente", "ferramenta", "modelo", "duracao_ms", "erro")

    def registrar(self, usuario_id: str = "", agente: str = "",
                  ferramenta: str = "", modelo: str = "",
                  duracao_ms: int = 0, erro: str = "") -> int:
        return self.insert(
            usuario_id=usuario_id, agente=agente, ferramenta=ferramenta,
            modelo=modelo, duracao_ms=duracao_ms, erro=erro,
        )

    def ultimos(self, limite: int = 50) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} ORDER BY id DESC LIMIT ?", (limite,)
        )
        return [dict(r) for r in cur.fetchall()]

    def por_agente(self, agente: str, limite: int = 20) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE agente=? ORDER BY id DESC LIMIT ?",
            (agente, limite),
        )
        return [dict(r) for r in cur.fetchall()]

    def erros(self, limite: int = 20) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE erro!='' ORDER BY id DESC LIMIT ?",
            (limite,),
        )
        return [dict(r) for r in cur.fetchall()]
