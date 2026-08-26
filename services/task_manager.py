"""
TaskManager — gerenciador de tarefas do CRIS OS.

Cria, conclui, prioriza e gerencia prazos e responsaveis.
"""

import logging
from datetime import datetime, timedelta

from repositories.tarefa_repo import TarefaRepository

logger = logging.getLogger(__name__)


class TaskManager:
    """Gerenciador de tarefas com CRUD completo."""

    def __init__(self) -> None:
        self.repo = TarefaRepository()

    def criar(self, usuario_id: str, titulo: str, descricao: str = "",
              prioridade: str = "media", prazo: str = "",
              responsavel: str = "", agente: str = "",
              projeto_id: int | None = None) -> dict:
        """Cria uma nova tarefa."""
        tid = self.repo.criar(usuario_id, titulo, descricao,
                              prioridade, prazo, responsavel,
                              agente, "pendente", projeto_id)
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

    def cancelar(self, tarefa_id: int) -> bool:
        """Marca tarefa como cancelada."""
        return self.repo.atualizar(tarefa_id, status="cancelada")

    def excluir(self, tarefa_id: int) -> bool:
        """Exclui uma tarefa."""
        return self.repo.delete(tarefa_id)

    def por_projeto(self, projeto_id: int) -> list[dict]:
        """Lista tarefas de um projeto especifico."""
        return self.repo.por_projeto(projeto_id)

    def por_status(self, usuario_id: str, status: str) -> list[dict]:
        """Lista tarefas por status."""
        return self.repo.por_status(usuario_id, status)

    def atrasadas(self, usuario_id: str) -> list[dict]:
        """Lista tarefas pendentes com prazo vencido."""
        return self.repo.atrasadas(usuario_id)

    def delegar(self, tarefa_id: int, responsavel: str = "",
                agente: str = "") -> dict | None:
        """Delega uma tarefa a um responsavel/agente."""
        self.repo.atualizar(tarefa_id, responsavel=responsavel,
                            agente=agente)
        return self.repo.get_by_id(tarefa_id)

    def revisao_semanal(self, usuario_id: str) -> dict:
        """Gera um resumo semanal das tarefas do usuario."""
        todas = self.listar(usuario_id)
        hoje = datetime.now()
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        fim_semana = inicio_semana + timedelta(days=6)

        def na_semana(dt: str) -> bool:
            if not dt:
                return False
            try:
                d = datetime.strptime(dt[:10], "%Y-%m-%d")
            except ValueError:
                return False
            return inicio_semana.date() <= d.date() <= fim_semana.date()

        concluidas_semana = [
            t for t in todas
            if t.get("status") == "concluida" and na_semana(t.get("atualizado_em", ""))
        ]
        pendentes = [t for t in todas if t.get("status") == "pendente"]
        atrasadas = self.atrasadas(usuario_id)
        por_agente: dict[str, int] = {}
        for t in pendentes:
            ag = t.get("agente") or ""
            if ag:
                por_agente[ag] = por_agente.get(ag, 0) + 1
        por_prioridade: dict[str, int] = {}
        for t in pendentes:
            pr = t.get("prioridade", "media")
            por_prioridade[pr] = por_prioridade.get(pr, 0) + 1

        return {
            "semana_inicio": inicio_semana.strftime("%Y-%m-%d"),
            "semana_fim": fim_semana.strftime("%Y-%m-%d"),
            "total_tarefas": len(todas),
            "concluidas_semana": len(concluidas_semana),
            "pendentes": len(pendentes),
            "atrasadas": len(atrasadas),
            "por_prioridade": por_prioridade,
            "por_agente": por_agente,
        }
