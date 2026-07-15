"""
Porta: ExecutionTarget — quem sabe executar um passo de um determinado tipo.

O `ExecutionDispatcher` despacha por `ExecutionType`; o `id` ESTÁVEL identifica o
executor em logs/tracing/métricas/cache/telemetria e permite VÁRIOS targets do
mesmo tipo (ex.: browser.chrome, browser.mobile, browser.cloud) sem mudar o
contrato. Segue o precedente de `contracts/agent.py` (Context + Protocol juntos).

Este é o contrato ÚNICO e estável de execução: qualquer executor futuro
(Agent, Skill, Tool, Browser, Planner, MCP, DeepSearch) o implementa.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from core.domain.execution import ExecutionType

if TYPE_CHECKING:
    from core.models import ExecutionResult, ExecutionStep


@dataclass
class DispatchContext:
    """O que qualquer ExecutionTarget pode precisar para rodar um passo."""

    session: str
    query: str = ""
    correlation_id: str = ""
    caller: str = "orchestrator"
    confirmed: bool = False  # a Cris já confirmou a ação sensível? (gate de confirmação)


@runtime_checkable
class ExecutionTarget(Protocol):
    """Contrato único de execução — estável para qualquer executor futuro."""

    id: str  # identificador estável (logs/tracing/métricas/cache/telemetria)
    type: ExecutionType

    def run(self, step: "ExecutionStep", ctx: "DispatchContext") -> "ExecutionResult":
        """Executa UM passo e devolve um ExecutionResult (DTO universal)."""
        ...
