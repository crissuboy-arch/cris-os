"""
PromptLibrary — biblioteca de prompts do CRIS OS.

Salva, categoriza, favorita e pesquisa prompts.
"""

import logging

from repositories.prompt_repo import PromptRepository

logger = logging.getLogger(__name__)


class PromptLibrary:
    """Gerenciador de biblioteca de prompts."""

    def __init__(self) -> None:
        self.repo = PromptRepository()

    def adicionar(self, usuario_id: str, titulo: str, conteudo: str,
                  categoria: str = "", favorito: bool = False) -> dict:
        """Salva um prompt na biblioteca."""
        pid = self.repo.adicionar(usuario_id, titulo, conteudo, categoria, favorito)
        prompt = self.repo.get_by_id(pid)
        logger.info("Prompt salvo: '%s' (id=%d, cat=%s)", titulo, pid, categoria)
        return dict(prompt) if prompt else {"id": pid, "titulo": titulo}

    def listar(self, usuario_id: str) -> list[dict]:
        """Lista todos os prompts."""
        return self.repo.list_by_usuario(usuario_id)

    def favoritos(self, usuario_id: str) -> list[dict]:
        """Lista apenas prompts favoritados."""
        return self.repo.favoritos(usuario_id)

    def buscar(self, usuario_id: str, termo: str) -> list[dict]:
        """Busca prompts por titulo, conteudo ou categoria."""
        return self.repo.buscar(usuario_id, termo)

    def por_categoria(self, usuario_id: str, categoria: str) -> list[dict]:
        """Lista prompts de uma categoria."""
        return self.repo.por_categoria(usuario_id, categoria)

    def alternar_favorito(self, prompt_id: int) -> bool:
        """Alterna o status favorito de um prompt."""
        return self.repo.alternar_favorito(prompt_id)

    def atualizar(self, prompt_id: int, **kwargs) -> bool:
        """Atualiza um prompt."""
        return self.repo.update(prompt_id, **kwargs)

    def excluir(self, prompt_id: int) -> bool:
        """Exclui um prompt."""
        return self.repo.delete(prompt_id)
