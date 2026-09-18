"""
Agente: Business Builder
Recebe um Product Blueprint JA APROVADO e transforma em estrutura comercial
(modelo de negocio, oferta, monetizacao, funil, conteudo, lancamento).
Fase 4 do CRIS OS.

Fluxo: Product Architect -> aprovacao humana do produto -> Business Builder
-> Product Factory.
"""

from agents.base_specialist import create_agent
from agents.prompts import BUSINESS_BUILDER_PROMPT
from tools.business_builder_tools import get_tools

name = "business_builder"
description = "Transforma um produto ja aprovado em plano de negocio (oferta, monetizacao, funil, lancamento)"
system_prompt = BUSINESS_BUILDER_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
