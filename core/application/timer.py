"""
Timer de latência — mede cada etapa em milissegundos.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class StageTimer:
    """Acumula tempos por etapa nomeada."""

    def __init__(self) -> None:
        self._steps: dict[str, float] = {}
        self._stack: list[tuple[str, float]] = []

    def begin(self, name: str) -> None:
        self._stack.append((name, time.perf_counter()))

    def end(self, name: str | None = None) -> float:
        if not self._stack:
            return 0.0
        n, t0 = self._stack.pop()
        key = name or n
        elapsed = (time.perf_counter() - t0) * 1000
        self._steps[key] = round(elapsed, 1)
        return elapsed

    def mark(self, name: str) -> float:
        elapsed = (time.perf_counter() - self._stack[-1][1]) * 1000
        self._steps[name] = round(elapsed, 1)
        return elapsed

    def get(self, name: str) -> float:
        return self._steps.get(name, 0.0)

    def report(self) -> str:
        if not self._steps:
            return ""
        total = sum(self._steps.values())
        lines = [f"  {k}: {v:>8.1f}ms" for k, v in self._steps.items()]
        lines.append(f"  {'TOTAL':22s} {total:>8.1f}ms")
        return "\n".join(lines)
