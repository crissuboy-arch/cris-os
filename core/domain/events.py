"""
Eventos de domínio.

O Event é a unidade do backbone event-driven. TODO acontecimento relevante vira
um Event publicado no barramento e gravado no Event Log. O mesmo log serve para:
  - auditoria (o que aconteceu, quando, em qual pedido);
  - replicação (enviar eventos novos para a 2ª máquina);
  - failover (a réplica reprocessa os eventos e reconstrói o estado).

`correlation_id` amarra todos os eventos de um mesmo pedido da Cris.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _novo_id() -> str:
    return uuid.uuid4().hex


class EventType:
    """Tipos de evento conhecidos (string para não acoplar produtores/consumidores)."""

    # --- Fluxo base (v3) ---
    MESSAGE_RECEIVED = "message.received"
    INTENT_IDENTIFIED = "intent.identified"
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    RESPONSE_COMPOSED = "response.composed"
    RESPONSE_SENT = "response.sent"
    MEMORY_UPDATED = "memory.updated"

    # --- Camada de cognição: planejamento (Strategic Planner) ---
    OBJECTIVE_RECEIVED = "objective.received"
    CONTEXT_ANALYZED = "context.analyzed"
    STRATEGY_SELECTED = "strategy.selected"
    PLAN_CREATED = "plan.created"

    # --- Camada de cognição: execução (Execution Manager) ---
    EXECUTION_STARTED = "execution.started"
    EXECUTION_PROGRESS = "execution.progress"
    TASK_RETRIED = "task.retried"
    TASK_TIMEOUT = "task.timeout"
    EXECUTION_COMPLETED = "execution.completed"

    # --- Camada de cognição: supervisão (Quality Supervisor) ---
    QUALITY_EVALUATED = "quality.evaluated"
    QUALITY_APPROVED = "quality.approved"
    QUALITY_REJECTED = "quality.rejected"
    REEXECUTION_REQUESTED = "reexecution.requested"

    # --- Skills (execução de skills) ---
    SKILL_STARTED = "skill.started"
    SKILL_COMPLETED = "skill.completed"
    SKILL_FAILED = "skill.failed"

    # --- Capability Registry ---
    CAPABILITY_REGISTERED = "capability.registered"
    CAPABILITY_UNREGISTERED = "capability.unregistered"
    CAPABILITY_HEALTH_CHANGED = "capability.health.changed"
    CAPABILITY_CONFLICT_DETECTED = "capability.conflict.detected"
    CAPABILITY_CALL_STARTED = "capability.call.started"
    CAPABILITY_CALL_COMPLETED = "capability.call.completed"
    CAPABILITY_CALL_FAILED = "capability.call.failed"
    CAPABILITY_FALLBACK = "capability.fallback"
    CAPABILITY_NOT_FOUND = "capability.not_found"


@dataclass
class Event:
    """Um acontecimento imutável no sistema."""

    type: str
    payload: dict = field(default_factory=dict)
    correlation_id: str = field(default_factory=_novo_id)
    id: str = field(default_factory=_novo_id)
    source: str = "core"
    ts: str = field(default_factory=_agora)
