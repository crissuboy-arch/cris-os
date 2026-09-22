"""
Testes da ponte Cris OS -> executores especializados (ProductionWorkOrder,
Production Router, Executor Adapter). Fecha o gap confirmado: a Task 3 do
Execution Engine ("Preparar handoff de ativos necessários") especifica
`required_assets`, mas nada os transformava em ordens rastreáveis para um
executor real (PageForge/Pink Logic/Criador-de-App/ForgeHub/NEXORA).

ZERO chamada externa/paga -- todo classificador é determinístico (sem LLM).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

import tools.execution_engine_tools as eet
from core.executor_adapter import EXECUTOR_REGISTRY, AdapterNaoConectado, obter_adapter
from core.production_orders import gerar_work_orders_da_task, pode_marcar_completed, sincronizar_producao_do_plano
from core.production_router import classificar_requisito, normalizar_asset_type, resolver_executor
from core.scalaflow_bridge import montar_status
from memory.layers import ProjectMemory
from memory.project_brain import (
    BusinessPlan,
    ExecutionPlan,
    IntelligenceHandoffStore,
    MarketIntelligenceHandoff,
    PendingApprovalStore,
    ProductionWorkOrder,
    ProjectBrainStore,
    Task,
    UserFocusStore,
)
from storage import SQLiteMemory

SESSION = "telegram:1"


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_production_orders.db"


@pytest.fixture()
def brain_store(db_path):
    backend = SQLiteMemory(db_path)
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


@pytest.fixture()
def pending_store(brain_store):
    return PendingApprovalStore(brain_store.project_memory)


@pytest.fixture()
def handoff_store(brain_store):
    return IntelligenceHandoffStore(brain_store.project_memory)


def _brain_carla_com_task3_completed(brain_store, requisitos=None):
    """Constrói um projeto no MESMO formato real de Carla: handoff
    persistido, BusinessPlan aprovado, ExecutionPlan com a Task 3
    ("Preparar handoff de ativos necessários") já COMPLETED com os
    requisitos reais como evidence -- exatamente o dado real observado em
    produção."""
    requisitos = requisitos if requisitos is not None else ["Landing page com prova social", "Materiais de marketing digital"]
    brain = brain_store.create(name="Carla Figurinhas", tipo="opportunity")
    brain.market_intelligence.append(MarketIntelligenceHandoff(handoff_id="ho_carla_teste", project_id=brain.project_id, status="PERSISTED"))
    brain.business_plan = BusinessPlan(project_id=brain.project_id, approval_status="APPROVED", required_assets=list(requisitos))

    t1 = Task(title="Analisar plano de negócio aprovado", status="COMPLETED", agent="execution_engine")
    t2 = Task(title="Definir requisitos de aquisição", status="COMPLETED", agent="business_builder", dependencies=[t1.task_id])
    t3 = Task(
        title="Preparar handoff de ativos necessários", status="COMPLETED", agent="business_builder",
        dependencies=[t2.task_id], evidence=list(requisitos), output_refs=[f"bizplan:{brain.project_id}:v1"],
    )
    t4 = Task(title="Simular ação externa (DRY_RUN)", status="READY", agent="campaign_executor", dependencies=[t3.task_id], requires_approval=True, external_action=True)
    brain.execution_plan = ExecutionPlan(project_id=brain.project_id, source_artifact_type="BUSINESS_PLAN", status="RUNNING", tasks=[t1, t2, t3, t4])
    brain_store.save(brain)
    return brain, t3


# ---------------------------------------------------------------------------
# 1) Normalização determinística (Seção 13)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("requisito,esperado", [
    ("Landing page com prova social", "LANDING_PAGE"),
    ("LANDING_PAGE", "LANDING_PAGE"),
    ("Materiais de marketing digital", "MARKETING_MATERIAL"),
    ("MARKETING_MATERIAL", "MARKETING_MATERIAL"),
    ("APP", "APP"),
    ("Mini-app de recomendação", "APP"),
    ("CRM", "CRM"),
    ("Sistema de follow-up de leads", "CRM"),
    ("Carrossel para Instagram", "CAROUSEL"),
    ("Ebook de bônus", "EBOOK"),
    ("Algo completamente aleatório sem sentido nenhum", "UNKNOWN"),
    ("", "UNKNOWN"),
])
def test_normalizar_asset_type(requisito, esperado):
    assert normalizar_asset_type(requisito) == esperado


@pytest.mark.parametrize("asset_type,executor", [
    ("APP", "APP_BUILDER"),
    ("LANDING_PAGE", "PAGEFORGE"),
    ("MARKETING_MATERIAL", "PINK_LOGIC"),
    ("EBOOK", "PINK_LOGIC"),
    ("CAROUSEL", "PINK_LOGIC"),
    ("DISTRIBUTION", "FORGEHUB"),
    ("CRM", "NEXORA"),
    ("UNKNOWN", "NEEDS_ROUTING"),
])
def test_resolver_executor(asset_type, executor):
    assert resolver_executor(asset_type) == executor


def test_classificar_requisito_landing_page_com_prova_social():
    assert classificar_requisito("Landing page com prova social") == ("LANDING_PAGE", "PAGEFORGE")


def test_classificar_requisito_materiais_de_marketing_digital():
    assert classificar_requisito("Materiais de marketing digital") == ("MARKETING_MATERIAL", "PINK_LOGIC")


# ---------------------------------------------------------------------------
# 2) Task 3 -> WorkOrders (dados reais da Carla)
# ---------------------------------------------------------------------------

def test_task3_gera_duas_work_orders_como_esperado_para_carla(brain_store):
    brain, t3 = _brain_carla_com_task3_completed(brain_store)
    ordens = gerar_work_orders_da_task(brain, t3)

    assert len(ordens) == 2
    landing, material = ordens
    assert landing.asset_type == "LANDING_PAGE" and landing.executor_type == "PAGEFORGE" and landing.status == "READY"
    assert material.asset_type == "MARKETING_MATERIAL" and material.executor_type == "PINK_LOGIC" and material.status == "READY"

    for wo in ordens:
        assert wo.project_id == brain.project_id
        assert wo.handoff_id == "ho_carla_teste"
        assert wo.execution_plan_id == brain.execution_plan.execution_id
        assert wo.source_task_id == t3.task_id
        assert wo.status != "DISPATCHED"  # nada foi enviado


def test_task_nao_completed_nao_gera_work_order(brain_store):
    brain, t3 = _brain_carla_com_task3_completed(brain_store)
    t3.status = "PENDING"
    assert gerar_work_orders_da_task(brain, t3) == []


def test_requisito_desconhecido_vira_needs_routing(brain_store):
    brain, t3 = _brain_carla_com_task3_completed(brain_store, requisitos=["Algo completamente aleatório sem sentido"])
    ordens = gerar_work_orders_da_task(brain, t3)
    assert len(ordens) == 1
    assert ordens[0].asset_type == "UNKNOWN"
    assert ordens[0].executor_type == "NEEDS_ROUTING"
    assert ordens[0].status == "NEEDS_ROUTING"


# ---------------------------------------------------------------------------
# 3) Idempotência (Seção 5)
# ---------------------------------------------------------------------------

def test_reprocessar_task3_nao_duplica_work_orders(brain_store):
    brain, t3 = _brain_carla_com_task3_completed(brain_store)
    primeira = gerar_work_orders_da_task(brain, t3)
    segunda = gerar_work_orders_da_task(brain, t3)

    assert len(brain.production_work_orders) == 2
    assert [w.work_order_id for w in primeira] == [w.work_order_id for w in segunda]


def test_sincronizar_producao_do_plano_e_idempotente(brain_store):
    brain, _ = _brain_carla_com_task3_completed(brain_store)
    sincronizar_producao_do_plano(brain)
    sincronizar_producao_do_plano(brain)
    assert len(brain.production_work_orders) == 2


def test_restart_preserva_work_orders(db_path, brain_store):
    brain, t3 = _brain_carla_com_task3_completed(brain_store)
    ordens = gerar_work_orders_da_task(brain, t3)
    brain.production_work_orders = ordens
    brain_store.save(brain)

    backend2 = SQLiteMemory(db_path)
    store2 = ProjectBrainStore(ProjectMemory(backend2))
    recarregado = store2.load(brain.project_id)
    assert len(recarregado.production_work_orders) == 2
    assert {w.work_order_id for w in recarregado.production_work_orders} == {w.work_order_id for w in ordens}
    backend2.close()


def test_isolamento_entre_projetos_nao_mistura_work_orders(brain_store):
    carla, t3_carla = _brain_carla_com_task3_completed(brain_store)
    outro, t3_outro = _brain_carla_com_task3_completed(brain_store, requisitos=["APP de fidelidade"])
    carla.production_work_orders = gerar_work_orders_da_task(carla, t3_carla)
    outro.production_work_orders = gerar_work_orders_da_task(outro, t3_outro)
    brain_store.save(carla)
    brain_store.save(outro)

    carla_recarregado = brain_store.load(carla.project_id)
    outro_recarregado = brain_store.load(outro.project_id)
    assert len(carla_recarregado.production_work_orders) == 2
    assert len(outro_recarregado.production_work_orders) == 1
    assert outro_recarregado.production_work_orders[0].asset_type == "APP"
    ids_carla = {w.work_order_id for w in carla_recarregado.production_work_orders}
    ids_outro = {w.work_order_id for w in outro_recarregado.production_work_orders}
    assert ids_carla.isdisjoint(ids_outro)


# ---------------------------------------------------------------------------
# 3b) COMPLETED sem output/evidência nunca é permitido (Seção 8)
# ---------------------------------------------------------------------------

def test_pode_marcar_completed_exige_output_para_asset_que_produz_artefato():
    sem_output = ProductionWorkOrder(asset_type="LANDING_PAGE", status="READY", output_refs=[])
    assert pode_marcar_completed(sem_output) is False

    com_output = ProductionWorkOrder(asset_type="LANDING_PAGE", status="READY", output_refs=["preview_url:https://exemplo.test/preview"])
    assert pode_marcar_completed(com_output) is True


def test_pode_marcar_completed_asset_logistico_nao_exige_output():
    ordem_crm = ProductionWorkOrder(asset_type="CRM", status="READY", output_refs=[])
    assert pode_marcar_completed(ordem_crm) is True


def test_todas_as_work_orders_criadas_para_carla_nunca_estao_completed_sem_output():
    """Nenhuma WorkOrder criada nesta fase avança sozinha para COMPLETED --
    esta é uma prova estrutural: se algum código futuro tentasse marcar
    COMPLETED sem output, `pode_marcar_completed` bloquearia."""
    for asset_type in ("LANDING_PAGE", "MARKETING_MATERIAL", "APP", "EBOOK", "CAROUSEL"):
        wo = ProductionWorkOrder(asset_type=asset_type, status="READY", output_refs=[])
        assert pode_marcar_completed(wo) is False, f"{asset_type} nao deveria poder completar sem output"


# ---------------------------------------------------------------------------
# 4) Nenhum dispatch externo acidental (Seção 12 do critério de aceite)
# ---------------------------------------------------------------------------

def test_adapter_stub_nunca_marca_dispatched():
    # PINK_LOGIC (intencionalmente não tocado nesta missão) continua no
    # stub seguro -- PAGEFORGE agora tem adapter real, ver test_pageforge_adapter.py.
    wo = ProductionWorkOrder(project_id="proj_x", asset_type="MARKETING_MATERIAL", executor_type="PINK_LOGIC", status="READY")
    adapter = obter_adapter("PINK_LOGIC")
    assert isinstance(adapter, AdapterNaoConectado)
    resultado = adapter.dispatch(wo)
    assert resultado.status == "READY"  # nunca avançou


def test_todos_executores_conhecidos_tem_adapter_registrado():
    for executor in ("APP_BUILDER", "PAGEFORGE", "PINK_LOGIC", "FORGEHUB", "NEXORA"):
        assert executor in EXECUTOR_REGISTRY


def test_needs_routing_nao_tem_adapter():
    assert obter_adapter("NEEDS_ROUTING") is None


def test_work_order_pronta_para_dispatch_respeita_aprovacao():
    pronta = ProductionWorkOrder(status="READY", requires_approval=False)
    assert pronta.esta_pronta_para_dispatch() is True

    aguardando = ProductionWorkOrder(status="READY", requires_approval=True, approved=False)
    assert aguardando.esta_pronta_para_dispatch() is False

    needs_routing = ProductionWorkOrder(status="NEEDS_ROUTING")
    assert needs_routing.esta_pronta_para_dispatch() is False


# ---------------------------------------------------------------------------
# 5) Ponta a ponta real: "execute o plano" (mesma função de produção) gera
# WorkOrders automaticamente quando a Task 3 completa de verdade.
# ---------------------------------------------------------------------------

def test_execute_o_plano_real_gera_work_orders_apos_task3(monkeypatch, brain_store, pending_store):
    from memory.project_brain import ProductBlueprint

    brain = brain_store.create(name="Carla Figurinhas", tipo="opportunity")
    brain.blueprint = ProductBlueprint(project_id=brain.project_id, recommended_product_type="kit_digital", decision_status="APPROVED")
    brain.business_plan = BusinessPlan(
        project_id=brain.project_id, approval_status="APPROVED",
        required_assets=["Landing page com prova social", "Materiais de marketing digital"],
        acquisition_channels=["Instagram"],
    )
    brain_store.save(brain)

    monkeypatch.setattr(eet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(eet, "get_project_brain_store", lambda: brain_store)

    # 1a chamada: sem execution_plan ainda -> cria em READY_FOR_APPROVAL
    # (mesmo comportamento real observado com a Carla -- precisa de uma
    # aprovação do ExecutionPlan antes de rodar tasks de verdade).
    eet.gerenciar_execucao("execute o plano", SESSION)
    intermediario = brain_store.load(brain.project_id)
    assert intermediario.execution_plan.status == "READY_FOR_APPROVAL"
    intermediario.execution_plan.status = "APPROVED"  # equivalente a "Aprovado" via Approval Router
    brain_store.save(intermediario)

    # 2a chamada: agora liberado para rodar -> t1/t2/t3 completam de verdade.
    resposta = eet.gerenciar_execucao("execute o plano", SESSION)
    assert "execução" in resposta.lower()

    recarregado = brain_store.load(brain.project_id)
    t3 = next(t for t in recarregado.execution_plan.tasks if t.title == "Preparar handoff de ativos necessários")
    assert t3.status == "COMPLETED"
    assert len(recarregado.production_work_orders) == 2
    tipos = {w.asset_type for w in recarregado.production_work_orders}
    assert tipos == {"LANDING_PAGE", "MARKETING_MATERIAL"}
    for w in recarregado.production_work_orders:
        assert w.source_task_id == t3.task_id
        assert w.status in {"READY", "NEEDS_ROUTING"}


def test_execute_o_plano_chamado_duas_vezes_nao_duplica_work_orders(monkeypatch, brain_store):
    from memory.project_brain import ProductBlueprint

    brain = brain_store.create(name="Carla Figurinhas", tipo="opportunity")
    brain.blueprint = ProductBlueprint(project_id=brain.project_id, recommended_product_type="kit_digital", decision_status="APPROVED")
    brain.business_plan = BusinessPlan(
        project_id=brain.project_id, approval_status="APPROVED",
        required_assets=["Landing page com prova social"], acquisition_channels=["Instagram"],
    )
    brain_store.save(brain)

    monkeypatch.setattr(eet, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(eet, "get_project_brain_store", lambda: brain_store)

    eet.gerenciar_execucao("execute o plano", SESSION)  # cria READY_FOR_APPROVAL
    intermediario = brain_store.load(brain.project_id)
    intermediario.execution_plan.status = "APPROVED"
    brain_store.save(intermediario)

    eet.gerenciar_execucao("execute o plano", SESSION)  # roda de verdade -> gera WorkOrder
    eet.gerenciar_execucao("execute o plano", SESSION)  # retry/idempotente -- plan já COMPLETED

    recarregado = brain_store.load(brain.project_id)
    assert len(recarregado.production_work_orders) == 1


# ---------------------------------------------------------------------------
# 6) Status API expõe produção (Seção 9)
# ---------------------------------------------------------------------------

def test_status_api_expoe_producao(brain_store, handoff_store, pending_store):
    brain, t3 = _brain_carla_com_task3_completed(brain_store)
    brain.production_work_orders = gerar_work_orders_da_task(brain, t3)
    brain_store.save(brain)
    handoff_store.registrar("ho_carla_teste", brain.project_id, "PERSISTED")

    status = montar_status("ho_carla_teste", brain_store, handoff_store, pending_store, session=SESSION)
    assert status["production"]["total"] == 2
    assert status["production"]["ready"] == 2
    ids_esperados = {w.work_order_id for w in brain.production_work_orders}
    ids_no_status = {wo["work_order_id"] for wo in status["production"]["work_orders"]}
    assert ids_no_status == ids_esperados
    tipos = {wo["asset_type"] for wo in status["production"]["work_orders"]}
    assert tipos == {"LANDING_PAGE", "MARKETING_MATERIAL"}


def test_status_api_sem_work_orders_ainda(brain_store, handoff_store, pending_store):
    brain = brain_store.create(name="Projeto sem producao ainda")
    brain.market_intelligence.append(MarketIntelligenceHandoff(handoff_id="ho_sem_producao", project_id=brain.project_id, status="PERSISTED"))
    brain_store.save(brain)
    handoff_store.registrar("ho_sem_producao", brain.project_id, "PERSISTED")

    status = montar_status("ho_sem_producao", brain_store, handoff_store, pending_store, session=SESSION)
    assert status["production"] == {"total": 0, "ready": 0, "dispatched": 0, "running": 0, "completed": 0, "failed": 0, "needs_routing": 0, "work_orders": []}


# ---------------------------------------------------------------------------
# 7) Telegram: consulta sem dispatch
# ---------------------------------------------------------------------------

def test_telegram_consulta_producao_formata_corretamente(monkeypatch, brain_store):
    import tools.market_intelligence_tools as mit

    brain, t3 = _brain_carla_com_task3_completed(brain_store)
    brain.production_work_orders = gerar_work_orders_da_task(brain, t3)
    brain_store.save(brain)

    monkeypatch.setattr(mit, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(mit, "get_project_brain_store", lambda: brain_store)

    resposta = mit.gerenciar_market_intelligence("o que falta produzir?", SESSION)
    assert "PageForge" in resposta
    assert "Pink Logic" in resposta
    assert "aguardando integração/envio" in resposta


def test_telegram_consulta_producao_nunca_despacha(monkeypatch, brain_store):
    import tools.market_intelligence_tools as mit

    def _boom(*a, **k):
        raise AssertionError("consulta de produção nunca deveria despachar nada")

    for adapter in EXECUTOR_REGISTRY.values():
        monkeypatch.setattr(adapter, "dispatch", _boom)

    brain, t3 = _brain_carla_com_task3_completed(brain_store)
    brain.production_work_orders = gerar_work_orders_da_task(brain, t3)
    brain_store.save(brain)

    monkeypatch.setattr(mit, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(mit, "get_project_brain_store", lambda: brain_store)

    mit.gerenciar_market_intelligence("quais ativos faltam?", SESSION)
    mit.gerenciar_market_intelligence("status da produção", SESSION)
    # se _boom tivesse sido chamado, o teste já teria falhado com AssertionError


def test_nenhuma_chamada_http_externa(monkeypatch, brain_store):
    import requests

    def _boom(*a, **k):
        raise AssertionError("producao nunca deveria fazer chamada HTTP externa")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    brain, t3 = _brain_carla_com_task3_completed(brain_store)
    gerar_work_orders_da_task(brain, t3)
