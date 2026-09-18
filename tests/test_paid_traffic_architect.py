"""
Testes da Fase 5: Paid Traffic Architect (logica pura, sem Telegram/orchestrator).

Nada aqui bate em nenhuma API de Ads real nem gasta OpenRouter de verdade --
LLM e sempre um Fake controlado neste arquivo.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

import pytest

from core.paid_traffic_architect import avaliar_prontidao, criar_plano_trafego
from memory.project_brain import Identidade, ProductBlueprint, ProjectBrain, TrafficPlan


def _brain_minimo() -> ProjectBrain:
    return ProjectBrain(identidade=Identidade(project_id="proj_teste", name="x"))


def _brain_pronto(tipo="mini_app") -> ProjectBrain:
    brain = ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Curso de Velas"))
    brain.mercado.target_country = "BR"
    brain.oportunidade.evidence = ["3 resultados no TikTok"]
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id,
        recommended_product_type=tipo,
        decision_status="APPROVED",
        target_audience="Iniciantes em velas artesanais",
        country="BR",
        differentiation="Metodo passo a passo guiado",
        evidence=["3 resultados no TikTok"],
    )
    return brain


class FakeLLMJSON:
    _provider_name = "fake:inteligente"

    def __init__(self, payload):
        self.payload = payload
        self.chamadas = 0

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        self.chamadas += 1
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False))

    def is_alive(self):
        return True


class FakeLLMBoom:
    _provider_name = "fake:inteligente"

    def chat(self, messages, tools=None):
        raise RuntimeError("OpenRouter indisponivel (simulado)")

    def is_alive(self):
        return False


_PAYLOAD_VALIDO = {
    "objective": "Validar demanda com trafego pago de baixo custo",
    "audience_summary": "Iniciantes em velas artesanais no Brasil",
    "channels": [
        {
            "channel": "TIKTOK_ADS", "role": "PRIMARY_TEST", "priority": "alta",
            "rationale": "Evidencia real de TikTok ja coletada pelo Opportunity Analyst",
            "campaign_objective": "Trafego para landing page",
            "campaign_structure": "1 campanha, 2 conjuntos de anuncio",
            "ad_sets_or_groups": ["Interesse: artesanato", "Interesse: DIY"],
            "targeting_strategy": "Interesses amplos, otimizacao por evento de landing view",
            "keyword_strategy": None,
            "placements": ["Feed", "For You"],
            "creative_requirements": ["Video vertical 15s", "Hook nos 3 primeiros segundos"],
            "landing_destination": "Landing page do curso",
            "conversion_event": "ViewContent",
            "test_hypothesis": "Publico organico do TikTok converte em leads",
            "evidence_used": ["3 resultados no TikTok"],
            "assumptions": ["Publico do TikTok tem interesse real, nao so entretenimento"],
            "risks": ["Custo de aquisicao pode ser alto no inicio"],
        },
        {
            "channel": "GOOGLE_SEARCH", "role": "SECONDARY_TEST", "priority": "media",
            "rationale": "Existe intencao de busca provavel para 'como fazer velas artesanais'",
            "campaign_objective": "Leads",
            "campaign_structure": "1 campanha de busca, clusters por intencao",
            "ad_sets_or_groups": ["Cluster: aprender a fazer velas"],
            "targeting_strategy": "Busca por intencao",
            "keyword_strategy": "REQUIRES_KEYWORD_DATA",
            "placements": [],
            "creative_requirements": ["Headlines e descriptions"],
            "landing_destination": "Landing page do curso",
            "conversion_event": "Lead",
            "test_hypothesis": "Existe volume de busca organico pelo tema",
            "evidence_used": [],
            "assumptions": ["Existe volume de busca (nao confirmado)"],
            "risks": ["Sem dado real de volume/CPC"],
        },
    ],
    "angles": ["Aprenda um hobby rentavel", "Metodo passo a passo sem experiencia previa"],
    "hooks": ["Voce sabia que da pra fazer velas artesanais em casa?"],
    "creative_matrix": [
        {
            "angle": "Aprenda um hobby rentavel", "hook": "Voce sabia que da pra fazer velas em casa?",
            "format": "short_video", "channel": "TIKTOK_ADS", "audience": "Iniciantes",
            "cta": "Saiba mais", "evidence_or_hypothesis": "HIPOTESE -- baseado no angulo do concorrente",
            "asset_required": True,
        },
    ],
    "testing_plan": ["Rodar TikTok Ads por 7 dias antes de decidir escalar"],
    "measurement_plan": ["CTR", "CPC", "Taxa de conversao da landing"],
    "stop_conditions": ["Custo por lead 3x acima do esperado sem nenhum resultado em 5 dias"],
    "scale_conditions": ["Pelo menos 10 leads qualificados com custo aceitavel"],
    "budget_scenarios": [
        {"nome": "LOW", "valor": "R$20/dia", "type": "PLANNING_ASSUMPTION"},
        {"nome": "STANDARD", "valor": "R$50/dia", "type": "PLANNING_ASSUMPTION"},
        {"nome": "EXPANDED", "valor": "R$150/dia", "type": "PLANNING_ASSUMPTION"},
    ],
    "assumptions": ["Publico tem acesso a internet/smartphone"],
    "unknowns": ["Se o publico do TikTok converte em vendas reais"],
    "risks": ["Nenhum teste real de conversao feito ainda"],
    "approval_required_actions": ["Conectar conta de anuncio", "Publicar campanha", "Gastar orcamento real"],
}


# ---------------------------------------------------------------------------
# Pre-condicoes -- NEEDS_INFORMATION honesto (nunca fabrica plano)
# ---------------------------------------------------------------------------

def test_sem_blueprint_retorna_needs_information():
    brain = _brain_minimo()
    lacunas = avaliar_prontidao(brain)
    assert lacunas
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert plano.status == "NEEDS_INFORMATION"
    assert plano.missing_information


def test_blueprint_nao_aprovado_retorna_needs_information():
    brain = _brain_pronto()
    brain.blueprint.decision_status = "PENDING_APPROVAL"
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert plano.status == "NEEDS_INFORMATION"
    assert any("aprovado" in m.lower() for m in plano.missing_information)


def test_sem_publico_retorna_needs_information():
    brain = _brain_pronto()
    brain.blueprint.target_audience = None
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert plano.status == "NEEDS_INFORMATION"


def test_projeto_pronto_nao_gera_lacunas():
    brain = _brain_pronto()
    assert avaliar_prontidao(brain) == []


# ---------------------------------------------------------------------------
# Geracao com LLM (Fake) -- canais, criativos, orcamento, honestidade
# ---------------------------------------------------------------------------

def test_criar_plano_com_llm_valido_fica_ready_for_approval():
    brain = _brain_pronto()
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert plano.status == "READY_FOR_APPROVAL"
    assert plano.esta_aprovado() is False
    assert len(plano.channels) == 2


def test_canal_fora_do_vocabulario_fechado_e_descartado():
    payload = dict(_PAYLOAD_VALIDO)
    payload["channels"] = [dict(payload["channels"][0], channel="SNAPCHAT_ADS")]
    brain = _brain_pronto()
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert plano.channels == []


def test_role_invalido_vira_later():
    payload = json.loads(json.dumps(_PAYLOAD_VALIDO))
    payload["channels"][0]["role"] = "VAI_FUNCIONAR"
    brain = _brain_pronto()
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert plano.channels[0]["role"] == "LATER"


@pytest.mark.parametrize("canal_esperado", ["TIKTOK_ADS", "GOOGLE_SEARCH"])
def test_canais_suportados_tiktok_e_google(canal_esperado):
    brain = _brain_pronto()
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    canais = {c["channel"] for c in plano.channels}
    assert canal_esperado in canais


def test_meta_ads_suportado_no_vocabulario():
    from memory.project_brain import TRAFFIC_CHANNELS
    assert "META_ADS" in TRAFFIC_CHANNELS
    assert "GOOGLE_DISPLAY" in TRAFFIC_CHANNELS
    assert "YOUTUBE_ADS" in TRAFFIC_CHANNELS


def test_creative_matrix_nunca_gera_asset_so_especifica():
    brain = _brain_pronto()
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert plano.creative_matrix
    for item in plano.creative_matrix:
        assert item["asset_required"] is True


def test_orcamento_nao_informado_gera_cenarios_planning_assumption():
    brain = _brain_pronto()
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert plano.budget_informado_pelo_usuario is None
    assert len(plano.budget_scenarios) == 3
    nomes = {c["nome"] for c in plano.budget_scenarios}
    assert nomes == {"LOW", "STANDARD", "EXPANDED"}
    for cenario in plano.budget_scenarios:
        assert cenario["type"] == "PLANNING_ASSUMPTION"


def test_orcamento_informado_pelo_usuario_e_preservado_sem_cenarios():
    brain = _brain_pronto()
    orcamento = {"currency": "BRL", "daily_budget": "50", "total_test_budget": None}
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO), orcamento_informado=orcamento)
    assert plano.budget_informado_pelo_usuario == orcamento
    assert plano.budget_scenarios == []


def test_google_keyword_sem_dado_real_marcado_requires_keyword_data():
    brain = _brain_pronto()
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    google = next(c for c in plano.channels if c["channel"] == "GOOGLE_SEARCH")
    assert google["keyword_strategy"] == "REQUIRES_KEYWORD_DATA"


def test_measurement_plan_define_metricas_nao_resultados():
    brain = _brain_pronto()
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert "CTR" in plano.measurement_plan
    assert "CPC" in plano.measurement_plan
    # nunca um NUMERO de CTR/CPC -- so o NOME da metrica a observar
    for metrica in plano.measurement_plan:
        assert not any(ch.isdigit() for ch in metrica)


def test_llm_indisponivel_cai_no_fallback_sem_fabricar_prontidao():
    brain = _brain_pronto()
    plano = criar_plano_trafego(brain, llm=FakeLLMBoom())
    assert plano.generated_by == "fallback_deterministico"
    assert plano.status == "NEEDS_INFORMATION"
    assert plano.channels == []


def test_sem_llm_nenhum_cai_no_fallback():
    brain = _brain_pronto()
    plano = criar_plano_trafego(brain, llm=None)
    assert plano.generated_by == "fallback_deterministico"


def test_uma_unica_chamada_de_llm_gera_plano_inteiro():
    brain = _brain_pronto()
    fake = FakeLLMJSON(_PAYLOAD_VALIDO)
    criar_plano_trafego(brain, llm=fake)
    assert fake.chamadas == 1


# ---------------------------------------------------------------------------
# Honestidade estrutural -- nunca ha campo pra metrica/resultado inventado
# ---------------------------------------------------------------------------

def test_nao_existe_campo_para_metricas_de_performance_inventadas():
    from dataclasses import fields
    nomes = {f.name for f in fields(TrafficPlan)}
    proibidos = {"ctr", "cpc", "cpm", "cpa", "roas", "cvr", "vendas", "receita",
                 "conversoes", "demanda", "lucro", "volume_de_pesquisa", "resultados_historicos"}
    assert not (nomes & proibidos)


def test_esta_aprovado_so_true_para_approved_exato():
    tp = TrafficPlan(project_id="p1", status="READY_FOR_APPROVAL")
    assert tp.esta_aprovado() is False
    tp.status = "APPROVED"
    assert tp.esta_aprovado() is True
    tp.status = "NEEDS_INFORMATION"
    assert tp.esta_aprovado() is False


# ---------------------------------------------------------------------------
# Evidence Guard integrado -- claims do concorrente/metricas inventadas
# ---------------------------------------------------------------------------

def test_claim_de_concorrente_e_removida_do_plano():
    payload = json.loads(json.dumps(_PAYLOAD_VALIDO))
    payload["channels"][0]["rationale"] = "O concorrente já ajudou mais de 13.000 pessoas com esse anúncio"
    brain = _brain_pronto()
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert "13.000" not in plano.channels[0]["rationale"]
    assert "REMOVIDA" in plano.channels[0]["rationale"]


def test_metrica_de_trafego_inventada_e_removida():
    payload = json.loads(json.dumps(_PAYLOAD_VALIDO))
    payload["channels"][0]["rationale"] = "Esse canal deve ter ROAS esperado de 3x e CTR esperado de 4%"
    brain = _brain_pronto()
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(payload))
    assert "3x" not in plano.channels[0]["rationale"]
    assert "REMOVIDA" in plano.channels[0]["rationale"]


def test_oferta_vencedora_e_produto_comprovado_sao_removidos():
    from core.evidence_guard import sanitizar_claims_herdadas
    assert "REMOVIDA" in sanitizar_claims_herdadas("Essa é uma oferta vencedora, produto comprovado no mercado.")


def test_alta_demanda_e_vai_converter_sao_removidos():
    from core.evidence_guard import sanitizar_claims_herdadas
    assert "REMOVIDA" in sanitizar_claims_herdadas("Existe alta demanda e esse anúncio vai converter bem.")
