"""
Modelos de dados do Agent Builder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEACTIVATED = "deactivated"
    ARCHIVED = "archived"


@dataclass
class CapabilityBinding:
    """Mapeia uma intencao (keyword) a uma chamada de capability.

    Exemplo:
        CapabilityBinding(
            keyword="criar nota",
            capability="notes.create",
            input_template={"title": "Nota: {instruction}", "content": "{instruction}"},
        )
    """
    keyword: str
    capability: str
    input_template: dict = field(default_factory=lambda: {"input": "{instruction}"})
    description: str = ""
    priority: int = 50  # ordem de resolucao (maior = testado primeiro)


@dataclass
class AgentConfig:
    """Configuracoes de execucao do agente."""
    timeout_ms: int = 30000
    max_iterations: int = 10
    allow_fallback: bool = True


@dataclass
class AgentDefinition:
    """Definicao completa de um agente.

    E a representacao canonica — o "source of truth" de um agente no Agent Builder.
    Persistida como artefato independente (diretorio com manifest.json).
    """
    agent_id: str
    name: str
    version: str
    description: str
    status: str = AgentStatus.DRAFT
    bindings: list[CapabilityBinding] = field(default_factory=list)
    config: AgentConfig = field(default_factory=AgentConfig)
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=_agora)
    updated_at: str = field(default_factory=_agora)
    published_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "status": self.status if isinstance(self.status, str) else self.status.value,
            "bindings": [
                {
                    "keyword": b.keyword,
                    "capability": b.capability,
                    "input_template": b.input_template,
                    "description": b.description,
                    "priority": b.priority,
                }
                for b in self.bindings
            ],
            "config": {
                "timeout_ms": self.config.timeout_ms,
                "max_iterations": self.config.max_iterations,
                "allow_fallback": self.config.allow_fallback,
            },
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "published_at": self.published_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentDefinition:
        bindings = [
            CapabilityBinding(
                keyword=b["keyword"],
                capability=b["capability"],
                input_template=b.get("input_template", {"input": "{instruction}"}),
                description=b.get("description", ""),
                priority=b.get("priority", 50),
            )
            for b in data.get("bindings", [])
        ]
        cfg = data.get("config", {})
        config = AgentConfig(
            timeout_ms=cfg.get("timeout_ms", 30000),
            max_iterations=cfg.get("max_iterations", 10),
            allow_fallback=cfg.get("allow_fallback", True),
        )
        return cls(
            agent_id=data["agent_id"],
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            status=data.get("status", AgentStatus.DRAFT),
            bindings=bindings,
            config=config,
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", _agora()),
            updated_at=data.get("updated_at", _agora()),
            published_at=data.get("published_at"),
        )