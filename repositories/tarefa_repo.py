"""
TarefaRepository — acesso a tarefas no SQLite.
"""

from repositories.base import BaseRepository


class TarefaRepository(BaseRepository):
    TABELA = "tarefas"
    COLUNAS = ("usuario_id", "titulo", "descricao", "prioridade",
               "prazo", "responsavel", "status", "projeto_id")

    def criar(self, usuario_id: str, titulo: str, descricao: str = "",
              prioridade: str = "media", prazo: str = "",
              responsavel: str = "", status: str = "pendente",
              projeto_id: int | None = None) -> int:
        return self.insert(
            usuario_id=usuario_id, titulo=titulo, descricao=descricao,
            prioridade=prioridade, prazo=prazo, responsavel=responsavel,
            status=status, projeto_id=projeto_id,
        )

    def atualizar(self, id: int, **kwargs) -> bool:
        if "atualizado_em" not in kwargs:
            from datetime import datetime
            kwargs["atualizado_em"] = datetime.now().isoformat()
        return self.update(id, **kwargs)

    def concluir(self, id: int) -> bool:
        from datetime import datetime
        return self.update(id, status="concluida", atualizado_em=datetime.now().isoformat())

    def pendentes(self, usuario_id: str) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE usuario_id=? AND status='pendente' "
            f"ORDER BY CASE prioridade WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END, prazo ASC",
            (usuario_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def por_projeto(self, projeto_id: int) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE projeto_id=? ORDER BY id DESC",
            (projeto_id,),
        )
        return [dict(r) for r in cur.fetchall()]
