"""
PluginLoader — descobre plugins no diretorio plugins/, le manifestos,
instancia as classes e registra capabilities no CoreAPI.

Cada plugin recebe sua propria instancia de CoreAPI, isolada por nome.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from core.application.core_api import CoreAPI
from core.capability import CapabilityRegistry
from core.configuration import PluginConfigStore
from core.events import InProcessEventBus
from core.permission import SimplePermissionChecker
from core.plugins.base import PluginBase
from core.plugins.models import PluginManifest, PluginState

logger = logging.getLogger(__name__)


class PluginLoader:
    """Carrega plugins de um diretorio, conectando manifesto + classe + CoreAPI."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        event_bus: InProcessEventBus,
        plugins_dir: str | Path | None = None,
        config_store: PluginConfigStore | None = None,
        permission_checker: SimplePermissionChecker | None = None,
    ) -> None:
        self._registry = registry
        self._event_bus = event_bus
        self._config_store = config_store or PluginConfigStore()
        self._permission_checker = permission_checker or SimplePermissionChecker()
        self.plugins_dir = Path(plugins_dir) if plugins_dir else Path("plugins")
        self._loaded: dict[str, PluginBase] = {}
        self._unsubscribe_fns: list[callable] = []

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def load_all(self) -> dict[str, PluginBase]:
        """Descobre e carrega TODOS os plugins em plugins_dir."""
        if not self.plugins_dir.is_dir():
            logger.warning("Diretorio de plugins nao encontrado: %s", self.plugins_dir)
            return {}

        for entry in sorted(self.plugins_dir.iterdir()):
            if entry.is_dir() and (entry / "manifest.json").exists():
                try:
                    plugin = self._load_one(entry)
                    self._loaded[plugin.name] = plugin
                    logger.info("Plugin carregado: %s v%s", plugin.name, plugin.version)
                except Exception as exc:
                    logger.error("Falha ao carregar plugin em %s: %s", entry.name, exc)

        return dict(self._loaded)

    def start_all(self) -> None:
        """Ativa todos os plugins carregados."""
        for name, plugin in self._loaded.items():
            try:
                plugin.on_start()
                plugin.state = PluginState.ACTIVE
                logger.info("Plugin ativado: %s", name)
            except Exception as exc:
                plugin.state = PluginState.DEGRADED
                logger.error("Plugin %s entrou em estado DEGRADED: %s", name, exc)

    def stop_all(self) -> None:
        """Para todos os plugins ativos."""
        for fn in self._unsubscribe_fns:
            fn()
        for name, plugin in self._loaded.items():
            try:
                plugin.on_stop()
                plugin.state = PluginState.STOPPED
            except Exception as exc:
                logger.error("Plugin %s falhou ao parar: %s", name, exc)

    def get(self, name: str) -> PluginBase | None:
        return self._loaded.get(name)

    def list_loaded(self) -> list[str]:
        return list(self._loaded.keys())

    def get_core_api(self, plugin_name: str) -> CoreAPI:
        """Cria uma instancia de CoreAPI para o plugin especificado.

        Metodo publico para que AgentRuntime possa obter CoreAPI sem
        acessar atributos privados.
        """
        api = self._make_api(plugin_name)
        api._capability_executor = self.execute_capability
        return api

    # ------------------------------------------------------------------
    # Execucao de capabilities
    # ------------------------------------------------------------------

    def execute_capability(self, capability_name: str, input_data: dict, context: dict | None = None) -> dict:
        """Resolve e executa uma capability pelo nome, roteando ao plugin correto.

        Fluxo:
          1. Resolve a melhor capability via CapabilityRegistry
          2. Encontra o plugin que a registrou
          3. Chama plugin.execute() com dados de entrada
        """
        from core.capability.models import ResolveContext

        # Resolve qual plugin atende esta capability
        try:
            resolved = self._registry.resolve(
                capability_name,
                context=ResolveContext(caller_plugin_id="agent_runtime"),
            )
        except Exception as exc:
            logger.error("Capability '%s' nao encontrada: %s", capability_name, exc)
            return {"success": False, "error": f"Capability '{capability_name}' nao encontrada: {exc}"}

        plugin_id = resolved.capability.plugin_id
        plugin = self._loaded.get(plugin_id)

        if plugin is None:
            logger.error("Plugin '%s' nao carregado (capability: %s)", plugin_id, capability_name)
            return {"success": False, "error": f"Plugin '{plugin_id}' nao esta carregado"}

        logger.info(
            "Executando capability '%s' via plugin '%s' (health=%s)",
            capability_name, plugin_id, resolved.capability.health.value,
        )
        return plugin.execute(capability_name, input_data, context)

    def _make_api(self, plugin_name: str) -> CoreAPI:
        """Cria uma instancia de CoreAPI isolada para um plugin."""
        return CoreAPI(
            registry=self._registry,
            event_bus=self._event_bus,
            plugin_name=plugin_name,
            config_store=self._config_store,
            permission_checker=self._permission_checker,
        )

    def _load_one(self, plugin_dir: Path) -> PluginBase:
        manifest_data = json.loads((plugin_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest = PluginManifest.from_dict(manifest_data)

        py_files = list(plugin_dir.glob("*.py"))
        if not py_files:
            raise FileNotFoundError(f"Nenhum arquivo .py encontrado em {plugin_dir}")

        # Carrega o primeiro .py como modulo
        mod_path = py_files[0]
        spec = importlib.util.spec_from_file_location(
            f"plugins.{plugin_dir.name}", str(mod_path)
        )
        if not spec or not spec.loader:
            raise ImportError(f"Nao foi possivel carregar {mod_path}")

        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)

        # Busca a classe que herda de PluginBase
        plugin_cls: type[PluginBase] | None = None
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and issubclass(attr, PluginBase) and attr is not PluginBase:
                plugin_cls = attr
                break

        if not plugin_cls:
            raise TypeError(
                f"Nenhuma subclasse de PluginBase encontrada em {mod_path}"
            )

        # Cria CoreAPI ISOLADA para este plugin
        api = self._make_api(manifest.name)
        plugin = plugin_cls(manifest, api)

        # Registra capabilities
        for cap in manifest.capabilities:
            api.register_capability(
                name=cap.name,
                version=cap.version,
                priority=cap.priority,
                description=cap.description,
                input_schema=cap.input_schema,
                output_schema=cap.output_schema,
                timeout_ms=cap.timeout_ms,
                idempotent=cap.idempotent,
            )

        # Assina eventos
        for sub in manifest.subscriptions:
            def _make_handler(ptype: str, p: PluginBase) -> callable:
                def _handler(event):
                    if event.type == ptype:
                        try:
                            p.on_event(event)
                        except Exception:
                            logger.exception("[%s] Erro ao processar evento %s", p.name, ptype)
                return _handler

            handler = _make_handler(sub.event_type, plugin)
            unsubscribe = api.subscribe(sub.event_type, handler)
            self._unsubscribe_fns.append(unsubscribe)

        # Hook de instalacao
        plugin.on_install()
        return plugin