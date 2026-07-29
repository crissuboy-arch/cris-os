"""
PluginBase — classe base para plugins do CRIS OS.

Um plugin e:
  - Um diretorio com manifest.json declarando capabilities + subscriptions
  - Uma classe Python que herda de PluginBase e implementa os handlers

O PluginLoader le o manifesto, instancia o plugin, registra capabilities
no CapabilityRegistry e assina eventos no EventBus.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from core.application.core_api import CoreAPI
from core.plugins.models import PluginManifest, PluginState

logger = logging.getLogger(__name__)


class PluginBase(ABC):
    """Classe base para todos os plugins.

    Subclasses devem implementar:
      - execute(capability_name, input, context) -> dict
      - on_event(event) -> None  (se assinar eventos)
      - on_install() / on_uninstall() (opcional)
    """

    def __init__(self, manifest: PluginManifest, api: CoreAPI) -> None:
        self.manifest = manifest
        self.api = api
        self.state = PluginState.INSTALLED

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def kind(self) -> str:
        return self.manifest.kind

    @property
    def version(self) -> str:
        return self.manifest.version

    # ------------------------------------------------------------------
    # Ciclo de vida — hook methods
    # ------------------------------------------------------------------

    def on_install(self) -> None:
        """Chamado apos o plugin ser instalado e registrado."""

    def on_start(self) -> None:
        """Chamado quando o plugin e ativado."""

    def on_stop(self) -> None:
        """Chamado quando o plugin e desativado."""

    def on_uninstall(self) -> None:
        """Chamado antes do plugin ser removido."""

    # ------------------------------------------------------------------
    # Handlers obrigatorios
    # ------------------------------------------------------------------

    @abstractmethod
    def execute(self, capability_name: str, input_data: dict, context: dict | None = None) -> dict:
        """Executa uma capability deste plugin.

        Args:
            capability_name: Nome da capability a executar.
            input_data: Dados de entrada.
            context: Contexto de execucao (opcional).

        Returns:
            Dict com resultado (deve conter ao menos 'success': bool).
        """

    def on_event(self, event: Any) -> None:
        """Callback para eventos assinados.

        Sobrescreva se o plugin assinar eventos.
        """
        pass

    # ------------------------------------------------------------------
    # Metricas
    # ------------------------------------------------------------------

    def record_metric(self, name: str, plugin_id: str, duration_ms: int, success: bool) -> None:
        """Registra metrica de chamada de capability."""
        self.api.registry.record_call(name, plugin_id, duration_ms, success)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log_info(self, msg: str, *args: Any) -> None:
        logger.info("[%s] %s", self.name, msg % args if args else msg)

    def log_error(self, msg: str, *args: Any) -> None:
        logger.error("[%s] %s", self.name, msg % args if args else msg)