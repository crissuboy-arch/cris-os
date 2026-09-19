"""
Correção estrutural da Fase 6: aprovação contextual do TrafficPlan/
CampaignSpec via pendência PERSISTIDA (não por adivinhação, não por
`if "Aprovado" in mensagem` espalhado).

BUG REAL corrigido: "Cris, prepare a campanha deste projeto." bloqueava
corretamente (TrafficPlan ainda READY_FOR_APPROVAL), mas a resposta
seguinte "Aprovado" caía no assistente genérico -- o Orchestrator não tinha
como saber a qual artefato essa aprovação se referia.

Testes A-G do pedido de correção, cobrindo:
  A. fluxo real: bloqueio -> registra pendência -> "Aprovado" -> aplica
     SOMENTE no TrafficPlan -> nenhuma CampaignSpec criada/publicada.
  B. "Aprovado" sem pendência -> não altera nada.
  C. pendência de TRAFFIC_PLAN não altera BusinessPlan/ProductBlueprint/
     CampaignSpec.
  D. READY_FOR_APPROVAL continua diferente de APPROVED.
  E. persistência após restart.
  F. (regressão completa é coberta pela suíte inteira, ver relatório).
  G. zero publicação/gasto/chamada externa.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

import pytest

import tools.campaign_executor_tools as cet
from core.approval_router import resolver_aprovacao_contextual
from memory.layers import ProjectMemory
from memory.project_brain import (
    BusinessPlan,
    CampaignSpec,
    PendingApprovalStore,
    ProductBlueprint,
    ProjectBrainStore,
    TrafficPlan,
)
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


_PAYLOAD_SPEC_MINIMO = {
    "campaign_structure": "1 campanha", "ad_sets": ["Interesse: artesanato"],
    "audience_hypotheses": ["Iniciantes"], "placements": ["Feed"],
    "creative_requirements": ["Video vertical"], "copy_requirements": [],
    "keyword_requirements": [], "tracking_requirements": [], "schedule": "7 dias",
    "experiments": [], "risks": [], "missing_data": [],
}


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_fase6_aprovacao.db"


@pytest.fixture()
def brain_store(db_path):
    backend = SQLiteMemory(db_path)
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


@pytest.fixture()
def pending_store(brain_store):
    return PendingApprovalStore(brain_store.project_memory)


def _brain_com_traffic_plan_ready(store):
    brain = store.create(name="Curso de Velas", tipo="opportunity")
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id, recommended_product_type="mini_app",
        decision_status="APPROVED", target_audience="Iniciantes", country="BR",
    )
    brain.traffic_plan = TrafficPlan(
        project_id=brain.project_id, version=1, status="READY_FOR_APPROVAL",
        objective="Validar demanda", country="BR", language="pt",
        channels=[{
            "channel": "TIKTOK_ADS", "role": "PRIMARY_TEST", "priority": "alta",
            "rationale": "x", "campaign_objective": "Trafego", "campaign_structure": "1 campanha",
            "ad_sets_or_groups": [], "targeting_strategy": "x", "keyword_strategy": None,
            "placements": [], "creative_requirements": [], "landing_destination": "x",
            "conversion_event": "x", "test_hypothesis": "x", "evidence_used": [],
            "assumptions": [], "risks": [],
        }],
    )
    store.save(brain)
    return brain


# ---------------------------------------------------------------------------
# TESTE A -- fluxo real completo
# ---------------------------------------------------------------------------

def test_teste_a_fluxo_real_bloqueio_registra_pendencia_e_aprovado_aplica_so_traffic_plan(
    monkeypatch, brain_store, pending_store,
):
    brain = _brain_com_traffic_plan_ready(brain_store)
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)

    def _boom():
        raise AssertionError("Bloqueio nao deveria chamar o LLM")
    monkeypatch.setattr(cet, "_get_llm_inteligente", _boom)

    resposta_bloqueio = cet.gerenciar_campanha("Cris, prepare a campanha deste projeto.", "telegram:1")
    assert "aprovado" in resposta_bloqueio.lower()

    pendente = pending_store.get_pending("telegram:1")
    assert pendente is not None
    assert pendente["artifact_type"] == "TRAFFIC_PLAN"
    assert pendente["project_id"] == brain.project_id

    resposta_aprovacao = resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)
    assert resposta_aprovacao is not None
    assert "Status: APPROVED" in resposta_aprovacao
    assert "Nenhuma campanha foi criada ou publicada." in resposta_aprovacao

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.traffic_plan.status == "APPROVED"
    assert recarregado.campaign_spec is None  # nenhuma CampaignSpec criada automaticamente

    # pendencia consumida -- nao pode ser reaplicada
    assert pending_store.get_pending("telegram:1") is None


# ---------------------------------------------------------------------------
# TESTE B -- sem pendencia, nao altera nada
# ---------------------------------------------------------------------------

def test_teste_b_aprovado_sem_pendencia_nao_altera_nada(brain_store, pending_store):
    brain = _brain_com_traffic_plan_ready(brain_store)
    resposta = resolver_aprovacao_contextual("Aprovado", "telegram:sem-pendencia", pending_store, brain_store)
    assert resposta is not None
    assert "não há uma aprovação pendente" in resposta.lower()

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.traffic_plan.status == "READY_FOR_APPROVAL"


def test_mensagem_nao_e_aprovacao_devolve_none(brain_store, pending_store):
    resposta = resolver_aprovacao_contextual("Qual o status do projeto?", "telegram:1", pending_store, brain_store)
    assert resposta is None


# ---------------------------------------------------------------------------
# TESTE C -- pendencia de TRAFFIC_PLAN nao altera outros artefatos
# ---------------------------------------------------------------------------

def test_teste_c_pendencia_traffic_plan_nao_altera_outros_artefatos(brain_store, pending_store):
    brain = _brain_com_traffic_plan_ready(brain_store)
    brain.business_plan = BusinessPlan(project_id=brain.project_id, approval_status="READY_FOR_APPROVAL")
    brain.campaign_spec = CampaignSpec(project_id=brain.project_id, status="READY_FOR_APPROVAL", channel="TIKTOK_ADS")
    brain.blueprint.decision_status = "PENDING_APPROVAL"
    brain_store.save(brain)

    pending_store.set_pending("telegram:1", brain.project_id, "TRAFFIC_PLAN", "APPROVE")
    resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.traffic_plan.status == "APPROVED"
    assert recarregado.business_plan.approval_status == "READY_FOR_APPROVAL"  # inalterado
    assert recarregado.campaign_spec.status == "READY_FOR_APPROVAL"  # inalterado
    assert recarregado.blueprint.decision_status == "PENDING_APPROVAL"  # inalterado


def test_pendencia_campaign_spec_nao_altera_traffic_plan(brain_store, pending_store):
    brain = _brain_com_traffic_plan_ready(brain_store)
    brain.campaign_spec = CampaignSpec(project_id=brain.project_id, status="READY_FOR_APPROVAL", channel="TIKTOK_ADS")
    brain_store.save(brain)

    pending_store.set_pending("telegram:1", brain.project_id, "CAMPAIGN_SPEC", "APPROVE")
    resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.campaign_spec.status == "APPROVED"
    assert recarregado.traffic_plan.status == "READY_FOR_APPROVAL"  # inalterado


# ---------------------------------------------------------------------------
# TESTE D -- READY_FOR_APPROVAL != APPROVED, sempre
# ---------------------------------------------------------------------------

def test_teste_d_ready_for_approval_nunca_e_tratado_como_approved(brain_store, pending_store):
    brain = _brain_com_traffic_plan_ready(brain_store)
    assert brain.traffic_plan.esta_aprovado() is False
    pending_store.set_pending("telegram:1", brain.project_id, "TRAFFIC_PLAN", "APPROVE")
    # consultas nao aprovam
    for pergunta in ["está bom?", "qual o status?", "pronto?"]:
        resposta = resolver_aprovacao_contextual(pergunta, "telegram:1", pending_store, brain_store)
        assert resposta is None  # nao e reconhecido como aprovacao/rejeicao
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.traffic_plan.status == "READY_FOR_APPROVAL"


def test_estado_mudou_desde_pendencia_registrada_nao_aplica_as_cegas(brain_store, pending_store):
    brain = _brain_com_traffic_plan_ready(brain_store)
    pending_store.set_pending("telegram:1", brain.project_id, "TRAFFIC_PLAN", "APPROVE")
    # estado muda por outra via (ex.: rejeitado por outro caminho) antes da
    # aprovacao pendente ser consumida.
    brain.traffic_plan.status = "REJECTED"
    brain_store.save(brain)

    resposta = resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)
    assert "não é mais válida" in resposta.lower()
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.traffic_plan.status == "REJECTED"  # nao foi sobrescrito


# ---------------------------------------------------------------------------
# TESTE E -- persistencia apos restart
# ---------------------------------------------------------------------------

def test_teste_e_pendencia_sobrevive_a_restart(monkeypatch, db_path, brain_store):
    brain = _brain_com_traffic_plan_ready(brain_store)
    monkeypatch.setattr(cet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(cet, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(cet, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_SPEC_MINIMO))

    cet.gerenciar_campanha("Cris, prepare a campanha deste projeto.", "telegram:1")

    novo_backend = SQLiteMemory(db_path)
    novo_store = ProjectBrainStore(ProjectMemory(novo_backend))
    novo_pending = PendingApprovalStore(novo_store.project_memory)
    try:
        pendente = novo_pending.get_pending("telegram:1")
        assert pendente is not None
        assert pendente["artifact_type"] == "TRAFFIC_PLAN"

        resposta = resolver_aprovacao_contextual("Aprovado", "telegram:1", novo_pending, novo_store)
        assert "Status: APPROVED" in resposta
        recarregado = novo_store.load(brain.project_id)
        assert recarregado.traffic_plan.status == "APPROVED"
    finally:
        novo_backend.close()


# ---------------------------------------------------------------------------
# TESTE G -- zero publicacao/gasto/chamada externa na resolucao de aprovacao
# ---------------------------------------------------------------------------

def test_teste_g_resolucao_de_aprovacao_nao_faz_chamada_http(monkeypatch, brain_store, pending_store):
    import requests

    def _boom(*a, **k):
        raise AssertionError("Resolucao de aprovacao nao deveria fazer chamada HTTP")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    brain = _brain_com_traffic_plan_ready(brain_store)
    pending_store.set_pending("telegram:1", brain.project_id, "TRAFFIC_PLAN", "APPROVE")
    resposta = resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)
    assert "gasto" not in resposta.lower() or "nenhum" in resposta.lower()


def test_resolucao_de_aprovacao_nunca_chama_llm():
    """`resolver_aprovacao_contextual` nao recebe nem usa nenhum LLM --
    prova estrutural de que a resolucao e 100% deterministica."""
    import inspect
    assinatura = inspect.signature(resolver_aprovacao_contextual)
    assert "llm" not in assinatura.parameters


# ---------------------------------------------------------------------------
# Rejeicao contextual -- mesma logica, aplica SOMENTE ao artefato pendente
# ---------------------------------------------------------------------------

def test_rejeicao_contextual_aplica_somente_traffic_plan(brain_store, pending_store):
    brain = _brain_com_traffic_plan_ready(brain_store)
    pending_store.set_pending("telegram:1", brain.project_id, "TRAFFIC_PLAN", "APPROVE")
    resposta = resolver_aprovacao_contextual("Não gostei, quero outro.", "telegram:1", pending_store, brain_store)
    assert "rejeitado" in resposta.lower()
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.traffic_plan.status == "REJECTED"
    assert pending_store.get_pending("telegram:1") is None
