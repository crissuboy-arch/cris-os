"""
Portas do backbone event-driven: EventBus e EventLog.

- EventBus: publica eventos e notifica assinantes (pub/sub em processo agora,
  pronto para virar assíncrono/multiprocesso depois).
- EventLog: persiste os eventos em ordem (append-only). É a fonte da verdade para
  auditoria, replicação e failover.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from core.domain.events import Event

# Assinante: função que reage a um evento.
Subscriber = Callable[[Event], None]


@runtime_checkable
class EventBus(Protocol):
    def publish(self, event: Event) -> None: ...

    def subscribe(self, event_type: str, handler: Subscriber) -> None:
        """Assina um tipo de evento ('*' para todos)."""
        ...


@runtime_checkable
class EventLog(Protocol):
    def append(self, event: Event) -> int:
        """Grava o evento e devolve seu número de sequência (cursor)."""
        ...

    def read_since(self, cursor: int = 0, limit: int = 500) -> list[tuple[int, Event]]:
        """Lê eventos com sequência > cursor (para replicação/reprocessamento)."""
        ...
