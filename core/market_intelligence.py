"""
Market Intelligence (Fase 9) -- fronteira de integração ScalaFlow -> CRIS OS.

SCALAFLOW = inteligência (o que vale a pena explorar). CRIS OS = cérebro/
orquestração (decide, estrutura, aprova, executa sob controle humano). Este
módulo é o ÚNICO ponto de entrada de inteligência de mercado vinda de fora
-- ele NUNCA aprova nada, NUNCA executa nada, NUNCA gasta dinheiro. Ele só
valida, classifica honestamente e persiste no MESMO Project Brain (nenhum
banco/Project Brain/Event Bus/Approval Router paralelo).

DECISÃO ARQUITETURAL (documentada -- ver auditoria da Fase 9): não existe
hoje NENHUM mecanismo de "push" do ScalaFlow para o CRIS OS (o repositório
ScalaFlow/ScalaFlow Insights foi auditado e não contém nenhum webhook/
handoff endereçado ao CRIS OS) -- a integração real e já funcional hoje é
"pull" (`tools/opportunity_tools.py` lê diretamente as tabelas
`*_minerados`/`collected_ads` do Supabase do ScalaFlow). Esta fase NÃO
substitui isso -- ela prepara o lado CRIS OS de um contrato "push"
estruturado (`MarketIntelligenceHandoff`) para quando o ScalaFlow (ou
qualquer outra fonte) precisar empurrar inteligência já processada, sem
inventar nenhum endpoint/payload/autenticação do lado ScalaFlow que não
existe ainda -- ver docs/SCALAFLOW_CRIS_OS_INTEGRATION.md para o que falta
do lado ScalaFlow para conectar de verdade.

VERIFICATION BEFORE TRUST: nada vindo de fora vira fato confirmado
automaticamente. Toda evidência é classificada (OBSERVED/DERIVED/INFERRED/
UNKNOWN) e toda confiança é auditada -- uma afirmação forte sem evidência
suficiente é REBAIXADA deterministicamente, nunca aceita como está.

FAIL CLOSED: em caso de dúvida (payload malformado, projeto ambíguo,
evidência crítica ausente para uma afirmação forte), o handoff nunca entra
silenciosamente no Project Brain -- vira REJECTED ou NEEDS_REVIEW,
explicitamente.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from memory.project_brain import (
    CONFIDENCE_NIVEIS_VALIDOS,
    EVIDENCE_TIPOS_VALIDOS,
    MARKET_INTELLIGENCE_ESTADOS_VALIDOS,
    SCHEMA_VERSIONS_SUPORTADAS,
    MarketIntelligenceHandoff,
    ProjectBrain,
)

logger = logging.getLogger(__name__)

# Tamanho maximo de payload aceito (protecao contra payload excessivo --
# pedido explicito da Fase 9). 256 KB e generoso pra um handoff estruturado
# de UMA oportunidade (nunca deveria carregar um dataset inteiro).
_TAMANHO_MAXIMO_PAYLOAD_BYTES = 256 * 1024

_URL_PREFIXOS_VALIDOS = ("http://", "https://")


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Validacao do payload -- FAIL CLOSED: qualquer problema rejeita o handoff
# INTEIRO antes de tocar no Project Brain.
# ---------------------------------------------------------------------------

def _validar_timestamp(valor) -> bool:
    if valor is None:
        return True
    try:
        datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _validar_url(valor) -> bool:
    if valor is None:
        return True
    return isinstance(valor, str) and valor.lower().startswith(_URL_PREFIXOS_VALIDOS)


def validar_payload(payload: dict) -> tuple[bool, list[str]]:
    """
    Validacao ESTRUTURAL do payload cru (antes de virar um
    `MarketIntelligenceHandoff`). Devolve `(valido, erros)` -- NUNCA lanca
    excecao, mesmo com payload completamente malformado (ex.: nao ser um
    dict).
    """
    erros: list[str] = []

    if not isinstance(payload, dict):
        return False, ["Payload malformado: esperado um objeto/dict."]

    try:
        tamanho = len(json.dumps(payload, ensure_ascii=False))
    except (TypeError, ValueError):
        return False, ["Payload malformado: não é serializável em JSON."]
    if tamanho > _TAMANHO_MAXIMO_PAYLOAD_BYTES:
        erros.append(f"Payload excede o tamanho máximo permitido ({_TAMANHO_MAXIMO_PAYLOAD_BYTES} bytes).")

    handoff_id = payload.get("handoff_id")
    if not handoff_id or not isinstance(handoff_id, str):
        erros.append("Campo obrigatório ausente ou inválido: 'handoff_id'.")

    source_system = payload.get("source_system")
    if not source_system or not isinstance(source_system, str):
        erros.append("Campo obrigatório ausente ou inválido: 'source_system'.")

    schema_version = payload.get("schema_version", "1.0")
    if schema_version not in SCHEMA_VERSIONS_SUPORTADAS:
        erros.append(f"schema_version não suportada: {schema_version!r} (suportadas: {sorted(SCHEMA_VERSIONS_SUPORTADAS)}).")

    score = payload.get("opportunity_score")
    if score is not None:
        try:
            score_num = float(score)
            if not (0 <= score_num <= 100):
                erros.append(f"opportunity_score fora do intervalo válido [0, 100]: {score!r}.")
        except (TypeError, ValueError):
            erros.append(f"opportunity_score com tipo inválido: {score!r}.")

    confidence_level = payload.get("confidence_level", "UNKNOWN")
    if confidence_level not in CONFIDENCE_NIVEIS_VALIDOS:
        erros.append(f"confidence_level inválido: {confidence_level!r} (válidos: {sorted(CONFIDENCE_NIVEIS_VALIDOS)}).")

    if not _validar_timestamp(payload.get("created_at")):
        erros.append(f"created_at não é um timestamp ISO válido: {payload.get('created_at')!r}.")

    for campo_url in ("sales_page_url",):
        if not _validar_url(payload.get(campo_url)):
            erros.append(f"{campo_url} não parece uma URL válida: {payload.get(campo_url)!r}.")
    for url in payload.get("competitor_urls") or []:
        if not _validar_url(url):
            erros.append(f"competitor_urls contém uma URL inválida: {url!r}.")

    for i, ev in enumerate(payload.get("evidence") or []):
        if not isinstance(ev, dict):
            erros.append(f"evidence[{i}] deve ser um objeto/dict.")
            continue
        ev_tipo = ev.get("evidence_type", "UNKNOWN")
        if ev_tipo not in EVIDENCE_TIPOS_VALIDOS:
            erros.append(f"evidence[{i}].evidence_type inválido: {ev_tipo!r}.")
        ev_conf = ev.get("confidence_level", "UNKNOWN")
        if ev_conf not in CONFIDENCE_NIVEIS_VALIDOS:
            erros.append(f"evidence[{i}].confidence_level inválido: {ev_conf!r}.")
        if not _validar_url(ev.get("source_url")):
            erros.append(f"evidence[{i}].source_url não parece uma URL válida: {ev.get('source_url')!r}.")
        if not _validar_timestamp(ev.get("captured_at")):
            erros.append(f"evidence[{i}].captured_at não é um timestamp ISO válido: {ev.get('captured_at')!r}.")

    return (not erros), erros


def _construir_handoff(payload: dict) -> MarketIntelligenceHandoff:
    """SOMENTE chamada depois de `validar_payload` passar -- monta o
    dataclass a partir de campos JA VALIDADOS, nunca inventando o que não
    veio no payload (ausente = `None`/lista vazia, nunca um valor default
    "otimista")."""
    campos_validos = {f for f in MarketIntelligenceHandoff.__dataclass_fields__}
    dados = {k: v for k, v in payload.items() if k in campos_validos}
    dados.setdefault("schema_version", "1.0")
    dados["received_at"] = _agora()
    dados["status"] = "RECEIVED"
    return MarketIntelligenceHandoff(**dados)


# ---------------------------------------------------------------------------
# Verification before trust -- nunca aceita uma afirmacao forte sem
# evidencia suficiente atras dela.
# ---------------------------------------------------------------------------

def _classificar_confianca(handoff: MarketIntelligenceHandoff) -> tuple[str, list[str]]:
    """
    Rebaixa deterministicamente `confidence_level` quando a afirmação não
    tem evidência real por trás -- "verification before trust" é uma REGRA
    APLICADA aqui, não só documentada. Devolve `(nivel_final, avisos)`.
    """
    avisos: list[str] = []
    nivel = handoff.confidence_level or "UNKNOWN"

    tem_evidencia_real = any(
        (ev.get("evidence_type") in {"OBSERVED", "DERIVED"}) for ev in handoff.evidence
    )
    if not tem_evidencia_real and nivel in {"MEDIUM", "HIGH"}:
        avisos.append(
            f"confidence_level original ({nivel}) foi rebaixado para LOW -- "
            "nenhuma evidência OBSERVED/DERIVED encontrada para sustentar essa confiança.",
        )
        nivel = "LOW"

    if not handoff.evidence and nivel != "UNKNOWN":
        avisos.append("Nenhuma evidência foi informada -- confidence_level rebaixado para UNKNOWN.")
        nivel = "UNKNOWN"

    return nivel, avisos


def _precisa_revisao_humana(handoff: MarketIntelligenceHandoff) -> bool:
    """Uma afirmação de alto impacto (ex.: score alto) sem evidência
    suficiente nunca vira PERSISTED direto -- fica NEEDS_REVIEW (fail
    closed) em vez de ser aceita ou descartada silenciosamente."""
    if handoff.opportunity_score is not None and handoff.opportunity_score >= 70 and not handoff.evidence:
        return True
    return False


# ---------------------------------------------------------------------------
# Deduplicacao / idempotencia
# ---------------------------------------------------------------------------

def eh_duplicado(handoff_id: str, handoff_store) -> bool:
    return handoff_store.ja_processado(handoff_id)


# ---------------------------------------------------------------------------
# Resolucao de projeto -- NUNCA adivinha; cria de forma controlada quando
# nao ha ambiguidade, ou sinaliza NEEDS_REVIEW quando ha.
# ---------------------------------------------------------------------------

def resolver_projeto(handoff: MarketIntelligenceHandoff, brain_store) -> tuple[ProjectBrain | None, str | None]:
    """
    Devolve `(brain, erro)`. `erro` é `None` quando a resolução deu certo
    (`brain` é o projeto correto, existente ou recém-criado); caso
    contrário `brain` é `None` e `erro` descreve por que não foi possível
    resolver sem adivinhar.
    """
    if handoff.project_id:
        brain = brain_store.load(handoff.project_id)
        if not brain:
            return None, f"project_id informado ({handoff.project_id}) não existe no Project Brain."
        return brain, None

    if handoff.external_project_ref:
        candidatos = [
            b for b in brain_store.list_all()
            if b.origem.source_offer_id == handoff.external_project_ref
        ]
        if len(candidatos) == 1:
            return candidatos[0], None
        if len(candidatos) > 1:
            return None, (
                f"external_project_ref ({handoff.external_project_ref}) corresponde a "
                f"{len(candidatos)} projetos -- ambíguo, não adivinhado."
            )
        # nenhum candidato -- cria um projeto novo controladamente (abaixo)

    nome = handoff.title or handoff.product_name or f"Oportunidade ScalaFlow ({handoff.handoff_id})"
    brain = brain_store.create(name=nome, tipo="opportunity")
    return brain, None


# ---------------------------------------------------------------------------
# Aplicacao ao Project Brain -- reaproveita EXATAMENTE os campos canonicos
# ja usados por Opportunity Analyst/Product Architect/Business Builder
# (Origem/Mercado/Oportunidade) -- nenhum modelo paralelo.
# ---------------------------------------------------------------------------

def _aplicar_ao_project_brain(brain: ProjectBrain, handoff: MarketIntelligenceHandoff) -> None:
    if handoff.market:
        brain.mercado.market = handoff.market
    if handoff.niche:
        brain.mercado.niche = handoff.niche
    if handoff.country:
        brain.mercado.target_country = handoff.country
    if handoff.language:
        brain.mercado.target_language = handoff.language

    if handoff.external_project_ref and not brain.origem.source_offer_id:
        brain.origem.source_offer_id = handoff.external_project_ref
    if handoff.source_module and not brain.origem.source_platform:
        brain.origem.source_platform = handoff.source_module
    if handoff.sales_page_url and not brain.origem.source_url:
        brain.origem.source_url = handoff.sales_page_url
    if handoff.country and not brain.origem.source_country:
        brain.origem.source_country = handoff.country
    if handoff.description and not brain.origem.source_headline:
        brain.origem.source_headline = handoff.description

    if handoff.opportunity_score is not None:
        brain.oportunidade.score = handoff.opportunity_score
    for chave, sinais in (
        ("trend", handoff.trend_signals), ("demand", handoff.demand_signals),
        ("competition", handoff.competition_signals), ("ad", handoff.ad_signals),
        ("social", handoff.social_signals), ("search", handoff.search_signals),
    ):
        if sinais:
            brain.oportunidade.signals[chave] = sinais
    if handoff.trend_signals:
        brain.oportunidade.trend_signals.update(handoff.trend_signals)
    if handoff.competition_signals:
        brain.oportunidade.competition.update(handoff.competition_signals)

    # Evidencia: SEMPRE rastreavel (fonte + tipo + confianca), nunca uma
    # frase solta -- reaproveita `Oportunidade.evidence` (lista de string),
    # formatando cada Evidence de forma legivel e auditavel.
    for ev in handoff.evidence:
        linha = (
            f"[{ev.get('evidence_type', 'UNKNOWN')}/{ev.get('confidence_level', 'UNKNOWN')}] "
            f"{ev.get('metric_name') or handoff.title or 'sinal'}"
            f"{': ' + str(ev.get('metric_value')) if ev.get('metric_value') is not None else ''}"
            f"{' ' + ev.get('metric_unit') if ev.get('metric_unit') else ''}"
            f" (fonte: {ev.get('source_name') or ev.get('source_type') or 'desconhecida'}, "
            f"handoff: {handoff.handoff_id})"
        )
        if linha not in brain.oportunidade.evidence:
            brain.oportunidade.evidence.append(linha)

    if handoff.warnings:
        for w in handoff.warnings:
            aviso = f"[ScalaFlow/{handoff.handoff_id}] {w}"
            if aviso not in brain.oportunidade.risks:
                brain.oportunidade.risks.append(aviso)


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def receive_intelligence(payload: dict, brain_store, handoff_store) -> dict:
    """
    Ponto de entrada ÚNICO de inteligência de mercado externa (Fase 9).
    Pipeline: VALIDATION -> PROVENANCE (implícito -- `Evidence` já carrega
    origem/tipo/timestamp) -> DEDUPLICATION -> PROJECT RESOLUTION ->
    PROJECT BRAIN. NUNCA aprova, executa ou publica nada -- só recebe,
    valida e persiste de forma honesta e rastreável.

    Devolve um dict estruturado: `{status, handoff_id, project_id, errors,
    warnings}` -- `status` é sempre um de `MARKET_INTELLIGENCE_ESTADOS_VALIDOS`.
    """
    handoff_id_bruto = payload.get("handoff_id") if isinstance(payload, dict) else None

    valido, erros = validar_payload(payload)
    if not valido:
        logger.warning("=== [MARKET_INTELLIGENCE] Payload rejeitado (%s): %s ===", handoff_id_bruto, erros)
        return {"status": "REJECTED", "handoff_id": handoff_id_bruto, "project_id": None, "errors": erros, "warnings": []}

    handoff_id = payload["handoff_id"]

    if eh_duplicado(handoff_id, handoff_store):
        indice = handoff_store.buscar(handoff_id)
        logger.info("=== [MARKET_INTELLIGENCE] Handoff duplicado ignorado: %s ===", handoff_id)
        return {
            "status": "DUPLICATE", "handoff_id": handoff_id,
            "project_id": indice.get("project_id") if indice else None,
            "errors": [], "warnings": ["Este handoff já havia sido processado anteriormente -- ignorado (idempotente)."],
        }

    handoff = _construir_handoff(payload)
    handoff.status = "VALIDATED"

    nivel_final, avisos_confianca = _classificar_confianca(handoff)
    handoff.confidence_level = nivel_final
    handoff.warnings = list(handoff.warnings) + avisos_confianca

    if _precisa_revisao_humana(handoff):
        handoff.status = "NEEDS_REVIEW"
        handoff.warnings.append(
            "opportunity_score alto sem nenhuma evidência associada -- "
            "necessário revisão humana antes de confiar nesta pontuação.",
        )
        handoff_store.registrar(handoff_id, None, "NEEDS_REVIEW")
        logger.info("=== [MARKET_INTELLIGENCE] Handoff marcado NEEDS_REVIEW: %s ===", handoff_id)
        return {
            "status": "NEEDS_REVIEW", "handoff_id": handoff_id, "project_id": None,
            "errors": [], "warnings": handoff.warnings,
        }

    brain, erro_resolucao = resolver_projeto(handoff, brain_store)
    if erro_resolucao:
        handoff.status = "NEEDS_REVIEW"
        handoff.warnings.append(erro_resolucao)
        handoff_store.registrar(handoff_id, None, "NEEDS_REVIEW")
        logger.info("=== [MARKET_INTELLIGENCE] Resolução de projeto ambígua/falhou: %s -- %s ===", handoff_id, erro_resolucao)
        return {
            "status": "NEEDS_REVIEW", "handoff_id": handoff_id, "project_id": None,
            "errors": [], "warnings": handoff.warnings + [erro_resolucao],
        }

    handoff.project_id = brain.project_id
    _aplicar_ao_project_brain(brain, handoff)
    handoff.status = "PERSISTED"
    brain.market_intelligence.append(handoff)
    brain.registrar_run("market_intelligence", f"Handoff de inteligência recebido e persistido ({handoff.handoff_id})")
    brain_store.save(brain)
    handoff_store.registrar(handoff_id, brain.project_id, "PERSISTED")

    logger.info("=== [MARKET_INTELLIGENCE] Handoff persistido: %s -> projeto %s ===", handoff_id, brain.project_id)
    return {
        "status": "PERSISTED", "handoff_id": handoff_id, "project_id": brain.project_id,
        "errors": [], "warnings": handoff.warnings,
    }


def get_intelligence(handoff_id: str, brain_store, handoff_store) -> MarketIntelligenceHandoff | None:
    indice = handoff_store.buscar(handoff_id)
    if not indice or not indice.get("project_id"):
        return None
    brain = brain_store.load(indice["project_id"])
    if not brain:
        return None
    return next((h for h in brain.market_intelligence if h.handoff_id == handoff_id), None)


def get_project_intelligence(project_id: str, brain_store) -> list[MarketIntelligenceHandoff]:
    brain = brain_store.load(project_id)
    if not brain:
        return []
    return list(brain.market_intelligence)
