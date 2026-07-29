"""Modelos do sistema de plugins — manifesto e estado."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PluginState(str, Enum):
    """Estado do ciclo de vida do plugin."""
    INSTALLED = "installed"
    ACTIVE = "active"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    UNINSTALLED = "uninstalled"


@dataclass
class CapabilityDef:
    """Declaracao de uma capability no manifesto do plugin."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    priority: int = 50
    input_schema: dict | None = None
    output_schema: dict | None = None
    timeout_ms: int = 30000
    idempotent: bool = False


@dataclass
class SubscriptionDef:
    """Declaracao de assinatura de evento no manifesto."""
    event_type: str
    description: str = ""


@dataclass
class PluginManifest:
    """Manifesto de um plugin — lido de manifest.json."""
    name: str
    version: str
    description: str = ""
    kind: str = "plugin"
    capabilities: list[CapabilityDef] = field(default_factory=list)
    subscriptions: list[SubscriptionDef] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    author: str = ""
    min_core_version: str = "1.0.0"

    @classmethod
    def from_dict(cls, data: dict) -> PluginManifest:
        caps = [CapabilityDef(**c) for c in data.get("capabilities", [])]
        subs = [SubscriptionDef(**s) for s in data.get("subscriptions", [])]
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            kind=data.get("kind", "plugin"),
            capabilities=caps,
            subscriptions=subs,
            dependencies=data.get("dependencies", []),
            author=data.get("author", ""),
            min_core_version=data.get("min_core_version", "1.0.0"),
        )