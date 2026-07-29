"""
MemoryManager — gerenciador de memoria do CRIS OS.

Salva automaticamente:
  - conversas
  - preferencias
  - contexto recente
  - contexto permanente

Cada agente pode consultar a memoria antes de responder.
"""

import logging
from datetime import datetime

from repositories.conversa_repo import ConversaRepository
from repositories.preferencia_repo import PreferenciaRepository

logger = logging.getLogger(__name__)


class MemoryManager:
    """Gerenciador central de memoria persistente."""

    def __init__(self) -> None:
        self.conversas = ConversaRepository()
        self.preferencias = PreferenciaRepository()

    # -- Conversas -----------------------------------------------------------

    def salvar_conversa(self, usuario_id: str, papel: str,
                        conteudo: str, agente: str = "") -> int:
        """Salva uma mensagem no historico."""
        return self.conversas.adicionar(usuario_id, papel, conteudo, agente)

    def historico(self, usuario_id: str, limite: int = 20) -> list[dict]:
        """Retorna historico recente do usuario."""
        return self.conversas.historico(usuario_id, limite)

    def historico_por_agente(self, usuario_id: str, agente: str,
                             limite: int = 20) -> list[dict]:
        """Retorna historico filtrado por agente."""
        return self.conversas.historico_por_agente(usuario_id, agente, limite)

    def limpar_conversas(self, usuario_id: str) -> bool:
        """Limpa todo o historico do usuario."""
        return self.conversas.limpar(usuario_id)

    def contexto_recente(self, usuario_id: str, limite: int = 10) -> str:
        """Retorna as ultimas mensagens como texto formatado para contexto."""
        hist = self.historico(usuario_id, limite)
        if not hist:
            return ""
        linhas = []
        for msg in reversed(hist):
            agente = f" ({msg['agente']})" if msg.get("agente") else ""
            linhas.append(f"{msg['papel']}{agente}: {msg['conteudo'][:200]}")
        return "\n".join(linhas)

    # -- Preferencias --------------------------------------------------------

    def definir_preferencia(self, usuario_id: str, chave: str, valor: str) -> int:
        """Define ou atualiza uma preferencia."""
        return self.preferencias.definir(usuario_id, chave, valor)

    def obter_preferencia(self, usuario_id: str, chave: str,
                          padrao: str = "") -> str:
        """Retorna uma preferencia ou valor padrao."""
        return self.preferencias.obter(usuario_id, chave, padrao)

    def listar_preferencias(self, usuario_id: str) -> list[dict]:
        """Lista todas as preferencias do usuario."""
        return self.preferencias.listar_por_usuario(usuario_id)
