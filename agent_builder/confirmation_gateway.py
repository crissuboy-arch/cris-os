"""
StudioConfirmationGateway — gerencia confirmacoes pendentes para acoes sensiveis.

Quando uma capability requer confirmacao, a execucao e pausada e
o resultado retorna com confirmation_required=True.
O gateway armazena a pendencia e aguarda confirmacao/rejeicao humana.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

MAX_PENDING = 50


@dataclass
class PendingConfirmation:
    """Uma confirmacao pendente."""
    id: str
    agent_id: str
    agent_name: str
    capability: str
    instruction: str
    params: dict = field(default_factory=dict)
    status: str = "pending"  # pending | confirmed | rejected | expired
    created_at: float = field(default_factory=time.time)
    resolved_at: float | None = None
    resolved_by: str = ""
    notes: str = ""


class StudioConfirmationGateway:
    """Gerencia fila de confirmacoes pendentes."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingConfirmation] = {}
        self._counter: int = 0

    def create(
        self,
        agent_id: str,
        agent_name: str,
        capability: str,
        instruction: str,
        params: dict | None = None,
    ) -> PendingConfirmation:
        """Cria uma confirmacao pendente."""
        self._counter += 1
        conf = PendingConfirmation(
            id=f"confirm-{self._counter:06d}",
            agent_id=agent_id,
            agent_name=agent_name,
            capability=capability,
            instruction=instruction,
            params=params or {},
        )
        self._pending[conf.id] = conf

        # Trim old pending
        if len(self._pending) > MAX_PENDING:
            oldest = sorted(self._pending.values(), key=lambda c: c.created_at)
            for c in oldest[:len(oldest) - MAX_PENDING]:
                self._pending.pop(c.id, None)

        logger.info("Confirmation created: %s for %s.%s", conf.id, agent_name, capability)
        return conf

    def confirm(self, confirmation_id: str, notes: str = "") -> bool:
        """Confirma uma acao pendente."""
        conf = self._pending.get(confirmation_id)
        if conf is None or conf.status != "pending":
            return False
        conf.status = "confirmed"
        conf.resolved_at = time.time()
        conf.notes = notes
        logger.info("Confirmation confirmed: %s", confirmation_id)
        return True

    def reject(self, confirmation_id: str, notes: str = "") -> bool:
        """Rejeita uma acao pendente."""
        conf = self._pending.get(confirmation_id)
        if conf is None or conf.status != "pending":
            return False
        conf.status = "rejected"
        conf.resolved_at = time.time()
        conf.notes = notes
        logger.info("Confirmation rejected: %s", confirmation_id)
        return True

    def get(self, confirmation_id: str) -> PendingConfirmation | None:
        return self._pending.get(confirmation_id)

    def list_pending(self) -> list[dict]:
        """Lista confirmacoes pendentes (mais recente primeiro)."""
        items = sorted(self._pending.values(), key=lambda c: c.created_at, reverse=True)
        return [self._to_dict(c) for c in items if c.status == "pending"]

    def list_all(self, limit: int = 50) -> list[dict]:
        """Lista todas as confirmacoes."""
        items = sorted(self._pending.values(), key=lambda c: c.created_at, reverse=True)
        return [self._to_dict(c) for c in items[:limit]]

    def stats(self) -> dict:
        """Metricas de confirmacoes."""
        total = len(self._pending)
        pending = sum(1 for c in self._pending.values() if c.status == "pending")
        confirmed = sum(1 for c in self._pending.values() if c.status == "confirmed")
        rejected = sum(1 for c in self._pending.values() if c.status == "rejected")
        return {
            "total": total,
            "pending": pending,
            "confirmed": confirmed,
            "rejected": rejected,
        }

    @staticmethod
    def _to_dict(c: PendingConfirmation) -> dict:
        return {
            "id": c.id,
            "agent_id": c.agent_id,
            "agent_name": c.agent_name,
            "capability": c.capability,
            "instruction": c.instruction,
            "params": c.params,
            "status": c.status,
            "created_at": c.created_at,
            "resolved_at": c.resolved_at,
            "resolved_by": c.resolved_by,
            "notes": c.notes,
        }


# Singleton
_confirmation_gateway: StudioConfirmationGateway | None = None


def get_confirmation_gateway() -> StudioConfirmationGateway:
    global _confirmation_gateway
    if _confirmation_gateway is None:
        _confirmation_gateway = StudioConfirmationGateway()
    return _confirmation_gateway
