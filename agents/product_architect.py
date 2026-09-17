"""
Agente: Product Architect
Recebe uma oportunidade ja investigada (Opportunity Analyst + Decision
Engine) e propoe um FORMATO DE PRODUTO, com aprovacao humana obrigatoria
antes de qualquer producao (Product Factory). Fase 3 do CRIS OS.

Fluxo: ScalaFlow -> Opportunity Analyst -> Decision Engine -> Product
Architect -> aprovacao humana -> Product Factory (fundacao).
"""

from agents.base_specialist import create_agent
from agents.prompts import PRODUCT_ARCHITECT_PROMPT
from tools.product_architect_tools import get_tools

name = "product_architect"
description = "Propoe formato de produto para uma oportunidade e gerencia aprovacao/rejeicao antes de produzir"
system_prompt = PRODUCT_ARCHITECT_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
