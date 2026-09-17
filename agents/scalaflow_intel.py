"""
Agente: ScalaFlow Intel
Busca produtos/ofertas quentes minerados no ScalaFlow (dado real, via Supabase).
Separa PROMPTS, FERRAMENTAS (tools/scalaflow_tools.py), LOGICA.

Nao confundir com a pasta agents/scalaflow/ (agente antigo, so-prompt, do
sistema classico DEFAULT_AGENT=secretary) -- este aqui roda no sistema novo
(DEFAULT_AGENT=auto) e de fato executa a busca em vez de so conversar.
"""

from agents.base_specialist import create_agent
from agents.prompts import SCALAFLOW_INTEL_PROMPT
from tools.scalaflow_tools import get_tools

name = "scalaflow_intel"
description = "Busca produtos e ofertas quentes minerados no ScalaFlow (dado real do Supabase)"
system_prompt = SCALAFLOW_INTEL_PROMPT


def create(llm):
    return create_agent(name, description, system_prompt, llm, tools=get_tools())
