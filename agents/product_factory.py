"""
Agente: Product Factory
Prepara e mostra o plano de producao (entregaveis especificos do formato de
produto aprovado) e o artifact manifest. Fase 4 do CRIS OS -- expoe sob
demanda pelo Telegram a Product Factory ja existente desde a Fase 3
(`core/product_factory.py`), sem duplicar a logica.

Fluxo: Business Builder -> Product Factory -> artefatos/entregaveis ->
aguardar aprovacao humana para publicacao (fase futura).
"""

from agents.base_specialist import create_agent
from agents.prompts import PRODUCT_FACTORY_PROMPT
from tools.product_factory_tools import get_tools

name = "product_factory"
description = "Prepara e mostra o plano de producao e os artefatos necessarios para um produto ja aprovado"
system_prompt = PRODUCT_FACTORY_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
