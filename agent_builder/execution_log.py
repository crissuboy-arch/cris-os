"""
StudioExecutionLog — registro de execucoes do Studio para observabilidade.

Armazena em memoria (lista simples) com maximo de 100 entradas.
Cada execucao registra: agent, instruction, status, duration_ms,
capabilities_called, permissions_denied, memory_ops, errors.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

MAX_LOG_ENTRIES = 100


@dataclass
class ExecutionRecord:
    """Um registro de execucao do Studio."""
    id: str
    agent_id: str
    agent_name: str
    instruction: str
    status: str  # success | error | denied
    duration_ms: float = 0.0
    system_prompt: str = ""
    bindings_attempted: list[str] = field(default_factory=list)
    capabilities_called: list[dict] = field(default_factory=list)
    permissions_checked: list[dict] = field(default_factory=list)
    permissions_denied: list[str] = field(default_factory=list)
    memory_reads: list[dict] = field(default_factory=list)
    memory_writes: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    output: str = ""
    timestamp: float = field(default_factory=time.time)
    session: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "instruction": self.instruction,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "system_prompt": self.system_prompt,
            "bindings_attempted": self.bindings_attempted,
            "capabilities_called": self.capabilities_called,
            "permissions_checked": self.permissions_checked,
            "permissions_denied": self.permissions_denied,
            "memory_reads": self.memory_reads,
            "memory_writes": self.memory_writes,
            "errors": self.errors,
            "output": self.output,
            "timestamp": self.timestamp,
            "session": self.session,
        }


class StudioExecutionLog:
    """Armazena e recupera registros de execucao do Studio."""

    def __init__(self) -> None:
        self._records: list[ExecutionRecord] = []
        self._counter: int = 0

    def add(self, record: ExecutionRecord) -> None:
        self._records.append(record)
        # Trim old entries
        if len(self._records) > MAX_LOG_ENTRIES:
            self._records = self._records[-MAX_LOG_ENTRIES:]

    def create_record(
        self,
        agent_id: str,
        agent_name: str,
        instruction: str,
        session: str = "studio",
    ) -> ExecutionRecord:
        self._counter += 1
        record = ExecutionRecord(
            id=f"exec-{self._counter:06d}",
            agent_id=agent_id,
            agent_name=agent_name,
            instruction=instruction,
            status="running",
            session=session,
        )
        return record

    def list_all(self, limit: int = 50) -> list[dict]:
        """Lista os ultimos registros (mais recente primeiro)."""
        sorted_records = sorted(self._records, key=lambda r: r.timestamp, reverse=True)
        return [r.to_dict() for r in sorted_records[:limit]]

    def get(self, record_id: str) -> ExecutionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def get_by_agent(self, agent_id: str, limit: int = 20) -> list[dict]:
        filtered = [r for r in self._records if r.agent_id == agent_id]
        sorted_records = sorted(filtered, key=lambda r: r.timestamp, reverse=True)
        return [r.to_dict() for r in sorted_records[:limit]]

    def stats(self) -> dict:
        """Metricas basicas de todas as execucoes."""
        total = len(self._records)
        if total == 0:
            return {"total": 0, "success": 0, "error": 0, "denied": 0, "avg_duration_ms": 0}

        success = sum(1 for r in self._records if r.status == "success")
        error = sum(1 for r in self._records if r.status == "error")
        denied = sum(1 for r in self._records if r.status == "denied")
        avg_duration = sum(r.duration_ms for r in self._records) / total

        return {
            "total": total,
            "success": success,
            "error": error,
            "denied": denied,
            "avg_duration_ms": round(avg_duration, 2),
        }

    def clear(self) -> int:
        """Limpa todos os registros. Retorna quantos foram removidos."""
        count = len(self._records)
        self._records.clear()
        return count


# Singleton global para uso pelo backend
_execution_log = StudioExecutionLog()


def get_execution_log() -> StudioExecutionLog:
    return _execution_log
