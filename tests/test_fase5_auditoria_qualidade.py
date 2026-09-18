"""
Testes da auditoria final de qualidade do Paid Traffic Architect (Fase 5,
6º round de correcao pos-teste real). Todos os testes usam fixtures
GENERICAS -- nenhuma regra e hardcoded para o projeto real
`proj_cb094b4ef6a4` (velas artesanais); as mesmas regras precisam valer
para QUALQUER ProjectBrain.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

import pytest

from core.evidence_guard import sanitizar_claims_herdadas
from core.paid_traffic_architect import avaliar_prontidao, criar_plano_trafego
from memory.project_brain import Identidade, ProductBlueprint, ProjectBrain, TrafficPlan


def _brain_generico(tipo="ferramenta_web", nicho="produtos genericos", pais="US") -> ProjectBrain:
    """Fixture deliberadamente GENERICA -- nao usa velas artesanais nem
    qualquer dado do projeto real, pra provar que as regras nao sao
    hardcoded pra um projeto especifico."""
    brain = ProjectBrain(identidade=Identidade(project_id="proj_generico_xyz", name="Produto Generico"))
    brain.mercado.niche = nicho
    brain.mercado.target_country = pais
    brain.oportunidade.evidence = ["2 resultados no YouTube"]
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id,
        recommended_product_type=tipo,
        decision_status="APPROVED",
        target_audience="Publico generico interessado no nicho",
        country=pais,
        differentiation="Diferencial generico",
        evidence=["2 resultados no YouTube"],
    )
    return brain


class FakeLLMJSON:
    _provider_name = "fake:inteligente"

    def __init__(self, payload):
        self.payload = payload

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False))

    def is_alive(self):
        return True


def _canal(channel, role, **extra):
    base = {
        "channel": channel, "role": role, "priority": "media",
        "rationale": "Racional generico baseado em evidencia real",
        "campaign_objective": "Trafego", "campaign_structure": "1 campanha",
        "ad_sets_or_groups": ["Grupo generico"], "targeting_strategy": "Segmentacao generica",
        "keyword_strategy": None, "placements": [], "creative_requirements": ["Video generico"],
        "landing_destination": "Landing page", "conversion_event": "Lead",
        "test_hypothesis": "Hipotese generica de teste", "evidence_used": ["2 resultados no YouTube"],
        "assumptions": [], "risks": [],
    }
    base.update(extra)
    return base


def _payload_com_canais(canais, **extra):
    payload = {
        "objective": "Validar demanda", "audience_summary": "Publico generico",
        "channels": canais, "angles": ["Angulo generico"], "hooks": ["Hook generico"],
        "creative_matrix": [
            {"angle": "Angulo generico", "hook": "Hook generico", "format": "short_video",
             "channel": canais[0]["channel"] if canais else "TIKTOK_ADS", "audience": "Generico",
             "cta": "Saiba mais", "evidence_or_hypothesis": "HIPOTESE"},
        ],
        "testing_plan": ["Rodar por 7 dias"], "measurement_plan": ["CTR", "CPC"],
        "stop_conditions": ["Sem resultado em 5 dias"], "scale_conditions": ["10 leads"],
        "budget_scenarios": [
            {"nome": "LOW", "valor": "R$20/dia", "type": "PLANNING_ASSUMPTION"},
            {"nome": "STANDARD", "valor": "R$50/dia", "type": "PLANNING_ASSUMPTION"},
            {"nome": "EXPANDED", "valor": "R$150/dia", "type": "PLANNING_ASSUMPTION"},
        ],
        "assumptions": [], "unknowns": [], "risks": [], "approval_required_actions": [],
    }
    payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# MARKET CONTEXT GUARD
# ---------------------------------------------------------------------------

def test_mercado_existente_chega_ao_plano_via_nicho():
    """O blueprint.market raramente e preenchido -- o mercado real
    disponivel costuma estar em `mercado.niche`. O plano precisa
    aproveitar isso em vez de mostrar vazio."""
    brain = _brain_generico(nicho="suplementos esportivos", pais="US")
    payload = _payload_com_canais([_canal("TIKTOK_ADS", "PRIMARY_TEST")])
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert plano.market == "suplementos esportivos"
    assert plano.country == "US"
    assert plano.market != "REQUIRES_MARKET_DATA"


def test_mercado_ausente_vira_requires_market_data():
    brain = _brain_generico()
    brain.mercado.niche = None
    brain.mercado.market = None
    brain.blueprint.niche = None
    brain.blueprint.market = None
    payload = _payload_com_canais([_canal("TIKTOK_ADS", "PRIMARY_TEST")])
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert plano.market == "REQUIRES_MARKET_DATA"


def test_pais_ausente_vira_requires_market_data():
    brain = _brain_generico()
    brain.mercado.target_country = None
    brain.blueprint.country = None
    brain.origem.source_country = None
    payload = _payload_com_canais([_canal("TIKTOK_ADS", "PRIMARY_TEST")])
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert plano.country == "REQUIRES_MARKET_DATA"


# ---------------------------------------------------------------------------
# EVIDENCE GUARD PARA TODO O TRAFFIC PLAN
# ---------------------------------------------------------------------------

def test_fornecedor_nao_construido_nao_vira_fato():
    brain = _brain_generico()
    canal = _canal("TIKTOK_ADS", "PRIMARY_TEST", rationale="O produto dá acesso a fornecedores exclusivos")
    payload = _payload_com_canais([canal])
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    rationale = plano.channels[0]["rationale"]
    assert "acesso a fornecedores" not in rationale.lower() or "HIPÓTESE" in rationale
    assert "HIPÓTESE DE FUNCIONALIDADE" in rationale


def test_evidence_guard_cobre_unknowns_e_approval_actions():
    brain = _brain_generico()
    canal = _canal("TIKTOK_ADS", "PRIMARY_TEST")
    payload = _payload_com_canais(
        [canal],
        unknowns=["Não sabemos se o produto já ajudou mais de 10.000 pessoas"],
        approval_required_actions=["Confirmar que já temos rede de fornecedores estabelecida"],
    )
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert "10.000" not in " ".join(plano.unknowns)
    assert "REMOVIDA" in " ".join(plano.unknowns)
    assert "HIPÓTESE DE FUNCIONALIDADE" in " ".join(plano.approval_required_actions)


# ---------------------------------------------------------------------------
# SOCIAL PROOF GUARD
# ---------------------------------------------------------------------------

def test_prova_social_inexistente_nao_e_inventada():
    brain = _brain_generico()
    payload = _payload_com_canais([_canal("TIKTOK_ADS", "PRIMARY_TEST")])
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert plano.social_proof_status == "NOT_AVAILABLE"


def test_prova_social_removida_mesmo_se_llm_tentar_inventar():
    brain = _brain_generico()
    canal = _canal("TIKTOK_ADS", "PRIMARY_TEST", rationale="Já temos depoimentos de clientes satisfeitos")
    payload = _payload_com_canais([canal])
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert "depoimentos" not in plano.channels[0]["rationale"].lower() or "REMOVIDA" in plano.channels[0]["rationale"]


# ---------------------------------------------------------------------------
# ASSET GUARD
# ---------------------------------------------------------------------------

def test_ativo_inexistente_vira_asset_required():
    brain = _brain_generico()
    payload = _payload_com_canais([_canal("TIKTOK_ADS", "PRIMARY_TEST")])
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert plano.creative_matrix
    for item in plano.creative_matrix:
        assert item["asset_required"] is True


def test_asset_required_nunca_pode_ser_desligado_pelo_llm():
    """Mesmo se o LLM (por erro) mandar asset_required=false, a validacao
    nunca confia nisso -- nenhum ativo existe nesta fase, ponto final."""
    brain = _brain_generico()
    payload = _payload_com_canais([_canal("TIKTOK_ADS", "PRIMARY_TEST")])
    payload["creative_matrix"][0]["asset_required"] = False
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert plano.creative_matrix[0]["asset_required"] is True


# ---------------------------------------------------------------------------
# CHANNEL PRIORITIZATION GUARD -- exatamente UM PRIMARY_TEST
# ---------------------------------------------------------------------------

def test_exatamente_um_primary_test_quando_llm_manda_varios():
    brain = _brain_generico()
    canais = [
        _canal("TIKTOK_ADS", "PRIMARY_TEST"),
        _canal("META_ADS", "PRIMARY_TEST"),  # LLM (por erro) marcou 2 como primario
        _canal("GOOGLE_SEARCH", "SECONDARY_TEST"),
    ]
    payload = _payload_com_canais(canais)
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    primarios = [c for c in plano.channels if c["role"] == "PRIMARY_TEST"]
    assert len(primarios) == 1
    assert primarios[0]["channel"] == "TIKTOK_ADS"  # o primeiro fica, deterministico


def test_pode_haver_varios_secondary_test():
    brain = _brain_generico()
    canais = [
        _canal("TIKTOK_ADS", "PRIMARY_TEST"),
        _canal("META_ADS", "SECONDARY_TEST"),
        _canal("GOOGLE_SEARCH", "SECONDARY_TEST"),
    ]
    payload = _payload_com_canais(canais)
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    secundarios = [c for c in plano.channels if c["role"] == "SECONDARY_TEST"]
    assert len(secundarios) == 2


def test_sem_evidencia_para_escolher_primario_vira_needs_information():
    """Pedido explicito: 'nao inventar certeza' -- se nenhum canal foi
    classificado PRIMARY_TEST, o plano inteiro fica NEEDS_INFORMATION
    (preserva a analise, mas nao apresenta como pronto pra aprovar)."""
    brain = _brain_generico()
    canais = [
        _canal("TIKTOK_ADS", "SECONDARY_TEST"),
        _canal("META_ADS", "LATER"),
    ]
    payload = _payload_com_canais(canais)
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert plano.status == "NEEDS_INFORMATION"
    assert plano.channels  # a analise nao foi descartada
    assert any("primary" in m.lower() or "primário" in m.lower() or "canal" in m.lower() for m in plano.missing_information)


# ---------------------------------------------------------------------------
# BUDGET GUARD
# ---------------------------------------------------------------------------

def test_orcamento_ausente_vira_requires_user_input():
    brain = _brain_generico()
    payload = _payload_com_canais([_canal("TIKTOK_ADS", "PRIMARY_TEST")])
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert plano.budget_status == "REQUIRES_USER_INPUT"
    assert plano.budget_informado_pelo_usuario is None


def test_orcamento_informado_marca_provided_e_preserva_valor():
    brain = _brain_generico()
    payload = _payload_com_canais([_canal("TIKTOK_ADS", "PRIMARY_TEST")])
    orcamento = {"currency": "USD", "daily_budget": "30", "total_test_budget": None}
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload), orcamento_informado=orcamento)
    assert plano.budget_status == "PROVIDED"
    assert plano.budget_informado_pelo_usuario == orcamento
    assert plano.budget_scenarios == []  # nunca inventa cenario quando ha valor real


# ---------------------------------------------------------------------------
# KEYWORD DATA GUARD (Google Search) -- generico, qualquer projeto
# ---------------------------------------------------------------------------

def test_google_search_sem_keyword_data_continua_requires_keyword_data():
    brain = _brain_generico(nicho="qualquer outro nicho")
    canal = _canal("GOOGLE_SEARCH", "SECONDARY_TEST", keyword_strategy="REQUIRES_KEYWORD_DATA")
    payload = _payload_com_canais([_canal("TIKTOK_ADS", "PRIMARY_TEST"), canal])
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    google = next(c for c in plano.channels if c["channel"] == "GOOGLE_SEARCH")
    assert google["keyword_strategy"] == "REQUIRES_KEYWORD_DATA"


# ---------------------------------------------------------------------------
# METRICS GUARD
# ---------------------------------------------------------------------------

def test_metricas_nunca_sao_inventadas_como_fato():
    assert "REMOVIDA" in sanitizar_claims_herdadas("CTR esperado de 5% e ROAS esperado de 4x")
    assert "REMOVIDA" in sanitizar_claims_herdadas("CPA ideal de R$10")


def test_measurement_plan_e_so_lista_de_metricas_nunca_valores():
    brain = _brain_generico()
    payload = _payload_com_canais([_canal("TIKTOK_ADS", "PRIMARY_TEST")])
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    for metrica in plano.measurement_plan:
        assert not any(ch.isdigit() for ch in metrica)


# ---------------------------------------------------------------------------
# Plano continua funcionando normalmente com evidencia suficiente
# ---------------------------------------------------------------------------

def test_plano_fica_ready_for_approval_com_evidencia_e_um_primary_test():
    brain = _brain_generico()
    payload = _payload_com_canais([
        _canal("TIKTOK_ADS", "PRIMARY_TEST"),
        _canal("META_ADS", "SECONDARY_TEST"),
    ])
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert plano.status == "READY_FOR_APPROVAL"
    assert plano.esta_aprovado() is False


def test_needs_information_continua_funcionando_sem_blueprint():
    brain = ProjectBrain(identidade=Identidade(project_id="proj_vazio", name="x"))
    lacunas = avaliar_prontidao(brain)
    assert lacunas
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_payload_com_canais([_canal("TIKTOK_ADS", "PRIMARY_TEST")])))
    assert plano.status == "NEEDS_INFORMATION"


# ---------------------------------------------------------------------------
# Estrutural: nunca ha campo pra metrica/resultado inventado (regressao)
# ---------------------------------------------------------------------------

def test_estrutura_do_traffic_plan_nao_permite_metrica_fixa():
    from dataclasses import fields
    nomes = {f.name for f in fields(TrafficPlan)}
    proibidos = {"ctr", "cpc", "cpm", "cpa", "roas", "cvr", "vendas", "receita", "conversoes"}
    assert not (nomes & proibidos)
