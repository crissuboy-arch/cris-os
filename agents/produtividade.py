"""
Agente: Produtividade
Planejamento, organizacao e produtividade.
Separa PROMPTS, FERRAMENTAS (tools/productivity_tools.py), LOGICA.
"""

from agents.base_specialist import create_agent
from agents.prompts import PRODUTIVIDADE_PROMPT
from tools.productivity_tools import get_tools

name = "produtividade"
description = "Planeja tarefas, cria checklists e organiza a rotina"
system_prompt = PRODUTIVIDADE_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
