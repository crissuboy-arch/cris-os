"""
Porta: canal de comunicação (entrada/saída com a Cris).

Telegram, WhatsApp, Discord, Email, Instagram... todos implementam este contrato.
Um canal só sabe traduzir a plataforma <-> IncomingMessage e chamar o `handler`
(que é o Gateway). Ele NÃO conhece agentes, LLM nem memória.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from core.models import IncomingMessage, OutgoingMessage

# O Gateway entrega esta função ao canal. Recebe a mensagem normalizada e
# devolve o texto de resposta pronto para enviar de volta.
Handler = Callable[[IncomingMessage], str]


@runtime_checkable
class Channel(Protocol):
    """Contrato de um canal de comunicação."""

    name: str

    def run(self) -> None:
        """Inicia o canal (fica escutando mensagens). Geralmente bloqueante."""
        ...

    def send(self, message: OutgoingMessage) -> bool:
        """Envia uma mensagem proativa para o canal.

        Args:
            message: Mensagem a enviar (recipient_id, text).

        Returns:
            True se enviou com sucesso, False caso contrário.
        """
        ...
