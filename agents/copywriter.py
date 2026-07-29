"""
Agente: Copywriter
Cria textos persuasivos e conversao.
Separa PROMPTS, FERRAMENTAS (tools/copy_tools.py), LOGICA.
"""

from agents.base_specialist import create_agent
from agents.prompts import COPYWRITER_PROMPT
from tools.copy_tools import get_tools

name = "copywriter"
description = "Cria textos persuasivos, paginas de venda e campanhas de conversao"
system_prompt = COPYWRITER_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
