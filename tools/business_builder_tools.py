"""
Ferramentas do agente Business Builder (Fase 4).

Fluxo: Product Architect -> APROVACAO HUMANA DO PRODUTO -> BUSINESS BUILDER
-> Product Factory.

Reaproveita a MESMA infraestrutura ja existente (Fase 2/3): foco por sessao
(`tools/opportunity_tools.py:get_foco_atual`), Project Brain
(`get_project_brain_store`), OpenRouter (`llm/openrouter.py`). NAO cria
memoria paralela nem um segundo "current project" global.

Gate de seguranca (pedido explicito da Fase 4, item 12): se o produto ainda
nao foi aprovado pelo Product Architect, o Business Builder NUNCA avanca
silenciosamente -- responde pedindo a aprovacao primeiro.
"""

from __future__ import annotations

import logging

from config.settings import settings
from core.business_builder import blueprint_aprovado, construir_plano_negocio, gerar_handoff
from memory.project_brain import BusinessPlan, ProjectBrain
from tools.base import Tool
from tools.opportunity_tools import get_foco_atual, get_project_brain_store

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

logger = logging.getLogger(__name__)

_MENSAGEM_NAO_APROVADO = (
    "Esse produto ainda não foi aprovado. Primeiro precisamos aprovar o "
    "Product Blueprint (fale com o Product Architect: \"Aprovado\" para o "
    "formato recomendado, ou \"Aprovo o formato X\" se ainda for hipótese)."
)

_PALAVRAS_MOSTRAR = frozenset({"mostre", "mostra", "exibir", "ver", "veja"})
_FRASES_MOSTRAR = ("plano de negocio", "plano de negócio", "pendencias", "pendências")
_FRASES_HANDOFF = ("handoff", "gere o handoff", "handoff do plano de negocio", "handoff do plano de negócio")


def _headers_ok() -> bool:
    return bool(settings.OPENROUTER_API_KEY) and settings.OPENROUTER_API_KEY != "COLE_SUA_CHAVE_AQUI"


_llm_economico_cache = None


def _get_llm_economico():
    """Business Builder usa o tier ECONOMICO (nao o INTELIGENTE do Product
    Architect) -- estruturar uma oferta em cima de um formato JA aprovado e
    uma tarefa mais simples que escolher entre 20+ formatos, e o cost-first
    pede explicitamente para nao usar modelo caro em tarefa simples."""
    global _llm_economico_cache
    if _llm_economico_cache is None:
        if not _headers_ok():
            return None
        try:
            from llm.openrouter import MODELO_PADRAO_ECONOMICO, OpenRouterProvider

            provider = OpenRouterProvider(
                api_key=settings.OPENROUTER_API_KEY,
                model=settings.OPENROUTER_MODEL_ECONOMICO or MODELO_PADRAO_ECONOMICO,
                base_url=settings.OPENROUTER_BASE_URL,
                timeout=settings.OPENROUTER_TIMEOUT,
                tier="economico",
            )
            _llm_economico_cache = provider if provider.is_alive() else None
        except Exception as exc:
            logger.warning("=== [BUSINESS_BUILDER] Falha ao configurar OpenRouter: %s ===", exc)
            _llm_economico_cache = None
    return _llm_economico_cache


def _contains_any(texto: str, palavras: frozenset[str], frases: tuple = ()) -> bool:
    tokens = set(texto.split())
    if tokens & palavras:
        return True
    return any(f in texto for f in frases)


def _get_pending_approval_store():
    """Reaproveita a MESMA `ProjectMemory` do `get_project_brain_store()`
    DESTE modulo -- mesmo principio de `tools/paid_traffic_tools.py`/
    `tools/campaign_executor_tools.py` (Fase 6): nunca usar o banco de
    producao real durante testes que trocam `get_project_brain_store`."""
    from memory.project_brain import PendingApprovalStore

    return PendingApprovalStore(get_project_brain_store().project_memory)


def _sincronizar_pendencia_aprovacao(session: str, project_id: str, plano: BusinessPlan) -> None:
    """Correcao estrutural (Fase 7, mesmo padrao da Fase 6): sempre que um
    BusinessPlan chega/permanece em READY_FOR_APPROVAL, registra
    deterministicamente que a proxima aprovacao contextual valida desta
    sessao se refere ao BUSINESS_PLAN deste projeto -- e isso que permite
    `agents/orchestrator.py` (via `core/approval_router.py`) resolver um
    "Aprovado" curto sem adivinhar a qual artefato ele se refere. O
    Business Builder NAO tem (nem precisa ter) um `_aprovar`/`_rejeitar`
    proprio -- o Approval Router central e o UNICO caminho de aprovacao."""
    if plano.approval_status == "READY_FOR_APPROVAL":
        _get_pending_approval_store().set_pending(session, project_id, "BUSINESS_PLAN", "APPROVE")


def _formatar_handoff(handoff: dict) -> str:
    linhas = [
        "📦 HANDOFF DO PLANO DE NEGÓCIO (contrato de dados -- nenhuma ação executada)",
        "",
        f"project_id: {handoff['project_id']}",
        f"business_plan_id: {handoff['business_plan_id']}",
        f"status: {handoff['status']}",
    ]
    if handoff.get("positioning"):
        linhas.append(f"positioning: {handoff['positioning']}")
    if handoff.get("target_audience"):
        linhas.append(f"target_audience: {handoff['target_audience']}")
    if handoff.get("core_offer"):
        linhas.append(f"core_offer: {handoff['core_offer']}")
    if handoff.get("pricing_strategy"):
        linhas.append(f"pricing_strategy: {handoff['pricing_strategy']}")
    if handoff.get("acquisition_channels"):
        linhas.append("acquisition_channels: " + ", ".join(handoff["acquisition_channels"]))
    if handoff.get("required_assets"):
        linhas.append("required_assets: " + "; ".join(handoff["required_assets"]))
    if handoff.get("kpis"):
        linhas.append("kpis: " + ", ".join(handoff["kpis"]))
    if handoff.get("risks"):
        linhas.append("risks: " + "; ".join(handoff["risks"]))
    if handoff.get("assumptions"):
        linhas.append("assumptions: " + "; ".join(handoff["assumptions"]))
    return "\n".join(linhas)


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


def _formatar_plano_negocio(brain: ProjectBrain, bp: BusinessPlan) -> str:
    linhas = [
        "🏢 PLANO DE NEGÓCIO",
        "",
        f"Projeto: {brain.project_id} | Produto: {brain.blueprint.recommended_product_type}",
        "",
    ]
    if bp.business_model:
        linhas.append(f"Modelo de negócio: {bp.business_model}")
    if bp.value_proposition:
        linhas.append(f"Proposta de valor: {bp.value_proposition}")
    if bp.target_audience:
        linhas.append(f"Público-alvo: {bp.target_audience}")
    if bp.problem:
        linhas.append(f"Problema: {bp.problem}")
    if bp.solution:
        linhas.append(f"Solução: {bp.solution}")
    if bp.positioning:
        linhas.append(f"Posicionamento: {bp.positioning}")
    if bp.mechanism:
        linhas.append(f"Mecanismo/diferencial: {bp.mechanism}")
    if bp.main_offer:
        linhas.append(f"Oferta principal: {bp.main_offer}")
    if bp.monetization_format:
        linhas.append(f"Monetização: {bp.monetization_format}")

    linhas.append("")
    if bp.price:
        etiqueta = "HIPÓTESE (sem benchmark real)" if bp.price_is_hypothesis else "preço"
        linhas.append(f"Preço [{etiqueta}]: {bp.price}")
    else:
        linhas.append("Preço: (sem hipótese ainda)")
    if bp.bonuses:
        linhas.append("Bônus possíveis: " + "; ".join(bp.bonuses))
    if bp.order_bump:
        linhas.append(f"Order bump possível: {bp.order_bump}")
    if bp.upsell:
        linhas.append("Upsell possível: " + "; ".join(bp.upsell))
    if bp.downsell:
        linhas.append("Downsell possível: " + "; ".join(bp.downsell))

    if bp.acquisition_channels:
        linhas.append("")
        linhas.append("Canais de aquisição: " + ", ".join(bp.acquisition_channels))
    if bp.sales_channels:
        linhas.append("Canais de venda: " + ", ".join(bp.sales_channels))

    if bp.headline or bp.sales_page_structure:
        linhas.append("")
        linhas.append("PÁGINA DE VENDAS")
        if bp.headline:
            linhas.append(f"Headline: {bp.headline}")
        if bp.promise:
            linhas.append(f"Promessa (responsável): {bp.promise}")
        if bp.sales_page_structure:
            linhas.append(f"Estrutura: {bp.sales_page_structure}")
        if bp.key_arguments:
            linhas.append("Principais argumentos: " + "; ".join(bp.key_arguments))
        if bp.objections:
            linhas.append("Objeções:")
            for o in bp.objections:
                linhas.append(f"  - {o.get('objecao', '?')} -> {o.get('resposta', '?')}")
        if bp.cta:
            linhas.append(f"CTA: {bp.cta}")

    if bp.funnel_structure or bp.email_sequence:
        linhas.append("")
        linhas.append("FUNIL")
        if bp.funnel_structure:
            linhas.append(f"Estrutura do funil: {bp.funnel_structure}")
        for email in bp.email_sequence:
            linhas.append(
                f"  E-mail {email.get('numero', '?')}: {email.get('assunto', '?')} "
                f"({email.get('objetivo', '?')})"
            )

    if bp.content_strategy or bp.content_channels:
        linhas.append("")
        linhas.append("CONTEÚDO")
        if bp.content_strategy:
            linhas.append(f"Estratégia: {bp.content_strategy}")
        if bp.content_channels:
            linhas.append("Canais: " + ", ".join(bp.content_channels))

    if bp.launch_strategy or bp.plan_30_days:
        linhas.append("")
        linhas.append("LANÇAMENTO")
        if bp.launch_strategy:
            linhas.append(f"Estratégia: {bp.launch_strategy}")
        for bloco in bp.plan_30_days:
            linhas.append(f"  {bloco.get('periodo', '?')}: " + "; ".join(bloco.get("acoes", [])))

    linhas.append("")
    linhas.append("HONESTIDADE (DADO / EVIDÊNCIA / HIPÓTESE / PENDÊNCIA)")
    if bp.evidence:
        linhas.append("Evidências: " + "; ".join(bp.evidence))
    if bp.assumptions:
        linhas.append("Hipóteses assumidas: " + "; ".join(bp.assumptions))
    if bp.missing_evidence:
        linhas.append("Pendências (evidência ausente): " + "; ".join(bp.missing_evidence))
    if bp.risks:
        linhas.append("Riscos: " + "; ".join(bp.risks))
    if bp.dependencies:
        linhas.append("Dependências: " + "; ".join(bp.dependencies))
    if bp.next_steps:
        linhas.append("Próximos passos: " + "; ".join(bp.next_steps))

    linhas.append("")
    linhas.append(f"Status do plano de negócio: {bp.approval_status}")
    linhas.append(
        "Nenhuma venda, receita, CPA, ROAS, conversão ou demanda foi "
        "inventada -- números desse tipo só existirão com tráfego real rodando."
    )
    if bp.approval_status == "READY_FOR_APPROVAL":
        linhas.append("")
        linhas.append('Responda "Aprovado" pra marcar este plano como aprovado (nenhum conteúdo/ativo é produzido automaticamente).')
    return "\n".join(linhas)


def gerenciar_negocio(entrada: str, session: str = "") -> str:
    """Ponto de entrada unico da Tool (montar / mostrar plano de negocio)."""
    texto = (entrada or "").strip().lower()
    if not texto:
        return ""

    brain = _resolver_projeto(session)
    if isinstance(brain, str):
        return brain

    if not blueprint_aprovado(brain):
        return _MENSAGEM_NAO_APROVADO

    if _contains_any(texto, frozenset(), _FRASES_HANDOFF):
        handoff = gerar_handoff(brain)
        if not handoff:
            status = brain.business_plan.approval_status if brain.business_plan else "nenhum plano ainda"
            return (
                "Ainda não há um plano de negócio aprovado para gerar o "
                f"handoff (status atual: {status})."
            )
        return _formatar_handoff(handoff)

    if brain.business_plan and _contains_any(texto, _PALAVRAS_MOSTRAR, _FRASES_MOSTRAR):
        # Ja calculado -- reexibe SEM gastar de novo no OpenRouter (cost-first).
        _sincronizar_pendencia_aprovacao(session, brain.project_id, brain.business_plan)
        return _formatar_plano_negocio(brain, brain.business_plan)

    store = get_project_brain_store()
    if brain.business_plan and "monte" not in texto and "montar" not in texto and "refaz" not in texto:
        # Pergunta generica sobre negocio/oferta/monetizacao com plano ja
        # existente: reaproveita em vez de gerar de novo.
        _sincronizar_pendencia_aprovacao(session, brain.project_id, brain.business_plan)
        return _formatar_plano_negocio(brain, brain.business_plan)

    plano = construir_plano_negocio(brain, llm=_get_llm_economico())
    brain.business_plan = plano
    brain.registrar_run("business_builder", f"Montou plano de negócio para '{brain.blueprint.recommended_product_type}'")
    store.save(brain)
    _sincronizar_pendencia_aprovacao(session, brain.project_id, plano)
    return _formatar_plano_negocio(brain, plano)


def get_tools() -> list[Tool]:
    return [
        Tool(
            "business_builder",
            "Transforma um produto ja aprovado em plano de negocio "
            "(oferta, monetizacao, funil, conteudo, lancamento)",
            [
                "negocio", "negócio", "monetiz",
                "modelo de negocio", "modelo de negócio",
                "plano de negocio", "plano de negócio",
                "monte a oferta", "montar a oferta", "estruture a oferta",
                "monte o modelo de negocio", "monte o modelo de negócio",
                "como vamos monetizar", "transforme em negocio",
                "transforme em negócio", "transforme esse produto em um negocio",
                "transforme esse produto em um negócio",
                "transforme o produto aprovado em um negocio",
                "transforme o produto aprovado em um negócio",
                "transforme esse produto aprovado em um negocio",
                "transforme esse produto aprovado em um negócio",
                # Fase 7 -- roteamento ampliado (nao depender exclusivamente
                # das frases acima, ja fragil por natureza).
                "businessplan", "business plan",
                "estrategia de negocio", "estratégia de negócio",
                "estrategia de monetizacao", "estratégia de monetização",
                "posicionamento",
                "handoff",
                *_FRASES_HANDOFF,
            ],
            gerenciar_negocio,
        ),
    ]
