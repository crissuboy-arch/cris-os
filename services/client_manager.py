"""
ClientManager — gerenciador de clientes do CRIS OS.

Salva nome, empresa, telefone, email, observacoes e historico.
"""

import logging

from repositories.cliente_repo import ClienteRepository as Repo

logger = logging.getLogger(__name__)


class ClientManager:
    """Gerenciador de clientes com CRUD completo."""

    def __init__(self) -> None:
        self.repo = Repo()

    def criar(self, usuario_id: str, nome: str, empresa: str = "",
              telefone: str = "", email: str = "",
              observacoes: str = "") -> dict:
        """Cadastra um novo cliente."""
        cid = self.repo.criar(usuario_id, nome, empresa, telefone, email, observacoes)
        cliente = self.repo.get_by_id(cid)
        logger.info("Cliente criado: '%s' (id=%d)", nome, cid)
        return dict(cliente) if cliente else {"id": cid, "nome": nome}

    def listar(self, usuario_id: str) -> list[dict]:
        """Lista todos os clientes do usuario."""
        return self.repo.list_by_usuario(usuario_id)

    def abrir(self, cliente_id: int) -> dict | None:
        """Retorna um cliente pelo ID."""
        return self.repo.get_by_id(cliente_id)

    def atualizar(self, cliente_id: int, **kwargs) -> bool:
        """Atualiza dados de um cliente."""
        return self.repo.atualizar(cliente_id, **kwargs)

    def excluir(self, cliente_id: int) -> bool:
        """Exclui um cliente."""
        return self.repo.delete(cliente_id)

    def buscar(self, usuario_id: str, termo: str) -> list[dict]:
        """Busca clientes por nome, empresa, telefone ou email."""
        return self.repo.buscar(usuario_id, termo)
