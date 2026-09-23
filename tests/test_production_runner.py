"""
Testes do Production Runner (`core/production_runner.py`, Etapa 17) --
processamento automático de ProductionWorkOrders ELEGÍVEIS, sem depender de
um comando manual "execute essa WorkOrder".

ZERO chamada real: todo adapter usado aqui é um FAKE em memória, registrado
temporariamente em `core.executor_adapter.EXECUTOR_REGISTRY` e sempre
restaurado ao final de cada teste (fixture `_registry_original`). O runner
em si é DESLIGADO por padrão em produção (`PRODUCTION_RUNNER_ENABLED=false`)
-- estes testes cobrem a lógica, nunca ativam o loop periódico de verdade.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

import core.executor_adapter as executor_adapter
from config.settings import settings
from core.executor_adapter import AdapterNaoConectado
from core.production_runner import (
    elegivel_para_dispatch_automatico,
    processar_fila_elegivel,
    processar_work_orders_do_projeto,
)
from memory.layers import ProjectMemory
from memory.project_brain import ProjectBrainStore, ProductionWorkOrder
from storage import SQLiteMemory


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_production_runner.db"


@pytest.fixture()
def brain_store(db_path):
    backend = SQLiteMemory(db_path)
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


class FakeAdapterConectado:
    """Adapter fake REAL (não é o stub) -- registra chamadas, nunca faz
    rede de verdade. Simula sucesso: muda status para DISPATCHED."""

    def __init__(self):
        self.chamadas: list[str] = []

    def can_handle(self, wo):
        return wo.executor_type == "FAKE_EXECUTOR"

    def dispatch(self, wo):
        self.chamadas.append(wo.work_order_id)
        wo.status = "DISPATCHED"
        wo.attempts += 1
        return wo

    def get_status(self, wo):
        return wo.status

    def collect_result(self, wo):
        return wo


class FakeAdapterQueFalha:
    def dispatch(self, wo):
        raise RuntimeError("falha simulada de rede")

    def can_handle(self, wo):
        return True

    def get_status(self, wo):
        return wo.status

    def collect_result(self, wo):
        return wo


@pytest.fixture(autouse=True)
def _registry_isolado(monkeypatch):
    """Registra um executor FAKE_EXECUTOR->fake_adapter isolado para os
    testes, sem tocar nos adapters reais (PAGEFORGE etc.) -- restaurado
    automaticamente ao final via monkeypatch."""
    fake = FakeAdapterConectado()
    registry_teste = dict(executor_adapter.EXECUTOR_REGISTRY)
    registry_teste["FAKE_EXECUTOR"] = fake
    monkeypatch.setattr(executor_adapter, "EXECUTOR_REGISTRY", registry_teste)
    return fake


def _work_order(**overrides) -> ProductionWorkOrder:
    base = dict(project_id="proj_teste", asset_type="LANDING_PAGE", executor_type="FAKE_EXECUTOR", status="READY")
    base.update(overrides)
    return ProductionWorkOrder(**base)


# ---------------------------------------------------------------------------
# elegivel_para_dispatch_automatico -- nunca fail-open
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", [
    "CREATED", "DISPATCHED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED",
    "NEEDS_ROUTING", "WAITING_APPROVAL",
])
def test_apenas_ready_e_elegivel(status):
    wo = _work_order(status=status)
    elegivel, motivo = elegivel_para_dispatch_automatico(wo)
    assert elegivel is False
    assert status in motivo or "READY" in motivo


def test_ready_sem_aprovacao_pendente_e_elegivel():
    wo = _work_order(status="READY", requires_approval=False)
    elegivel, _ = elegivel_para_dispatch_automatico(wo)
    assert elegivel is True


def test_ready_com_aprovacao_pendente_nao_e_elegivel():
    wo = _work_order(status="READY", requires_approval=True, approved=False)
    elegivel, motivo = elegivel_para_dispatch_automatico(wo)
    assert elegivel is False
    assert "aprova" in motivo.lower()


def test_ready_com_aprovacao_ja_concedida_e_elegivel():
    wo = _work_order(status="READY", requires_approval=True, approved=True)
    elegivel, _ = elegivel_para_dispatch_automatico(wo)
    assert elegivel is True


def test_executor_nao_conectado_stub_nao_e_elegivel():
    wo = _work_order(status="READY", executor_type="PINK_LOGIC")  # continua no stub
    adapter = executor_adapter.obter_adapter("PINK_LOGIC")
    assert isinstance(adapter, AdapterNaoConectado)
    elegivel, motivo = elegivel_para_dispatch_automatico(wo)
    assert elegivel is False
    assert "não" in motivo.lower() or "stub" in motivo.lower() or "conectado" in motivo.lower()


def test_executor_pageforge_real_e_elegivel_quando_ready_e_sem_aprovacao():
    wo = _work_order(status="READY", executor_type="PAGEFORGE", requires_approval=False)
    elegivel, _ = elegivel_para_dispatch_automatico(wo)
    assert elegivel is True


def test_executor_desconhecido_needs_routing_nao_e_elegivel():
    wo = _work_order(status="READY", executor_type="NEEDS_ROUTING")
    elegivel, motivo = elegivel_para_dispatch_automatico(wo)
    assert elegivel is False
    assert "nenhum adapter" in motivo.lower()


# ---------------------------------------------------------------------------
# processar_work_orders_do_projeto -- dispatch sequencial, nunca duplica
# ---------------------------------------------------------------------------

def test_processa_somente_workorder_elegivel(_registry_isolado):
    from memory.project_brain import ProjectBrain, Identidade

    elegivel = _work_order(work_order_id="wo_elegivel")
    completa = _work_order(work_order_id="wo_completa", status="COMPLETED")
    pendente_aprovacao = _work_order(work_order_id="wo_pendente", requires_approval=True, approved=False)
    stub = _work_order(work_order_id="wo_stub", executor_type="PINK_LOGIC")

    brain = ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Teste"))
    brain.production_work_orders = [elegivel, completa, pendente_aprovacao, stub]

    resultados = processar_work_orders_do_projeto(brain)

    assert len(resultados) == 1
    assert resultados[0]["work_order_id"] == "wo_elegivel"
    assert _registry_isolado.chamadas == ["wo_elegivel"]
    assert elegivel.status == "DISPATCHED"
    # as outras 3 continuam EXATAMENTE como estavam -- nunca tocadas
    assert completa.status == "COMPLETED"
    assert pendente_aprovacao.status == "READY" and pendente_aprovacao.approved is False
    assert stub.status == "READY"


def test_falha_do_adapter_nao_derruba_o_runner(monkeypatch):
    from memory.project_brain import ProjectBrain, Identidade

    registry_teste = dict(executor_adapter.EXECUTOR_REGISTRY)
    registry_teste["FAKE_EXECUTOR"] = FakeAdapterQueFalha()
    monkeypatch.setattr(executor_adapter, "EXECUTOR_REGISTRY", registry_teste)

    wo1 = _work_order(work_order_id="wo_falha")
    wo2 = _work_order(work_order_id="wo_ok_depois")
    brain = ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Teste"))
    brain.production_work_orders = [wo1, wo2]

    resultados = processar_work_orders_do_projeto(brain)  # nunca lança exceção

    assert len(resultados) == 2  # ambas tentadas -- uma falha nao impede a proxima
    assert wo1.last_error and "falha simulada" in wo1.last_error
    assert wo1.status == "READY"  # dispatch falhou antes de mudar o status


def test_nenhuma_workorder_elegivel_nao_falha(monkeypatch):
    from memory.project_brain import ProjectBrain, Identidade

    def _boom(*a, **k):
        raise AssertionError("nao deveria chamar nenhum adapter -- nada elegivel")
    registry_teste = dict(executor_adapter.EXECUTOR_REGISTRY)
    monkeypatch.setattr(executor_adapter, "EXECUTOR_REGISTRY", registry_teste)

    brain = ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Teste"))
    brain.production_work_orders = [_work_order(status="COMPLETED"), _work_order(status="FAILED")]

    resultados = processar_work_orders_do_projeto(brain)
    assert resultados == []


# ---------------------------------------------------------------------------
# processar_fila_elegivel -- varre múltiplos projetos, persiste só o que mudou
# ---------------------------------------------------------------------------

def test_processa_fila_entre_multiplos_projetos_isoladamente(brain_store, _registry_isolado):
    projeto_a = brain_store.create(name="Projeto A")
    projeto_a.production_work_orders = [_work_order(project_id=projeto_a.project_id, work_order_id="wo_a")]
    brain_store.save(projeto_a)

    projeto_b = brain_store.create(name="Projeto B")
    projeto_b.production_work_orders = [_work_order(project_id=projeto_b.project_id, work_order_id="wo_b", status="COMPLETED")]
    brain_store.save(projeto_b)

    resultados = processar_fila_elegivel(brain_store)

    assert len(resultados) == 1
    assert resultados[0]["work_order_id"] == "wo_a"

    recarregado_a = brain_store.load(projeto_a.project_id)
    recarregado_b = brain_store.load(projeto_b.project_id)
    assert recarregado_a.production_work_orders[0].status == "DISPATCHED"
    assert recarregado_b.production_work_orders[0].status == "COMPLETED"  # intocado


def test_processar_fila_chamado_duas_vezes_nao_duplica_dispatch(brain_store, _registry_isolado):
    projeto = brain_store.create(name="Projeto")
    projeto.production_work_orders = [_work_order(project_id=projeto.project_id, work_order_id="wo_unica")]
    brain_store.save(projeto)

    r1 = processar_fila_elegivel(brain_store)
    r2 = processar_fila_elegivel(brain_store)  # retry/segunda passada

    assert len(r1) == 1
    assert len(r2) == 0  # ja nao esta mais READY -- nao e reprocessada
    assert _registry_isolado.chamadas == ["wo_unica"]  # so 1 chamada real, nunca 2


def test_projeto_sem_nenhuma_workorder_elegivel_nao_e_salvo(brain_store, monkeypatch):
    """Otimização/efeito colateral verificado: um projeto sem nada a
    processar nunca é reescrito -- evita updated_at mudando à toa."""
    projeto = brain_store.create(name="Projeto")
    projeto.production_work_orders = [_work_order(project_id=projeto.project_id, status="COMPLETED")]
    brain_store.save(projeto)
    antes = brain_store.load(projeto.project_id).identidade.updated_at

    processar_fila_elegivel(brain_store)

    depois = brain_store.load(projeto.project_id).identidade.updated_at
    assert antes == depois


def test_isolamento_tipo_carla_pink_logic(brain_store, _registry_isolado):
    """Réplica fiel do cenário real: uma WorkOrder já COMPLETED (tipo
    Carla) e uma no stub PINK_LOGIC no MESMO projeto -- nenhuma das duas
    pode ser tocada pelo runner automático."""
    projeto = brain_store.create(name="Projeto tipo Carla")
    wo_completa = _work_order(project_id=projeto.project_id, work_order_id="wo_carla_like", status="COMPLETED", executor_type="PAGEFORGE")
    wo_pink = _work_order(project_id=projeto.project_id, work_order_id="wo_pink_like", executor_type="PINK_LOGIC")
    projeto.production_work_orders = [wo_completa, wo_pink]
    brain_store.save(projeto)

    resultados = processar_fila_elegivel(brain_store)

    assert resultados == []
    recarregado = brain_store.load(projeto.project_id)
    assert recarregado.production_work_orders[0].status == "COMPLETED"
    assert recarregado.production_work_orders[1].status == "READY"  # nunca despachada (stub)


# ---------------------------------------------------------------------------
# Feature flag -- desligado por padrão
# ---------------------------------------------------------------------------

def test_production_runner_desligado_por_padrao():
    assert settings.PRODUCTION_RUNNER_ENABLED is False


def test_intervalo_padrao_razoavel():
    assert settings.PRODUCTION_RUNNER_INTERVAL_SECONDS > 0


# ---------------------------------------------------------------------------
# Nenhuma chamada de rede real em nenhum teste deste arquivo
# ---------------------------------------------------------------------------

def test_nenhuma_chamada_http_real(monkeypatch, brain_store, _registry_isolado):
    import requests

    def _boom(*a, **k):
        raise AssertionError("production_runner nunca deveria fazer chamada HTTP real nos testes")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    projeto = brain_store.create(name="Projeto")
    projeto.production_work_orders = [_work_order(project_id=projeto.project_id)]
    brain_store.save(projeto)
    processar_fila_elegivel(brain_store)
