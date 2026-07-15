"""
WorkflowEngine — cria, rastreia e coordena a execução das tarefas.

Responsabilidade única: dado um plano [(agente, instrução)], para cada item:
  1. cria uma Task e a persiste (pending) — permite ACOMPANHAR e, no futuro,
     RETOMAR após um crash/failover;
  2. monta o contexto de memória ESCOPADO ao agente (via MemoryFacade);
  3. executa o agente;
  4. atualiza a Task (done|error) e publica eventos no barramento.

Hoje a execução é sequencial; o desenho já permite paralelizar depois (cada Task
é independente e rastreada).
"""

from __future__ import annotations

import logging

from core.domain.events import Event, EventType
from core.models import AgentResult, Task

logger = logging.getLogger(__name__)


class WorkflowEngine:
    def __init__(self, registry, task_store, event_bus, memory_facade,
                 fallback_agent: str = "secretary") -> None:
        self.registry = registry
        self.task_store = task_store
        self.event_bus = event_bus
        self.memory = memory_facade
        self.fallback_agent = fallback_agent

    def run(self, plan: list[tuple[str, str]], session: str, query: str,
            correlation_id: str) -> list[AgentResult]:
        from core.models import _agora

        resultados: list[AgentResult] = []

        for nome, instrucao in plan:
            agente = self.registry.get(nome) or self.registry.get(self.fallback_agent)
            if agente is None:
                continue

            task = Task(agent=agente.name, instruction=instrucao, status="pending")
            self.task_store.save(task)
            self._emit(EventType.TASK_CREATED, correlation_id, task)

            # Contexto de memória escopado ao domínio do agente.
            escopo = getattr(agente, "projects", [])
            contexto = self.memory.build_context(escopo, session, query)

            task.status = "running"
            task.updated_at = _agora()
            self.task_store.update(task)
            self._emit(EventType.TASK_ASSIGNED, correlation_id, task)

            resultado = agente.handle(task, contexto)

            task.status = "done" if resultado.success else "error"
            task.result = resultado.output
            task.updated_at = _agora()
            self.task_store.update(task)
            self._emit(
                EventType.AGENT_COMPLETED if resultado.success else EventType.AGENT_FAILED,
                correlation_id, task,
            )

            resultados.append(resultado)

        return resultados

    def _emit(self, tipo: str, correlation_id: str, task: Task) -> None:
        self.event_bus.publish(
            Event(
                type=tipo,
                correlation_id=correlation_id,
                source="workflow",
                payload={"task_id": task.id, "agent": task.agent, "status": task.status},
            )
        )
