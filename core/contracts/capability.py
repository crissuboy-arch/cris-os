"""
Contratos do sistema de Capabilities.

Define os protocolos (interfaces) que o Core expõe e os plugins consomem.
O CapabilityEngine (futuro módulo) implementará estes contratos.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from core.capability.models import (
    Capability,
    CapabilityRegistryStats,
    CapabilityResult,
    CapabilityStatus,
    HealthStatus,
    ResolveContext,
    ResolvedCapability,
)


@runtime_checkable
class CapabilityProvider(Protocol):
    """Protocolo que um plugin deve implementar para fornecer uma capability.

    O método execute() é chamado pelo CapabilityEngine quando o Core resolve
    que este provider deve atender uma requisição.
    """

    @property
    def capability_name(self) -> str: ...

    @property
    def capability_version(self) -> str: ...

    def execute(self, input: dict, context: dict) -> CapabilityResult:
        """Executa a capability com o input e contexto fornecidos."""
        ...


@runtime_checkable
class CapabilityRegistryProtocol(Protocol):
    """Protocolo do Capability Registry exposto via CoreAPI."""

    def register(self, capability: Capability) -> None: ...
    def unregister(self, name: str, plugin_id: str) -> None: ...
    def unregister_plugin(self, plugin_id: str) -> None: ...

    def resolve(
        self,
        name: str,
        constraint: str | None = None,
        context: ResolveContext | None = None,
    ) -> ResolvedCapability: ...
    def resolve_all(
        self,
        name: str,
        constraint: str | None = None,
        context: ResolveContext | None = None,
    ) -> list[ResolvedCapability]: ...

    def find_by_name(self, name: str) -> list[Capability]: ...
    def find_by_plugin(self, plugin_id: str) -> list[Capability]: ...
    def find_by_domain(self, domain_prefix: str) -> list[Capability]: ...
    def get(self, name: str, plugin_id: str, version: str | None = None) -> Capability | None: ...
    def list_all(self) -> list[Capability]: ...
    def list_plugins(self) -> list[str]: ...

    def update_health(self, name: str, plugin_id: str, health: HealthStatus) -> None: ...
    def get_health(self, name: str, plugin_id: str) -> HealthStatus: ...

    def get_stats(self) -> CapabilityRegistryStats: ...


@runtime_checkable
class CapabilityEngineProtocol(Protocol):
    """Protocolo do Capability Engine (futuro módulo de execução)."""

    def call(
        self,
        name: str,
        input: dict,
        version: str | None = None,
        timeout: int | None = None,
    ) -> CapabilityResult: ...

    def call_with_context(
        self,
        name: str,
        input: dict,
        context: ResolveContext,
    ) -> CapabilityResult: ...

    def is_available(self, name: str, version: str | None = None) -> bool: ...


# Aliases para uso nos manifests dos plugins
CapabilityDef = dict[str, Any]
CapabilityRequire = dict[str, Any]
CapabilityProvide = dict[str, Any]