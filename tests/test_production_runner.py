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
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

import core.executor_adapter as executor_adapter
from config.settings import settings
from core.executor_adapter import AdapterNaoConectado
from core.production_runner import (
    MAX_TENTATIVAS_AUTOMATICAS,
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


class FakeAdapterQueFalhaTransitoriamente:
    """Simula um erro transitório (ex.: 429/5xx do PageForge): NUNCA muda o
    `status` (fica READY, retryable), só registra `last_error` e conta as
    chamadas -- igual ao comportamento real de `pageforge_adapter.py` nos
    ramos 429/5xx."""

    def __init__(self):
        self.chamadas: list[str] = []

    def can_handle(self, wo):
        return True

    def dispatch(self, wo):
        self.chamadas.append(wo.work_order_id)
        wo.attempts += 1
        wo.last_error = "PageForge indisponível/sobrecarregado (HTTP 503)."
        wo.updated_at = datetime.now(timezone.utc).isoformat()
        return wo  # status permanece RUNNING (setado pelo runner antes do dispatch)

    def get_status(self, wo):
        return wo.status

    def collect_result(self, wo):
        return wo


class FakeAdapterRecuperavel:
    """Usado nos testes de recuperação pós-restart: `collect_result` é quem
    decide o resultado "real" encontrado no executor -- `dispatch` nunca é
    chamado nestes testes (a recuperação é sempre só leitura)."""

    def __init__(self, resultado_recuperado: str | None):
        self.resultado_recuperado = resultado_recuperado
        self.chamadas_dispatch: list[str] = []
        self.chamadas_collect: list[str] = []

    def can_handle(self, wo):
        return True

    def dispatch(self, wo):
        self.chamadas_dispatch.append(wo.work_order_id)
        wo.status = "DISPATCHED"
        wo.attempts += 1
        return wo

    def get_status(self, wo):
        return wo.status

    def collect_result(self, wo):
        self.chamadas_collect.append(wo.work_order_id)
        if self.resultado_recuperado is not None:
            wo.status = self.resultado_recuperado
            wo.last_error = None
        # resultado_recuperado=None simula "nada encontrado" -- status
        # permanece RUNNING, exatamente como o PageForge quando o ledger
        # não confirma nada reconhecível.
        return wo


def _ha(segundos: float) -> str:
    """Timestamp ISO `segundos` atrás -- usado para simular que o backoff já
    passou (ou ainda não) sem depender de `time.sleep` real nos testes."""
    return (datetime.now(timezone.utc) - timedelta(seconds=segundos)).isoformat()


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
    """Etapa 18: quando o adapter lança uma exceção inesperada, o estado é
    INDETERMINADO (pode ter havido efeito remoto antes da exceção) -- por
    isso a WorkOrder NUNCA é revertida às cegas para READY (arriscaria um
    segundo dispatch real). Fica em RUNNING, para a varredura de recuperação
    do próximo ciclo decidir com segurança."""
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
    assert wo1.last_error and "runner durante dispatch" in wo1.last_error
    assert wo1.status == "RUNNING"  # nunca revertido a READY às cegas


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


# ---------------------------------------------------------------------------
# Etapa 18 -- política de retry: máximo de tentativas, nunca infinito
# ---------------------------------------------------------------------------

def test_max_tentativas_automaticas_e_um_valor_conservador_e_finito():
    assert MAX_TENTATIVAS_AUTOMATICAS == 3


def test_workorder_com_tentativas_esgotadas_nao_e_elegivel():
    wo = _work_order(status="READY", attempts=MAX_TENTATIVAS_AUTOMATICAS)
    elegivel, motivo = elegivel_para_dispatch_automatico(wo)
    assert elegivel is False
    assert "esgotad" in motivo.lower()


def test_workorder_abaixo_do_limite_de_tentativas_continua_elegivel():
    wo = _work_order(status="READY", attempts=MAX_TENTATIVAS_AUTOMATICAS - 1, updated_at=_ha(3600))
    elegivel, _ = elegivel_para_dispatch_automatico(wo)
    assert elegivel is True


def test_dead_letter_marca_failed_quando_tentativas_esgotam(_registry_isolado):
    """Nunca deixa uma WorkOrder presa em READY para sempre, invisível ao
    runner -- ao esgotar as tentativas, ela vira FAILED explicitamente,
    preservando o `last_error` anterior no texto novo (histórico nunca
    apagado)."""
    from memory.project_brain import ProjectBrain, Identidade

    wo = _work_order(work_order_id="wo_esgotada", attempts=MAX_TENTATIVAS_AUTOMATICAS, last_error="PageForge indisponível (HTTP 503).")
    brain = ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Teste"))
    brain.production_work_orders = [wo]

    resultados = processar_work_orders_do_projeto(brain)

    assert wo.status == "FAILED"
    assert "esgotad" in wo.last_error.lower()
    assert "HTTP 503" in wo.last_error  # histórico anterior preservado, não apagado
    assert _registry_isolado.chamadas == []  # nunca chegou a tentar despachar de novo
    assert len(resultados) == 1
    assert resultados[0]["motivo_elegibilidade"] == "tentativas esgotadas (dead letter)"


def test_nao_faz_retry_infinito_apos_esgotar_tentativas(monkeypatch):
    """Simula 3 falhas transitórias consecutivas (ciclo a ciclo) -- na
    4ª passada, a WorkOrder já não é mais elegível e é dead-lettered, nunca
    tentada uma 4ª vez de verdade."""
    from memory.project_brain import ProjectBrain, Identidade

    fake = FakeAdapterQueFalhaTransitoriamente()
    registry_teste = dict(executor_adapter.EXECUTOR_REGISTRY)
    registry_teste["FAKE_EXECUTOR"] = fake
    monkeypatch.setattr(executor_adapter, "EXECUTOR_REGISTRY", registry_teste)

    wo = _work_order(work_order_id="wo_flaky")
    brain = ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Teste"))
    brain.production_work_orders = [wo]

    for _ in range(MAX_TENTATIVAS_AUTOMATICAS):
        wo.status = "READY"  # adapter real deixaria READY; aqui simulamos o "próximo ciclo" já sem esperar o backoff de verdade
        wo.updated_at = _ha(3600)  # já passou tempo suficiente p/ qualquer backoff
        processar_work_orders_do_projeto(brain)

    assert wo.attempts == MAX_TENTATIVAS_AUTOMATICAS
    assert len(fake.chamadas) == MAX_TENTATIVAS_AUTOMATICAS

    # 4ª passada: já esgotou -- nunca mais chama o adapter, vira dead letter.
    wo.status = "READY"
    wo.updated_at = _ha(3600)
    processar_work_orders_do_projeto(brain)

    assert len(fake.chamadas) == MAX_TENTATIVAS_AUTOMATICAS  # nenhuma chamada a mais
    assert wo.status == "FAILED"


# ---------------------------------------------------------------------------
# Etapa 18 -- backoff: nunca retry imediato em loop apertado
# ---------------------------------------------------------------------------

def test_backoff_bloqueia_retry_imediato_apos_falha_transitoria():
    wo = _work_order(status="READY", attempts=1, updated_at=_ha(1))  # falhou há 1s
    elegivel, motivo = elegivel_para_dispatch_automatico(wo)
    assert elegivel is False
    assert "backoff" in motivo.lower()


def test_backoff_libera_retry_apos_tempo_suficiente():
    wo = _work_order(status="READY", attempts=1, updated_at=_ha(61))  # 60s já passaram
    elegivel, _ = elegivel_para_dispatch_automatico(wo)
    assert elegivel is True


def test_backoff_da_segunda_tentativa_e_maior_que_o_da_primeira():
    """Backoff crescente -- espera mais tempo a cada tentativa, nunca
    constante nem decrescente."""
    wo_apos_1a = _work_order(status="READY", attempts=1, updated_at=_ha(120))  # 2min, ok p/ 1a espera (60s)
    wo_apos_2a = _work_order(status="READY", attempts=2, updated_at=_ha(120))  # 2min, NAO ok p/ 2a espera (300s)

    elegivel_1a, _ = elegivel_para_dispatch_automatico(wo_apos_1a)
    elegivel_2a, motivo_2a = elegivel_para_dispatch_automatico(wo_apos_2a)

    assert elegivel_1a is True
    assert elegivel_2a is False
    assert "backoff" in motivo_2a.lower()


# ---------------------------------------------------------------------------
# Etapa 18 -- crash-safety: marca RUNNING e persiste ANTES do dispatch real
# ---------------------------------------------------------------------------

def test_marca_running_e_persiste_antes_de_chamar_dispatch(brain_store, monkeypatch):
    """Prova de crash-safety: o adapter, DENTRO da própria chamada de
    dispatch (simulando o momento exato de uma chamada de rede em
    andamento), relê o projeto do armazenamento -- e já deve encontrar
    RUNNING lá, nunca READY. Isso é o que garante que um crash real bem
    nesse instante não faria um restart re-despachar do zero."""
    status_visto_pelo_storage_durante_dispatch = {}

    class AdapterQueChecaPersistenciaNoMeio:
        def can_handle(self, wo):
            return True

        def dispatch(self, wo):
            recarregado = brain_store.load(wo.project_id)
            status_visto_pelo_storage_durante_dispatch["status"] = recarregado.production_work_orders[0].status
            wo.status = "DISPATCHED"
            wo.attempts += 1
            return wo

        def get_status(self, wo):
            return wo.status

        def collect_result(self, wo):
            return wo

    registry_teste = dict(executor_adapter.EXECUTOR_REGISTRY)
    registry_teste["FAKE_EXECUTOR"] = AdapterQueChecaPersistenciaNoMeio()
    monkeypatch.setattr(executor_adapter, "EXECUTOR_REGISTRY", registry_teste)

    projeto = brain_store.create(name="Projeto")
    projeto.production_work_orders = [_work_order(project_id=projeto.project_id, work_order_id="wo_x")]
    brain_store.save(projeto)

    processar_work_orders_do_projeto(brain_store.load(projeto.project_id), brain_store=brain_store)

    assert status_visto_pelo_storage_durante_dispatch["status"] == "RUNNING"


def test_sem_brain_store_ainda_funciona_mas_sem_persistencia_intermediaria(_registry_isolado):
    """Chamada direta sem `brain_store` (uso em teste/memória pura) continua
    funcionando exatamente como antes -- só não ganha a proteção extra de
    persistir o marcador RUNNING no meio do caminho."""
    from memory.project_brain import ProjectBrain, Identidade

    wo = _work_order(work_order_id="wo_sem_store")
    brain = ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Teste"))
    brain.production_work_orders = [wo]

    resultados = processar_work_orders_do_projeto(brain)

    assert len(resultados) == 1
    assert wo.status == "DISPATCHED"


def test_dispatch_bem_sucedido_nao_deixa_running_residual(_registry_isolado):
    wo = _work_order(work_order_id="wo_ok")
    from memory.project_brain import ProjectBrain, Identidade
    brain = ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Teste"))
    brain.production_work_orders = [wo]

    processar_work_orders_do_projeto(brain)

    assert wo.status == "DISPATCHED"  # nunca fica preso em RUNNING quando o dispatch teve sucesso


# ---------------------------------------------------------------------------
# Etapa 18 -- recovery: nunca redespacha às cegas após restart/crash
# ---------------------------------------------------------------------------

def test_recuperacao_consulta_resultado_real_via_collect_result_nunca_dispatch(monkeypatch):
    from memory.project_brain import ProjectBrain, Identidade

    fake = FakeAdapterRecuperavel(resultado_recuperado="COMPLETED")
    registry_teste = dict(executor_adapter.EXECUTOR_REGISTRY)
    registry_teste["FAKE_EXECUTOR"] = fake
    monkeypatch.setattr(executor_adapter, "EXECUTOR_REGISTRY", registry_teste)

    wo = _work_order(work_order_id="wo_presa", status="RUNNING")
    brain = ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Teste"))
    brain.production_work_orders = [wo]

    resultados = processar_work_orders_do_projeto(brain)

    assert wo.status == "COMPLETED"
    assert fake.chamadas_collect == ["wo_presa"]
    assert fake.chamadas_dispatch == []  # NUNCA redespachado -- só consultado
    assert resultados[0]["motivo_elegibilidade"].startswith("recuperação pós-restart")


def test_recuperacao_sem_resultado_confirmavel_marca_failed_nunca_redespacha(monkeypatch):
    """O caso mais importante desta etapa: quando nem o executor confirma
    nada (ex.: ledger do PageForge com o bug conhecido do Blob privado, ou
    qualquer outra ambiguidade), o runner NUNCA arrisca um redispatch --
    marca FAILED para revisão manual."""
    from memory.project_brain import ProjectBrain, Identidade

    fake = FakeAdapterRecuperavel(resultado_recuperado=None)  # nada encontrado
    registry_teste = dict(executor_adapter.EXECUTOR_REGISTRY)
    registry_teste["FAKE_EXECUTOR"] = fake
    monkeypatch.setattr(executor_adapter, "EXECUTOR_REGISTRY", registry_teste)

    wo = _work_order(work_order_id="wo_ambigua", status="RUNNING", attempts=1)
    brain = ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Teste"))
    brain.production_work_orders = [wo]

    resultados = processar_work_orders_do_projeto(brain)

    assert wo.status == "FAILED"
    assert "nunca redespachada automaticamente" in wo.last_error
    assert fake.chamadas_dispatch == []
    assert resultados[0]["status_antes"] == "RUNNING"
    assert resultados[0]["status_depois"] == "FAILED"


def test_recuperacao_sem_adapter_registrado_marca_failed(monkeypatch):
    """Caso extremo: executor_type mudou/foi removido do registro entre o
    dispatch original e o restart -- ainda assim nunca trava para sempre em
    RUNNING, nunca lança exceção."""
    from memory.project_brain import ProjectBrain, Identidade

    registry_teste = dict(executor_adapter.EXECUTOR_REGISTRY)
    registry_teste.pop("FAKE_EXECUTOR", None)
    monkeypatch.setattr(executor_adapter, "EXECUTOR_REGISTRY", registry_teste)

    wo = _work_order(work_order_id="wo_orfa", status="RUNNING", executor_type="FAKE_EXECUTOR")
    brain = ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Teste"))
    brain.production_work_orders = [wo]

    resultados = processar_work_orders_do_projeto(brain)

    assert wo.status == "FAILED"
    assert "nenhum adapter registrado" in wo.last_error.lower()
    assert resultados[0]["status_depois"] == "FAILED"


def test_recuperacao_roda_antes_de_qualquer_dispatch_novo_no_mesmo_ciclo(monkeypatch):
    """Uma WorkOrder presa em RUNNING e outra nova READY no MESMO projeto:
    a recuperação da primeira nunca é confundida com um dispatch da
    segunda -- cada uma segue seu próprio caminho, isoladamente."""
    from memory.project_brain import ProjectBrain, Identidade

    fake = FakeAdapterRecuperavel(resultado_recuperado="FAILED")
    registry_teste = dict(executor_adapter.EXECUTOR_REGISTRY)
    registry_teste["FAKE_EXECUTOR"] = fake
    monkeypatch.setattr(executor_adapter, "EXECUTOR_REGISTRY", registry_teste)

    wo_presa = _work_order(work_order_id="wo_presa", status="RUNNING")
    wo_nova = _work_order(work_order_id="wo_nova", status="READY")
    brain = ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Teste"))
    brain.production_work_orders = [wo_presa, wo_nova]

    resultados = processar_work_orders_do_projeto(brain)

    assert wo_presa.status == "FAILED"  # recuperada
    assert wo_nova.status == "DISPATCHED"  # despachada normalmente
    assert fake.chamadas_collect == ["wo_presa"]
    assert fake.chamadas_dispatch == ["wo_nova"]
    assert len(resultados) == 2


def test_processa_fila_recupera_running_de_multiplos_projetos_isoladamente(brain_store, monkeypatch):
    fake_a = FakeAdapterRecuperavel(resultado_recuperado="COMPLETED")
    registry_teste = dict(executor_adapter.EXECUTOR_REGISTRY)
    registry_teste["FAKE_EXECUTOR"] = fake_a
    monkeypatch.setattr(executor_adapter, "EXECUTOR_REGISTRY", registry_teste)

    projeto_a = brain_store.create(name="Projeto A")
    projeto_a.production_work_orders = [_work_order(project_id=projeto_a.project_id, work_order_id="wo_a", status="RUNNING")]
    brain_store.save(projeto_a)

    projeto_b = brain_store.create(name="Projeto B")
    projeto_b.production_work_orders = [_work_order(project_id=projeto_b.project_id, work_order_id="wo_b", status="COMPLETED")]
    brain_store.save(projeto_b)

    processar_fila_elegivel(brain_store)

    recarregado_a = brain_store.load(projeto_a.project_id)
    recarregado_b = brain_store.load(projeto_b.project_id)
    assert recarregado_a.production_work_orders[0].status == "COMPLETED"  # recuperada
    assert recarregado_b.production_work_orders[0].status == "COMPLETED"  # intocado (nem estava RUNNING)
