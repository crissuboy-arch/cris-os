"""
ProjetoRepository — acesso a projetos no SQLite.
"""

from repositories.base import BaseRepository


class ProjetoRepository(BaseRepository):
    TABELA = "projetos"
    COLUNAS = ("usuario_id", "nome", "descricao", "status", "contexto")

    def criar(self, usuario_id: str, nome: str, descricao: str = "",
              status: str = "ativo", contexto: str = "") -> int:
        return self.insert(
            usuario_id=usuario_id, nome=nome, descricao=descricao,
            status=status, contexto=contexto,
        )

    def atualizar(self, id: int, **kwargs) -> bool:
        if "atualizado_em" not in kwargs:
            from datetime import datetime
            kwargs["atualizado_em"] = datetime.now().isoformat()
        return self.update(id, **kwargs)

    def listar_ativos(self, usuario_id: str) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE usuario_id=? AND status='ativo' "
            f"ORDER BY atualizado_em DESC",
            (usuario_id,),
        )
        return [dict(r) for r in cur.fetchall()]
