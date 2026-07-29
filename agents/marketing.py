"""
Agente: Marketing
Campanhas e estrategias de marketing.
Nao possui ferramentas dedicadas — usa apenas o LLM.
"""

from agents.base_specialist import create_agent
from agents.prompts import MARKETING_PROMPT

name = "marketing"
description = "Cria campanhas e estrategias de marketing"
system_prompt = MARKETING_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm)
