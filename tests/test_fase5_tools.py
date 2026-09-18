"""
Testes da Fase 5: camada de Tools do Paid Traffic Architect -- persistencia
real no Project Brain (sem banco/JSON paralelo), sobrevivencia a restart,
isolamento entre projetos, gate de aprovacao explicita (READY_FOR_APPROVAL
!= APPROVED), GET/STATUS com zero chamadas de LLM, integracao com o
Artifact Manifest (GET_CURRENT_PROJECT_MANIFEST continua determinístico) e
ausencia total de acoes externas/gasto.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

import pytest

import tools.paid_traffic_tools as ptt
import tools.product_factory_tools as pft
from memory.layers import ProjectMemory
from memory.project_brain import ProductBlueprint, ProjectBrainStore
from storage import SQLiteMemory


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


_PAYLOAD_MINIMO = {
    "objective": "Validar demanda", "audience_summary": "Iniciantes em velas artesanais",
    "channels": [
        {
            "channel": "TIKTOK_ADS", "role": "PRIMARY_TEST", "priority": "alta",
            "rationale": "Evidencia real de TikTok ja coletada", "campaign_objective": "Trafego",
            "campaign_structure": "1 campanha", "ad_sets_or_groups": ["Interesse: artesanato"],
            "targeting_strategy": "Interesses amplos", "keyword_strategy": None,
            "placements": ["Feed"], "creative_requirements": ["Video vertical"],
            "landing_destination": "Landing page", "conversion_event": "ViewContent",
            "test_hypothesis": "Publico converte", "evidence_used": ["TikTok"],
            "assumptions": [], "risks": [],
        },
    ],
    "angles": ["Aprenda um hobby rentavel"], "hooks": ["Voce sabia?"],
    "creative_matrix": [], "testing_plan": ["Rodar por 7 dias"],
    "measurement_plan": ["CTR", "CPC"], "stop_conditions": ["Custo alto sem resultado"],
    "scale_conditions": ["10 leads qualificados"],
    "budget_scenarios": [
        {"nome": "LOW", "valor": "R$20/dia", "type": "PLANNING_ASSUMPTION"},
        {"nome": "STANDARD", "valor": "R$50/dia", "type": "PLANNING_ASSUMPTION"},
        {"nome": "EXPANDED", "valor": "R$150/dia", "type": "PLANNING_ASSUMPTION"},
    ],
    "assumptions": [], "unknowns": [], "risks": [], "approval_required_actions": [],
}


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_fase5_tools.db"


@pytest.fixture()
def brain_store(db_path):
    backend = SQLiteMemory(db_path)
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def _brain_pronto(store, tipo="mini_app"):
    brain = store.create(name="Curso de Velas", tipo="opportunity")
    brain.mercado.target_country = "BR"
    brain.oportunidade.evidence = ["3 resultados no TikTok"]
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id, recommended_product_type=tipo,
        decision_status="APPROVED", target_audience="Iniciantes em velas artesanais",
        country="BR", differentiation="Metodo guiado", evidence=["3 resultados no TikTok"],
    )
    store.save(brain)
    return brain


# ---------------------------------------------------------------------------
# Criacao + persistencia real (nunca banco/JSON paralelo)
# ---------------------------------------------------------------------------

def test_criar_plano_persiste_no_mesmo_project_brain(monkeypatch, brain_store):
    brain = _brain_pronto(brain_store)
    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(ptt, "get_project_brain_store", lambda: brain_store)
    fake = FakeLLMJSON(_PAYLOAD_MINIMO)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: fake)

    resposta = ptt.gerenciar_trafego("Cris, crie o plano de tráfego deste projeto.", "telegram:1")
    assert "PLANO DE TRÁFEGO" in resposta
    assert fake.chamadas == 1

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.traffic_plan is not None
    assert recarregado.traffic_plan.status == "READY_FOR_APPROVAL"
    assert recarregado.traffic_plan.project_id == brain.project_id


def test_plano_sobrevive_a_restart(monkeypatch, db_path, brain_store):
    brain = _brain_pronto(brain_store)
    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(ptt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_MINIMO))

    ptt.gerenciar_trafego("Cris, crie o plano de tráfego deste projeto.", "telegram:1")

    novo_backend = SQLiteMemory(db_path)
    novo_store = ProjectBrainStore(ProjectMemory(novo_backend))
    try:
        recarregado = novo_store.load(brain.project_id)
        assert recarregado.traffic_plan is not None
        assert recarregado.traffic_plan.status == "READY_FOR_APPROVAL"
        assert len(recarregado.traffic_plan.channels) == 1
    finally:
        novo_backend.close()


def test_isolamento_entre_projetos(monkeypatch, brain_store):
    brain_a = _brain_pronto(brain_store)
    brain_b = _brain_pronto(brain_store)
    assert brain_a.project_id != brain_b.project_id

    monkeypatch.setattr(ptt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_MINIMO))

    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain_a.project_id)
    ptt.gerenciar_trafego("crie o plano de tráfego", "telegram:A")

    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain_b.project_id)
    resposta_b = ptt.gerenciar_trafego("mostre o plano de tráfego", "telegram:B")
    assert "Ainda não há plano de tráfego" in resposta_b

    a_recarregado = brain_store.load(brain_a.project_id)
    b_recarregado = brain_store.load(brain_b.project_id)
    assert a_recarregado.traffic_plan is not None
    assert b_recarregado.traffic_plan is None


# ---------------------------------------------------------------------------
# Gate de aprovacao -- READY_FOR_APPROVAL != APPROVED
# ---------------------------------------------------------------------------

def test_ready_for_approval_nunca_vira_approved_sozinho(monkeypatch, brain_store):
    brain = _brain_pronto(brain_store)
    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(ptt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_MINIMO))

    ptt.gerenciar_trafego("crie o plano de tráfego", "telegram:1")
    for pergunta in ["está bom?", "qual o plano?", "mostre o plano de tráfego", "o que acha?", "pronto?"]:
        ptt.gerenciar_trafego(pergunta, "telegram:1")
        recarregado = brain_store.load(brain.project_id)
        assert recarregado.traffic_plan.status != "APPROVED"


def test_aprovacao_explicita_funciona(monkeypatch, brain_store):
    brain = _brain_pronto(brain_store)
    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(ptt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_MINIMO))

    ptt.gerenciar_trafego("crie o plano de tráfego", "telegram:1")
    resposta = ptt.gerenciar_trafego("Aprovado.", "telegram:1")
    assert "aprovado" in resposta.lower()

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.traffic_plan.esta_aprovado() is True
    assert "nenhuma conta de anúncio foi conectada" in resposta.lower() or "nenhuma campanha foi criada" in resposta.lower()


def test_nao_ha_plano_para_aprovar_antes_de_criar(monkeypatch, brain_store):
    brain = _brain_pronto(brain_store)
    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(ptt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_MINIMO))

    # "Aprovado." sozinho, sem nenhum plano ainda -- gerenciar_trafego cai no
    # fluxo padrao (CREATE), ja que so aprova quando ja existe brain.traffic_plan.
    resposta = ptt.gerenciar_trafego("Aprovado.", "telegram:1")
    assert "PLANO DE TRÁFEGO" in resposta or "não há" in resposta.lower()


# ---------------------------------------------------------------------------
# GET/STATUS -- zero LLM quando ja persistido (cost-first)
# ---------------------------------------------------------------------------

def test_get_traffic_plan_zero_llm_quando_ja_persistido(monkeypatch, brain_store):
    brain = _brain_pronto(brain_store)
    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(ptt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_MINIMO))

    ptt.gerenciar_trafego("crie o plano de tráfego", "telegram:1")

    def _boom():
        raise AssertionError("GET_TRAFFIC_PLAN nao deveria chamar o LLM de novo")
    monkeypatch.setattr(ptt, "_get_llm_inteligente", _boom)

    resposta = ptt.gerenciar_trafego("mostre o plano de tráfego atual", "telegram:1")
    assert "PLANO DE TRÁFEGO" in resposta


def test_get_traffic_status_zero_llm(monkeypatch, brain_store):
    brain = _brain_pronto(brain_store)
    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(ptt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_MINIMO))

    ptt.gerenciar_trafego("crie o plano de tráfego", "telegram:1")

    def _boom():
        raise AssertionError("GET_TRAFFIC_STATUS nao deveria chamar o LLM")
    monkeypatch.setattr(ptt, "_get_llm_inteligente", _boom)

    resposta = ptt.gerenciar_trafego("qual o status do plano de tráfego?", "telegram:1")
    assert "READY_FOR_APPROVAL" in resposta


def test_revisar_plano_sempre_chama_llm_de_novo(monkeypatch, brain_store):
    brain = _brain_pronto(brain_store)
    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(ptt, "get_project_brain_store", lambda: brain_store)
    fake1 = FakeLLMJSON(_PAYLOAD_MINIMO)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: fake1)
    ptt.gerenciar_trafego("crie o plano de tráfego", "telegram:1")

    fake2 = FakeLLMJSON(_PAYLOAD_MINIMO)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: fake2)
    ptt.gerenciar_trafego("revise o plano de tráfego", "telegram:1")
    assert fake2.chamadas == 1

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.traffic_plan.version == 2


# ---------------------------------------------------------------------------
# Integracao com o Artifact Manifest -- continua deterministico
# ---------------------------------------------------------------------------

def test_manifesto_reflete_traffic_plan_sem_novo_llm_ou_write(monkeypatch, brain_store):
    brain = _brain_pronto(brain_store)
    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(ptt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_MINIMO))
    ptt.gerenciar_trafego("crie o plano de tráfego", "telegram:1")

    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)

    def _boom_llm():
        raise AssertionError("Manifesto nunca deveria chamar LLM")
    monkeypatch.setattr(pft, "_get_llm_economico", _boom_llm)

    original_save = brain_store.save
    def _boom_save(*args, **kwargs):
        raise AssertionError("Manifesto nunca deveria escrever no Project Brain")
    monkeypatch.setattr(brain_store, "save", _boom_save)
    try:
        resposta = pft.gerenciar_producao("mostre o manifesto atual", "telegram:1")
    finally:
        monkeypatch.setattr(brain_store, "save", original_save)

    assert "status_trafego_pago: READY_FOR_APPROVAL" in resposta


def test_manifesto_mostra_not_started_antes_de_qualquer_plano(monkeypatch, brain_store):
    brain = _brain_pronto(brain_store)
    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)

    resposta = pft.gerenciar_producao("mostre o manifesto atual", "telegram:1")
    assert "status_trafego_pago: None" in resposta


# ---------------------------------------------------------------------------
# Ausencia de acoes externas / gasto / API de Ads
# ---------------------------------------------------------------------------

def test_nenhuma_chamada_http_no_fluxo_completo(monkeypatch, brain_store):
    import requests

    def _boom(*args, **kwargs):
        raise AssertionError("Nenhuma chamada HTTP deveria acontecer aqui")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    brain = _brain_pronto(brain_store)
    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(ptt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_MINIMO))

    ptt.gerenciar_trafego("crie o plano de tráfego", "telegram:1")
    ptt.gerenciar_trafego("Aprovado.", "telegram:1")


def test_nenhuma_api_de_ads_e_referenciada_no_codigo():
    """Nenhuma integracao real com Meta/Google/TikTok Ads foi adicionada --
    o modulo so IMPORTA o que ja existia (requests via truststore, igual
    aos outros modulos), nunca um SDK de Ads."""
    import tools.paid_traffic_tools as modulo
    fonte = open(modulo.__file__, encoding="utf-8").read()
    proibidos = ["facebook_business", "google_ads", "tiktok_business_api", "marketing_api"]
    for termo in proibidos:
        assert termo not in fonte.lower()
