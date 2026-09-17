"""
Agente: Opportunity Analyst
Investiga uma oferta do ScalaFlow cruzando sinais reais (TikTok, Instagram,
YouTube, Google Trends, historico do proprio ScalaFlow) e recomenda um
caminho via Decision Engine. Fase 2 do CRIS OS -- sem LLM, sem inventar dado.

Nao confundir com `scalaflow_intel` (lista/filtra anuncios). Este agente
INVESTIGA uma oferta especifica e decide um caminho, guardando tudo no
Project Brain (memory/project_brain.py).
"""

from agents.base_specialist import create_agent
from agents.prompts import OPPORTUNITY_ANALYST_PROMPT
from tools.opportunity_tools import get_tools

name = "opportunity_analyst"
description = "Investiga uma oferta do ScalaFlow (sinais reais multi-plataforma) e recomenda um caminho"
system_prompt = OPPORTUNITY_ANALYST_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
