"""
NoopReplicator — implementação inicial da porta Replicator.

Não envia nada para fora ainda (não há 2ª máquina conectada), mas drena o outbox
e registra o que SERIA enviado. Quando a réplica existir, troca-se por um
HttpReplicator/FileReplicator que cumpre a mesma porta — sem mudar o resto.

Fluxo real (futuro): um loop periódico lê `ops.pending_outbox()`, chama
`replicator.ship(...)` e confirma com `ops.ack_outbox(seq)`.
"""

from __future__ import annotations

import logging

from core.domain.events import Event

logger = logging.getLogger(__name__)


class NoopReplicator:
    def ship(self, events: list[tuple[int, Event]]) -> None:
        if events:
            ultimos = events[-1][0]
            logger.debug("Replicacao (noop): %d eventos ate seq=%s", len(events), ultimos)
