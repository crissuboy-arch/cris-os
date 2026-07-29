"""
Agente: Social Media
Cria conteudo para redes sociais.
Separa PROMPTS (prompts.py), FERRAMENTAS (tools/social_tools.py), LOGICA (aqui).
"""

from agents.base_specialist import create_agent
from agents.prompts import SOCIAL_MEDIA_PROMPT
from tools.social_tools import get_tools

name = "social_media"
description = "Cria legendas, posts e conteudo para redes sociais"
system_prompt = SOCIAL_MEDIA_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
