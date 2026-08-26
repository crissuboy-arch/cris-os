"""
DependenciaRepository — acesso a dependencias entre tarefas no SQLite.
"""

from repositories.base import BaseRepository


class DependenciaRepository(BaseRepository):
    TABELA = "dependencias"
    COLUNAS = ("usuario_id", "tarefa_id", "depende_de")

    def criar(self, usuario_id: str, tarefa_id: int, depende_de: int) -> int:
        return self.insert(usuario_id=usuario_id, tarefa_id=tarefa_id,
                           depende_de=depende_de)

    def por_tarefa(self, tarefa_id: int) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE tarefa_id=?",
            (tarefa_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def por_usuario(self, usuario_id: str) -> list[dict]:
        conn = self._conn()
        cur = conn.execute(
            f"SELECT * FROM {self.TABELA} WHERE usuario_id=?",
            (usuario_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def bloqueadas(self, usuario_id: str) -> list[int]:
        """Tarefas que dependem de outra ainda pendente/concluida."""
        conn = self._conn()
        cur = conn.execute(
            f"SELECT d.tarefa_id FROM {self.TABELA} d "
            f"JOIN tarefas t ON t.id = d.depende_de "
            f"WHERE d.usuario_id=? AND t.status != 'concluida'",
            (usuario_id,),
        )
        return [r[0] for r in cur.fetchall()]

    def excluir_por_tarefa(self, tarefa_id: int) -> None:
        conn = self._conn()
        conn.execute(f"DELETE FROM {self.TABELA} WHERE tarefa_id=?", (tarefa_id,))
        conn.commit()
