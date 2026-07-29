"""
Modelos de dados do Agent Builder.

Fase 3: estendido com instructions, memory, permissions, tools e binding sources.
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


class BindingSource(str, Enum):
    """De onde o valor do binding vem."""
    FIXED = "fixed"
    INPUT = "input"
    CONTEXT = "context"
    PREVIOUS_RESULT = "previous_result"


class MemoryType(str, Enum):
    """Tipos de memoria suportados."""
    NONE = "none"
    SESSION = "session"
    AGENT = "agent"
    PROJECT = "project"


# ======================================================================
# Binding
# ======================================================================


@dataclass
class CapabilityBinding:
    """Mapeia uma intencao (keyword) a uma chamada de capability.

    Fase 3: adiciona source (fixed/input/context/previous_result),
    context_path (para CONTEXT), default_value e type_hint.

    Exemplo:
        CapabilityBinding(
            keyword="criar nota",
            capability="notes.create",
            input_template={"title": "Nota: {instruction}", "content": "{instruction}"},
            source=BindingSource.INPUT,
        )
    """
    keyword: str
    capability: str
    input_template: dict = field(default_factory=lambda: {"input": "{instruction}"})
    description: str = ""
    priority: int = 50  # ordem de resolucao (maior = testado primeiro)
    source: str = BindingSource.INPUT
    context_path: str = ""  # ex: "user.name", "project.current"
    default_value: str = ""
    type_hint: str = ""  # str, int, float, bool, list, dict

    def to_dict(self) -> dict:
        d = {
            "keyword": self.keyword,
            "capability": self.capability,
            "input_template": self.input_template,
            "description": self.description,
            "priority": self.priority,
            "source": self.source if isinstance(self.source, str) else self.source.value,
            "context_path": self.context_path,
            "default_value": self.default_value,
            "type_hint": self.type_hint,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> CapabilityBinding:
        return cls(
            keyword=data["keyword"],
            capability=data["capability"],
            input_template=data.get("input_template", {"input": "{instruction}"}),
            description=data.get("description", ""),
            priority=data.get("priority", 50),
            source=data.get("source", BindingSource.INPUT),
            context_path=data.get("context_path", ""),
            default_value=data.get("default_value", ""),
            type_hint=data.get("type_hint", ""),
        )


# ======================================================================
# Instructions (Fase 3)
# ======================================================================


@dataclass
class AgentInstructions:
    """Instrucoes detalhadas do agente (monta o system prompt)."""
    role: str = ""
    objective: str = ""
    rules: list[str] = field(default_factory=list)
    restrictions: list[str] = field(default_factory=list)
    output_format: str = ""
    custom_prompt: str = ""

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "objective": self.objective,
            "rules": list(self.rules),
            "restrictions": list(self.restrictions),
            "output_format": self.output_format,
            "custom_prompt": self.custom_prompt,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentInstructions:
        return cls(
            role=data.get("role", ""),
            objective=data.get("objective", ""),
            rules=data.get("rules", []),
            restrictions=data.get("restrictions", []),
            output_format=data.get("output_format", ""),
            custom_prompt=data.get("custom_prompt", ""),
        )


# ======================================================================
# Memory config (Fase 3)
# ======================================================================


@dataclass
class MemoryConfig:
    """Configuracao de memoria do agente."""
    memory_type: str = MemoryType.NONE
    scope: list[str] = field(default_factory=list)  # projetos acessiveis ["*"] = todos
    read_enabled: bool = True
    write_enabled: bool = False
    project: str = ""  # projeto padrao para escrita

    def to_dict(self) -> dict:
        return {
            "memory_type": self.memory_type if isinstance(self.memory_type, str) else self.memory_type.value,
            "scope": list(self.scope),
            "read_enabled": self.read_enabled,
            "write_enabled": self.write_enabled,
            "project": self.project,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MemoryConfig:
        return cls(
            memory_type=data.get("memory_type", MemoryType.NONE),
            scope=data.get("scope", []),
            read_enabled=data.get("read_enabled", True),
            write_enabled=data.get("write_enabled", False),
            project=data.get("project", ""),
        )


# ======================================================================
# Permissions config (Fase 3)
# ======================================================================


@dataclass
class PermissionConfig:
    """Configuracao de permissoes do agente."""
    allowed_capabilities: list[str] = field(default_factory=list)
    denied_capabilities: list[str] = field(default_factory=list)
    require_confirmation: list[str] = field(default_factory=list)  # capabilities que exigem confirmacao

    def to_dict(self) -> dict:
        return {
            "allowed_capabilities": list(self.allowed_capabilities),
            "denied_capabilities": list(self.denied_capabilities),
            "require_confirmation": list(self.require_confirmation),
        }

    @classmethod
    def from_dict(cls, data: dict) -> PermissionConfig:
        return cls(
            allowed_capabilities=data.get("allowed_capabilities", []),
            denied_capabilities=data.get("denied_capabilities", []),
            require_confirmation=data.get("require_confirmation", []),
        )


# ======================================================================
# Tools config (Fase 3)
# ======================================================================


@dataclass
class ToolsConfig:
    """Configuracao de ferramentas do agente."""
    internal: list[str] = field(default_factory=list)  # nomes de tools internas
    http: list[dict] = field(default_factory=list)  # [{name, url, method, headers}]
    mcp: list[dict] = field(default_factory=list)  # [{name, server, tool}]

    def to_dict(self) -> dict:
        return {
            "internal": list(self.internal),
            "http": [dict(h) for h in self.http],
            "mcp": [dict(m) for m in self.mcp],
        }

    @classmethod
    def from_dict(cls, data: dict) -> ToolsConfig:
        return cls(
            internal=data.get("internal", []),
            http=data.get("http", []),
            mcp=data.get("mcp", []),
        )


# ======================================================================
# Config
# ======================================================================


@dataclass
class AgentConfig:
    """Configuracoes de execucao do agente."""
    timeout_ms: int = 30000
    max_iterations: int = 10
    allow_fallback: bool = True


# ======================================================================
# AgentDefinition (Fase 3: estendido)
# ======================================================================


@dataclass
class AgentDefinition:
    """Definicao completa de um agente.

    Fase 3: adiciona instructions, memory, permissions, tools.
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
    # --- Fase 3 fields ---
    instructions: AgentInstructions = field(default_factory=AgentInstructions)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    permissions: PermissionConfig = field(default_factory=PermissionConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "status": self.status if isinstance(self.status, str) else self.status.value,
            "bindings": [b.to_dict() for b in self.bindings],
            "config": {
                "timeout_ms": self.config.timeout_ms,
                "max_iterations": self.config.max_iterations,
                "allow_fallback": self.config.allow_fallback,
            },
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "published_at": self.published_at,
            # --- Fase 3 ---
            "instructions": self.instructions.to_dict(),
            "memory": self.memory.to_dict(),
            "permissions": self.permissions.to_dict(),
            "tools": self.tools.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentDefinition:
        bindings = [CapabilityBinding.from_dict(b) for b in data.get("bindings", [])]
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
            instructions=AgentInstructions.from_dict(data.get("instructions", {})),
            memory=MemoryConfig.from_dict(data.get("memory", {})),
            permissions=PermissionConfig.from_dict(data.get("permissions", {})),
            tools=ToolsConfig.from_dict(data.get("tools", {})),
        )