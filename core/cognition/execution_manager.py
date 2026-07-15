"""
ExecutionManager — EXECUTA o plano (com controle operacional).

Responsabilidade única: receber um Plan e levá-lo até o fim com robustez:
  - distribui cada PlanStep ao agente certo (via WorkflowEngine v3);
  - monitora o progresso;
  - reexecuta tarefas que falham (até max_retries);
  - detecta falhas;
  - controla timeout por passo.

Eventos que publicará (via Event Bus):
  EXECUTION_STARTED · EXECUTION_PROGRESS · TASK_RETRIED · TASK_TIMEOUT ·
  EXECUTION_COMPLETED

Relação com o v3: o WorkflowEngine continua sendo o "braço" que despacha o agente
e persiste a Task. O ExecutionManager é a "gerência" em volta: política de
retentativa, timeout, paralelismo e monitoramento.

⚠️ ESQUELETO: `execute()` levanta NotImplementedError de propósito.
"""

from __future__ import annotations

from core.domain.planning import ExecutionReport, Plan


class ExecutionManager:
    def __init__(self, workflow_engine, event_bus,
                 default_timeout: int = 120, max_retries: int = 1) -> None:
        self.workflow = workflow_engine
        self.event_bus = event_bus
        self.default_timeout = default_timeout
        self.max_retries = max_retries

    def execute(self, plan: Plan) -> ExecutionReport:
        """
        TODO (pós-revisão):
          - publicar EXECUTION_STARTED;
          - para cada PlanStep (respeitando depends_on; paralelo quando possível):
              * despachar via WorkflowEngine;
              * aplicar timeout (TASK_TIMEOUT) e retentativas (TASK_RETRIED);
              * publicar EXECUTION_PROGRESS;
          - montar o ExecutionReport (resultados, falhas, completed);
          - publicar EXECUTION_COMPLETED;
          - devolver o relatório.
        """
        raise NotImplementedError(
            "ExecutionManager.execute ainda não implementado (camada de cognição em "
            "evolução arquitetural)."
        )
