"""
Gateway — a fronteira entre os canais e o núcleo.

Todo canal (Telegram, WhatsApp, ...) entrega aqui uma IncomingMessage e recebe o
texto de resposta. O Gateway é o lugar certo para regras transversais a TODOS os
canais: autorização, logging, (futuro) limite de taxa e mapeamento de sessão.

Mantém os canais burros e o orquestrador focado: baixo acoplamento, alta coesão.
"""

from __future__ import annotations

import logging
import time

from core.models import IncomingMessage

logger = logging.getLogger(__name__)


class Gateway:
    """Recebe mensagens normalizadas e devolve a resposta do Orquestrador."""

    def __init__(self, orchestrator, allowed_senders: set[str] | None = None) -> None:
        self.orchestrator = orchestrator
        # Conjunto de sender_id autorizados. Vazio/None = libera geral (testes).
        self.allowed_senders = allowed_senders or set()

    def _autorizado(self, incoming: IncomingMessage) -> bool:
        if not self.allowed_senders:
            return True
        return incoming.sender_id in self.allowed_senders

    def handle(self, incoming: IncomingMessage) -> str:
        """Ponto de entrada único do núcleo (é o `Handler` que os canais chamam)."""
        t0 = time.perf_counter()
        if not self._autorizado(incoming):
            logger.warning(
                "Mensagem barrada de %s:%s (não autorizado)",
                incoming.channel,
                incoming.sender_id,
            )
            return "Este é um assistente pessoal privado. Acesso não autorizado."

        texto = (incoming.text or "").strip()
        if not texto:
            return ""

        logger.info("=== [GATEWAY] Mensagem RECEBIDA de %s:%s: '%s' ===",
                     incoming.channel, incoming.sender_id, texto[:120])

        try:
            t_orch_start = time.perf_counter()
            resposta = self.orchestrator.handle(incoming)
            t_orch_end = time.perf_counter()
            total_ms = (t_orch_end - t0) * 1000
            orch_ms = (t_orch_end - t_orch_start) * 1000
            logger.info("=== [PERF] Gateway: autorizacao=%.1fms  orquestrador=%.1fms  total=%.0fms ===",
                        (t_orch_start - t0) * 1000, orch_ms, total_ms)
            logger.info("=== [GATEWAY] Resposta ENVIADA para %s:%s: '%s' ===",
                        incoming.channel, incoming.sender_id, resposta[:200])
            return resposta
        except Exception as exc:  # noqa: BLE001 - nunca derrubar o canal
            logger.exception("=== [GATEWAY] Erro no orquestrador ===")
            return f"Ops, deu um problema aqui do meu lado. Detalhe técnico: {exc}"
