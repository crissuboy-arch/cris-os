"""
ProjectManager — gerenciador de projetos do CRIS OS.

Permite criar, listar, abrir projetos com contexto e historico.
"""

import logging
from datetime import datetime

from repositories.projeto_repo import ProjetoRepository
from repositories.tarefa_repo import TarefaRepository

logger = logging.getLogger(__name__)


class ProjectManager:
    """Gerenciador de projetos com CRUD completo."""

    def __init__(self) -> None:
        self.repo = ProjetoRepository()
        self.tarefa_repo = TarefaRepository()

    # -- CRUD ----------------------------------------------------------------

    def criar(self, usuario_id: str, nome: str, descricao: str = "",
              contexto: str = "") -> dict:
        """Cria um novo projeto."""
        pid = self.repo.criar(usuario_id, nome, descricao, "ativo", contexto)
        projeto = self.repo.get_by_id(pid)
        logger.info("Projeto criado: '%s' (id=%d)", nome, pid)
        return dict(projeto) if projeto else {"id": pid, "nome": nome}

    def listar(self, usuario_id: str) -> list[dict]:
        """Lista todos os projetos do usuario."""
        return self.repo.listar_ativos(usuario_id)

    def listar_todos(self, usuario_id: str) -> list[dict]:
        """Lista todos os projetos (inclusive inativos)."""
        return self.repo.list_by_usuario(usuario_id)

    def abrir(self, projeto_id: int) -> dict | None:
        """Retorna um projeto pelo ID."""
        proj = self.repo.get_by_id(projeto_id)
        if proj:
            proj["tarefas"] = self.tarefa_repo.por_projeto(projeto_id)
        return proj

    def atualizar(self, projeto_id: int, **kwargs) -> bool:
        """Atualiza campos de um projeto."""
        return self.repo.atualizar(projeto_id, **kwargs)

    def arquivar(self, projeto_id: int) -> bool:
        """Arquiva um projeto (status='arquivado')."""
        return self.repo.atualizar(projeto_id, status="arquivado",
                                   atualizado_em=datetime.now().isoformat())

    def excluir(self, projeto_id: int) -> bool:
        """Exclui um projeto."""
        return self.repo.delete(projeto_id)

    # -- Contexto ------------------------------------------------------------

    def contexto(self, projeto_id: int) -> str:
        """Retorna o contexto salvo de um projeto."""
        proj = self.repo.get_by_id(projeto_id)
        if not proj:
            return ""
        return proj.get("contexto", "")

    def atualizar_contexto(self, projeto_id: int, contexto: str) -> bool:
        """Atualiza o contexto de um projeto."""
        return self.repo.atualizar(projeto_id, contexto=contexto,
                                   atualizado_em=datetime.now().isoformat())

    def historico_tarefas(self, projeto_id: int) -> list[dict]:
        """Retorna todas as tarefas de um projeto."""
        return self.tarefa_repo.por_projeto(projeto_id)
