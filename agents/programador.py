"""
Agente: Programador
Gera codigo, corrige bugs, revisa.
Separa PROMPTS, FERRAMENTAS (tools/coding_tools.py), LOGICA.
"""

from agents.base_specialist import create_agent
from agents.prompts import PROGRAMADOR_PROMPT
from tools.coding_tools import get_tools

name = "programador"
description = "Gera codigo, corrige bugs, cria APIs e testes"
system_prompt = PROGRAMADOR_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
