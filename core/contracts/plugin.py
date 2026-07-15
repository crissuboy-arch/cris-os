"""
Porta: Plugin.

Tudo que estende o CRIS OS é um plugin descoberto por manifesto: agentes (hoje),
e — na mesma mecânica — canais, ferramentas, provedores de LLM e adaptadores MCP
(próximas fases). O núcleo NUNCA importa um plugin concreto; o PluginManager os
descobre e registra. É assim que "novos agentes entram sem alterar o núcleo"
(princípio Aberto/Fechado — OCP).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

# Tipos de plugin previstos.
KIND_AGENT = "agent"
KIND_CHANNEL = "channel"
KIND_TOOL = "tool"
KIND_LLM = "llm"
KIND_MCP = "mcp"


@runtime_checkable
class Plugin(Protocol):
    name: str
    kind: str  # um dos KIND_*
