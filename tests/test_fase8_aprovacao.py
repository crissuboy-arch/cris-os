"""
Testes da Fase 8: aprovação contextual do ExecutionPlan e de Tasks
individuais via Approval Router central (Fases 6/7, reaproveitado -- NENHUM
segundo Approval Router criado).

Cobre explicitamente:
  - aprovação exigida quando requires_approval=true.
  - aprovação atua SOMENTE na task correta (identifica project_id +
    execution_id + task_id -- nunca ambígua).
  - Approval Router existente é reutilizado -- não criado nenhum novo.
  - aprovar o plano de execução não altera BusinessPlan/ProductBlueprint.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from core.approval_router import resolver_aprovacao_contextual
from core.execution_engine import criar_execution_plan, executar_plano
from memory.layers import ProjectMemory
from memory.project_brain import BusinessPlan, PendingApprovalStore, ProductBlueprint, ProjectBrainStore
from storage import SQLiteMemory


@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_fase8_aprovacao.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


@pytest.fixture()
def pending_store(brain_store):
    return PendingApprovalStore(brain_store.project_memory)


def _brain_com_business_plan_aprovado(store):
    brain = store.create(name="Automação com IA", tipo="opportunity")
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id, recommended_product_type="curso",
        decision_status="APPROVED", target_audience="Profissionais",
    )
    brain.business_plan = BusinessPlan(
        project_id=brain.project_id, approval_status="APPROVED",
        positioning="O mais prático", target_audience="Profissionais",
        acquisition_channels=["LinkedIn"], required_assets=["Landing page"],
    )
    store.save(brain)
    return brain


# ---------------------------------------------------------------------------
# Aprovacao do PLANO (EXECUTION_PLAN -- usa o mecanismo generico ja existente)
# ---------------------------------------------------------------------------

def test_aprovar_execution_plan_nao_altera_business_plan_nem_blueprint(brain_store, pending_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    brain.execution_plan = plan
    brain_store.save(brain)

    blueprint_status_antes = brain.blueprint.decision_status
    business_plan_status_antes = brain.business_plan.approval_status

    pending_store.set_pending("telegram:1", brain.project_id, "EXECUTION_PLAN", "APPROVE")
    resposta = resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)
    assert "plano de execução" in resposta.lower()
    assert "Status: APPROVED" in resposta

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.execution_plan.status == "APPROVED"
    assert recarregado.blueprint.decision_status == blueprint_status_antes
    assert recarregado.business_plan.approval_status == business_plan_status_antes


def test_rejeitar_execution_plan(brain_store, pending_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    brain.execution_plan = plan
    brain_store.save(brain)

    pending_store.set_pending("telegram:1", brain.project_id, "EXECUTION_PLAN", "APPROVE")
    resposta = resolver_aprovacao_contextual("Não gostei, quero outro.", "telegram:1", pending_store, brain_store)
    assert "rejeitado" in resposta.lower()

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.execution_plan.status == "CANCELLED"


# ---------------------------------------------------------------------------
# Aprovacao de TASK individual (EXECUTION_TASK -- caso especial do router)
# ---------------------------------------------------------------------------

def test_aprovacao_exigida_quando_requires_approval_true(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)

    t4 = plan.tasks[3]
    assert t4.requires_approval is True
    assert t4.approved is False
    assert t4.status == "READY"  # pronta, mas NAO executada sem aprovacao


def test_aprovacao_atua_somente_na_task_correta(brain_store, pending_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)
    brain_store.save(brain)

    t1, t2, t3, t4 = plan.tasks
    pending_store.set_pending("telegram:1", brain.project_id, "EXECUTION_TASK", "APPROVE", task_id=t4.task_id)
    resposta = resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)
    assert t4.task_id in resposta
    assert plan.execution_id in resposta

    recarregado = brain_store.load(brain.project_id)
    tarefas = {t.task_id: t for t in recarregado.execution_plan.tasks}
    assert tarefas[t4.task_id].approved is True
    # as outras 3 tasks (ja COMPLETED antes) continuam intactas
    assert tarefas[t1.task_id].status == "COMPLETED"
    assert tarefas[t2.task_id].status == "COMPLETED"
    assert tarefas[t3.task_id].status == "COMPLETED"


def test_rejeitar_task_individual_cancela_somente_ela(brain_store, pending_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)
    brain_store.save(brain)

    t4 = plan.tasks[3]
    pending_store.set_pending("telegram:1", brain.project_id, "EXECUTION_TASK", "APPROVE", task_id=t4.task_id)
    resolver_aprovacao_contextual("Não gostei, quero outro.", "telegram:1", pending_store, brain_store)

    recarregado = brain_store.load(brain.project_id)
    tarefas = {t.task_id: t for t in recarregado.execution_plan.tasks}
    assert tarefas[t4.task_id].status == "CANCELLED"
    assert tarefas[plan.tasks[0].task_id].status == "COMPLETED"  # inalterada


def test_aprovacao_task_sem_pendencia_task_id_nao_aplica_as_cegas(brain_store, pending_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)
    brain_store.save(brain)

    # pendencia corrompida -- sem task_id
    pending_store.set_pending("telegram:1", brain.project_id, "EXECUTION_TASK", "APPROVE")
    resposta = resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)
    assert "não há uma aprovação pendente" in resposta.lower()

    recarregado = brain_store.load(brain.project_id)
    t4 = recarregado.execution_plan.tasks[3]
    assert t4.approved is False  # nunca aplicado as cegas


def test_aprovacao_task_ja_concluida_nao_e_mais_valida(brain_store, pending_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)
    t4 = plan.tasks[3]
    t4.approved = True
    executar_plano(brain)  # completa a task 4
    brain_store.save(brain)
    assert t4.status == "COMPLETED"

    # pendencia antiga (ja consumida) tenta aprovar de novo
    pending_store.set_pending("telegram:1", brain.project_id, "EXECUTION_TASK", "APPROVE", task_id=t4.task_id)
    resposta = resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)
    assert "não é mais válida" in resposta.lower()


def test_pendencia_de_task_nao_confunde_com_traffic_plan_ou_campaign_spec(brain_store, pending_store):
    from memory.project_brain import CampaignSpec, TrafficPlan

    brain = _brain_com_business_plan_aprovado(brain_store)
    brain.traffic_plan = TrafficPlan(project_id=brain.project_id, version=1, status="READY_FOR_APPROVAL")
    brain.campaign_spec = CampaignSpec(project_id=brain.project_id, status="READY_FOR_APPROVAL", channel="TIKTOK_ADS")
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)
    brain_store.save(brain)

    t4 = plan.tasks[3]
    pending_store.set_pending("telegram:1", brain.project_id, "EXECUTION_TASK", "APPROVE", task_id=t4.task_id)
    resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.traffic_plan.status == "READY_FOR_APPROVAL"  # inalterado
    assert recarregado.campaign_spec.status == "READY_FOR_APPROVAL"  # inalterado


# ---------------------------------------------------------------------------
# Zero LLM, zero chamada externa na resolucao de aprovacao
# ---------------------------------------------------------------------------

def test_aprovacao_de_task_nao_faz_chamada_http(monkeypatch, brain_store, pending_store):
    import requests

    def _boom(*a, **k):
        raise AssertionError("Aprovacao de task nao deveria fazer chamada HTTP")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)
    brain_store.save(brain)

    t4 = plan.tasks[3]
    pending_store.set_pending("telegram:1", brain.project_id, "EXECUTION_TASK", "APPROVE", task_id=t4.task_id)
    resolver_aprovacao_contextual("Aprovado", "telegram:1", pending_store, brain_store)
