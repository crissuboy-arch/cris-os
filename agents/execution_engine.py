"""
Agente: Execution Engine
Transforma um artefato ja aprovado (BusinessPlan/TrafficPlan/CampaignSpec/
ProductBlueprint) num plano de execucao com tarefas dependentes, e processa
essas tarefas respeitando aprovacao humana e ausencia total de execucao
externa real. Fase 8 do CRIS OS.

Fluxo: artefato aprovado -> Execution Engine -> ExecutionPlan + Tasks ->
AgentOrchestrator (quando uma task precisar de um agente especialista) ->
Project Brain -> resposta.
"""

from agents.base_specialist import create_agent
from agents.prompts import EXECUTION_ENGINE_PROMPT
from tools.execution_engine_tools import get_tools

name = "execution_engine"
description = "Transforma um artefato ja aprovado num plano de execucao com tarefas dependentes, sem executar acoes externas reais"
system_prompt = EXECUTION_ENGINE_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
