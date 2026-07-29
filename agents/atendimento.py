"""
Agente: Atendimento
Responde clientes com qualidade.
Separa PROMPTS, FERRAMENTAS (tools/service_tools.py), LOGICA.
"""

from agents.base_specialist import create_agent
from agents.prompts import ATENDIMENTO_PROMPT
from tools.service_tools import get_tools

name = "atendimento"
description = "Atende clientes com respostas humanizadas e eficientes"
system_prompt = ATENDIMENTO_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
