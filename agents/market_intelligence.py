"""
Agente: Market Intelligence
Mostra a inteligência de mercado (handoffs vindos do ScalaFlow, via
`core/market_intelligence.py`) já recebida e persistida para o projeto em
foco. Fase 9 do CRIS OS -- fronteira de integração ScalaFlow <-> CRIS OS.

Este agente NAO recebe handoffs novos (isso é uma chamada Python direta a
`receive_intelligence`, feita por quem integrar o ScalaFlow) -- ele só
mostra o que já foi validado e persistido.
"""

from agents.base_specialist import create_agent
from agents.prompts import MARKET_INTELLIGENCE_PROMPT
from tools.market_intelligence_tools import get_tools

name = "market_intelligence"
description = "Mostra a inteligencia de mercado (ScalaFlow) ja recebida e persistida para o projeto em foco"
system_prompt = MARKET_INTELLIGENCE_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
