"""
Testes da Fase 6: Campaign Executor (lógica pura, sem Telegram/orchestrator).

Nada aqui bate em nenhuma API de Ads real nem gasta OpenRouter de verdade --
LLM é sempre um Fake controlado neste arquivo.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

from core.campaign_executor import avaliar_prontidao_campanha, criar_campaign_spec
from memory.project_brain import CampaignSpec, Identidade, ProductBlueprint, ProjectBrain, TrafficPlan


def _canal_primario_valido() -> dict:
    return {
        "channel": "TIKTOK_ADS", "role": "PRIMARY_TEST", "priority": "alta",
        "rationale": "Evidencia real de TikTok ja coletada", "campaign_objective": "Trafego",
        "campaign_structure": "1 campanha", "ad_sets_or_groups": ["Interesse: artesanato"],
        "targeting_strategy": "Interesses amplos", "keyword_strategy": None,
        "placements": ["Feed"], "creative_requirements": ["Video vertical"],
        "landing_destination": "Landing page", "conversion_event": "ViewContent",
        "test_hypothesis": "Publico converte", "evidence_used": ["TikTok"],
        "assumptions": [], "risks": [],
    }


def _brain_com_traffic_plan(status="APPROVED", channels=None) -> ProjectBrain:
    brain = ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Curso de Velas"))
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id, decision_status="APPROVED",
        recommended_product_type="mini_app", target_audience="Iniciantes",
        country="BR",
    )
    brain.traffic_plan = TrafficPlan(
        project_id=brain.project_id, version=1, status=status,
        objective="Validar demanda", country="BR", language="pt",
        audience_summary="Iniciantes em velas artesanais",
        channels=channels if channels is not None else [_canal_primario_valido()],
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
    "campaign_structure": "1 campanha, 2 ad sets por interesse",
    "ad_sets": ["Interesse: artesanato", "Interesse: DIY"],
    "audience_hypotheses": ["Mulheres 25-45 interessadas em artesanato (hipótese)"],
    "placements": ["Feed", "For You"],
    "creative_requirements": ["Vídeo vertical 15s com hook nos 3 primeiros segundos"],
    "copy_requirements": ["Headline focada no método passo a passo"],
    "keyword_requirements": [],
    "tracking_requirements": ["Pixel de ViewContent na landing page"],
    "schedule": "Rodar por 7 dias corridos antes de revisar",
    "experiments": ["Testar 2 hooks diferentes em paralelo"],
    "risks": ["Custo de aquisição pode ser alto no início"],
    "missing_data": [],
}


# ---------------------------------------------------------------------------
# GATE -- TrafficPlan precisa estar APPROVED (teste A/B do requisito)
# ---------------------------------------------------------------------------

def test_traffic_plan_nao_aprovado_gera_lacuna_e_nunca_fabrica_spec():
    for status in ("READY_FOR_APPROVAL", "NEEDS_INFORMATION", "DRAFT"):
        brain = _brain_com_traffic_plan(status=status)
        lacunas = avaliar_prontidao_campanha(brain)
        assert lacunas
        assert any("aprovado" in m.lower() for m in lacunas)
        spec = criar_campaign_spec(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
        assert spec.status == "NEEDS_INFORMATION"
        assert spec.channel is None


def test_sem_traffic_plan_nenhum_gera_lacuna():
    brain = ProjectBrain(identidade=Identidade(project_id="proj_x", name="x"))
    lacunas = avaliar_prontidao_campanha(brain)
    assert lacunas
    assert "trafego" in lacunas[0].lower() or "tráfego" in lacunas[0].lower()


def test_sem_canal_primary_test_gera_lacuna():
    canal_secundario = dict(_canal_primario_valido(), role="SECONDARY_TEST")
    brain = _brain_com_traffic_plan(status="APPROVED", channels=[canal_secundario])
    lacunas = avaliar_prontidao_campanha(brain)
    assert lacunas
    assert any("primary_test" in m.lower() for m in lacunas)


def test_traffic_plan_aprovado_nao_gera_lacunas():
    brain = _brain_com_traffic_plan(status="APPROVED")
    assert avaliar_prontidao_campanha(brain) == []


def test_traffic_plan_aprovado_gera_campaign_spec_ready_for_approval():
    brain = _brain_com_traffic_plan(status="APPROVED")
    spec = criar_campaign_spec(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert spec.status == "READY_FOR_APPROVAL"
    assert spec.esta_aprovado() is False
    assert spec.channel == "TIKTOK_ADS"
    assert spec.campaign_id.startswith("camp_")


# ---------------------------------------------------------------------------
# Orcamento -- nunca inventado, extraido deterministicamente na camada de Tools
# ---------------------------------------------------------------------------

def test_orcamento_informado_e_preservado_sem_alteracao():
    brain = _brain_com_traffic_plan(status="APPROVED")
    orcamento = {"currency": "EUR", "daily": "20", "total": None, "source": "user_provided", "status": "PROVIDED"}
    spec = criar_campaign_spec(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO), orcamento_informado=orcamento)
    assert spec.budget == orcamento


def test_sem_orcamento_informado_fica_requires_budget():
    brain = _brain_com_traffic_plan(status="APPROVED")
    spec = criar_campaign_spec(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert spec.budget["status"] == "REQUIRES_BUDGET"
    assert spec.budget["currency"] is None


# ---------------------------------------------------------------------------
# Google Search -- keyword_requirements sempre inclui REQUIRES_KEYWORD_DATA
# ---------------------------------------------------------------------------

def test_google_search_sem_keyword_data_marcado_requires_keyword_data():
    canal_google = dict(_canal_primario_valido(), channel="GOOGLE_SEARCH")
    brain = _brain_com_traffic_plan(status="APPROVED", channels=[canal_google])
    spec = criar_campaign_spec(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert "REQUIRES_KEYWORD_DATA" in spec.keyword_requirements


def test_canal_nao_google_nao_forca_keyword_data():
    brain = _brain_com_traffic_plan(status="APPROVED")  # TIKTOK_ADS
    spec = criar_campaign_spec(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert "REQUIRES_KEYWORD_DATA" not in spec.keyword_requirements


# ---------------------------------------------------------------------------
# Fallback determinístico -- nunca fabrica prontidão sem LLM
# ---------------------------------------------------------------------------

def test_llm_indisponivel_cai_no_fallback_sem_fabricar_prontidao():
    brain = _brain_com_traffic_plan(status="APPROVED")
    spec = criar_campaign_spec(brain, llm=FakeLLMBoom())
    assert spec.generated_by == "fallback_deterministico"
    assert spec.status == "NEEDS_INFORMATION"


def test_sem_llm_nenhum_cai_no_fallback():
    brain = _brain_com_traffic_plan(status="APPROVED")
    spec = criar_campaign_spec(brain, llm=None)
    assert spec.generated_by == "fallback_deterministico"


def test_uma_unica_chamada_de_llm_gera_spec_inteira():
    brain = _brain_com_traffic_plan(status="APPROVED")
    fake = FakeLLMJSON(_PAYLOAD_VALIDO)
    criar_campaign_spec(brain, llm=fake)
    assert fake.chamadas == 1


# ---------------------------------------------------------------------------
# Honestidade estrutural -- nunca há campo pra métrica inventada; execução
# externa sempre desabilitada, mesmo aprovado.
# ---------------------------------------------------------------------------

def test_nao_existe_campo_para_metricas_de_performance_inventadas():
    from dataclasses import fields
    nomes = {f.name for f in fields(CampaignSpec)}
    proibidos = {"ctr", "cpc", "cpm", "cpa", "roas", "cvr", "vendas", "receita",
                 "conversoes", "demanda", "lucro", "resultados_historicos"}
    assert not (nomes & proibidos)


def test_execution_mode_sempre_disabled_mesmo_apos_criacao():
    brain = _brain_com_traffic_plan(status="APPROVED")
    spec = criar_campaign_spec(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert spec.execution_mode == "EXTERNAL_EXECUTION_DISABLED"
    assert spec.external_execution_status == "NOT_EXECUTED"


def test_esta_aprovado_so_true_para_approved_exato():
    spec = CampaignSpec(project_id="p1", status="READY_FOR_APPROVAL")
    assert spec.esta_aprovado() is False
    spec.status = "APPROVED"
    assert spec.esta_aprovado() is True
    # mesmo aprovada, o modo de execucao continua desabilitado -- aprovacao
    # da ESPECIFICACAO nunca libera execucao externa nesta fase.
    assert spec.execution_mode == "EXTERNAL_EXECUTION_DISABLED"


def test_esta_aprovado_false_para_needs_information():
    spec = CampaignSpec(project_id="p1", status="NEEDS_INFORMATION")
    assert spec.esta_aprovado() is False


# ---------------------------------------------------------------------------
# Evidence Guard integrado -- claim de concorrente nunca vira fato do produto
# ---------------------------------------------------------------------------

def test_claim_de_concorrente_e_removida_da_spec():
    payload = json.loads(json.dumps(_PAYLOAD_VALIDO))
    payload["campaign_structure"] = "O concorrente já ajudou mais de 13.000 pessoas com esse anúncio"
    brain = _brain_com_traffic_plan(status="APPROVED")
    spec = criar_campaign_spec(brain, llm=FakeLLMJSON(payload))
    assert "13.000" not in spec.campaign_structure
    assert "REMOVIDA" in spec.campaign_structure


def test_metrica_inventada_e_removida_da_spec():
    payload = json.loads(json.dumps(_PAYLOAD_VALIDO))
    payload["risks"] = ["Esse canal deve ter ROAS esperado de 3x"]
    brain = _brain_com_traffic_plan(status="APPROVED")
    spec = criar_campaign_spec(brain, llm=FakeLLMJSON(payload))
    assert not any("3x" in r for r in spec.risks)
