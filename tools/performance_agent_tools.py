"""
Ferramentas do agente Performance Agent (Fase 6 -- fundação).

Só LÊ métricas REAIS/IMPORTADAS já registradas no Project Brain -- nunca
inventa. Sem nenhum snapshot utilizável, a resposta é SEMPRE
determinística, sem chamar LLM (checado ANTES de qualquer configuração de
LLM -- ver `gerenciar_performance`).
"""

from __future__ import annotations

import logging

from config.settings import settings
from core.performance_agent import diagnosticar_performance, tem_metricas_utilizaveis
from memory.project_brain import ProjectBrain
from tools.base import Tool
from tools.opportunity_tools import get_foco_atual, get_project_brain_store

logger = logging.getLogger(__name__)

_FRASES_PERFORMANCE = (
    "como esta a campanha", "como está a campanha",
    "como esta a performance", "como está a performance",
    "analise os resultados", "analise a performance", "analisar a performance",
    "veja a performance", "resultado da campanha", "resultados da campanha",
    "metricas da campanha", "métricas da campanha",
    "performance da campanha", "performance desta campanha",
    "performance deste projeto",
)


def _headers_ok() -> bool:
    return bool(settings.OPENROUTER_API_KEY) and settings.OPENROUTER_API_KEY != "COLE_SUA_CHAVE_AQUI"


_llm_inteligente_cache = None


def _get_llm_inteligente():
    global _llm_inteligente_cache
    if _llm_inteligente_cache is None:
        if not _headers_ok():
            return None
        try:
            from llm.openrouter import MODELO_PADRAO_INTELIGENTE, OpenRouterProvider

            provider = OpenRouterProvider(
                api_key=settings.OPENROUTER_API_KEY,
                model=settings.OPENROUTER_MODEL_INTELIGENTE or MODELO_PADRAO_INTELIGENTE,
                base_url=settings.OPENROUTER_BASE_URL,
                timeout=settings.OPENROUTER_TIMEOUT,
                tier="inteligente",
            )
            _llm_inteligente_cache = provider if provider.is_alive() else None
        except Exception as exc:
            logger.warning("=== [PERFORMANCE_AGENT] Falha ao configurar OpenRouter: %s ===", exc)
            _llm_inteligente_cache = None
    return _llm_inteligente_cache


def _resolver_projeto(session: str) -> ProjectBrain | str:
    foco = get_foco_atual(session)
    if not foco:
        return (
            "Não sei a qual projeto você se refere -- investigue uma "
            "oportunidade e aprove um formato de produto primeiro."
        )
    brain = get_project_brain_store().load(foco)
    if not brain:
        return "Não consegui recuperar o projeto em foco."
    return brain


def gerenciar_performance(entrada: str, session: str = "") -> str:
    texto = (entrada or "").strip()
    if not texto:
        return ""

    brain = _resolver_projeto(session)
    if isinstance(brain, str):
        return brain

    # DETERMINISTICO -- zero LLM quando nao ha metrica utilizavel (regra
    # mais importante deste agente: nunca inventar diagnostico so pra
    # responder algo).
    if not tem_metricas_utilizaveis(brain):
        return (
            "Ainda não existem métricas reais/importadas suficientes para "
            f"avaliar a performance desta campanha.\n\nProjeto: {brain.project_id}"
        )

    return diagnosticar_performance(brain, llm=_get_llm_inteligente())


def get_tools() -> list[Tool]:
    return [
        Tool(
            "performance_agent",
            "Analisa métricas reais/importadas de uma campanha (nunca inventa dado)",
            [
                "performance", "desempenho",
                *_FRASES_PERFORMANCE,
            ],
            gerenciar_performance,
        ),
    ]
