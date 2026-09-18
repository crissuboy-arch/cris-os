"""
Agente: Paid Traffic Architect
Transforma um produto/oferta ja aprovado num plano de trafego pago
estruturado (Meta Ads, Google Search/Display, YouTube Ads, TikTok Ads),
SEM executar nenhuma campanha. Fase 5 do CRIS OS.

Fluxo: Product Architect -> aprovacao humana -> (Business Builder) -> Paid
Traffic Architect -> Project Brain -> resposta.
"""

from agents.base_specialist import create_agent
from agents.prompts import PAID_TRAFFIC_ARCHITECT_PROMPT
from tools.paid_traffic_tools import get_tools

name = "paid_traffic_architect"
description = "Monta um plano de trafego pago estruturado para um produto/oferta ja aprovado, sem executar campanhas"
system_prompt = PAID_TRAFFIC_ARCHITECT_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
