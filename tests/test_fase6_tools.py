"""
Testes da Fase 6: camada de Tools do Campaign Executor -- gate do TrafficPlan
(nunca cria CampaignSpec sem plano aprovado), persistência real no MESMO
Project Brain, preview/status com zero LLM, aprovação da ESPECIFICAÇÃO
(nunca libera execução externa), integração com o Artifact Manifest, e
ausência total de ações externas/gasto/segredo no output.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

import pytest

import tools.campaign_executor_tools as cet
import tools.product_factory_tools as pft
from memory.layers import ProjectMemory
from memory.project_brain import ProductBlueprint, ProjectBrainStore, TrafficPlan
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


_CANAL_PRIMARIO = {
    "channel": "TIKTOK_ADS", "role": "PRIMARY_TEST", "priority": "alta",
    "rationale": "Evidencia real de TikTok ja coletada", "campaign_objective": "Trafego",
    "campaign_structure": "1 campanha", "ad_sets_or_groups": ["Interesse: artesanato"],
    "targeting_strategy": "Interesses amplos", "keyword_strategy": None,
    "placements": ["Feed"], "creative_requirements": ["Video vertical"],
    "landing_destination": "Landing page", "conversion_event": "ViewContent",
    "test_hypothesis": "Publico converte", "evidence_used": ["TikTok"],
    "assumptions": [], "risks": [],
}

_PAYLOAD_SPEC_MINIMO = {
    "campaign_structure": "1 campanha, 2 ad sets",
    "ad_sets": ["Interesse: artesanato"], "audience_hypotheses": ["Iniciantes"],
    "placements": ["Feed"], "creative_requirements": ["Video vertical"],
    "copy_requirements": ["Headline curta"], "keyword_requirements": [],
    "tracking_requirements": ["Pixel de ViewContent"], "schedule": "7 dias",
    "experiments": [], "risks": [], "missing_data": [],
}


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_fase6_tools.db"


@pytest.fixture()
def brain_store(db_path):
    backend = SQLiteMemory(db_path)
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def _brain_com_traffic_plan(store, status="APPROVED"):
    brain = store.create(name="Curso de Velas", tipo="opportunity")
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id, recommended_product_type="mini_app",
        decision_status="APPROVED", target_audience="Iniciantes", country="BR",
    )
    brain.traffic_plan = TrafficPlan(
        project_id=brain.project_id, version=1, status=status,
        objective="Validar demanda", country="BR", language="pt",
        audience_summary="Iniciantes em velas artesanais",
        channels=[dict(_CANAL_PRIMARIO)],
    )
    store.save(brain)
    return brain


# ---------------------------------------------------------------------------
# GATE -- TrafficPlan nao aprovado (requisito A): nunca cria, nunca chama
# LLM, nunca altera o Project Brain.
# ---------------------------------------------------------------------------

def test_traffic_plan_nao_aprovado_bloqueia_deterministicamente(monkeypatch, brain_store):
    brain = _brain_com_traffic_plan(brain_store, status="READY_FOR_APPROVAL")
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)

    def _boom():
        raise AssertionError("Gate nao aprovado nao deveria chamar o LLM")
    monkeypatch.setattr(cet, "_get_llm_inteligente", _boom)

    original_save = brain_store.save
    def _boom_save(*a, **k):
        raise AssertionError("Gate nao aprovado nao deveria escrever no Project Brain")
    monkeypatch.setattr(brain_store, "save", _boom_save)
    try:
        resposta = cet.gerenciar_campanha("Cris, prepare a campanha deste projeto.", "telegram:1")
    finally:
        monkeypatch.setattr(brain_store, "save", original_save)

    assert "aprovado" in resposta.lower()
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.campaign_spec is None


# ---------------------------------------------------------------------------
# TrafficPlan aprovado -- CampaignSpec pode ser criada (requisito B) e
# persiste no MESMO Project Brain (sem banco/JSON paralelo).
# ---------------------------------------------------------------------------

def test_traffic_plan_aprovado_cria_e_persiste_campaign_spec(monkeypatch, brain_store):
    brain = _brain_com_traffic_plan(brain_store, status="APPROVED")
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)
    fake = FakeLLMJSON(_PAYLOAD_SPEC_MINIMO)
    monkeypatch.setattr(cet, "_get_llm_inteligente", lambda: fake)

    resposta = cet.gerenciar_campanha("Cris, prepare a campanha deste projeto.", "telegram:1")
    assert "ESPECIFICAÇÃO DE CAMPANHA" in resposta
    assert fake.chamadas == 1

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.campaign_spec is not None
    assert recarregado.campaign_spec.status == "READY_FOR_APPROVAL"
    assert recarregado.campaign_spec.project_id == brain.project_id


# ---------------------------------------------------------------------------
# Orcamento -- "20 euros por dia" -> EUR / 20 / DAILY (requisito E) e sem
# orcamento -> REQUIRES_BUDGET (requisito F).
# ---------------------------------------------------------------------------

def test_orcamento_20_euros_por_dia_extraido_corretamente(monkeypatch, brain_store):
    brain = _brain_com_traffic_plan(brain_store, status="APPROVED")
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(cet, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_SPEC_MINIMO))

    cet.gerenciar_campanha("Cris, prepare a campanha deste projeto com orçamento de 20 euros por dia.", "telegram:1")
    recarregado = brain_store.load(brain.project_id)
    budget = recarregado.campaign_spec.budget
    assert budget["currency"] == "EUR"
    assert budget["daily"] == "20"
    assert budget["status"] == "PROVIDED"


def test_sem_orcamento_fica_requires_budget(monkeypatch, brain_store):
    brain = _brain_com_traffic_plan(brain_store, status="APPROVED")
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(cet, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_SPEC_MINIMO))

    cet.gerenciar_campanha("Cris, prepare a campanha deste projeto.", "telegram:1")
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.campaign_spec.budget["status"] == "REQUIRES_BUDGET"


def test_orcamento_10_dolares_por_dia(monkeypatch, brain_store):
    brain = _brain_com_traffic_plan(brain_store, status="APPROVED")
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(cet, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_SPEC_MINIMO))

    cet.gerenciar_campanha("Cris, prepare o teste com 10 dólares por dia.", "telegram:1")
    recarregado = brain_store.load(brain.project_id)
    budget = recarregado.campaign_spec.budget
    assert budget["currency"] == "USD"
    assert budget["daily"] == "10"


# ---------------------------------------------------------------------------
# Preview -- zero LLM quando ja existe spec (requisitos H/I), sempre DRY_RUN
# ---------------------------------------------------------------------------

def test_preview_zero_llm_quando_ja_existe_spec(monkeypatch, brain_store):
    brain = _brain_com_traffic_plan(brain_store, status="APPROVED")
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(cet, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_SPEC_MINIMO))
    cet.gerenciar_campanha("Cris, prepare a campanha deste projeto.", "telegram:1")

    def _boom():
        raise AssertionError("Preview nao deveria chamar o LLM de novo")
    monkeypatch.setattr(cet, "_get_llm_inteligente", _boom)

    resposta = cet.gerenciar_campanha("Cris, mostre como esta campanha ficaria antes de publicar.", "telegram:1")
    assert "Modo: DRY_RUN" in resposta
    assert "Nenhuma campanha foi publicada. Nenhum dinheiro foi gasto." in resposta


def test_preview_sem_spec_nunca_chama_llm(monkeypatch, brain_store):
    brain = _brain_com_traffic_plan(brain_store, status="APPROVED")
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)

    def _boom():
        raise AssertionError("Preview sem spec nao deveria chamar o LLM")
    monkeypatch.setattr(cet, "_get_llm_inteligente", _boom)

    resposta = cet.gerenciar_campanha("Preview da campanha.", "telegram:1")
    assert "não há uma campanha preparada" in resposta.lower()


# ---------------------------------------------------------------------------
# Gate de aprovacao -- READY_FOR_APPROVAL != APPROVED, e mesmo aprovada
# nenhuma publicacao externa acontece (requisitos C/D)
# ---------------------------------------------------------------------------

def test_aprovacao_explicita_da_spec_nunca_libera_execucao_externa(monkeypatch, brain_store):
    brain = _brain_com_traffic_plan(brain_store, status="APPROVED")
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(cet, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_SPEC_MINIMO))

    cet.gerenciar_campanha("Cris, prepare a campanha deste projeto.", "telegram:1")
    resposta = cet.gerenciar_campanha("Aprovado.", "telegram:1")
    assert "aprovada" in resposta.lower()

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.campaign_spec.esta_aprovado() is True
    assert recarregado.campaign_spec.execution_mode == "EXTERNAL_EXECUTION_DISABLED"
    assert "nenhuma campanha foi publicada" in resposta.lower() or "publicação externa permanece desabilitada" in resposta.lower()


def test_ready_for_approval_nunca_vira_approved_sozinho(monkeypatch, brain_store):
    brain = _brain_com_traffic_plan(brain_store, status="APPROVED")
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(cet, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_SPEC_MINIMO))

    cet.gerenciar_campanha("Cris, prepare a campanha deste projeto.", "telegram:1")
    for pergunta in ["está bom?", "qual o status da campanha?", "preview da campanha", "pronto?"]:
        cet.gerenciar_campanha(pergunta, "telegram:1")
        recarregado = brain_store.load(brain.project_id)
        assert recarregado.campaign_spec.status != "APPROVED"


# ---------------------------------------------------------------------------
# UserFocusStore apos restart (requisito N) -- reaproveitado sem mudanca
# ---------------------------------------------------------------------------

def test_campaign_spec_sobrevive_a_restart(monkeypatch, db_path, brain_store):
    brain = _brain_com_traffic_plan(brain_store, status="APPROVED")
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(cet, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_SPEC_MINIMO))

    cet.gerenciar_campanha("Cris, prepare a campanha deste projeto.", "telegram:1")

    novo_backend = SQLiteMemory(db_path)
    novo_store = ProjectBrainStore(ProjectMemory(novo_backend))
    try:
        recarregado = novo_store.load(brain.project_id)
        assert recarregado.campaign_spec is not None
        assert recarregado.campaign_spec.status == "READY_FOR_APPROVAL"
    finally:
        novo_backend.close()


# ---------------------------------------------------------------------------
# Manifesto deriva CampaignSpec do Project Brain (requisito Q)
# ---------------------------------------------------------------------------

def test_manifesto_reflete_campaign_spec_sem_novo_llm_ou_write(monkeypatch, brain_store):
    brain = _brain_com_traffic_plan(brain_store, status="APPROVED")
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(cet, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_SPEC_MINIMO))
    cet.gerenciar_campanha("Cris, prepare a campanha deste projeto.", "telegram:1")

    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)

    def _boom_llm():
        raise AssertionError("Manifesto nunca deveria chamar LLM")
    monkeypatch.setattr(pft, "_get_llm_economico", _boom_llm)

    original_save = brain_store.save
    def _boom_save(*a, **k):
        raise AssertionError("Manifesto nunca deveria escrever no Project Brain")
    monkeypatch.setattr(brain_store, "save", _boom_save)
    try:
        resposta = pft.gerenciar_producao("mostre o manifesto atual", "telegram:1")
    finally:
        monkeypatch.setattr(brain_store, "save", original_save)

    assert "status_campaign_spec: READY_FOR_APPROVAL" in resposta


# ---------------------------------------------------------------------------
# Ausencia de acoes externas / gasto / API de Ads / segredo no output
# ---------------------------------------------------------------------------

def test_nenhuma_chamada_http_no_fluxo_completo(monkeypatch, brain_store):
    import requests

    def _boom(*a, **k):
        raise AssertionError("Nenhuma chamada HTTP deveria acontecer aqui")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    brain = _brain_com_traffic_plan(brain_store, status="APPROVED")
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(cet, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_SPEC_MINIMO))

    cet.gerenciar_campanha("Cris, prepare a campanha deste projeto.", "telegram:1")
    cet.gerenciar_campanha("Aprovado.", "telegram:1")


def test_nenhuma_api_de_ads_e_referenciada_no_codigo():
    fonte = open(cet.__file__, encoding="utf-8").read()
    proibidos = ["facebook_business", "google_ads", "tiktok_business_api", "marketing_api"]
    for termo in proibidos:
        assert termo not in fonte.lower()


def test_resposta_nunca_contem_segredo(monkeypatch, brain_store):
    brain = _brain_com_traffic_plan(brain_store, status="APPROVED")
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(cet, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_SPEC_MINIMO))

    resposta = cet.gerenciar_campanha("Cris, prepare a campanha deste projeto.", "telegram:1")
    resposta += cet.gerenciar_campanha("Aprovado.", "telegram:1")
    for termo_proibido in ["sk-", "api_key", "apikey", "secret", "token", "bearer "]:
        assert termo_proibido not in resposta.lower()
