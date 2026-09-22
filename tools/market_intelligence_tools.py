"""
Ferramentas do agente Market Intelligence (Fase 9 + ponte ScalaFlow).

O recebimento real de um handoff continua sendo uma chamada Python direta a
`core/market_intelligence.py:receive_intelligence` (feita pelo receptor
HTTP) -- este módulo NUNCA cria/reenvia um handoff novo. Ele faz duas
coisas: (1) mostra a inteligência já recebida para o projeto em foco
(leitura pura); (2) AVANÇA/RETOMA um projeto a partir de um `handoff_id`
JÁ persistido (mecanismo de RESUME -- ver `core/scalaflow_bridge.py`),
para quando o botão de origem no ScalaFlow já está SENT/desabilitado e a
única forma de continuar é por aqui. Uma vez que `receive_intelligence`
grava em `brain.mercado`/`brain.origem`/`brain.oportunidade`, TODOS os
agentes já existentes (Product Architect, Business Builder, Execution
Engine, ...) já sabem ler esses mesmos campos -- nenhuma integração
adicional é necessária para eles.
"""

from __future__ import annotations

import logging
import re

from memory.project_brain import ProjectBrain
from tools.base import Tool
from tools.opportunity_tools import get_foco_atual, get_project_brain_store

logger = logging.getLogger(__name__)

_FRASES_INTELLIGENCE = (
    "inteligência de mercado", "inteligencia de mercado",
    "market intelligence", "handoffs recebidos", "handoffs de inteligência",
)

# Mecanismo de RESUME/ADVANCE (integração ScalaFlow -- ver
# `core/scalaflow_bridge.py`): avança um projeto JÁ persistido a partir do
# `handoff_id`, sem nunca criar/reenviar um handoff novo. Usado quando o
# botão de origem no ScalaFlow já está SENT/desabilitado (a única forma de
# continuar é por aqui, não por um novo POST do ScalaFlow).
_FRASES_AVANCAR = (
    "avance o handoff", "avançar o handoff", "avance handoff", "avançar handoff",
    "retome o projeto", "retomar o projeto", "retome o handoff", "retomar o handoff",
    "continue o handoff", "continuar o handoff",
    "avance o projeto scalaflow", "avançar o projeto scalaflow",
)
_PADRAO_HANDOFF_ID = re.compile(r"\b(?:ho_|handoff_)[A-Za-z0-9_]+\b")


def _extrair_handoff_id(texto_original: str, brain: ProjectBrain | None) -> str | None:
    encontrado = _PADRAO_HANDOFF_ID.search(texto_original)
    if encontrado:
        return encontrado.group(0)
    if brain and brain.market_intelligence:
        return brain.market_intelligence[-1].handoff_id
    return None


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


def _mensagem_resultado(resultado: dict) -> str:
    status = resultado["status"]
    if status == "PENDING_APPROVAL_CREATED":
        aviso = "" if resultado.get("notificado") else "\n\n(A notificação Telegram pode não ter sido entregue -- verifique os logs.)"
        return (
            f"Plano de negócio criado para o projeto {resultado['project_id']} "
            f"a partir do handoff {resultado['handoff_id']}.\n\n"
            'Uma aprovação pendente foi registrada -- responda "Aprovado" ou '
            f'"Rejeito" quando quiser decidir.{aviso}'
        )
    if status in {"PENDING_APPROVAL_ALREADY_SET", "ALREADY_APPROVED", "PENDING_APPROVAL_BLOCKED_BY_OTHER", "NEEDS_MORE_EVIDENCE", "BUSINESS_PLAN_NOT_READY"}:
        return resultado["message"]
    if status == "HANDOFF_NOT_FOUND":
        return resultado["message"]
    if status == "PROJECT_NOT_FOUND":
        return resultado["message"]
    return resultado.get("message") or f"Status: {status}"


def gerenciar_market_intelligence(entrada: str, session: str = "") -> str:
    texto_original = (entrada or "").strip()
    texto = texto_original.lower()
    if not texto:
        return ""

    if any(f in texto for f in _FRASES_AVANCAR):
        brain = _resolver_projeto(session)
        brain_obj = brain if isinstance(brain, ProjectBrain) else None
        handoff_id = _extrair_handoff_id(texto_original, brain_obj)
        if not handoff_id:
            return (
                "Não encontrei um handoff_id no seu pedido nem um projeto em "
                "foco com inteligência de mercado recebida -- informe o "
                "handoff_id (ex.: \"avance o handoff ho_...\")."
            )
        from core.scalaflow_bridge import avancar_a_partir_do_handoff

        store = get_project_brain_store()
        from memory.project_brain import IntelligenceHandoffStore, PendingApprovalStore

        handoff_store = IntelligenceHandoffStore(store.project_memory)
        pending_store = PendingApprovalStore(store.project_memory)
        resultado = avancar_a_partir_do_handoff(handoff_id, store, handoff_store, pending_store, session=session)
        return _mensagem_resultado(resultado)

    brain = _resolver_projeto(session)
    if isinstance(brain, str):
        return brain
    return _formatar_intelligence(brain)


def get_tools() -> list[Tool]:
    return [
        Tool(
            "market_intelligence",
            "Mostra a inteligência de mercado (ScalaFlow) já recebida e "
            "persistida para o projeto em foco, e avança/retoma um projeto "
            "a partir de um handoff já persistido (sem novo handoff)",
            list(_FRASES_INTELLIGENCE) + list(_FRASES_AVANCAR),
            gerenciar_market_intelligence,
        ),
    ]
