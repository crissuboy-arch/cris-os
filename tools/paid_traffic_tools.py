"""
Ferramentas do agente Paid Traffic Architect (Fase 5).

Fluxo: Product Architect -> aprovacao humana -> (Business Builder) -> PAID
TRAFFIC ARCHITECT -> Project Brain -> resposta.

Este modulo e o "cola" entre:
  - tools/opportunity_tools.py (reaproveita o MESMO foco por sessao -- sem
    memoria paralela);
  - core/paid_traffic_architect.py (decide canais/angulos/criativos, com LLM
    quando disponivel);
  - core/tool_registry.py (`PAID_TRAFFIC_ARCHITECT`, executor real);
  - memory/project_brain.py (persistencia -- `brain.traffic_plan`).

Regra de ouro (igual ao Product Architect/Business Builder): NUNCA interpreta
conversa ambigua como aprovacao. So um conjunto fechado de palavras/frases
conta como aprovacao ("esta bom?"/"qual o plano?"/"pronto?" NUNCA aprovam).
"""

from __future__ import annotations

import logging
import re

from config.settings import settings
from core.paid_traffic_architect import criar_plano_trafego
from core.tool_registry import PAID_TRAFFIC_ARCHITECT, ToolRegistry
from memory.project_brain import ProjectBrain, TrafficPlan
from tools.base import Tool
from tools.opportunity_tools import get_foco_atual, get_project_brain_store

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

logger = logging.getLogger(__name__)

_PALAVRAS_APROVACAO = frozenset({
    "aprovado", "aprovada", "aprovo", "autorizado", "autorizo",
    "confirmado", "confirmo",
})
_FRASES_APROVACAO = ("pode criar", "pode seguir", "pode comecar", "pode começar")

_PALAVRAS_REJEICAO = frozenset({"rejeitado", "rejeitada", "rejeito"})
_FRASES_REJEICAO = ("nao gostei", "não gostei", "quero outro", "outro plano")

_FRASES_STATUS = (
    "status do plano de trafego", "status do plano de tráfego",
    "qual o status do plano de trafego", "qual o status do plano de tráfego",
    "status do trafego pago", "status do tráfego pago",
)
_FRASES_MOSTRAR = (
    "mostre o plano de trafego", "mostre o plano de tráfego",
    "plano de trafego atual", "plano de tráfego atual",
    "ver plano de trafego", "ver plano de tráfego",
    "veja o plano de trafego", "veja o plano de tráfego",
)
_FRASES_REVISAR = (
    "revise o plano de trafego", "revise o plano de tráfego",
    "refaca o plano de trafego", "refaça o plano de tráfego",
    "atualize o plano de trafego", "atualize o plano de tráfego",
    "gere outro plano de trafego", "gere outro plano de tráfego",
)

# Extracao DETERMINISTICA (sem LLM) de um orcamento real informado pelo
# usuario na propria mensagem -- pedido explicito: "se o usuario informou
# orcamento real, preservar sem alterar silenciosamente".
_PADRAO_ORCAMENTO = re.compile(
    r"(r\$|us\$|\$)\s*([\d]+(?:[.,]\d+)?)\s*(por dia|/dia|di[áa]rios?|ao dia)?",
    re.IGNORECASE,
)


def _extrair_orcamento_informado(texto: str) -> dict | None:
    m = _PADRAO_ORCAMENTO.search(texto)
    if not m:
        return None
    moeda_bruta, valor, periodo = m.group(1), m.group(2), m.group(3)
    moeda = {"r$": "BRL", "us$": "USD", "$": "USD"}.get(moeda_bruta.lower(), moeda_bruta)
    eh_diario = bool(periodo)
    return {
        "currency": moeda,
        "daily_budget": valor if eh_diario else None,
        "total_test_budget": valor if not eh_diario else None,
    }


def _headers_ok() -> bool:
    return bool(settings.OPENROUTER_API_KEY) and settings.OPENROUTER_API_KEY != "COLE_SUA_CHAVE_AQUI"


_llm_inteligente_cache = None


def _get_llm_inteligente():
    """Paid Traffic Architect usa o tier INTELIGENTE (mesma logica do Product
    Architect): escolher/priorizar canais e criar angulos/hooks e uma tarefa
    de julgamento, nao uma classificacao simples."""
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
            logger.warning("=== [PAID_TRAFFIC] Falha ao configurar OpenRouter: %s ===", exc)
            _llm_inteligente_cache = None
    return _llm_inteligente_cache


def _contains_any(texto: str, palavras: frozenset[str], frases: tuple = ()) -> bool:
    tokens = set(texto.split())
    if tokens & palavras:
        return True
    if any(p in texto for p in palavras):
        return True
    return any(f in texto for f in frases)


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


_MARCADOR_ROLE = {
    "PRIMARY_TEST": "🎯 PRIMÁRIO PARA TESTE",
    "SECONDARY_TEST": "🔹 secundário para teste",
    "LATER": "🕒 mais tarde (evidência ainda insuficiente)",
    "NOT_RECOMMENDED_NOW": "⛔ não recomendado agora",
}


def _formatar_plano_trafego(brain: ProjectBrain, tp: TrafficPlan) -> str:
    linhas = [
        "🚀 PLANO DE TRÁFEGO PAGO",
        "",
        f"Projeto: {brain.project_id} | Versão: {tp.version} | Status: {tp.status}",
    ]

    if tp.status == "NEEDS_INFORMATION":
        linhas.append("")
        linhas.append("Ainda não há informação suficiente para um plano pronto pra aprovar:")
        for lacuna in tp.missing_information:
            linhas.append(f"  - {lacuna}")
        if not tp.channels:
            # Nada mais foi avaliado (faltou pre-requisito basico, ex.: sem
            # blueprint aprovado) -- nao ha analise pra mostrar.
            return "\n".join(linhas)
        linhas.append("")
        linhas.append("Análise já feita até aqui (nenhuma parte foi aprovada ainda):")

    linhas.append("")
    if tp.objective:
        linhas.append(f"Objetivo: {tp.objective}")
    linhas.append(f"Mercado: {tp.market or 'REQUIRES_MARKET_DATA'} / País: {tp.country or 'REQUIRES_MARKET_DATA'}")
    if tp.audience_summary:
        linhas.append(f"Público: {tp.audience_summary}")

    if tp.channels:
        linhas.append("")
        linhas.append("CANAIS")
        for c in tp.channels:
            marcador = _MARCADOR_ROLE.get(c["role"], c["role"])
            linhas.append(f"{marcador} — {c['channel']} (prioridade: {c.get('priority') or '?'})")
            if c.get("rationale"):
                linhas.append(f"   Por quê: {c['rationale']}")
            if c.get("campaign_objective"):
                linhas.append(f"   Objetivo de campanha: {c['campaign_objective']}")
            if c.get("targeting_strategy"):
                linhas.append(f"   Segmentação: {c['targeting_strategy']}")
            if c.get("keyword_strategy"):
                linhas.append(f"   Keywords: {c['keyword_strategy']}")
            if c.get("placements"):
                linhas.append(f"   Posicionamentos: {', '.join(c['placements'])}")
            if c.get("landing_destination"):
                linhas.append(f"   Destino: {c['landing_destination']}")
            if c.get("conversion_event"):
                linhas.append(f"   Evento de conversão: {c['conversion_event']}")
            if c.get("test_hypothesis"):
                linhas.append(f"   Hipótese de teste: {c['test_hypothesis']}")
            if c.get("risks"):
                linhas.append(f"   Riscos: {'; '.join(c['risks'])}")
            linhas.append("")

    if tp.angles:
        linhas.append("ÂNGULOS: " + "; ".join(tp.angles))
    if tp.hooks:
        linhas.append("HOOKS: " + "; ".join(tp.hooks))

    if tp.creative_matrix:
        linhas.append("")
        linhas.append("CRIATIVOS NECESSÁRIOS (especificação -- nenhum asset foi gerado)")
        for item in tp.creative_matrix:
            linhas.append(
                f"  [{item.get('format') or '?'}/{item.get('channel') or '?'}] "
                f"{item.get('angle') or ''} -> {item.get('hook') or ''} "
                f"(CTA: {item.get('cta') or '?'})",
            )

    if tp.testing_plan:
        linhas.append("")
        linhas.append("PLANO DE TESTE: " + "; ".join(tp.testing_plan))
    if tp.measurement_plan:
        linhas.append("MENSURAÇÃO (métricas a observar, sem resultado ainda): " + "; ".join(tp.measurement_plan))
    if tp.stop_conditions:
        linhas.append("CONDIÇÕES DE PARADA: " + "; ".join(tp.stop_conditions))
    if tp.scale_conditions:
        linhas.append("CONDIÇÕES DE ESCALA: " + "; ".join(tp.scale_conditions))

    linhas.append("")
    linhas.append(f"Orçamento: {tp.budget_status}")
    if tp.budget_informado_pelo_usuario:
        linhas.append(f"Orçamento informado (real, preservado sem alteração): {tp.budget_informado_pelo_usuario}")
    elif tp.budget_scenarios:
        linhas.append("Cenários de teste ilustrativos (HIPÓTESE DE PLANEJAMENTO, não garantia de resultado -- aguardando você informar o orçamento real):")
        for cenario in tp.budget_scenarios:
            linhas.append(f"  {cenario['nome']}: {cenario['valor']} [{cenario['type']}]")

    linhas.append(f"Prova social: {tp.social_proof_status}")
    if tp.social_proof_status == "NOT_AVAILABLE":
        linhas.append("  (nenhum depoimento/avaliação/cliente real registrado -- nada disso foi inventado)")

    linhas.append("")
    linhas.append("HONESTIDADE (EVIDÊNCIA / HIPÓTESE / DESCONHECIDO)")
    if tp.evidence_summary:
        linhas.append("Evidências: " + "; ".join(tp.evidence_summary))
    if tp.assumptions:
        linhas.append("Hipóteses assumidas: " + "; ".join(tp.assumptions))
    if tp.unknowns:
        linhas.append("Desconhecidos: " + "; ".join(tp.unknowns))
    if tp.risks:
        linhas.append("Riscos: " + "; ".join(tp.risks))

    if tp.approval_required_actions:
        linhas.append("")
        linhas.append("Ações que exigem aprovação humana explícita antes de acontecer:")
        for acao in tp.approval_required_actions:
            linhas.append(f"  - {acao}")

    linhas.append("")
    linhas.append(
        "Nenhuma métrica de performance (CTR/CPC/CPM/CPA/ROAS/CVR/vendas/"
        "demanda) foi inventada -- números desse tipo só existirão com "
        "campanha real rodando."
    )

    if tp.status == "READY_FOR_APPROVAL":
        linhas.append("")
        linhas.append('Responda "Aprovado" pra marcar este plano como aprovado (nenhuma campanha é criada automaticamente).')
    return "\n".join(linhas)


def _preparar_e_persistir(brain: ProjectBrain, texto_original: str, versao_anterior: TrafficPlan | None) -> TrafficPlan:
    registry: ToolRegistry = _obter_registry()
    orcamento = _extrair_orcamento_informado(texto_original)
    tp = registry.executar(
        PAID_TRAFFIC_ARCHITECT,
        brain=brain,
        llm=_get_llm_inteligente(),
        orcamento_informado=orcamento,
        versao_anterior=versao_anterior,
    )
    if not isinstance(tp, TrafficPlan):
        # `registry.executar` nunca deveria devolver outra coisa aqui, mas a
        # API generica do registry aceita string de erro -- nunca finge que
        # deu certo se nao deu.
        raise RuntimeError(f"Tool Registry nao devolveu um TrafficPlan valido: {tp!r}")
    return tp


_registry_cache = None


def _obter_registry() -> ToolRegistry:
    global _registry_cache
    if _registry_cache is None:
        from core.tool_registry import criar_registry_padrao

        _registry_cache = criar_registry_padrao()
    return _registry_cache


def _get_pending_approval_store():
    """Reaproveita a MESMA `ProjectMemory` do `get_project_brain_store()`
    DESTE modulo -- nunca a de `tools.opportunity_tools` diretamente. Isso
    garante que testes que trocam `get_project_brain_store` (monkeypatch,
    padrao ja usado desde a Fase 5) tambem afetam onde a pendencia de
    aprovacao e lida/escrita, sem precisar de um segundo patch nem arriscar
    usar o banco de producao real durante testes."""
    from memory.project_brain import PendingApprovalStore

    return PendingApprovalStore(get_project_brain_store().project_memory)


def _sincronizar_pendencia_aprovacao(session: str, project_id: str, tp: TrafficPlan) -> None:
    """
    Correção estrutural (Fase 6): sempre que um TrafficPlan chega/permanece
    em READY_FOR_APPROVAL, registra deterministicamente que a próxima
    aprovação contextual válida desta sessão se refere ao TRAFFIC_PLAN deste
    projeto -- é isso que permite `agents/orchestrator.py` resolver um
    "Aprovado" curto sem adivinhar a qual artefato ele se refere (ver
    `core/approval_router.py`).
    """
    if tp.status == "READY_FOR_APPROVAL":
        _get_pending_approval_store().set_pending(session, project_id, "TRAFFIC_PLAN", "APPROVE")


def _aprovar(brain: ProjectBrain, session: str = "") -> str:
    store = get_project_brain_store()
    tp = brain.traffic_plan
    if not tp or tp.status != "READY_FOR_APPROVAL":
        return (
            "Ainda não há um plano de tráfego pronto pra aprovar "
            f"(status atual: {tp.status if tp else 'nenhum plano'})."
        )
    tp.status = "APPROVED"
    brain.registrar_aprovacao("TRAFFIC_PLAN_APPROVED")
    store.save(brain)
    _get_pending_approval_store().clear_pending(session)
    return (
        "✅ Plano de tráfego aprovado.\n\n"
        "Nenhuma conta de anúncio foi conectada, nenhuma campanha foi criada "
        "e nenhum valor foi gasto -- isso pertence a uma fase futura, com "
        "aprovação humana explícita separada.\n\n"
        f"Projeto: {brain.project_id} | Status: {tp.status}"
    )


def _rejeitar(brain: ProjectBrain, session: str = "") -> str:
    store = get_project_brain_store()
    tp = brain.traffic_plan
    if not tp:
        return "Ainda não há nenhum plano de tráfego para rejeitar."
    tp.status = "REJECTED"
    brain.registrar_aprovacao("TRAFFIC_PLAN_REJECTED")
    store.save(brain)
    _get_pending_approval_store().clear_pending(session)
    return (
        "Entendido, plano de tráfego rejeitado. Peça um novo plano quando "
        f"quiser revisar.\n\nProjeto: {brain.project_id}"
    )


def gerenciar_trafego(entrada: str, session: str = "") -> str:
    """Ponto de entrada unico da Tool (criar / mostrar / status / aprovar /
    rejeitar / revisar plano de trafego pago)."""
    texto_original = (entrada or "").strip()
    texto = texto_original.lower()
    if not texto:
        return ""

    brain = _resolver_projeto(session)
    if isinstance(brain, str):
        return brain

    tp = brain.traffic_plan

    if tp and _contains_any(texto, _PALAVRAS_APROVACAO, _FRASES_APROVACAO):
        return _aprovar(brain, session)
    if tp and _contains_any(texto, _PALAVRAS_REJEICAO, _FRASES_REJEICAO):
        return _rejeitar(brain, session)

    if _contains_any(texto, frozenset(), _FRASES_STATUS):
        if not tp:
            return f"Ainda não há plano de tráfego para este projeto.\n\nProjeto: {brain.project_id}"
        return f"Status do plano de tráfego: {tp.status} (versão {tp.version})\n\nProjeto: {brain.project_id}"

    if _contains_any(texto, frozenset(), _FRASES_MOSTRAR):
        if not tp:
            return (
                f"Ainda não há plano de tráfego para este projeto -- peça "
                f'"crie o plano de tráfego" primeiro.\n\nProjeto: {brain.project_id}'
            )
        _sincronizar_pendencia_aprovacao(session, brain.project_id, tp)
        return _formatar_plano_trafego(brain, tp)  # cache -- zero custo novo

    if _contains_any(texto, frozenset(), _FRASES_REVISAR):
        store = get_project_brain_store()
        novo_tp = _preparar_e_persistir(brain, texto_original, versao_anterior=tp)
        brain.traffic_plan = novo_tp
        brain.registrar_run("paid_traffic_architect", f"Revisou plano de trafego (v{novo_tp.version}, status {novo_tp.status})")
        store.save(brain)
        _sincronizar_pendencia_aprovacao(session, brain.project_id, novo_tp)
        return _formatar_plano_trafego(brain, novo_tp)

    # Default: CREATE_TRAFFIC_PLAN -- se ja existe um plano REAL (gerado com
    # sucesso), reexibe (cost-first); so gera do zero se ainda nao existir
    # nenhum.
    #
    # CORRECAO de bug real: um plano com status NEEDS_INFORMATION NUNCA e
    # tratado como "final" aqui -- ele nao representa um resultado gerado
    # (nenhum LLM foi chamado pra produzi-lo, `avaliar_prontidao` e pura/
    # local/gratuita), so um "ainda nao sei". Reexibir esse cache
    # indefinidamente significava que uma correcao na logica de prontidao
    # (ex.: a fonte canonica de evidencias) NUNCA se refletia pro usuario --
    # o comando sempre devolvia o mesmo NEEDS_INFORMATION antigo, mesmo
    # depois de o projeto passar a ter informacao suficiente. Por isso,
    # NEEDS_INFORMATION sempre reavalia (barato); so READY_FOR_APPROVAL/
    # APPROVED/REJECTED sao tratados como cache real.
    if tp and tp.status != "NEEDS_INFORMATION":
        _sincronizar_pendencia_aprovacao(session, brain.project_id, tp)
        return _formatar_plano_trafego(brain, tp)

    store = get_project_brain_store()
    # NEEDS_INFORMATION nao conta como "versao anterior real" -- o primeiro
    # plano de verdade continua sendo a versao 1, mesmo apos N tentativas
    # bloqueadas por falta de informacao.
    versao_anterior_real = tp if (tp and tp.status != "NEEDS_INFORMATION") else None
    novo_tp = _preparar_e_persistir(brain, texto_original, versao_anterior=versao_anterior_real)
    brain.traffic_plan = novo_tp
    brain.registrar_run("paid_traffic_architect", f"Criou plano de trafego (status {novo_tp.status})")
    store.save(brain)
    _sincronizar_pendencia_aprovacao(session, brain.project_id, novo_tp)
    return _formatar_plano_trafego(brain, novo_tp)


def get_tools() -> list[Tool]:
    return [
        Tool(
            "paid_traffic_architect",
            "Transforma um produto/oferta ja aprovado num plano de trafego "
            "pago estruturado (Meta/Google/YouTube/TikTok), sem executar "
            "nenhuma campanha",
            [
                "trafego", "tráfego",
                "estrategia de anuncios", "estratégia de anúncios",
                "como vamos anunciar", "plano de trafego", "plano de tráfego",
                "plano de campanha", "campanha paga", "anuncios pagos",
                "anúncios pagos", "trafego pago", "tráfego pago",
                "meta ads", "google ads", "tiktok ads", "google display",
                "youtube ads",
                "status do plano de trafego", "status do plano de tráfego",
                "mostre o plano de trafego", "mostre o plano de tráfego",
                "revise o plano de trafego", "revise o plano de tráfego",
                # continuacao (aprovacao/rejeicao) -- mesmo motivo do
                # Product Architect: precisa ser superset das frases que o
                # orchestrator reconhece.
                "aprovado", "aprovada", "aprovo", "autorizado", "autorizo",
                "confirmado", "confirmo", "rejeitado", "rejeitada", "rejeito",
                "pode criar", "pode seguir", "nao gostei", "não gostei",
                "quero outro", "outro plano",
            ],
            gerenciar_trafego,
            # "plano" + nome de plataforma de anuncio junto (ex.: "quero o
            # plano de Meta, Google e TikTok desse projeto") -- mesma logica
            # de co-ocorrencia do orchestrator (ver agents/orchestrator.py).
            matcher=lambda t: _eh_pedido_trafego_por_plataforma(t),
        ),
    ]


def _eh_pedido_trafego_por_plataforma(texto: str) -> bool:
    """Mesma logica de `agents/orchestrator.py:_eh_comando_paid_traffic` --
    "meta" de proposito fora daqui (colide com "meta" no sentido de
    objetivo/goal); Meta Ads e reconhecido pela frase completa "meta ads"
    nas keywords da Tool."""
    texto_lower = texto.lower()
    return "plano" in texto_lower and any(
        p in texto_lower for p in ("tiktok", "google", "youtube")
    )
