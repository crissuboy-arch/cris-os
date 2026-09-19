"""
Agente: Campaign Executor
Transforma um plano de trafego pago ja aprovado (Fase 5) numa especificacao
de campanha (CampaignSpec) -- estrutura, publico/hipoteses, criativos
necessarios, tracking, orcamento -- SEM publicar nem executar nada. Fase 6
do CRIS OS.

Fluxo: Paid Traffic Architect -> TrafficPlan APPROVED -> aprovacao humana ->
Campaign Executor -> Project Brain -> DRY-RUN/PREVIEW -> resposta.
"""

from agents.base_specialist import create_agent
from agents.prompts import CAMPAIGN_EXECUTOR_PROMPT
from tools.campaign_executor_tools import get_tools

name = "campaign_executor"
description = "Transforma um plano de trafego ja aprovado numa especificacao de campanha, sem publicar nem executar nada"
system_prompt = CAMPAIGN_EXECUTOR_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
