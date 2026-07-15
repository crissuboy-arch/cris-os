"""
Modelos de dados do núcleo (estruturas normalizadas que circulam pelo sistema).

São apenas dados (dataclasses), sem lógica de negócio nem dependências externas.
Por isso podem ser importados por qualquer camada sem criar acoplamento.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.domain.execution import Effect, ExecutionType


def _agora() -> str:
    """Data/hora atual em ISO-8601 (UTC)."""
    return datetime.now(timezone.utc).isoformat()


def _novo_id() -> str:
    """Identificador curto e único."""
    return uuid.uuid4().hex[:12]


@dataclass
class IncomingMessage:
    """Mensagem que CHEGA de um canal (Telegram, WhatsApp, ...), já normalizada."""

    channel: str  # ex.: "telegram"
    sender_id: str  # id do remetente naquele canal
    text: str
    raw: dict = field(default_factory=dict)  # payload original (opcional)
    timestamp: str = field(default_factory=_agora)

    @property
    def session(self) -> str:
        """Chave única da conversa (canal + remetente). Ex.: 'telegram:12345'."""
        return f"{self.channel}:{self.sender_id}"


@dataclass
class OutgoingMessage:
    """Mensagem que SAI para um canal."""

    channel: str
    recipient_id: str
    text: str


@dataclass
class KnowledgeItem:
    """Um fato da memória permanente (projeto, cliente, decisão, ideia, ...)."""

    type: str  # project | client | decision | idea | objective | priority
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    id: str = field(default_factory=_novo_id)
    created_at: str = field(default_factory=_agora)


@dataclass
class Task:
    """Uma ordem de serviço que o Orquestrador entrega a um agente."""

    agent: str  # nome do agente responsável
    instruction: str  # o que ele deve fazer
    id: str = field(default_factory=_novo_id)
    status: str = "pending"  # pending | running | done | error
    result: str | None = None
    created_at: str = field(default_factory=_agora)
    updated_at: str = field(default_factory=_agora)


@dataclass
class AgentResult:
    """O resultado que um agente devolve ao Orquestrador."""

    agent: str
    output: str
    success: bool = True
    metadata: dict = field(default_factory=dict)


@dataclass
class Passage:
    """Um trecho recuperado da Base de Conhecimento (L4)."""

    source: str  # de onde veio (arquivo, doc, repo...)
    text: str
    score: float = 0.0


@dataclass
class SkillResult:
    """
    Resultado padronizado de uma Skill.

    As skills PODEM devolver um SkillResult ou um dict (compatibilidade). O
    normalizador `of()` converte qualquer um dos dois em SkillResult, preservando
    campos extras do dict (ex.: action, handoff_id) dentro de `data`.
    """

    skill: str
    ok: bool = True
    output: str = ""  # texto legível (resumo)
    data: dict = field(default_factory=dict)  # payload estruturado
    error: str = ""  # preenchido em falha

    @classmethod
    def of(cls, value, skill: str = "") -> "SkillResult":
        """Normaliza um SkillResult ou um dict em SkillResult (tolerante)."""
        if isinstance(value, SkillResult):
            return value
        if isinstance(value, dict):
            padrao = {"ok", "skill", "summary", "output", "error", "data"}
            data = dict(value.get("data") or {})
            data.update({k: v for k, v in value.items() if k not in padrao})
            return cls(
                skill=value.get("skill", skill),
                ok=bool(value.get("ok", True)),
                output=value.get("summary") or value.get("output", ""),
                data=data,
                error=value.get("error", ""),
            )
        return cls(skill=skill, ok=True, output=str(value))


@dataclass
class ExecutionStep:
    """
    Unidade de trabalho decidida pelo IntentRouter: O QUÊ e para QUE tipo de
    executor. É a ENTRADA universal do ExecutionDispatcher (substitui a tupla
    `(nome, instrução)`). NÃO confundir com `core.domain.planning.PlanStep`
    (passo interno da camada de cognição).
    """

    name: str
    type: ExecutionType = ExecutionType.AGENT
    instruction: str = ""  # agentes (e skills sem schema)
    payload: dict = field(default_factory=dict)  # args estruturados (do input_schema)
    effect: Effect = Effect.READ_ONLY  # gate de confirmação: SENSITIVE exige confirmação humana
    # --- reservados p/ orquestração futura (ainda NÃO consumidos) ---
    priority: int = 0  # 0 = normal; maior = mais urgente
    parallel: bool = False  # pode rodar em paralelo com irmãos
    depends_on: list[str] = field(default_factory=list)  # steps que devem terminar antes
    timeout: float | None = None  # segundos; None = sem limite


@dataclass
class ExecutionResult:
    """
    Resultado UNIVERSAL de qualquer execução (agente, skill, tool, browser,
    planner, MCP, deepsearch, ...). É o ÚNICO DTO que o ResponseComposer conhece;
    todo produtor converge para cá via `of()`/`from_*()`.
    """

    source: str  # quem produziu (nome do agente/skill/tool)
    type: ExecutionType = ExecutionType.AGENT
    output: str = ""
    success: bool = True
    error: str = ""
    data: dict = field(default_factory=dict)

    @classmethod
    def from_agent(cls, r) -> "ExecutionResult":
        return cls(source=r.agent, type=ExecutionType.AGENT, output=r.output,
                   success=r.success, data=dict(r.metadata or {}))

    @classmethod
    def from_skill(cls, r) -> "ExecutionResult":
        return cls(source=r.skill, type=ExecutionType.SKILL,
                   output=r.output or r.error, success=r.ok, error=r.error,
                   data=dict(r.data or {}))

    @classmethod
    def of(cls, value, source: str = "",
           type: ExecutionType = ExecutionType.AGENT) -> "ExecutionResult":
        """Normaliza qualquer resultado em ExecutionResult (idempotente/tolerante)."""
        if isinstance(value, ExecutionResult):
            return value
        if isinstance(value, AgentResult):
            return cls.from_agent(value)
        if isinstance(value, SkillResult):
            return cls.from_skill(value)
        if isinstance(value, dict):
            return cls(source=value.get("source", source), type=type,
                       output=value.get("output", ""),
                       success=bool(value.get("success", True)),
                       error=value.get("error", ""), data=dict(value.get("data") or {}))
        return cls(source=source, type=type, output=str(value))

