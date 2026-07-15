"""
PluginManager — descobre e registra plugins (começando pelos agentes).

Hoje os agentes são plugins descobertos por `manifest.json`. O runtime (raiz de
composição) carrega via agents/loader e **injeta** os agentes aqui — o manager não
importa nenhum plugin concreto. Canais, ferramentas, provedores e adaptadores MCP
entram na mesma mecânica nas próximas fases. Adicionar um agente = criar uma pasta.
"""

from __future__ import annotations

import logging

from core.registry import AgentRegistry, ToolRegistry

logger = logging.getLogger(__name__)


class PluginManager:
    def __init__(self) -> None:
        self.agents = AgentRegistry()
        self.tools = ToolRegistry()

    def register_agents(self, agentes) -> AgentRegistry:
        """Registra os agentes já carregados (injetados pelo runtime)."""
        for agente in agentes:
            self.agents.register(agente)
        logger.info("PluginManager registrou agentes: %s", ", ".join(self.agents.names()))
        return self.agents

    # TODO (próximas fases): discover_tools(), discover_channels(), discover_mcp()
    # seguindo a mesma descoberta por manifesto.
