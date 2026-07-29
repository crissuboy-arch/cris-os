"""EventLog — append-only de eventos, em memória (pronto para SQLite)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from core.domain.events import Event


@dataclass
class EventLogStats:
    """Estatisticas do Event Log."""

    total_events: int = 0
    oldest_sequence: int = 0
    newest_sequence: int = 0


class InMemoryEventLog:
    """Event Log em memoria — append-only, thread-safe.

    Preparado para ser substituido por SQLiteEventLog sem mudar
    quem usa (segue o protocolo `EventLog` em `core/contracts/events.py`).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[Event] = []
        self._sequence: int = 0

    def append(self, event: Event) -> int:
        with self._lock:
            self._sequence += 1
            self._events.append(event)
            return self._sequence

    def read_since(self, cursor: int = 0, limit: int = 500) -> list[tuple[int, Event]]:
        with self._lock:
            start = max(0, cursor)
            end = min(len(self._events), start + limit)
            return [(i + 1, self._events[i]) for i in range(start, end)]

    def read_all(self) -> list[tuple[int, Event]]:
        return self.read_since(0, len(self._events))

    def count(self) -> int:
        with self._lock:
            return len(self._events)

    def get_stats(self) -> EventLogStats:
        with self._lock:
            if not self._events:
                return EventLogStats()
            return EventLogStats(
                total_events=len(self._events),
                oldest_sequence=1,
                newest_sequence=self._sequence,
            )

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._sequence = 0