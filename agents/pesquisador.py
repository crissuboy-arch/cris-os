"""
Agente: Pesquisador
Pesquisa, analisa e compara.
Separa PROMPTS, FERRAMENTAS (tools/research_tools.py), LOGICA.
"""

from agents.base_specialist import create_agent
from agents.prompts import PESQUISADOR_PROMPT
from tools.research_tools import get_tools

name = "pesquisador"
description = "Pesquisa, analisa concorrentes e identifica tendencias"
system_prompt = PESQUISADOR_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
