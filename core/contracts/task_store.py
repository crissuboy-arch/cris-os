"""
Porta: persistência de tarefas (TaskStore).

O WorkflowEngine grava cada Task e seu ciclo de vida (pending -> running -> done
| error). Persistir tarefas é o que permite ACOMPANHAR a execução e, no futuro,
RETOMAR tarefas inacabadas após um crash ou troca de máquina (failover).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.models import Task


@runtime_checkable
class TaskStore(Protocol):
    def save(self, task: Task) -> None: ...
    def update(self, task: Task) -> None: ...
    def get(self, task_id: str) -> Task | None: ...
    def list_by_status(self, status: str) -> list[Task]: ...
