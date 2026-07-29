"""
TaskManager — gerenciador de tarefas do CRIS OS.

Cria, conclui, prioriza e gerencia prazos e responsaveis.
"""

import logging
from datetime import datetime

from repositories.tarefa_repo import TarefaRepository

logger = logging.getLogger(__name__)


class TaskManager:
    """Gerenciador de tarefas com CRUD completo."""

    def __init__(self) -> None:
        self.repo = TarefaRepository()

    def criar(self, usuario_id: str, titulo: str, descricao: str = "",
              prioridade: str = "media", prazo: str = "",
              responsavel: str = "", projeto_id: int | None = None) -> dict:
        """Cria uma nova tarefa."""
        tid = self.repo.criar(usuario_id, titulo, descricao,
                              prioridade, prazo, responsavel,
                              "pendente", projeto_id)
        tarefa = self.repo.get_by_id(tid)
        logger.info("Tarefa criada: '%s' (id=%d, prioridade=%s)",
                     titulo, tid, prioridade)
        return dict(tarefa) if tarefa else {"id": tid, "titulo": titulo}

    def listar(self, usuario_id: str) -> list[dict]:
        """Lista todas as tarefas do usuario."""
        return self.repo.list_by_usuario(usuario_id)

    def pendentes(self, usuario_id: str) -> list[dict]:
        """Lista apenas tarefas pendentes (ordenadas por prioridade)."""
        return self.repo.pendentes(usuario_id)

    def abrir(self, tarefa_id: int) -> dict | None:
        """Retorna uma tarefa pelo ID."""
        return self.repo.get_by_id(tarefa_id)

    def concluir(self, tarefa_id: int) -> bool:
        """Marca tarefa como concluida."""
        return self.repo.concluir(tarefa_id)

    def atualizar(self, tarefa_id: int, **kwargs) -> bool:
        """Atualiza campos de uma tarefa."""
        return self.repo.atualizar(tarefa_id, **kwargs)

    def excluir(self, tarefa_id: int) -> bool:
        """Exclui uma tarefa."""
        return self.repo.delete(tarefa_id)

    def por_projeto(self, projeto_id: int) -> list[dict]:
        """Lista tarefas de um projeto especifico."""
        return self.repo.por_projeto(projeto_id)
