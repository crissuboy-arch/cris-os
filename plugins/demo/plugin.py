"""
CRIS Demo Plugin — valida a arquitetura de plugins do Core.

Capacidades:
  - demo.hello: saudacao basica
  - demo.health: estado interno do plugin
  - demo.echo: ecoa parametros
  - demo.fallback: fallback explicito
  - demo.isolation: excecao proposital

Eventos:
  - Assina demo.ping e responde com demo.pong
"""

from __future__ import annotations

from typing import Any

from core.application.core_api import CoreAPI
from core.plugins.base import PluginBase
from core.plugins.models import PluginManifest


class DemoPlugin(PluginBase):
    """Plugin de demonstracao do CRIS OS."""

    def __init__(self, manifest: PluginManifest, api: CoreAPI) -> None:
        super().__init__(manifest, api)
        self._ping_count = 0

    # ------------------------------------------------------------------
    # Capacidades (chamadas pelo Core via execute)
    # ------------------------------------------------------------------

    def execute(self, capability_name: str, input_data: dict, context: dict | None = None) -> dict:
        t0 = self.api.now_ms()
        success = False
        try:
            result = self._dispatch(capability_name, input_data, context or {})
            success = True
            return result
        finally:
            duration = self.api.now_ms() - t0
            self.api.record_call(capability_name, duration, success)

    def _dispatch(self, name: str, data: dict, ctx: dict) -> dict:
        # --- demo.hello ---
        if name == "demo.hello":
            nome = data.get("name", "Mundo")
            return {
                "success": True,
                "greeting": f"Ola, {nome}! (do plugin {self.name} v{self.version})",
                "context": {"plugin": self.name, "state": self.state.value},
            }

        # --- demo.health ---
        if name == "demo.health":
            return {
                "success": True,
                "state": self.state.value,
                "version": self.version,
                "ping_count": self._ping_count,
            }

        # --- demo.echo ---
        if name == "demo.echo":
            return {"success": True, "echo": data, "plugin": self.name}

        # --- demo.fallback ---
        if name == "demo.fallback":
            return {
                "success": True,
                "message": "Fallback executado com sucesso — modo degradado ativo",
                "is_fallback": True,
            }

        # --- demo.isolation ---
        if name == "demo.isolation":
            trigger = data.get("trigger", "default")
            msg = f"Excecao proposital lancada pelo plugin {self.name} (trigger={trigger})"
            raise RuntimeError(msg)

        return {"success": False, "error": f"Capability desconhecida: {name}"}

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------

    def on_event(self, event: Any) -> None:
        if event.type == "demo.ping":
            self._ping_count += 1
            self.api.publish_event("demo.pong", plugin=self.name, ping_count=self._ping_count, original=event.payload)
            self.log_info("Recebido ping #%d", self._ping_count)

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def on_install(self) -> None:
        self.log_info("Plugin instalado com %d capabilities", len(self.manifest.capabilities))

    def on_start(self) -> None:
        self.log_info("Plugin ativado")

    def on_stop(self) -> None:
        self.log_info("Plugin desativado")

    def on_uninstall(self) -> None:
        self.log_info("Plugin removido")