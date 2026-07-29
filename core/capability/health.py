"""Health tracker — monitora o estado de saúde das capabilities passivamente.

O health é atualizado com base nos resultados das chamadas:
  - Sucesso → mantém ou melhora health
  - Falha consecutiva → rebaixa health
  - Timeout → rebaixa health
  - Recuperação após falhas → sobe health gradualmente
"""

from __future__ import annotations

from core.capability.models import HealthStatus


class HealthTracker:
    """Rastreia a saúde de capabilities baseado em histórico de chamadas.

    Regras:
      - 5 sucessos consecutivos → OK
      - 3 falhas consecutivas → DEGRADED
      - 5 falhas consecutivas → DOWN
      - 1 sucesso após DOWN → DEGRADED
    """

    def __init__(self) -> None:
        self._consecutive_failures: dict[str, int] = {}
        self._consecutive_successes: dict[str, int] = {}

    def _key(self, name: str, plugin_id: str) -> str:
        return f"{plugin_id}:{name}"

    def record_success(self, name: str, plugin_id: str) -> HealthStatus:
        """Registra um sucesso e retorna o novo health."""
        k = self._key(name, plugin_id)
        self._consecutive_successes[k] = self._consecutive_successes.get(k, 0) + 1
        self._consecutive_failures[k] = 0

        if self._consecutive_successes[k] >= 5:
            return HealthStatus.OK
        if self._consecutive_successes[k] >= 1 and self._consecutive_failures.get(k, 0) == 0:
            # Se estava DOWN, 1 sucesso sobe para DEGRADED
            return HealthStatus.DEGRADED
        return HealthStatus.UNKNOWN

    def record_failure(self, name: str, plugin_id: str) -> HealthStatus:
        """Registra uma falha e retorna o novo health."""
        k = self._key(name, plugin_id)
        self._consecutive_failures[k] = self._consecutive_failures.get(k, 0) + 1
        self._consecutive_successes[k] = 0

        fails = self._consecutive_failures[k]
        if fails >= 5:
            return HealthStatus.DOWN
        if fails >= 3:
            return HealthStatus.DEGRADED
        return HealthStatus.OK

    def get_health(self, name: str, plugin_id: str) -> HealthStatus | None:
        """Retorna o health deduzido pelo histórico, ou None se sem histórico."""
        k = self._key(name, plugin_id)
        fails = self._consecutive_failures.get(k, 0)
        succs = self._consecutive_successes.get(k, 0)

        if fails == 0 and succs == 0:
            return None
        if fails >= 5:
            return HealthStatus.DOWN
        if fails >= 3:
            return HealthStatus.DEGRADED
        if succs >= 5:
            return HealthStatus.OK
        if succs >= 1:
            return HealthStatus.DEGRADED  # recovering from failures or low success count
        return HealthStatus.UNKNOWN

    def reset(self, name: str, plugin_id: str) -> None:
        """Reseta o histórico para uma capability."""
        k = self._key(name, plugin_id)
        self._consecutive_failures.pop(k, None)
        self._consecutive_successes.pop(k, None)