"""
Ferramentas do agente Market Intelligence (Fase 9).

Este módulo é SOMENTE de LEITURA/consulta pelo Telegram (o recebimento real
de um handoff é uma chamada Python direta a
`core/market_intelligence.py:receive_intelligence`, feita por quem estiver
integrando o ScalaFlow -- não existe hoje nenhum comando de chat que
"invente" inteligência). Mostrar a inteligência já recebida para um
projeto é o que conecta este pipeline ao AgentOrchestrator (pedido
explícito da Fase 9): uma vez que `receive_intelligence` grava em
`brain.mercado`/`brain.origem`/`brain.oportunidade`, TODOS os agentes já
existentes (Opportunity Analyst, Product Architect, Business Builder, ...)
já sabem ler esses mesmos campos -- nenhuma integração adicional é
necessária para eles.
"""

from __future__ import annotations

import logging

from memory.project_brain import ProjectBrain
from tools.base import Tool
from tools.opportunity_tools import get_foco_atual, get_project_brain_store

logger = logging.getLogger(__name__)

_FRASES_INTELLIGENCE = (
    "inteligência de mercado", "inteligencia de mercado",
    "market intelligence", "handoffs recebidos", "handoffs de inteligência",
)


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


def _formatar_intelligence(brain: ProjectBrain) -> str:
    if not brain.market_intelligence:
        return f"Ainda não há inteligência de mercado recebida para este projeto.\n\nProjeto: {brain.project_id}"

    linhas = [
        f"🧠 INTELIGÊNCIA DE MERCADO — projeto {brain.project_id}",
        "",
        f"{len(brain.market_intelligence)} handoff(s) recebido(s):",
    ]
    for h in brain.market_intelligence:
        linhas.append("")
        linhas.append(f"  handoff_id: {h.handoff_id} | status: {h.status}")
        linhas.append(f"  fonte: {h.source_system or 'desconhecida'} / {h.source_module or '?'}")
        linhas.append(f"  confidence: {h.confidence_level}")
        if h.opportunity_score is not None:
            linhas.append(f"  opportunity_score: {h.opportunity_score}")
        if h.evidence:
            linhas.append(f"  evidências: {len(h.evidence)}")
        if h.warnings:
            linhas.append(f"  avisos: {'; '.join(h.warnings)}")

    linhas.append("")
    linhas.append("Nenhuma dessas afirmações foi tratada como fato automaticamente -- "
                   "confidence_level reflete somente a evidência real recebida.")
    return "\n".join(linhas)


def gerenciar_market_intelligence(entrada: str, session: str = "") -> str:
    texto = (entrada or "").strip().lower()
    if not texto:
        return ""
    brain = _resolver_projeto(session)
    if isinstance(brain, str):
        return brain
    return _formatar_intelligence(brain)


def get_tools() -> list[Tool]:
    return [
        Tool(
            "market_intelligence",
            "Mostra a inteligência de mercado (ScalaFlow) já recebida e "
            "persistida para o projeto em foco",
            list(_FRASES_INTELLIGENCE),
            gerenciar_market_intelligence,
        ),
    ]
