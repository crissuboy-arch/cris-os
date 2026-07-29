"""Metrics — coleta e expõe métricas de chamadas de capabilities."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class CapabilityMetrics:
    """Métricas agregadas por capability + plugin."""

    call_count: int = 0
    error_count: int = 0
    total_duration_ms: int = 0
    max_duration_ms: int = 0
    min_duration_ms: int = 0

    @property
    def avg_duration_ms(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.total_duration_ms / self.call_count

    @property
    def error_rate(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.error_count / self.call_count


@dataclass
class MetricsSnapshot:
    """Snapshot das métricas para um período."""

    total_calls: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0


class MetricsCollector:
    """Coleta métricas de chamadas de capabilities com segurança thread."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._capability_metrics: dict[str, dict[str, CapabilityMetrics]] = defaultdict(
            lambda: defaultdict(CapabilityMetrics)
        )
        self._latencies: dict[str, list[int]] = defaultdict(list)

    def _key(self, name: str, plugin_id: str) -> str:
        return f"{plugin_id}:{name}"

    def record_call(self, name: str, plugin_id: str, duration_ms: int, success: bool) -> None:
        """Registra uma chamada de capability."""
        with self._lock:
            m = self._capability_metrics[name][plugin_id]
            m.call_count += 1
            m.total_duration_ms += duration_ms
            if duration_ms > m.max_duration_ms:
                m.max_duration_ms = duration_ms
            if m.min_duration_ms == 0 or duration_ms < m.min_duration_ms:
                m.min_duration_ms = duration_ms
            if not success:
                m.error_count += 1

            k = self._key(name, plugin_id)
            self._latencies[k].append(duration_ms)
            # Mantém só os últimos 1000
            if len(self._latencies[k]) > 1000:
                self._latencies[k] = self._latencies[k][-1000:]

    def get_metrics(self, name: str, plugin_id: str) -> CapabilityMetrics:
        """Retorna métricas de uma capability específica."""
        with self._lock:
            return self._capability_metrics.get(name, {}).get(
                plugin_id, CapabilityMetrics()
            )

    def get_snapshot(self, name: str, plugin_id: str) -> MetricsSnapshot:
        """Retorna um snapshot com percentis."""
        with self._lock:
            m = self._capability_metrics.get(name, {}).get(plugin_id, CapabilityMetrics())
            k = self._key(name, plugin_id)
            lats = sorted(self._latencies.get(k, []))

            snapshot = MetricsSnapshot(
                total_calls=m.call_count,
                total_errors=m.error_count,
                avg_latency_ms=m.avg_duration_ms,
            )

            if lats:
                n = len(lats)
                snapshot.p50_latency_ms = lats[n // 2]
                snapshot.p95_latency_ms = lats[int(n * 0.95)]
                snapshot.p99_latency_ms = lats[int(n * 0.99)]

            return snapshot

    def get_all_metrics(self) -> dict[str, dict[str, CapabilityMetrics]]:
        """Retorna todas as métricas (para observability)."""
        with self._lock:
            return {
                name: dict(plugins)
                for name, plugins in self._capability_metrics.items()
            }

    def reset(self, name: str | None = None, plugin_id: str | None = None) -> None:
        """Reseta métricas."""
        with self._lock:
            if name and plugin_id:
                self._capability_metrics.get(name, {}).pop(plugin_id, None)
                self._latencies.pop(self._key(name, plugin_id), None)
            elif name:
                self._capability_metrics.pop(name, None)
                self._latencies = {
                    k: v for k, v in self._latencies.items()
                    if not k.endswith(f":{name}")
                }
            else:
                self._capability_metrics.clear()
                self._latencies.clear()