"""
Rotas de sistema — status, health check, metricas.
"""

import time

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
def status():
    """Status geral do CRIS OS."""
    from agents import discover_agents

    try:
        from core.llm_providers.ollama import OllamaProvider
        from core.config import get_settings
        settings = get_settings()
        ollama = OllamaProvider(model=settings.OLLAMA_MODEL, base_url=settings.OLLAMA_HOST)
        ollama_online = ollama.is_alive()
        modelo_ativo = settings.OLLAMA_MODEL
    except Exception:
        ollama_online = False
        modelo_ativo = "desconhecido"

    ods_online = True
    try:
        from core.llm_providers.ods_provider import ODSProvider
        ods = ODSProvider()
        ods_online = ods.is_alive()
    except Exception:
        ods_online = True

    # Contagem de agentes (nao instancia, apenas conta modulos)
    from agents import AGENT_MODULES, GENERAL_MODULE
    n_agentes = len(AGENT_MODULES) + 1

    from database.connection import get_connection
    conn = get_connection()
    try:
        n_projetos = conn.execute("SELECT COUNT(*) FROM projetos").fetchone()[0]
        n_clientes = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
        n_tarefas_pendentes = conn.execute("SELECT COUNT(*) FROM tarefas WHERE status='pendente'").fetchone()[0]
        n_conversas = conn.execute("SELECT COUNT(*) FROM conversas").fetchone()[0]
        n_prompts = conn.execute("SELECT COUNT(*) FROM prompts_favoritos").fetchone()[0]
    except Exception:
        n_projetos = n_clientes = n_tarefas_pendentes = n_conversas = n_prompts = 0

    return {
        "status": "online",
        "modelo_ativo": modelo_ativo,
        "ods_online": ods_online,
        "ollama_online": ollama_online,
        "agentes": n_agentes,
        "projetos": n_projetos,
        "clientes": n_clientes,
        "tarefas_pendentes": n_tarefas_pendentes,
        "conversas": n_conversas,
        "prompts": n_prompts,
        "tempo_resposta_ms": 0,
        "versao": "1.0.0",
    }


@router.get("/health")
def health():
    return {"status": "ok"}
