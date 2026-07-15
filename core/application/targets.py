"""
ExecutionTargets — adapters que ligam os motores concretos ao contrato único
`ExecutionTarget`. Os motores (WorkflowEngine, SkillRunner) ficam INTOCADOS.

Adicionar Browser/MCP/Planner/DeepSearch no futuro = mais uma classe aqui + um
`register(...)` no runtime. Dispatcher/Composer/Orchestrator NÃO mudam (OCP).
"""

from __future__ import annotations

from core.contracts.execution import DispatchContext
from core.domain.execution import ExecutionType
from core.models import ExecutionResult, ExecutionStep


class AgentTarget:
    """Executa passos de agente via WorkflowEngine (motor intocado)."""

    type = ExecutionType.AGENT

    def __init__(self, workflow, id: str = "agent.workflow") -> None:
        self.id = id
        self.workflow = workflow

    def run(self, step: ExecutionStep, ctx: DispatchContext) -> ExecutionResult:
        ars = self.workflow.run([(step.name, step.instruction)],
                                ctx.session, ctx.query, ctx.correlation_id)
        if not ars:
            return ExecutionResult(source=step.name, type=ExecutionType.AGENT,
                                   success=False, error=f"Agente '{step.name}' não encontrado.")
        return ExecutionResult.from_agent(ars[0])


class SkillTarget:
    """Executa passos de skill via SkillRunner (motor intocado)."""

    type = ExecutionType.SKILL

    def __init__(self, skill_runner, id: str = "skill.runner") -> None:
        self.id = id
        self.skill_runner = skill_runner

    def run(self, step: ExecutionStep, ctx: DispatchContext) -> ExecutionResult:
        sr = self.skill_runner.run(step.name, step.payload, ctx.session,
                                   ctx.correlation_id, ctx.caller)
        return ExecutionResult.from_skill(sr)
