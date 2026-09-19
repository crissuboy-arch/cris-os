"""
Agente: Performance Agent (fundacao, Fase 6)
Le metricas REAIS/IMPORTADAS de uma campanha ja registradas no Project
Brain e diagnostica FATOS/HIPOTESES/RISCOS -- nunca inventa metrica. Sem
nenhum snapshot real/importado, responde deterministicamente que ainda nao
ha dados suficientes.
"""

from agents.base_specialist import create_agent
from agents.prompts import PERFORMANCE_AGENT_PROMPT
from tools.performance_agent_tools import get_tools

name = "performance_agent"
description = "Analisa metricas reais/importadas de uma campanha (nunca inventa dado)"
system_prompt = PERFORMANCE_AGENT_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
