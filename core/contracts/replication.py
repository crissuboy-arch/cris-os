"""
Portas de replicação / segunda máquina.

Estratégia (aprovada): enviar o Event Log + eleição de líder por lease.
  - Replicator: envia os eventos pendentes (outbox) para a réplica, que os
    reprocessa para reconstruir o estado.
  - LeaseStore: um nó só age se for o LÍDER (segura o lease). Se o líder cair e
    o lease expirar, o standby assume.

Status: portas definidas + outbox e lease já persistidos. Envio real entre
máquinas é uma fase futura (ver replication/).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from core.domain.events import Event


@dataclass
class Lease:
    owner: str
    expires_at: str  # ISO-8601


@runtime_checkable
class Replicator(Protocol):
    def ship(self, events: list[tuple[int, Event]]) -> None:
        """Envia eventos para a réplica."""
        ...


@runtime_checkable
class LeaseStore(Protocol):
    def acquire(self, owner: str, ttl_seconds: int) -> bool: ...
    def renew(self, owner: str, ttl_seconds: int) -> bool: ...
    def current(self) -> Lease | None: ...
