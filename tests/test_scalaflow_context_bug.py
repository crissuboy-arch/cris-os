"""
Regressão do bug real: "TELEGRAM PERDEU O CONTEXTO DA CARLA".

CAUSA RAIZ: `core/scalaflow_bridge.py` criava BusinessPlan/PendingApproval
corretamente, mas NUNCA atualizava `UserFocusStore` (Fase 3, "foco atual" da
sessão). Frases genéricas ("execute o plano", "mostre o plano de negócio")
NÃO passam pelo Approval Router (só "Aprovado"/"Rejeito" passam) -- elas
resolvem o projeto via `get_foco_atual(session)`, que ficava travado no
ÚLTIMO projeto tocado pelo fluxo orgânico antigo (ex.: "Ana Martin"),
nunca atualizado para o projeto vindo do ScalaFlow.

Estes testes reproduzem o cenário EXATO com as funções REAIS das ferramentas
(`tools/execution_engine_tools.py`, `tools/business_builder_tools.py`,
`tools/market_intelligence_tools.py`, `core/approval_router.py`) -- nenhuma
reimplementação. Zero custo de IA (llm=None ou fakes em memória).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

import channels.telegram.bot as telegram_bot
import core.scalaflow_bridge as bridge
import tools.business_builder_tools as bbt
import tools.execution_engine_tools as eet
import tools.market_intelligence_tools as mit
from core.approval_router import resolver_aprovacao_contextual
from core.market_intelligence import receive_intelligence
from memory.layers import ProjectMemory
from memory.project_brain import (
    IntelligenceHandoffStore,
    PendingApprovalStore,
    ProjectBrainStore,
    TrafficPlan,
    UserFocusStore,
)
from storage import SQLiteMemory
from tests.test_scalaflow_bridge import (
    FakeLLMBusinessBuilder,
    FakeLLMProductArchitect,
    _payload_carla_like,
)

SESSION = "telegram:1"


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_scalaflow_context_bug.db"


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


@pytest.fixture()
def focus_store(brain_store):
    return UserFocusStore(brain_store.project_memory)


@pytest.fixture(autouse=True)
def _sessao_fixa(monkeypatch):
    monkeypatch.setattr(bridge, "sessao_cris", lambda: SESSION)


@pytest.fixture(autouse=True)
def _sem_notificacao_de_verdade(monkeypatch):
    monkeypatch.setattr(telegram_bot, "enviar_mensagem_proativa", lambda texto: True)


def _projeto_legado_com_traffic_plan_aprovado(brain_store, nome="Ana Martin"):
    """Simula um projeto pré-existente do fluxo ORGÂNICO antigo (Opportunity
    Analyst -> ... -> Paid Traffic Architect), com um TrafficPlan já
    aprovado -- EXATAMENTE a forma real de `proj_cb094b4ef6a4` em produção."""
    brain = brain_store.create(name=nome, tipo="opportunity")
    brain.traffic_plan = TrafficPlan(project_id=brain.project_id, version=1, status="APPROVED")
    brain_store.save(brain)
    return brain.project_id


def _avancar_carla(brain_store, handoff_store, pending_store, focus_store, handoff_id="ho_carla_teste"):
    receive_intelligence(_payload_carla_like(handoff_id), brain_store, handoff_store)
    return bridge.avancar_a_partir_do_handoff(
        handoff_id, brain_store, handoff_store, pending_store, session=SESSION,
        llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder(),
        focus_store=focus_store,
    )


def _monkeypatch_tools_para_store(monkeypatch, brain_store):
    for modulo in (eet, bbt, mit):
        monkeypatch.setattr(modulo, "get_project_brain_store", lambda: brain_store)
        monkeypatch.setattr(modulo, "get_foco_atual", lambda session: UserFocusStore(brain_store.project_memory).get_focus(session))


# ---------------------------------------------------------------------------
# Reprodução exata do bug: foco travado no projeto legado + "execute o plano"
# ---------------------------------------------------------------------------

def test_avancar_projeto_corrige_foco_para_o_projeto_scalaflow(brain_store, handoff_store, pending_store, focus_store):
    """A causa raiz: ANTES da correção, `avancar_a_partir_do_handoff` nunca
    tocava o foco. Este teste prova que agora ele SEMPRE aponta o foco da
    sessão para o projeto explicitamente resolvido."""
    projeto_legado = _projeto_legado_com_traffic_plan_aprovado(brain_store)
    focus_store.set_focus(SESSION, projeto_legado)  # simula foco travado (5 dias atrás, no caso real)
    assert focus_store.get_focus(SESSION) == projeto_legado

    resultado = _avancar_carla(brain_store, handoff_store, pending_store, focus_store)
    assert resultado["status"] == "PENDING_APPROVAL_CREATED"

    assert focus_store.get_focus(SESSION) == resultado["project_id"]
    assert focus_store.get_focus(SESSION) != projeto_legado


def test_execute_o_plano_resolve_carla_nao_o_projeto_legado(monkeypatch, brain_store, handoff_store, pending_store, focus_store):
    """Reprodução EXATA do incidente relatado: sessão com foco travado no
    projeto legado (com TrafficPlan aprovado) + Carla avançada e aprovada
    (BusinessPlan -> ExecutionPlan, ambos APPROVED) -> "execute o plano"
    DEVE resolver e processar o ExecutionPlan da Carla, nunca criar/tocar
    um ExecutionPlan no projeto legado.

    NOTA: este teste roda `executar_plano()` de verdade (via a MESMA função
    que o Telegram chamaria) -- mas contra um banco SQLite temporário e
    isolado (`tmp_path`), nunca o banco de produção real. Isso reproduz o
    bug fielmente sem tocar em nenhum dado real da Carla.
    """
    projeto_legado = _projeto_legado_com_traffic_plan_aprovado(brain_store)
    focus_store.set_focus(SESSION, projeto_legado)  # foco travado ANTES de tocar Carla

    resultado = _avancar_carla(brain_store, handoff_store, pending_store, focus_store)
    project_carla = resultado["project_id"]

    resolver_aprovacao_contextual("Aprovado", SESSION, pending_store, brain_store)  # BusinessPlan -> APPROVED, cria ExecutionPlan
    execution_id_carla = brain_store.load(project_carla).execution_plan.execution_id
    resolver_aprovacao_contextual("Aprovado", SESSION, pending_store, brain_store)  # ExecutionPlan -> APPROVED (mesmo cenário real)

    _monkeypatch_tools_para_store(monkeypatch, brain_store)
    resposta = eet.gerenciar_execucao("execute o plano", SESSION)

    assert project_carla in resposta
    assert execution_id_carla in resposta

    brain_legado = brain_store.load(projeto_legado)
    assert brain_legado.execution_plan is None  # NUNCA criou/tocou um ExecutionPlan no projeto legado

    brain_carla = brain_store.load(project_carla)
    assert brain_carla.execution_plan.execution_id == execution_id_carla  # nenhum ExecutionPlan novo/duplicado


def test_execute_o_plano_antes_da_aprovacao_ainda_resolve_carla(monkeypatch, brain_store, handoff_store, pending_store, focus_store):
    """Mesmo cenário, mas ExecutionPlan ainda READY_FOR_APPROVAL (não
    executa nada) -- confirma que a resolução de PROJETO está correta
    independente do estágio do ExecutionPlan."""
    projeto_legado = _projeto_legado_com_traffic_plan_aprovado(brain_store)
    focus_store.set_focus(SESSION, projeto_legado)

    resultado = _avancar_carla(brain_store, handoff_store, pending_store, focus_store)
    project_carla = resultado["project_id"]
    resolver_aprovacao_contextual("Aprovado", SESSION, pending_store, brain_store)  # cria ExecutionPlan READY_FOR_APPROVAL

    _monkeypatch_tools_para_store(monkeypatch, brain_store)
    resposta = eet.gerenciar_execucao("execute o plano", SESSION)

    assert project_carla in resposta
    brain_legado = brain_store.load(projeto_legado)
    assert brain_legado.execution_plan is None


# ---------------------------------------------------------------------------
# "Aprovado"/"Rejeito" NUNCA dependeram do foco -- já corretos, prova que o
# bug era exclusivo de comandos genéricos (execute/status/etc.)
# ---------------------------------------------------------------------------

def test_aprovado_resolve_pendencia_correta_mesmo_com_foco_no_projeto_errado(brain_store, handoff_store, pending_store, focus_store):
    projeto_legado = _projeto_legado_com_traffic_plan_aprovado(brain_store)
    resultado = _avancar_carla(brain_store, handoff_store, pending_store, focus_store)
    project_carla = resultado["project_id"]

    focus_store.set_focus(SESSION, projeto_legado)  # foco desviado DEPOIS de criar a pendência da Carla

    resposta = resolver_aprovacao_contextual("Aprovado", SESSION, pending_store, brain_store)
    assert project_carla in resposta

    brain_carla = brain_store.load(project_carla)
    brain_legado = brain_store.load(projeto_legado)
    assert brain_carla.business_plan.approval_status == "APPROVED"
    assert brain_legado.business_plan is None  # projeto legado nunca tocado


def test_rejeito_resolve_pendencia_correta_mesmo_com_foco_no_projeto_errado(brain_store, handoff_store, pending_store, focus_store):
    projeto_legado = _projeto_legado_com_traffic_plan_aprovado(brain_store)
    resultado = _avancar_carla(brain_store, handoff_store, pending_store, focus_store)
    project_carla = resultado["project_id"]
    focus_store.set_focus(SESSION, projeto_legado)

    resolver_aprovacao_contextual("Não gostei, quero outro.", SESSION, pending_store, brain_store)
    brain_carla = brain_store.load(project_carla)
    assert brain_carla.business_plan.approval_status == "REJECTED"


def test_sem_pendencia_informa_corretamente(brain_store, pending_store):
    resposta = resolver_aprovacao_contextual("Aprovado", SESSION, pending_store, brain_store)
    assert "não há uma aprovação pendente" in resposta.lower()


# ---------------------------------------------------------------------------
# "status"/consultas genéricas usam o foco correto após a correção
# ---------------------------------------------------------------------------

def test_status_generico_consulta_projeto_correto(monkeypatch, brain_store, handoff_store, pending_store, focus_store):
    projeto_legado = _projeto_legado_com_traffic_plan_aprovado(brain_store)
    focus_store.set_focus(SESSION, projeto_legado)
    resultado = _avancar_carla(brain_store, handoff_store, pending_store, focus_store)

    _monkeypatch_tools_para_store(monkeypatch, brain_store)
    resposta = mit.gerenciar_market_intelligence("inteligência de mercado", SESSION)
    assert resultado["project_id"] in resposta
    assert resultado["handoff_id"] in resposta


# ---------------------------------------------------------------------------
# Fail closed: sem foco nenhum + múltiplos projetos -> NUNCA escolhe sozinho
# ---------------------------------------------------------------------------

def test_sem_foco_e_multiplos_projetos_pede_selecao_explicita(monkeypatch, brain_store, handoff_store, pending_store, focus_store):
    _projeto_legado_com_traffic_plan_aprovado(brain_store, nome="Projeto A")
    _projeto_legado_com_traffic_plan_aprovado(brain_store, nome="Projeto B")
    outra_sessao = "telegram:999_sem_foco"

    _monkeypatch_tools_para_store(monkeypatch, brain_store)
    resposta = eet.gerenciar_execucao("execute o plano", outra_sessao)
    assert "não sei a qual projeto" in resposta.lower()

    # nenhum projeto novo foi criado, nenhum execution_plan foi gerado
    for brain in brain_store.list_all():
        assert brain.execution_plan is None


# ---------------------------------------------------------------------------
# Idempotência / restart -- contexto persiste, comando repetido não duplica
# ---------------------------------------------------------------------------

def test_restart_preserva_foco_da_carla(db_path, brain_store, handoff_store, pending_store, focus_store):
    resultado = _avancar_carla(brain_store, handoff_store, pending_store, focus_store)

    # Simula um restart: novas instâncias de store sobre o MESMO arquivo.
    backend2 = SQLiteMemory(db_path)
    pm2 = ProjectMemory(backend2)
    focus_store2 = UserFocusStore(pm2)
    assert focus_store2.get_focus(SESSION) == resultado["project_id"]
    backend2.close()


def test_comando_repetido_e_idempotente_nao_diverge_ids(brain_store, handoff_store, pending_store, focus_store):
    r1 = _avancar_carla(brain_store, handoff_store, pending_store, focus_store)
    r2 = bridge.avancar_a_partir_do_handoff(
        "ho_carla_teste", brain_store, handoff_store, pending_store, session=SESSION, focus_store=focus_store,
    )
    assert r1["project_id"] == r2["project_id"]
    assert r1["handoff_id"] == r2["handoff_id"] == "ho_carla_teste"
    assert focus_store.get_focus(SESSION) == r1["project_id"]
    assert len(brain_store.list_all()) == 1


def test_handoff_id_project_id_execution_plan_id_nunca_divergem(brain_store, handoff_store, pending_store, focus_store):
    resultado = _avancar_carla(brain_store, handoff_store, pending_store, focus_store)
    resolver_aprovacao_contextual("Aprovado", SESSION, pending_store, brain_store)

    brain = brain_store.load(resultado["project_id"])
    status = bridge.montar_status(resultado["handoff_id"], brain_store, handoff_store, pending_store, session=SESSION)

    assert status["project_id"] == brain.project_id == resultado["project_id"]
    assert status["handoff_id"] == brain.market_intelligence[-1].handoff_id == resultado["handoff_id"]
    assert status["execution_plan"]["id"] == brain.execution_plan.execution_id
