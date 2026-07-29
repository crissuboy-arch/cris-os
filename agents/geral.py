"""
Agente: Geral (fallback universal)
Usado quando nenhum outro agente atende a mensagem.
"""

from agents.base_specialist import create_agent
from agents.prompts import GERAL_PROMPT

name = "geral"
description = "Assistente geral para tarefas que nao se encaixam nos especialistas"
system_prompt = GERAL_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm)
