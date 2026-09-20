"""
Testes da Fase 8: camada de Tools do Execution Engine -- gate (sem artefato
aprovado nunca cria plano), persistência real no MESMO Project Brain,
status/pause/resume/cancel, integração com o Approval Router, e ausência
total de ações externas/gasto/segredo no output.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

import tools.execution_engine_tools as eet
from memory.layers import ProjectMemory
from memory.project_brain import BusinessPlan, PendingApprovalStore, ProductBlueprint, ProjectBrainStore
from storage import SQLiteMemory


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_fase8_tools.db"


@pytest.fixture()
def brain_store(db_path):
    backend = SQLiteMemory(db_path)
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


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
# GATE -- sem artefato aprovado, nunca cria plano
# ---------------------------------------------------------------------------

def test_sem_artefato_aprovado_bloqueia_deterministicamente(monkeypatch, brain_store):
    brain = brain_store.create(name="x", tipo="opportunity")
    monkeypatch.setattr(eet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(eet, "get_project_brain_store", lambda: brain_store)

    resposta = eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")
    assert "não é possível criar" in resposta.lower()

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.execution_plan is None


# ---------------------------------------------------------------------------
# Criacao + persistencia real (nunca banco/JSON paralelo)
# ---------------------------------------------------------------------------

def test_criar_plano_persiste_e_registra_pendencia(monkeypatch, brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    monkeypatch.setattr(eet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(eet, "get_project_brain_store", lambda: brain_store)

    resposta = eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")
    assert "EXECUÇÃO" in resposta
    assert "READY_FOR_APPROVAL" in resposta

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.execution_plan is not None
    assert recarregado.execution_plan.project_id == brain.project_id

    pending = PendingApprovalStore(brain_store.project_memory)
    pendente = pending.get_pending("telegram:1")
    assert pendente["artifact_type"] == "EXECUTION_PLAN"


def test_pedido_repetido_nao_cria_segundo_plano(monkeypatch, brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    monkeypatch.setattr(eet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(eet, "get_project_brain_store", lambda: brain_store)

    eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")
    primeiro_id = brain_store.load(brain.project_id).execution_plan.execution_id

    eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")
    segundo_id = brain_store.load(brain.project_id).execution_plan.execution_id
    assert primeiro_id == segundo_id


# ---------------------------------------------------------------------------
# Status -- zero LLM, zero escrita indevida
# ---------------------------------------------------------------------------

def test_status_zero_llm_e_mostra_andamento(monkeypatch, brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    monkeypatch.setattr(eet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(eet, "get_project_brain_store", lambda: brain_store)

    eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")
    resposta = eet.gerenciar_execucao("Qual o andamento deste projeto?", "telegram:1")
    assert "EXECUÇÃO" in resposta
    assert "Concluídas:" in resposta


def test_status_sem_plano_e_deterministico(monkeypatch, brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    monkeypatch.setattr(eet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(eet, "get_project_brain_store", lambda: brain_store)

    resposta = eet.gerenciar_execucao("Qual o andamento deste projeto?", "telegram:1")
    assert "ainda não há um plano de execução" in resposta.lower()


# ---------------------------------------------------------------------------
# Fluxo completo via tools: criar -> aprovar (via router) -> executar -> status
# ---------------------------------------------------------------------------

def test_fluxo_completo_via_tools_ate_task_pendente(monkeypatch, brain_store):
    from core.approval_router import resolver_aprovacao_contextual

    brain = _brain_com_business_plan_aprovado(brain_store)
    monkeypatch.setattr(eet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(eet, "get_project_brain_store", lambda: brain_store)

    eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")
    pending = PendingApprovalStore(brain_store.project_memory)
    resolver_aprovacao_contextual("Aprovado", "telegram:1", pending, brain_store)

    resposta = eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")
    assert "Concluídas: 3/4" in resposta
    assert "aguardando aprovação da tarefa" in resposta.lower()

    pendente = pending.get_pending("telegram:1")
    assert pendente["artifact_type"] == "EXECUTION_TASK"


# ---------------------------------------------------------------------------
# PAUSE / RESUME / CANCEL via tools
# ---------------------------------------------------------------------------

def test_pause_resume_cancel_via_tools(monkeypatch, brain_store):
    from core.approval_router import resolver_aprovacao_contextual

    brain = _brain_com_business_plan_aprovado(brain_store)
    monkeypatch.setattr(eet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(eet, "get_project_brain_store", lambda: brain_store)

    eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")
    pending = PendingApprovalStore(brain_store.project_memory)
    resolver_aprovacao_contextual("Aprovado", "telegram:1", pending, brain_store)
    eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")

    resposta_pause = eet.gerenciar_execucao("Pause a execução.", "telegram:1")
    assert "pausada" in resposta_pause.lower()
    assert brain_store.load(brain.project_id).execution_plan.status == "PAUSED"

    resposta_resume = eet.gerenciar_execucao("Continue a execução.", "telegram:1")
    assert "EXECUÇÃO" in resposta_resume
    assert brain_store.load(brain.project_id).execution_plan.status == "RUNNING"

    resposta_cancel = eet.gerenciar_execucao("Cancele a execução.", "telegram:1")
    assert "cancelada" in resposta_cancel.lower()
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.execution_plan.status == "CANCELLED"
    assert recarregado.execution_plan.tasks[0].status == "COMPLETED"  # preservada


# ---------------------------------------------------------------------------
# Persistencia apos restart real
# ---------------------------------------------------------------------------

def test_execution_plan_sobrevive_a_restart(monkeypatch, db_path, brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    monkeypatch.setattr(eet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(eet, "get_project_brain_store", lambda: brain_store)
    eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")

    novo_backend = SQLiteMemory(db_path)
    novo_store = ProjectBrainStore(ProjectMemory(novo_backend))
    try:
        recarregado = novo_store.load(brain.project_id)
        assert recarregado.execution_plan is not None
        assert recarregado.execution_plan.status == "READY_FOR_APPROVAL"
    finally:
        novo_backend.close()


# ---------------------------------------------------------------------------
# Handoff via tools
# ---------------------------------------------------------------------------

def test_handoff_via_tools(monkeypatch, brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    monkeypatch.setattr(eet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(eet, "get_project_brain_store", lambda: brain_store)
    eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")

    resposta = eet.gerenciar_execucao("Execution handoff.", "telegram:1")
    assert "EXECUTION HANDOFF" in resposta
    assert brain.project_id in resposta


# ---------------------------------------------------------------------------
# Ausencia de acoes externas / gasto / API / segredo no output
# ---------------------------------------------------------------------------

def test_nenhuma_chamada_http_no_fluxo_completo(monkeypatch, brain_store):
    import requests
    from core.approval_router import resolver_aprovacao_contextual

    def _boom(*a, **k):
        raise AssertionError("Nenhuma chamada HTTP deveria acontecer aqui")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    brain = _brain_com_business_plan_aprovado(brain_store)
    monkeypatch.setattr(eet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(eet, "get_project_brain_store", lambda: brain_store)

    eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")
    pending = PendingApprovalStore(brain_store.project_memory)
    resolver_aprovacao_contextual("Aprovado", "telegram:1", pending, brain_store)
    eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")


def test_nenhuma_api_de_ads_referenciada_no_codigo():
    fonte = open(eet.__file__, encoding="utf-8").read()
    proibidos = ["facebook_business", "google_ads", "tiktok_business_api", "marketing_api"]
    for termo in proibidos:
        assert termo not in fonte.lower()


def test_resposta_nunca_contem_segredo(monkeypatch, brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    monkeypatch.setattr(eet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(eet, "get_project_brain_store", lambda: brain_store)

    resposta = eet.gerenciar_execucao("Execute o plano aprovado deste projeto.", "telegram:1")
    for termo_proibido in ["sk-", "api_key", "apikey", "secret", "token", "bearer "]:
        assert termo_proibido not in resposta.lower()
