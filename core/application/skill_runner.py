"""
SkillRunner — executa UMA Skill por nome, no fluxo de aplicação.

É o análogo do WorkflowEngine, mas focado SÓ em skills (não decide roteamento
nem fala com a Cris). Para uma skill:
  1. resolve o executor pelo SkillRegistry (cache + validação de contrato, B2);
  2. cria e persiste uma Task (pending -> running) — rastreio/retomada;
  3. monta o SkillContext (memória ESTREITA `SkillMemory` do B3 + `publish`);
  4. executa e **normaliza** o retorno para `SkillResult` (tolerando `dict`, D2);
  5. fecha a Task (done|error) e publica `skill.started/completed/failed`.

Depende só de PORTAS e DTOs do núcleo (registry, task_store, event_bus e uma
`SkillMemory` injetada) — o adaptador concreto de memória é montado no
composition root. NÃO toca o Orquestrador, o IntentRouter nem o WorkflowEngine.
"""

from __future__ import annotations

import logging

from core.domain.events import Event, EventType
from core.models import SkillResult, Task, _agora
from core.skills import SkillContext
from core.skills.registry import SkillLoadError

logger = logging.getLogger(__name__)


class SkillRunner:
    """Executa uma skill habilitada, com rastreio (Task) e eventos `skill.*`."""

    def __init__(self, skills, task_store, event_bus, skill_memory,
                 default_caller: str = "orchestrator") -> None:
        self.skills = skills
        self.task_store = task_store
        self.event_bus = event_bus
        self.skill_memory = skill_memory  # porta SkillMemory (injetada)
        self.default_caller = default_caller

    def run(self, name: str, payload: dict | None = None, session: str = "",
            correlation_id: str = "", caller: str = "") -> SkillResult:
        payload = payload or {}
        caller = caller or self.default_caller

        # 1) Resolve o executor (cache + validação vêm do registry, B2).
        try:
            executor = self.skills.load_executor(name)
        except SkillLoadError as e:
            return self._falha(name, correlation_id, str(e))
        if executor is None:
            return self._falha(name, correlation_id,
                               f"Skill '{name}' não é executável (sem executor).")

        # 2) Rastreio: Task pending -> running.
        task = Task(agent=name, instruction=str(payload.get("action", "run")), status="pending")
        self.task_store.save(task)
        self._emit(EventType.SKILL_STARTED, correlation_id,
                   {"skill": name, "task_id": task.id, "status": task.status})
        task.status = "running"
        task.updated_at = _agora()
        self.task_store.update(task)

        # 3) Executa com o contexto injetado (memória estreita + publish).
        ctx = SkillContext(session=session, memory=self.skill_memory,
                           publish=self.event_bus.publish,
                           correlation_id=correlation_id, caller=caller)
        try:
            bruto = executor.execute(payload, ctx)
            resultado = SkillResult.of(bruto, skill=name)
        except Exception as e:  # skill quebrou em runtime -> falha rastreável
            logger.exception("Skill '%s' falhou ao executar", name)
            resultado = SkillResult(skill=name, ok=False, error=str(e))

        # 4) Fecha a Task e emite o desfecho.
        task.status = "done" if resultado.ok else "error"
        task.result = resultado.output or resultado.error
        task.updated_at = _agora()
        self.task_store.update(task)
        self._emit(EventType.SKILL_COMPLETED if resultado.ok else EventType.SKILL_FAILED,
                   correlation_id, {"skill": name, "task_id": task.id, "ok": resultado.ok})
        return resultado

    # ------------------------------------------------------------------
    def _falha(self, name: str, correlation_id: str, erro: str) -> SkillResult:
        """Falha antes de executar (sem executor / executor inválido)."""
        self._emit(EventType.SKILL_FAILED, correlation_id,
                   {"skill": name, "ok": False, "error": erro})
        return SkillResult(skill=name, ok=False, error=erro)

    def _emit(self, tipo: str, correlation_id: str, payload: dict) -> None:
        self.event_bus.publish(Event(
            type=tipo, correlation_id=correlation_id or "",
            source="skill_runner", payload=payload,
        ))
