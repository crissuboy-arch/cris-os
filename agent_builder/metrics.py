"""
StudioMetrics — engine de metricas para execucoes do Studio.

Registra metricas por agente, capability, plugin, e gerais.
Suporta aggregacao temporal (ultima hora, dia, semana).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Buckets de tempo em segundos
BUCKET_HOUR = 3600
BUCKET_DAY = 86400
BUCKET_WEEK = 604800


@dataclass
class MetricEntry:
    """Uma entrada de metrica."""
    agent_id: str
    agent_name: str
    capability: str
    plugin: str
    success: bool
    duration_ms: float
    timestamp: float = field(default_factory=time.time)
    session: str = ""
    error: str = ""
    memory_read: bool = False
    memory_write: bool = False
    permission_denied: bool = False


class StudioMetrics:
    """Engine de metricas do Studio."""

    def __init__(self) -> None:
        self._entries: list[MetricEntry] = []
        self._max_entries = 500

    def record(self, entry: MetricEntry) -> None:
        """Registra uma entrada de metrica."""
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

    def record_from_log(self, log_entry: dict) -> None:
        """Registra metrica a partir de um execution log entry."""
        caps = log_entry.get("capabilities_called", [])
        perm_denied = len(log_entry.get("permissions_denied", [])) > 0
        mem_reads = len(log_entry.get("memory_reads", [])) > 0
        mem_writes = len(log_entry.get("memory_writes", [])) > 0

        for cap_info in caps:
            cap_name = cap_info.get("capability", "unknown") if isinstance(cap_info, dict) else str(cap_info)
            self.record(MetricEntry(
                agent_id=log_entry.get("agent_id", ""),
                agent_name=log_entry.get("agent_name", ""),
                capability=cap_name,
                plugin=cap_name.split(".")[0] if "." in cap_name else "",
                success=log_entry.get("status") == "success",
                duration_ms=log_entry.get("duration_ms", 0),
                session=log_entry.get("session", ""),
                error=", ".join(log_entry.get("errors", [])),
                memory_read=mem_reads,
                memory_write=mem_writes,
                permission_denied=perm_denied,
            ))

    def summary(self, since_s: float | None = None) -> dict:
        """Resumo geral de metricas."""
        entries = self._filter_since(since_s)
        total = len(entries)
        if total == 0:
            return self._empty_summary()

        success = sum(1 for e in entries if e.success)
        errors = total - success
        durations = [e.duration_ms for e in entries if e.duration_ms > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0
        p95 = self._percentile(durations, 0.95)
        p99 = self._percentile(durations, 0.99)

        # By agent
        by_agent: dict[str, dict] = {}
        for e in entries:
            key = e.agent_name or "unknown"
            if key not in by_agent:
                by_agent[key] = {"total": 0, "success": 0, "error": 0, "avg_ms": 0, "durations": []}
            by_agent[key]["total"] += 1
            if e.success:
                by_agent[key]["success"] += 1
            else:
                by_agent[key]["error"] += 1
            by_agent[key]["durations"].append(e.duration_ms)

        for agent_data in by_agent.values():
            ds = agent_data["durations"]
            agent_data["avg_ms"] = round(sum(ds) / len(ds), 2) if ds else 0
            del agent_data["durations"]

        # By capability
        by_capability: dict[str, dict] = {}
        for e in entries:
            key = e.capability or "unknown"
            if key not in by_capability:
                by_capability[key] = {"total": 0, "success": 0, "error": 0}
            by_capability[key]["total"] += 1
            if e.success:
                by_capability[key]["success"] += 1
            else:
                by_capability[key]["error"] += 1

        # Memory
        memory_reads = sum(1 for e in entries if e.memory_read)
        memory_writes = sum(1 for e in entries if e.memory_write)
        permissions_denied = sum(1 for e in entries if e.permission_denied)

        return {
            "total": total,
            "success": success,
            "error": errors,
            "success_rate": round(success / total * 100, 1) if total > 0 else 0,
            "avg_duration_ms": round(avg_duration, 2),
            "p95_duration_ms": round(p95, 2),
            "p99_duration_ms": round(p99, 2),
            "by_agent": by_agent,
            "by_capability": by_capability,
            "memory_reads": memory_reads,
            "memory_writes": memory_writes,
            "permissions_denied": permissions_denied,
        }

    def agent_summary(self, agent_id: str, since_s: float | None = None) -> dict:
        """Metricas de um agente especifico."""
        entries = [e for e in self._filter_since(since_s) if e.agent_id == agent_id]
        total = len(entries)
        if total == 0:
            return {"agent_id": agent_id, "total": 0}

        success = sum(1 for e in entries if e.success)
        durations = [e.duration_ms for e in entries if e.duration_ms > 0]

        return {
            "agent_id": agent_id,
            "total": total,
            "success": success,
            "error": total - success,
            "success_rate": round(success / total * 100, 1),
            "avg_duration_ms": round(sum(durations) / len(durations), 2) if durations else 0,
        }

    def recent(self, limit: int = 20) -> list[dict]:
        """Ultimas entradas de metricas."""
        sorted_entries = sorted(self._entries, key=lambda e: e.timestamp, reverse=True)
        return [
            {
                "agent_name": e.agent_name,
                "capability": e.capability,
                "success": e.success,
                "duration_ms": e.duration_ms,
                "timestamp": e.timestamp,
                "error": e.error,
            }
            for e in sorted_entries[:limit]
        ]

    def clear(self) -> int:
        count = len(self._entries)
        self._entries.clear()
        return count

    def _filter_since(self, since_s: float | None) -> list[MetricEntry]:
        if since_s is None:
            return list(self._entries)
        cutoff = time.time() - since_s
        return [e for e in self._entries if e.timestamp >= cutoff]

    @staticmethod
    def _percentile(values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = int(len(sorted_vals) * pct)
        idx = min(idx, len(sorted_vals) - 1)
        return sorted_vals[idx]

    @staticmethod
    def _empty_summary() -> dict:
        return {
            "total": 0, "success": 0, "error": 0, "success_rate": 0,
            "avg_duration_ms": 0, "p95_duration_ms": 0, "p99_duration_ms": 0,
            "by_agent": {}, "by_capability": {},
            "memory_reads": 0, "memory_writes": 0, "permissions_denied": 0,
        }


# Singleton
_metrics: StudioMetrics | None = None


def get_metrics() -> StudioMetrics:
    global _metrics
    if _metrics is None:
        _metrics = StudioMetrics()
    return _metrics
