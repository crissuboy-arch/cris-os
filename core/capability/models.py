"""
Modelos de dados do sistema de Capabilities.

Define as estruturas que circulam pelo Capability Registry e Capability Engine:
- Capability: a definição de uma capacidade
- CapabilityResult: o retorno de uma chamada
- CapabilityContext: o contexto de quem chamou
- Enums de status, health e estratégias de fallback
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _novo_id() -> str:
    return uuid.uuid4().hex[:12]


class CapabilityStatus(str, Enum):
    """Status de uma capability no registro."""
    ACTIVE = "active"
    DEGRADED = "degraded"
    DEPRECATED = "deprecated"
    REMOVED = "removed"

    def __str__(self) -> str:
        return self.value


class HealthStatus(str, Enum):
    """Estado de saúde de uma capability."""
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value


class FallbackStrategy(str, Enum):
    """Estratégia de fallback quando o provider primário falha."""
    FAILOVER = "failover"
    CIRCUIT_BREAKER = "circuit_breaker"
    DEGRADED = "degraded"
    FALLBACK_VALUE = "fallback_value"

    def __str__(self) -> str:
        return self.value


class ConflictStrategy(str, Enum):
    """Como resolver conflitos quando dois plugins têm a mesma capability."""
    HIGHEST_PRIORITY = "highest_priority"
    HIGHEST_VERSION = "highest_version"
    BEST_HEALTH = "best_health"
    COMPOSITE_SCORE = "composite_score"

    def __str__(self) -> str:
        return self.value


@dataclass
class Capability:
    """Uma capacidade que um plugin EXPÕE para o resto do sistema.

    Attributes:
        name: Nome único da capability (ex.: "email.send")
        version: Versão semver (ex.: "1.2.0")
        plugin_id: Identificador do plugin que fornece esta capability
        priority: Prioridade 0-100. Maior = preferido em caso de múltiplos providers
        input_schema: JSON Schema do input esperado
        output_schema: JSON Schema do output retornado
        config_schema: JSON Schema da configuração da capability
        timeout_ms: Timeout máximo de execução em milissegundos
        idempotent: Se verdadeiro, pode ser repetido sem efeito colateral
        status: Status atual no registro
        health: Estado de saúde atual
        routing_rules: Regras contextuais de roteamento
        description: Descrição legível do que esta capability faz
    """

    name: str
    version: str
    plugin_id: str
    priority: int = 50
    input_schema: dict | None = None
    output_schema: dict | None = None
    config_schema: dict | None = None
    timeout_ms: int = 30000
    idempotent: bool = False
    status: CapabilityStatus = CapabilityStatus.ACTIVE
    health: HealthStatus = HealthStatus.UNKNOWN
    routing_rules: dict | None = None
    description: str = ""
    id: str = field(default_factory=_novo_id)
    registered_at: str = field(default_factory=_agora)
    updated_at: str = field(default_factory=_agora)


@dataclass
class CapabilityResult:
    """Resultado de uma chamada de capability.

    Attributes:
        success: Se a execução foi bem-sucedida
        output: Dado de saída (validado contra output_schema)
        error: Mensagem de erro em caso de falha
        provider_plugin_id: Plugin que executou (preenchido pelo Engine)
        provider_version: Versão usada (preenchido pelo Engine)
        duration_ms: Tempo de execução em ms
        correlation_id: ID de correlação para rastreamento
    """

    success: bool
    output: Any = None
    error: str | None = None
    provider_plugin_id: str = ""
    provider_version: str = ""
    duration_ms: int = 0
    correlation_id: str = ""


@dataclass
class CapabilityContext:
    """Contexto injetado pelo Core ao chamar um provider.

    Attributes:
        caller_plugin_id: Plugin que solicitou a chamada
        session_id: Sessão atual
        user_id: Usuário que iniciou a ação
        correlation_id: ID de correlação
        execution_id: ID da execução (se dentro de um agent run)
        metadata: Dados extras (environment, tags, etc.)
    """

    caller_plugin_id: str
    session_id: str = ""
    user_id: str = ""
    correlation_id: str = ""
    execution_id: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class CapabilityRegistration:
    """Registro interno de uma capability no registry (inclui runtime)."""

    capability: Capability
    call_count: int = 0
    error_count: int = 0
    total_duration_ms: int = 0
    last_called_at: str | None = None
    last_error_at: str | None = None

    @property
    def avg_latency_ms(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.total_duration_ms / self.call_count

    @property
    def error_rate(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.error_count / self.call_count


@dataclass
class ResolvedCapability:
    """Resultado da resolução: uma capability pronta para uso, com score."""

    capability: Capability
    score: float = 1.0


@dataclass
class ResolveContext:
    """Contexto para resolução de capability.

    Attributes:
        caller_plugin_id: Quem está chamando
        prefer_plugin_id: Provider preferido (se caller quiser sugerir)
        min_version: Versão mínima aceita
        tags: Tags para roteamento contextual
    """

    caller_plugin_id: str
    prefer_plugin_id: str | None = None
    min_version: str | None = None
    tags: dict[str, str] | None = None


@dataclass
class CapabilityRegistryStats:
    """Estatísticas do registry."""

    total_capabilities: int = 0
    total_plugins: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_health: dict[str, int] = field(default_factory=dict)
    total_calls: int = 0
    total_errors: int = 0
    cache_hit_ratio: float = 0.0