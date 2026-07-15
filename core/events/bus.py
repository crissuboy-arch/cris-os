"""
InProcessEventBus — barramento de eventos em processo.

Ao publicar um evento, o barramento:
  1. grava no Event Log (persistência = auditoria + replicação + failover);
  2. notifica os assinantes daquele tipo (e os de '*').

Hoje a entrega é SÍNCRONA (mesma thread), o que é simples e previsível. O
contrato, porém, já permite trocar por entrega assíncrona/fila depois SEM mudar
quem publica ou assina — basta outra implementação de EventBus.

Falhas em um assinante são registradas mas NÃO derrubam o fluxo (isolamento).
"""

from __future__ import annotations

import logging

from core.contracts.events import EventLog, Subscriber
from core.domain.events import Event

logger = logging.getLogger(__name__)

ALL = "*"


class InProcessEventBus:
    """Pub/sub síncrono, com persistência no Event Log."""

    def __init__(self, event_log: EventLog) -> None:
        self.event_log = event_log
        self._subscribers: dict[str, list[Subscriber]] = {}

    def subscribe(self, event_type: str, handler: Subscriber) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event: Event) -> None:
        # 1) Persistir primeiro (o log é a fonte da verdade).
        try:
            self.event_log.append(event)
        except Exception:  # noqa: BLE001 - log não pode derrubar o fluxo
            logger.exception("Falha ao gravar evento no Event Log: %s", event.type)

        # 2) Notificar assinantes do tipo específico e os globais ('*').
        for tipo in (event.type, ALL):
            for handler in self._subscribers.get(tipo, []):
                try:
                    handler(event)
                except Exception:  # noqa: BLE001 - um assinante ruim não quebra os outros
                    logger.exception("Assinante falhou no evento %s", event.type)
