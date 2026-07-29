"""
CoreAPI — facade unificada que o Core expoe para plugins.

Um plugin recebe uma instancia de CoreAPI e atraves dela acessa:

  - CapabilityRegistry (registrar/resolver capabilities)
  - EventBus (publicar/assinar eventos)
  - PluginManager (registro de plugins)
  - ConfigurationStore (configuracoes do plugin)
  - PermissionChecker (verificacao de permissoes)
  - Metodos utilitarios (health, metrics)

Isolamento: o plugin NAO tem acesso aos objetos internos do Core.
So ve o que a API expoe.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from core.capability import (
    Capability,
    CapabilityRegistry,
    CapabilityStatus,
    HealthStatus,
)
from core.capability.errors import CapabilityPermissionError
from core.configuration import PluginConfigStore
from core.domain.events import Event
from core.events import InProcessEventBus
from core.permission import SimplePermissionChecker

logger = logging.getLogger(__name__)


class CoreAPI:
    """Facade que o Core injeta nos plugins.

    Nao expoe implementacoes internas — apenas metodos de alto nivel.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        event_bus: InProcessEventBus,
        plugin_name: str,
        config_store: PluginConfigStore | None = None,
        permission_checker: SimplePermissionChecker | None = None,
        capability_executor: callable | None = None,
    ) -> None:
        self._registry = registry
        self._event_bus = event_bus
        self._plugin_name = plugin_name
        self._config = config_store or PluginConfigStore()
        self._permission = permission_checker or SimplePermissionChecker()
        self._capability_executor = capability_executor

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    @property
    def registry(self) -> CapabilityRegistry:
        return self._registry

    def register_capability(
        self,
        name: str,
        version: str = "1.0.0",
        priority: int = 50,
        description: str = "",
        input_schema: dict | None = None,
        output_schema: dict | None = None,
        timeout_ms: int = 30000,
        idempotent: bool = False,
    ) -> None:
        """Registra uma capability deste plugin no Registry."""
        cap = Capability(
            name=name,
            version=version,
            plugin_id=self._plugin_name,
            priority=priority,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            timeout_ms=timeout_ms,
            idempotent=idempotent,
            status=CapabilityStatus.ACTIVE,
            health=HealthStatus.OK,
        )
        self._registry.register(cap)
        logger.info("[%s] Capability registrada: %s v%s", self._plugin_name, name, version)

    def unregister_capability(self, name: str) -> None:
        """Remove uma capability deste plugin."""
        self._registry.unregister(name, self._plugin_name)

    # ------------------------------------------------------------------
    # Event Bus
    # ------------------------------------------------------------------

    def publish_event(self, event_type: str, **payload: Any) -> None:
        """Publica um evento no barramento."""
        event = Event(
            type=event_type,
            payload=payload,
            source=self._plugin_name,
        )
        self._event_bus.publish(event)

    def subscribe(self, event_type: str, handler) -> callable:
        """Assina um tipo de evento. Retorna funcao de unsubscribe."""
        return self._event_bus.subscribe(event_type, handler)

    # ------------------------------------------------------------------
    # Metricas
    # ------------------------------------------------------------------

    def record_call(self, name: str, duration_ms: int, success: bool) -> None:
        """Registra metrica de uma chamada de capability."""
        self._registry.record_call(name, self._plugin_name, duration_ms, success)

    def get_metrics(self, name: str) -> Any:
        """Retorna metricas de uma capability deste plugin."""
        return self._registry.get_metrics(name, self._plugin_name)

    def get_health(self, name: str) -> HealthStatus:
        """Retorna health de uma capability deste plugin."""
        return self._registry.get_health(name, self._plugin_name)

    def report_health(self, name: str, health: HealthStatus) -> None:
        """Define manualmente o health de uma capability."""
        self._registry.update_health(name, self._plugin_name, health)

    def record_success(self, name: str) -> None:
        """Registra sucesso (health tracker passivo)."""
        self._registry.record_success(name, self._plugin_name)

    def record_failure(self, name: str) -> None:
        """Registra falha (health tracker passivo)."""
        self._registry.record_failure(name, self._plugin_name)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def now_ms(self) -> int:
        return int(time.monotonic() * 1000)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @property
    def config(self):
        """Accesso a configuracao do plugin (escopo = nome do plugin)."""
        return self._config

    def get_config(self, key: str, default: str = "") -> str:
        """Retorna uma configuracao deste plugin."""
        return self._config.get(self._plugin_name, key, default)

    def set_config(self, key: str, value: str) -> None:
        """Define uma configuracao deste plugin."""
        self._config.set(self._plugin_name, key, value)

    def get_all_config(self) -> dict[str, str]:
        """Retorna todas as configuracoes deste plugin."""
        return self._config.get_all(self._plugin_name)

    def delete_config(self, key: str) -> bool:
        """Remove uma configuracao deste plugin."""
        return self._config.delete(self._plugin_name, key)

    # ------------------------------------------------------------------
    # Permission
    # ------------------------------------------------------------------

    @property
    def permission(self):
        """Accesso ao verificador de permissoes."""
        return self._permission

    def check_permission(self, capability_name: str) -> bool:
        """Verifica se este plugin tem permissao para chamar a capability."""
        return self._permission.check(self._plugin_name, capability_name)

    def require_permission(self, capability_name: str) -> None:
        """Verifica permissao. Levanta CapabilityPermissionError se negado."""
        self._permission.require(self._plugin_name, capability_name)

    # ------------------------------------------------------------------
    # Execucao de capabilities cross-plugin
    # ------------------------------------------------------------------

    def execute(self, capability_name: str, input_data: dict, context: dict | None = None) -> dict:
        """Executa uma capability de qualquer plugin.

        Usa o capability_executor fornecido (pelo PluginLoader, via AgentRuntime).
        Se nenhum executor foi configurado, retorna erro.
        """
        if self._capability_executor is None:
            logger.warning(
                "[%s] Nenhum capability_executor configurado — nao e possivel executar '%s'",
                self._plugin_name, capability_name,
            )
            return {"success": False, "error": "Agent Runtime nao configurou executor de capabilities"}
        return self._capability_executor(capability_name, input_data, context or {})