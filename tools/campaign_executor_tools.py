"""
Ferramentas do agente Campaign Executor (Fase 6).

Fluxo: Paid Traffic Architect -> TrafficPlan APPROVED -> aprovacao humana ->
CAMPAIGN EXECUTOR -> Project Brain (`campaign_spec`) -> DRY-RUN/PREVIEW ->
resposta.

GATE MAIS IMPORTANTE DESTA FASE: `gerenciar_campanha` chama
`avaliar_prontidao_campanha` ANTES de qualquer outra coisa no caminho de
criacao -- se o TrafficPlan nao estiver aprovado, a resposta e
DETERMINISTICA (nenhum LLM, nenhuma escrita no Project Brain, nenhuma
CampaignSpec criada).

Reaproveita o MESMO foco por sessao (`tools/opportunity_tools.py`) e o
Approval Gate central (`core/approval_gate.py`, Fase 6) -- nunca cria
memoria/estado paralelo.
"""

from __future__ import annotations

import logging
import re

from config.settings import settings
from core.approval_gate import eh_aprovacao, eh_rejeicao
from core.campaign_executor import avaliar_prontidao_campanha, criar_campaign_spec
from core.tool_registry import CAMPAIGN_EXECUTOR, ToolRegistry
from memory.project_brain import CampaignSpec, ProjectBrain
from tools.base import Tool
from tools.opportunity_tools import get_foco_atual, get_project_brain_store

logger = logging.getLogger(__name__)

_FRASES_STATUS = ("status da campanha", "qual o status da campanha")
_FRASES_PREVIEW = (
    "mostre como esta campanha ficaria", "mostre como essa campanha ficaria",
    "mostre como a campanha ficaria", "preview da campanha",
    "quero ver como vai ficar", "veja como ficaria a campanha",
    "como essa campanha ficaria antes de publicar",
    "como esta campanha ficaria antes de publicar",
)
_FRASES_CRIAR = (
    "prepare a campanha", "monte a campanha", "crie a campanha",
    "crie o rascunho da campanha", "estruture a campanha",
)

# Extracao DETERMINISTICA (sem LLM) de orcamento -- suporta simbolo
# (R$/US$/$) OU palavra por extenso (euros/dolares/reais), com ou sem
# periodo diario (correcao pos-teste real da Fase 6: "20 euros por dia" nao
# era reconhecido pelo padrao antigo, que so aceitava simbolo de moeda).
_MOEDA_PALAVRA = {
    "euro": "EUR", "euros": "EUR",
    "dolar": "USD", "dolares": "USD", "dólar": "USD", "dólares": "USD",
    "real": "BRL", "reais": "BRL",
}
_PADRAO_ORCAMENTO_CAMPANHA = re.compile(
    r"(?:(r\$|us\$|\$)\s*([\d]+(?:[.,]\d+)?)|([\d]+(?:[.,]\d+)?)\s*(euros?|d[óo]lares?|reais|real))"
    r"\s*(por dia|/dia|di[áa]rios?|ao dia)?",
    re.IGNORECASE,
)


def _extrair_orcamento_campanha(texto: str) -> dict | None:
    m = _PADRAO_ORCAMENTO_CAMPANHA.search(texto)
    if not m:
        return None
    simbolo, valor_simbolo, valor_palavra, moeda_palavra, periodo = m.groups()
    if simbolo:
        moeda = {"r$": "BRL", "us$": "USD", "$": "USD"}.get(simbolo.lower(), simbolo)
        valor = valor_simbolo
    else:
        moeda = _MOEDA_PALAVRA.get(moeda_palavra.lower())
        valor = valor_palavra
    eh_diario = bool(periodo)
    return {
        "currency": moeda,
        "daily": valor if eh_diario else None,
        "total": valor if not eh_diario else None,
        "source": "user_provided",
        "status": "PROVIDED",
    }


def _headers_ok() -> bool:
    return bool(settings.OPENROUTER_API_KEY) and settings.OPENROUTER_API_KEY != "COLE_SUA_CHAVE_AQUI"


_llm_inteligente_cache = None


def _get_llm_inteligente():
    """Campaign Executor usa o tier INTELIGENTE (mesma lógica do Paid
    Traffic Architect): estruturar uma campanha a partir de um plano já
    aprovado é uma tarefa de julgamento, não uma classificação simples."""
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
            logger.warning("=== [CAMPAIGN_EXECUTOR] Falha ao configurar OpenRouter: %s ===", exc)
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


def _get_pending_approval_store():
    """Reaproveita a MESMA `ProjectMemory` do `get_project_brain_store()`
    DESTE modulo -- nunca a de `tools.opportunity_tools` diretamente (mesmo
    motivo de `tools/paid_traffic_tools.py:_get_pending_approval_store`:
    nunca usar o banco de producao real durante testes que trocam
    `get_project_brain_store`)."""
    from memory.project_brain import PendingApprovalStore

    return PendingApprovalStore(get_project_brain_store().project_memory)


def _formatar_bloqueio(lacunas: list[str], brain: ProjectBrain, session: str) -> str:
    # Correcao estrutural (Fase 6): quando o bloqueio e especificamente por
    # o TrafficPlan ainda nao estar aprovado, registra deterministicamente
    # que a proxima aprovacao contextual valida desta sessao se refere ao
    # TRAFFIC_PLAN deste projeto -- isso e o que permite "Aprovado" (a
    # proxima mensagem) ser resolvido corretamente pelo Orchestrator (ver
    # `core/approval_router.py`), em vez de cair no assistente generico.
    tp = brain.traffic_plan
    if tp and tp.status == "READY_FOR_APPROVAL":
        _get_pending_approval_store().set_pending(session, brain.project_id, "TRAFFIC_PLAN", "APPROVE")

    linhas = ["Ainda não é possível preparar a campanha para este projeto:", ""]
    for lacuna in lacunas:
        linhas.append(f"  - {lacuna}")
    linhas.append("")
    linhas.append(f"Projeto: {brain.project_id}")
    return "\n".join(linhas)


def _formatar_campaign_spec(brain: ProjectBrain, spec: CampaignSpec) -> str:
    linhas = [
        "🎯 ESPECIFICAÇÃO DE CAMPANHA (CampaignSpec)",
        "",
        f"Projeto: {brain.project_id} | Campanha: {spec.campaign_id} | Versão: {spec.version} | Status: {spec.status}",
    ]

    if spec.status == "NEEDS_INFORMATION":
        linhas.append("")
        linhas.append("Ainda não há informação suficiente para uma especificação pronta pra aprovar:")
        for m in spec.missing_data:
            linhas.append(f"  - {m}")
        linhas.append("")
        linhas.append("Modo: DRY_RUN")
        linhas.append("Nenhuma campanha foi publicada. Nenhum dinheiro foi gasto.")
        return "\n".join(linhas)

    linhas.append("")
    linhas.append(f"Canal: {spec.channel}")
    if spec.objective:
        linhas.append(f"Objetivo: {spec.objective}")
    linhas.append(f"País: {spec.country or 'REQUIRES_MARKET_DATA'} / Idioma: {spec.language or 'REQUIRES_MARKET_DATA'}")
    if spec.destination:
        linhas.append(f"Destino: {spec.destination}")
    if spec.conversion_event:
        linhas.append(f"Evento de conversão: {spec.conversion_event}")

    linhas.append("")
    b = spec.budget or {}
    if b.get("status") == "REQUIRES_BUDGET":
        linhas.append('Orçamento: REQUIRES_BUDGET (informe um valor real -- ex.: "20 euros por dia")')
    else:
        if b.get("daily"):
            linhas.append(f"Orçamento: {b['daily']} {b.get('currency')} por dia [{b.get('source')}]")
        elif b.get("total"):
            linhas.append(f"Orçamento: {b['total']} {b.get('currency')} total [{b.get('source')}]")
        else:
            linhas.append(f"Orçamento: {b.get('status')}")

    if spec.campaign_structure:
        linhas.append("")
        linhas.append(f"Estrutura: {spec.campaign_structure}")
    if spec.ad_sets:
        linhas.append("Ad sets/grupos: " + "; ".join(spec.ad_sets))
    if spec.audience_hypotheses:
        linhas.append("Público/hipóteses: " + "; ".join(spec.audience_hypotheses))
    if spec.placements:
        linhas.append("Posicionamentos: " + ", ".join(spec.placements))
    if spec.creative_requirements:
        linhas.append("Criativos necessários: " + "; ".join(spec.creative_requirements))
    if spec.copy_requirements:
        linhas.append("Copy necessária: " + "; ".join(spec.copy_requirements))
    if spec.keyword_requirements:
        linhas.append("Keywords: " + "; ".join(spec.keyword_requirements))
    if spec.tracking_requirements:
        linhas.append("Tracking: " + "; ".join(spec.tracking_requirements))
    if spec.schedule:
        linhas.append(f"Cronograma: {spec.schedule}")
    if spec.experiments:
        linhas.append("Experimentos: " + "; ".join(spec.experiments))
    if spec.missing_data:
        linhas.append("")
        linhas.append("Dados faltantes: " + "; ".join(spec.missing_data))
    if spec.risks:
        linhas.append("Riscos: " + "; ".join(spec.risks))
    if spec.evidence_summary:
        linhas.append("Evidências: " + "; ".join(spec.evidence_summary))

    linhas.append("")
    linhas.append(f"Status: {spec.status}")
    linhas.append("Modo: DRY_RUN")
    linhas.append("")
    linhas.append("Nenhuma campanha foi publicada. Nenhum dinheiro foi gasto.")

    if spec.approval_required:
        linhas.append("")
        linhas.append("Ações que exigem aprovação humana explícita antes de acontecer:")
        for acao in spec.approval_required:
            linhas.append(f"  - {acao}")

    if spec.status == "READY_FOR_APPROVAL":
        linhas.append("")
        linhas.append('Responda "Aprovado" pra marcar esta especificação como aprovada (nenhuma campanha é criada/publicada automaticamente).')
    return "\n".join(linhas)


_registry_cache = None


def _obter_registry() -> ToolRegistry:
    global _registry_cache
    if _registry_cache is None:
        from core.tool_registry import criar_registry_padrao

        _registry_cache = criar_registry_padrao()
    return _registry_cache


def _preparar_e_persistir(brain: ProjectBrain, orcamento: dict | None, versao_anterior: CampaignSpec | None) -> CampaignSpec:
    registry: ToolRegistry = _obter_registry()
    spec = registry.executar(
        CAMPAIGN_EXECUTOR,
        brain=brain,
        llm=_get_llm_inteligente(),
        orcamento_informado=orcamento,
        versao_anterior=versao_anterior,
    )
    if not isinstance(spec, CampaignSpec):
        raise RuntimeError(f"Tool Registry não devolveu uma CampaignSpec válida: {spec!r}")
    return spec


def _sincronizar_pendencia_aprovacao(session: str, project_id: str, spec: CampaignSpec) -> None:
    """Mesmo princípio de `tools/paid_traffic_tools.py:_sincronizar_pendencia_aprovacao`
    -- registra que a próxima aprovação contextual válida desta sessão se
    refere à CAMPAIGN_SPEC deste projeto, sempre que ela chega/permanece em
    READY_FOR_APPROVAL."""
    if spec.status == "READY_FOR_APPROVAL":
        _get_pending_approval_store().set_pending(session, project_id, "CAMPAIGN_SPEC", "APPROVE")


def _aprovar(brain: ProjectBrain, session: str = "") -> str:
    store = get_project_brain_store()
    spec = brain.campaign_spec
    if not spec or spec.status != "READY_FOR_APPROVAL":
        return (
            "Ainda não há uma especificação de campanha pronta pra aprovar "
            f"(status atual: {spec.status if spec else 'nenhuma especificação'})."
        )
    spec.status = "APPROVED"
    brain.registrar_aprovacao("CAMPAIGN_SPEC_APPROVED")
    store.save(brain)
    _get_pending_approval_store().clear_pending(session)
    return (
        "✅ Especificação de campanha aprovada -- aprovada como "
        "ESPECIFICAÇÃO, não como execução.\n\n"
        "Nenhuma conta de anúncio foi conectada, nenhuma campanha foi "
        "publicada e nenhum valor foi gasto -- a publicação externa "
        "permanece desabilitada nesta fase, mesmo com a especificação "
        "aprovada.\n\n"
        f"Projeto: {brain.project_id} | Status: {spec.status} | Modo: {spec.execution_mode}"
    )


def _rejeitar(brain: ProjectBrain, session: str = "") -> str:
    store = get_project_brain_store()
    spec = brain.campaign_spec
    if not spec:
        return "Ainda não há nenhuma especificação de campanha para rejeitar."
    spec.status = "NOT_STARTED"
    brain.registrar_aprovacao("CAMPAIGN_SPEC_REJECTED")
    store.save(brain)
    _get_pending_approval_store().clear_pending(session)
    return f"Entendido, especificação de campanha rejeitada.\n\nProjeto: {brain.project_id}"


def gerenciar_campanha(entrada: str, session: str = "") -> str:
    """Ponto de entrada único da Tool (criar / preview / status / aprovar /
    rejeitar especificação de campanha)."""
    texto_original = (entrada or "").strip()
    texto = texto_original.lower()
    if not texto:
        return ""

    brain = _resolver_projeto(session)
    if isinstance(brain, str):
        return brain

    spec = brain.campaign_spec

    if spec and eh_aprovacao(texto):
        return _aprovar(brain, session)
    if spec and eh_rejeicao(texto):
        return _rejeitar(brain, session)

    if _contains_any(texto, frozenset(), _FRASES_STATUS):
        if not spec:
            return f"Ainda não há campanha preparada para este projeto.\n\nProjeto: {brain.project_id}"
        return f"Status da campanha: {spec.status} (versão {spec.version})\n\nProjeto: {brain.project_id}"

    if _contains_any(texto, frozenset(), _FRASES_PREVIEW):
        if not spec:
            return (
                f'Ainda não há uma campanha preparada para pré-visualizar -- '
                f'peça "prepare a campanha" primeiro.\n\nProjeto: {brain.project_id}'
            )
        _sincronizar_pendencia_aprovacao(session, brain.project_id, spec)
        return _formatar_campaign_spec(brain, spec)  # zero LLM -- so formata o que ja existe

    # Default: CREATE_CAMPAIGN_SPEC.
    #
    # GATE MAIS IMPORTANTE DA FASE 6: checado ANTES de qualquer outra coisa.
    # Se o TrafficPlan ainda nao estiver aprovado, a resposta e
    # DETERMINISTICA -- NENHUM LLM e chamado, NENHUMA CampaignSpec e criada,
    # NENHUMA escrita acontece no Project Brain.
    lacunas = avaliar_prontidao_campanha(brain)
    if lacunas:
        return _formatar_bloqueio(lacunas, brain, session)

    if spec and spec.status != "NEEDS_INFORMATION":
        _sincronizar_pendencia_aprovacao(session, brain.project_id, spec)
        return _formatar_campaign_spec(brain, spec)  # cache -- zero custo novo

    store = get_project_brain_store()
    orcamento = _extrair_orcamento_campanha(texto_original)
    versao_anterior_real = spec if (spec and spec.status != "NEEDS_INFORMATION") else None
    novo_spec = _preparar_e_persistir(brain, orcamento, versao_anterior_real)
    brain.campaign_spec = novo_spec
    brain.registrar_run("campaign_executor", f"Criou especificação de campanha (status {novo_spec.status})")
    store.save(brain)
    _sincronizar_pendencia_aprovacao(session, brain.project_id, novo_spec)
    return _formatar_campaign_spec(brain, novo_spec)


def get_tools() -> list[Tool]:
    return [
        Tool(
            "campaign_executor",
            "Transforma um plano de tráfego já aprovado numa especificação "
            "de campanha (CampaignSpec), sem publicar nem gastar nada",
            [
                "campanha", "campanhas",
                "prepare a campanha", "monte a campanha", "crie a campanha",
                "crie o rascunho da campanha", "estruture a campanha",
                "mostre como esta campanha ficaria", "preview da campanha",
                "quero ver como vai ficar", "veja como ficaria a campanha",
                "status da campanha", "qual o status da campanha",
                # continuacao (aprovacao/rejeicao) -- mesmo motivo do Paid
                # Traffic Architect: precisa ser superset do Approval Gate.
                "aprovado", "aprovada", "aprovo", "autorizado", "autorizo",
                "confirmado", "confirmo", "rejeitado", "rejeitada", "rejeito",
                "pode criar", "pode seguir", "nao gostei", "não gostei",
                "quero outro", "outro plano",
            ],
            gerenciar_campanha,
            matcher=lambda t: any(f in t.lower() for f in _FRASES_CRIAR),
        ),
    ]
