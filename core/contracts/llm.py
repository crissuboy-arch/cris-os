"""
Porta: provedor de modelo de linguagem (LLM).

O núcleo fala com QUALQUER modelo através desta interface. Hoje a implementação
é o Ollama (local); amanhã pode ser Claude Code ou outro, sem mudar o núcleo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ToolCall:
    """Uma chamada de função/ferramenta que o modelo decidiu fazer."""

    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Resposta do modelo: texto e/ou chamadas de ferramentas."""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


@runtime_checkable
class LLMProvider(Protocol):
    """Contrato que todo provedor de LLM deve cumprir."""

    def is_alive(self) -> bool:
        """True se o provedor está acessível."""
        ...

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """
        Envia uma lista de mensagens (role/content) e devolve a resposta.

        Se `tools` for informado (JSON schema de funções), o modelo pode
        responder com `tool_calls` em vez de texto puro.
        """
        ...
