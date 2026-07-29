"""
Agente: Vendas
Propostas, orcamentos e fechamento.
Separa PROMPTS, FERRAMENTAS (tools/sales_tools.py), LOGICA.
"""

from agents.base_specialist import create_agent
from agents.prompts import VENDAS_PROMPT
from tools.sales_tools import get_tools

name = "vendas"
description = "Cria propostas, orcamentos e estrategias de venda"
system_prompt = VENDAS_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
