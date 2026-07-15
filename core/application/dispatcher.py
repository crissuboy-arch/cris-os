"""
ExecutionDispatcher — despacha ExecutionSteps para ExecutionTargets, POR TIPO.

É AGNÓSTICO: não conhece Agent nem Skill. Só resolve `ExecutionType -> ExecutionTarget`
no `TargetRegistry` e chama o contrato único `run(step, ctx)`. Qualquer executor
futuro (Tool/MCP/Browser/Planner/DeepSearch) entra por `register()`, sem tocar aqui.
"""

from __future__ import annotations

import logging

from core.application.confirmation import ConfirmationGate
from core.contracts.execution import DispatchContext
from core.domain.execution import ExecutionType
from core.models import ExecutionResult, ExecutionStep

logger = logging.getLogger(__name__)


class TargetRegistry:
    """Catálogo de ExecutionTargets (indexado por tipo E por id)."""

    def __init__(self) -> None:
        self._by_type: dict[ExecutionType, object] = {}
        self._by_id: dict[str, object] = {}

    def register(self, target) -> "TargetRegistry":
        self._by_type[target.type] = target
        self._by_id[target.id] = target
        logger.info("ExecutionTarget registrado: id=%s type=%s", target.id, target.type)
        return self

    def get(self, type: ExecutionType):
        """Executor responsável por um tipo (usado no despacho)."""
        return self._by_type.get(type)

    def by_id(self, id: str):
        """Executor por id estável (usado por logs/tracing/métricas/cache)."""
        return self._by_id.get(id)


class ExecutionDispatcher:
    """Roteia cada passo para o target do seu tipo e devolve ExecutionResults.

    Antes de executar, consulta o `ConfirmationGate`: ações sensíveis
    (write/delete/publish/buy/send) não confirmadas são bloqueadas e viram um
    pedido de confirmação — sem tocar o alvo. Read-only passa direto.
    """

    def __init__(self, targets: TargetRegistry, gate: ConfirmationGate | None = None) -> None:
        self.targets = targets
        self.gate = gate or ConfirmationGate()

    def run(self, plan: list[ExecutionStep], ctx: DispatchContext) -> list[ExecutionResult]:
        resultados: list[ExecutionResult] = []
        for step in plan:
            bloqueio = self.gate.check(step, ctx)
            if bloqueio is not None:
                logger.info("Gate: passo sensível '%s' bloqueado (aguardando confirmação).", step.name)
                resultados.append(bloqueio)
                continue
            target = self.targets.get(step.type)
            if target is None:
                logger.warning("Sem ExecutionTarget para o tipo '%s' (passo '%s').",
                               step.type, step.name)
                resultados.append(ExecutionResult(
                    source=step.name, type=step.type, success=False,
                    error=f"Sem executor para o tipo '{step.type}'.",
                ))
                continue
            resultados.append(target.run(step, ctx))
        return resultados
