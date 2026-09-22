"""
Testes da Fase 7: aprovação contextual do BusinessPlan via Approval Router
central (Fase 6, reaproveitado -- NENHUM sistema de aprovação novo criado).

Cobre explicitamente os itens do checklist:
  - READY_FOR_APPROVAL é registrado corretamente.
  - "Aprovado" aprova somente o BusinessPlan pendente.
  - "Rejeitado" rejeita somente o BusinessPlan pendente.
  - Approval Router não confunde BusinessPlan com TrafficPlan.
  - Aprovar BusinessPlan NÃO altera ProductBlueprint/TrafficPlan/CampaignSpec.
  - Nenhuma campanha é publicada/criada por causa da aprovação do BusinessPlan.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

import pytest

import tools.business_builder_tools as bbt
from core.approval_router import resolver_aprovacao_contextual
from memory.layers import ProjectMemory
from memory.project_brain import (
    CampaignSpec,
    PendingApprovalStore,
    ProductBlueprint,
    ProjectBrainStore,
    TrafficPlan,
)
from storage import SQLiteMemory


class FakeLLMJSON:
    def __init__(self, payload: dict):
        self.payload = payload
        self._provider_name = "fake:economico"
        self.chamadas = 0

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        self.chamadas += 1
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False))

    def is_alive(self):
        return True


_PAYLOAD_MINIMO = {
    "business_model": "Curso online", "value_proposition": "Aprenda automação com IA",
    "target_audience": "Profissionais", "problem": "Não sabem automatizar",
    "solution": "Curso prático", "positioning": "O mais prático do mercado",
    "mechanism": "Método em 4 etapas", "main_offer": "Curso completo",
    "monetization_format": "Pagamento único", "price": "R$ 697", "price_is_hypothesis": True,
    "bonuses": [], "order_bump": None, "upsell": [], "downsell": [],
    "acquisition_channels": ["LinkedIn"], "sales_channels": ["Página própria"],
    "sales_page_structure": "Headline -> oferta -> CTA", "headline": "Automatize com IA",
    "promise": "Você vai aprender o básico de automação", "key_arguments": [],
    "objections": [], "cta": "Quero começar", "funnel_structure": "Lead -> oferta",
    "email_sequence": [
        {"numero": i, "objetivo": "x", "assunto": "x", "resumo": "x"} for i in range(1, 6)
    ],
    "content_strategy": "Conteúdo educativo", "content_channels": ["LinkedIn"],
    "launch_strategy": "Lista de espera", "plan_30_days": [],
    "assumptions": ["Público tem interesse real"], "missing_evidence": [],
    "risks": ["Mercado saturado"], "dependencies": [], "next_steps": ["Validar preço"],
    "desired_outcome": None, "subniche": None, "offer_type": "curso",
    "pricing_strategy": "Preço único", "estimated_price_range": None,
    "bonuses_strategy": None, "guarantee_strategy": None, "urgency_strategy": None,
    "primary_channel": "LinkedIn", "secondary_channels": [], "sales_model": "Checkout self-service",
    "estimated_ticket": None, "estimated_margin": None, "estimated_cac_target": None,
    "estimated_break_even": None, "revenue_scenarios": [],
    "competitors": [], "differentiation": "Foco prático", "market_gaps": [], "barriers": [],
    "validation_requirements": [], "confidence_score": "medio",
    "required_assets": ["Landing page"], "kpis": ["CAC"],
}


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_fase7_aprovacao.db"


@pytest.fixture()
def brain_store(db_path):
    backend = SQLiteMemory(db_path)
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


@pytest.fixture()
def pending_store(brain_store):
    return PendingApprovalStore(brain_store.project_memory)


def _brain_com_produto_aprovado(store):
    brain = store.create(name="Automação com IA", tipo="opportunity")
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id, recommended_product_type="curso",
        decision_status="APPROVED", target_audience="Profissionais",
        market="educação online", niche="automação com IA", country="BR",
    )
    store.save(brain)
    return brain


# ---------------------------------------------------------------------------
# READY_FOR_APPROVAL registra pendencia corretamente
# ---------------------------------------------------------------------------

def test_business_plan_ready_for_approval_registra_pendencia(monkeypatch, brain_store, pending_store):
    brain = _brain_com_produto_aprovado(brain_store)
    monkeypatch.setattr(bbt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(bbt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(bbt, "_get_llm_economico", lambda: FakeLLMJSON(_PAYLOAD_MINIMO))

    resposta = bbt.gerenciar_negocio("Prepare o BusinessPlan deste projeto.", "telegram:1")
    assert "PLANO DE NEGÓCIO" in resposta

    pendente = pending_store.get_pending("telegram:1")
    assert pendente is not None
    assert pendente["artifact_type"] == "BUSINESS_PLAN"
    assert pendente["project_id"] == brain.project_id

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.business_plan.approval_status == "READY_FOR_APPROVAL"


# ---------------------------------------------------------------------------
# "Aprovado" aprova SOMENTE o BusinessPlan pendente
# ---------------------------------------------------------------------------

def test_aprovado_aprova_somente_business_plan_pendente(monkeypatch, brain_store, pending_store):
    brain = _brain_com_produto_aprovado(brain_store)
    monkeypatch.setattr(bbt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(bbt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(bbt, "_get_llm_economico", lambda: FakeLLMJSON(_PAYLOAD_MINIMO))
    bbt.gerenciar_negocio("Prepare o BusinessPlan deste projeto.", "telegram:1")

    resposta = resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)
    assert resposta is not None
    assert "Plano de negócio aprovado" in resposta
    assert "Status: APPROVED" in resposta

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.business_plan.approval_status == "APPROVED"
    assert recarregado.business_plan.esta_aprovado() is True
    # A pendencia do BUSINESS_PLAN foi consumida, mas a aprovacao encadeia
    # automaticamente a criacao do ExecutionPlan (integracao ScalaFlow --
    # ver core/approval_router.py:_apos_business_plan_aprovado), que registra
    # sua PROPRIA pendencia -- por isso nao fica None, e sim EXECUTION_PLAN.
    nova_pendencia = pending_store.get_pending("telegram:1")
    assert nova_pendencia is not None
    assert nova_pendencia["artifact_type"] == "EXECUTION_PLAN"
    assert recarregado.execution_plan is not None
    assert recarregado.execution_plan.status == "READY_FOR_APPROVAL"


def test_rejeitado_rejeita_somente_business_plan_pendente(monkeypatch, brain_store, pending_store):
    brain = _brain_com_produto_aprovado(brain_store)
    monkeypatch.setattr(bbt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(bbt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(bbt, "_get_llm_economico", lambda: FakeLLMJSON(_PAYLOAD_MINIMO))
    bbt.gerenciar_negocio("Prepare o BusinessPlan deste projeto.", "telegram:1")

    resposta = resolver_aprovacao_contextual("Não gostei, quero outro.", "telegram:1", pending_store, brain_store)
    assert "rejeitado" in resposta.lower()

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.business_plan.approval_status == "REJECTED"
    assert pending_store.get_pending("telegram:1") is None


# ---------------------------------------------------------------------------
# Approval Router NAO confunde BusinessPlan com TrafficPlan/CampaignSpec, e
# aprovar o BusinessPlan NAO altera nenhum outro artefato.
# ---------------------------------------------------------------------------

def test_pendencia_business_plan_nao_confunde_com_traffic_plan(brain_store, pending_store):
    brain = _brain_com_produto_aprovado(brain_store)
    brain.business_plan_para_teste = None  # no-op, so pra clareza
    from memory.project_brain import BusinessPlan
    brain.business_plan = BusinessPlan(project_id=brain.project_id, approval_status="READY_FOR_APPROVAL")
    brain.traffic_plan = TrafficPlan(project_id=brain.project_id, version=1, status="READY_FOR_APPROVAL")
    brain_store.save(brain)

    pending_store.set_pending("telegram:1", brain.project_id, "BUSINESS_PLAN", "APPROVE")
    resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.business_plan.approval_status == "APPROVED"
    assert recarregado.traffic_plan.status == "READY_FOR_APPROVAL"  # inalterado


def test_aprovar_business_plan_nao_altera_product_blueprint_nem_campaign_spec(brain_store, pending_store):
    brain = _brain_com_produto_aprovado(brain_store)
    from memory.project_brain import BusinessPlan
    brain.business_plan = BusinessPlan(project_id=brain.project_id, approval_status="READY_FOR_APPROVAL")
    brain.campaign_spec = CampaignSpec(project_id=brain.project_id, status="READY_FOR_APPROVAL", channel="TIKTOK_ADS")
    blueprint_status_antes = brain.blueprint.decision_status
    brain_store.save(brain)

    pending_store.set_pending("telegram:1", brain.project_id, "BUSINESS_PLAN", "APPROVE")
    resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.business_plan.approval_status == "APPROVED"
    assert recarregado.blueprint.decision_status == blueprint_status_antes  # inalterado
    assert recarregado.campaign_spec.status == "READY_FOR_APPROVAL"  # inalterado -- NUNCA criada/alterada automaticamente


def test_pendencia_traffic_plan_nao_e_afetada_por_aprovacao_de_business_plan(brain_store, pending_store):
    """Garantia inversa: se a pendencia registrada e do BUSINESS_PLAN, uma
    tentativa de aprovar nao pode, por engano, tocar num TrafficPlan que
    tambem esteja READY_FOR_APPROVAL ao mesmo tempo."""
    brain = _brain_com_produto_aprovado(brain_store)
    from memory.project_brain import BusinessPlan
    brain.business_plan = BusinessPlan(project_id=brain.project_id, approval_status="READY_FOR_APPROVAL")
    brain.traffic_plan = TrafficPlan(project_id=brain.project_id, version=1, status="READY_FOR_APPROVAL")
    brain_store.save(brain)

    pending_store.set_pending("telegram:1", brain.project_id, "TRAFFIC_PLAN", "APPROVE")
    resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.traffic_plan.status == "APPROVED"
    assert recarregado.business_plan.approval_status == "READY_FOR_APPROVAL"  # inalterado


# ---------------------------------------------------------------------------
# READY_FOR_APPROVAL != APPROVED (consultas nunca aprovam)
# ---------------------------------------------------------------------------

def test_consultas_nunca_aprovam_business_plan(brain_store, pending_store):
    brain = _brain_com_produto_aprovado(brain_store)
    from memory.project_brain import BusinessPlan
    brain.business_plan = BusinessPlan(project_id=brain.project_id, approval_status="READY_FOR_APPROVAL")
    brain_store.save(brain)
    pending_store.set_pending("telegram:1", brain.project_id, "BUSINESS_PLAN", "APPROVE")

    for pergunta in ["está bom?", "qual o modelo de negócio?", "mostre o plano de negócio"]:
        resposta = resolver_aprovacao_contextual(pergunta, "telegram:1", pending_store, brain_store)
        assert resposta is None
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.business_plan.approval_status == "READY_FOR_APPROVAL"


# ---------------------------------------------------------------------------
# Nenhuma campanha criada/publicada, nenhuma chamada externa, zero LLM na aprovacao
# ---------------------------------------------------------------------------

def test_aprovacao_de_business_plan_nao_cria_campaign_spec(brain_store, pending_store):
    brain = _brain_com_produto_aprovado(brain_store)
    from memory.project_brain import BusinessPlan
    brain.business_plan = BusinessPlan(project_id=brain.project_id, approval_status="READY_FOR_APPROVAL")
    brain_store.save(brain)
    pending_store.set_pending("telegram:1", brain.project_id, "BUSINESS_PLAN", "APPROVE")

    resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.campaign_spec is None


def test_aprovacao_nao_faz_chamada_http(monkeypatch, brain_store, pending_store):
    import requests

    def _boom(*a, **k):
        raise AssertionError("Aprovacao de BusinessPlan nao deveria fazer chamada HTTP")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    brain = _brain_com_produto_aprovado(brain_store)
    from memory.project_brain import BusinessPlan
    brain.business_plan = BusinessPlan(project_id=brain.project_id, approval_status="READY_FOR_APPROVAL")
    brain_store.save(brain)
    pending_store.set_pending("telegram:1", brain.project_id, "BUSINESS_PLAN", "APPROVE")

    resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)


def test_resolucao_de_aprovacao_business_plan_nunca_usa_llm():
    import inspect
    assinatura = inspect.signature(resolver_aprovacao_contextual)
    assert "llm" not in assinatura.parameters


# ---------------------------------------------------------------------------
# Nao duplica BusinessPlan indevidamente (checklist da Fase 7)
# ---------------------------------------------------------------------------

def test_pedido_generico_repetido_nao_duplica_nem_gera_de_novo(monkeypatch, brain_store):
    brain = _brain_com_produto_aprovado(brain_store)
    monkeypatch.setattr(bbt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(bbt, "get_project_brain_store", lambda: brain_store)
    fake = FakeLLMJSON(_PAYLOAD_MINIMO)
    monkeypatch.setattr(bbt, "_get_llm_economico", lambda: fake)

    bbt.gerenciar_negocio("Prepare o BusinessPlan deste projeto.", "telegram:1")
    assert fake.chamadas == 1

    bbt.gerenciar_negocio("Qual modelo de negócio faz mais sentido para esta oportunidade?", "telegram:1")
    assert fake.chamadas == 1  # nao gerou um segundo plano -- reaproveitou o existente

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.business_plan is not None  # continua sendo UM unico plano (nao uma lista)
