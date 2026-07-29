"""
InProcessEventBus — barramento de eventos em processo.

Ao publicar um evento, o barramento:
  1. grava no Event Log (persistencia = auditoria + replicacao + failover);
  2. notifica os assinantes daquele tipo (e os de '*').

Entrega SINCRONA (mesma thread). O contrato EventBus (Protocol) permite
trocar por entrega assincrona/fila depois SEM mudar quem publica ou assina.

Falhas em um assinante sao registradas mas NAO derrubam o fluxo (isolamento).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from core.contracts.events import EventLog, Subscriber
from core.domain.events import Event
from core.events.errors import SubscriptionNotFoundError

logger = logging.getLogger(__name__)

ALL = "*"


@dataclass
class EventBusStats:
    """Estatisticas do Event Bus."""

    total_published: int = 0
    total_delivered: int = 0
    total_failures: int = 0
    subscribers_by_type: dict[str, int] = field(default_factory=dict)
    is_healthy: bool = True


class InProcessEventBus:
    """Pub/sub sincrono, com persistencia no Event Log.

    Thread-safe. Aceita qualquer objeto que implemente o protocolo EventLog.
    """

    def __init__(self, event_log: EventLog) -> None:
        self.event_log = event_log
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[Subscriber]] = {}
        self._total_published = 0
        self._total_delivered = 0
        self._total_failures = 0
        self._healthy = True

    # ------------------------------------------------------------------
    # Gerenciamento de assinaturas
    # ------------------------------------------------------------------

    def subscribe(self, event_type: str, handler: Subscriber) -> Callable[[], None]:
        """Assina um tipo de evento ('*' para todos).

        Returns:
            Funcao de unsubscribe (callable sem argumentos).
        """
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(handler)
            logger.debug("Assinante registrado para '%s'", event_type)

        def unsubscribe() -> None:
            self._unsubscribe(event_type, handler)

        return unsubscribe

    def _unsubscribe(self, event_type: str, handler: Subscriber) -> None:
        with self._lock:
            handlers = self._subscribers.get(event_type)
            if not handlers:
                raise SubscriptionNotFoundError(
                    f"Nenhum assinante para '{event_type}'"
                )
            try:
                handlers.remove(handler)
                logger.debug("Assinante removido de '%s'", event_type)
            except ValueError:
                raise SubscriptionNotFoundError(
                    f"Handler nao encontrado para '{event_type}'"
                )

    def subscribers_count(self, event_type: str | None = None) -> int:
        """Retorna numero de assinantes. Se event_type for None, total geral."""
        with self._lock:
            if event_type:
                return len(self._subscribers.get(event_type, []))
            return sum(len(h) for h in self._subscribers.values())

    def list_subscribed_types(self) -> list[str]:
        """Lista todos os tipos de evento com assinantes."""
        with self._lock:
            return list(self._subscribers.keys())

    # ------------------------------------------------------------------
    # Publicacao
    # ------------------------------------------------------------------

    def publish(self, event: Event) -> None:
        """Publica um evento: persiste + notifica assinantes."""
        # 1) Persistir primeiro (o log e a fonte da verdade).
        try:
            self.event_log.append(event)
        except Exception:
            logger.exception("Falha ao gravar evento no Event Log: %s", event.type)

        # 2) Notificar assinantes.
        start = time.monotonic()
        delivered = 0
        failures = 0

        with self._lock:
            handlers = list(self._subscribers.get(event.type, []))
            wildcard = list(self._subscribers.get(ALL, []))

        for handler in handlers + wildcard:
            try:
                handler(event)
                delivered += 1
            except Exception:
                logger.exception("Assinante falhou no evento %s", event.type)
                failures += 1

        elapsed_ms = (time.monotonic() - start) * 1000

        with self._lock:
            self._total_published += 1
            self._total_delivered += delivered
            self._total_failures += failures

        if failures > 0:
            logger.warning(
                "Evento %s: %d entregues, %d falhas em %.1fms",
                event.type, delivered, failures, elapsed_ms,
            )

    # ------------------------------------------------------------------
    # Saude
    # ------------------------------------------------------------------

    @property
    def healthy(self) -> bool:
        return self._healthy

    def health_check(self) -> bool:
        """Verifica se o bus esta saudavel."""
        try:
            with self._lock:
                self._healthy = True
            return True
        except Exception:
            self._healthy = False
            return False

    # ------------------------------------------------------------------
    # Metricas / Estatisticas
    # ------------------------------------------------------------------

    def get_stats(self) -> EventBusStats:
        with self._lock:
            return EventBusStats(
                total_published=self._total_published,
                total_delivered=self._total_delivered,
                total_failures=self._total_failures,
                subscribers_by_type={
                    t: len(h) for t, h in self._subscribers.items()
                },
                is_healthy=self._healthy,
            )

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_published = 0
            self._total_delivered = 0
            self._total_failures = 0