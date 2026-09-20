"""
Testes da Fase 8: Execution Engine (lógica pura, sem Telegram/orchestrator).

Nada aqui bate em nenhuma API externa nem gasta OpenRouter de verdade --
nenhuma chamada de LLM acontece em nenhum caminho deste motor.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from core.execution_engine import (
    avaliar_prontidao_execucao,
    cancelar_plano,
    criar_execution_plan,
    detectar_ciclo,
    executar_plano,
    gerar_execution_handoff,
    pausar_plano,
    retomar_plano,
)
from memory.layers import ProjectMemory
from memory.project_brain import BusinessPlan, ProductBlueprint, ProjectBrainStore, Task
from storage import SQLiteMemory


@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_execution_engine.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def _brain_com_business_plan_aprovado(store, **overrides):
    brain = store.create(name="Automação com IA", tipo="opportunity")
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id, recommended_product_type="curso",
        decision_status="APPROVED", target_audience="Profissionais",
    )
    defaults = dict(
        project_id=brain.project_id, approval_status="APPROVED",
        positioning="O mais prático do mercado", target_audience="Profissionais",
        main_offer="Curso completo", acquisition_channels=["LinkedIn", "YouTube"],
        primary_channel="LinkedIn", required_assets=["Landing page", "Vídeo de vendas"],
    )
    defaults.update(overrides)
    brain.business_plan = BusinessPlan(**defaults)
    store.save(brain)
    return brain


# ---------------------------------------------------------------------------
# GATE -- precisa de pelo menos um artefato aprovado
# ---------------------------------------------------------------------------

def test_sem_nenhum_artefato_aprovado_gera_lacuna(brain_store):
    brain = brain_store.create(name="x", tipo="opportunity")
    lacunas = avaliar_prontidao_execucao(brain)
    assert lacunas


def test_com_business_plan_aprovado_nao_gera_lacuna(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    assert avaliar_prontidao_execucao(brain) == []


def test_tipo_de_origem_explicito_mas_nao_aprovado_gera_lacuna(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    lacunas = avaliar_prontidao_execucao(brain, source_artifact_type="TRAFFIC_PLAN")
    assert lacunas


def test_criar_plano_sem_artefato_aprovado_devolve_plano_bloqueado(brain_store):
    brain = brain_store.create(name="x", tipo="opportunity")
    plan = criar_execution_plan(brain, objetivo="lançar")
    assert plan.status == "BLOCKED"
    assert plan.tasks[0].status == "BLOCKED"


# ---------------------------------------------------------------------------
# Criacao do plano -- 4 tasks padrao, sem ciclo, READY_FOR_APPROVAL
# ---------------------------------------------------------------------------

def test_criar_plano_gera_4_tasks_com_dependencias_corretas(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="Preparar estratégia para lançamento.")
    assert plan.status == "READY_FOR_APPROVAL"
    assert plan.source_artifact_type == "BUSINESS_PLAN"
    assert len(plan.tasks) == 4
    assert plan.tasks[0].dependencies == []
    assert plan.tasks[1].dependencies == [plan.tasks[0].task_id]
    assert plan.tasks[2].dependencies == [plan.tasks[1].task_id]
    assert plan.tasks[3].dependencies == [plan.tasks[2].task_id]
    assert plan.tasks[3].requires_approval is True
    assert plan.tasks[3].external_action is True


def test_project_id_preservado(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    assert plan.project_id == brain.project_id


def test_source_artifact_preservado(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    assert plan.source_artifact_type == "BUSINESS_PLAN"
    assert plan.source_artifact_id is not None


def test_plano_gerado_nunca_tem_ciclo(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    assert detectar_ciclo(plan.tasks) is False


def test_esta_aprovado_so_true_para_approved_exato():
    from memory.project_brain import ExecutionPlan
    plan = ExecutionPlan(project_id="p1", status="READY_FOR_APPROVAL")
    assert plan.esta_aprovado() is False
    plan.status = "APPROVED"
    assert plan.esta_aprovado() is True


# ---------------------------------------------------------------------------
# Deteccao de ciclo (requisito explícito)
# ---------------------------------------------------------------------------

def test_detectar_ciclo_direto():
    a = Task(task_id="a", dependencies=["b"])
    b = Task(task_id="b", dependencies=["a"])
    assert detectar_ciclo([a, b]) is True


def test_detectar_ciclo_indireto():
    p = Task(task_id="p", dependencies=["q"])
    q = Task(task_id="q", dependencies=["r"])
    r = Task(task_id="r", dependencies=["p"])
    assert detectar_ciclo([p, q, r]) is True


def test_sem_ciclo_grafo_linear():
    x = Task(task_id="x")
    y = Task(task_id="y", dependencies=["x"])
    assert detectar_ciclo([x, y]) is False


def test_dependencia_para_task_inexistente_e_tratada_como_invalida():
    a = Task(task_id="a", dependencies=["fantasma"])
    assert detectar_ciclo([a]) is True


# ---------------------------------------------------------------------------
# Execucao respeitando dependencias -- tarefa dependente nunca roda cedo
# ---------------------------------------------------------------------------

def test_execucao_respeita_ordem_de_dependencia(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan

    plan = executar_plano(brain)
    assert plan.tasks[0].status == "COMPLETED"
    assert plan.tasks[1].status == "COMPLETED"
    assert plan.tasks[2].status == "COMPLETED"
    # task 4 exige aprovacao -- nunca roda sozinha
    assert plan.tasks[3].status == "READY"
    assert plan.tasks[3].approved is False
    assert plan.status == "RUNNING"  # ainda nao completo -- falta a task 4


def test_plano_nao_aprovado_nao_processa_nenhuma_task(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    brain.execution_plan = plan  # READY_FOR_APPROVAL -- nao aprovado ainda

    resultado = executar_plano(brain)
    assert all(t.status == "PENDING" for t in resultado.tasks)
    assert resultado.status == "READY_FOR_APPROVAL"


def test_task_4_so_completa_apos_aprovacao_explicita(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)

    plan.tasks[3].approved = True
    plan = executar_plano(brain)
    assert plan.tasks[3].status == "COMPLETED"
    assert plan.tasks[3].simulated is True
    assert plan.status == "COMPLETED"


# ---------------------------------------------------------------------------
# task COMPLETED nunca reexecuta -- idempotencia
# ---------------------------------------------------------------------------

def test_task_completed_nao_executa_novamente(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)

    resultado_1 = plan.tasks[0].result
    updated_at_1 = plan.tasks[0].updated_at

    # chama de novo -- task 1 ja COMPLETED, nao deve mudar
    executar_plano(brain)
    assert plan.tasks[0].result == resultado_1
    assert plan.tasks[0].updated_at == updated_at_1


def test_idempotencia_apos_restart_real(tmp_path):
    db_path = tmp_path / "test_execution_idempotencia.db"
    backend = SQLiteMemory(db_path)
    store = ProjectBrainStore(ProjectMemory(backend))
    brain = _brain_com_business_plan_aprovado(store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)
    store.save(brain)
    backend.close()

    novo_backend = SQLiteMemory(db_path)
    novo_store = ProjectBrainStore(ProjectMemory(novo_backend))
    try:
        recarregado = novo_store.load(brain.project_id)
        assert recarregado.execution_plan.tasks[0].status == "COMPLETED"
        resultado_antes = recarregado.execution_plan.tasks[0].result

        plan_pos_restart = executar_plano(recarregado)
        assert plan_pos_restart.tasks[0].status == "COMPLETED"
        assert plan_pos_restart.tasks[0].result == resultado_antes  # nunca repetiu
        assert plan_pos_restart.tasks[3].status == "READY"  # continua exatamente onde parou
    finally:
        novo_backend.close()


# ---------------------------------------------------------------------------
# Falha bloqueia dependentes; retry_count; sem loop infinito
# ---------------------------------------------------------------------------

def test_falha_de_task_bloqueia_dependentes(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store, acquisition_channels=[], primary_channel=None)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan

    plan = executar_plano(brain)
    assert plan.tasks[0].status == "COMPLETED"
    assert plan.tasks[1].status == "BLOCKED"  # sem canal de aquisicao -- nunca inventa
    assert plan.tasks[2].status == "BLOCKED"  # depende da task 2
    assert plan.tasks[3].status == "BLOCKED"  # depende da task 3


def test_retry_count_incrementa_em_falha_de_infraestrutura(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan

    def _agente_que_falha(agent, texto, session):
        raise RuntimeError("falha simulada de infraestrutura")

    # forca a task 2 a usar o agent_invoker (remove o executor deterministico)
    plan.tasks[1].title = "Tarefa customizada sem executor padrão"
    plan.tasks[1].max_retries = 2

    plan = executar_plano(brain, agent_invoker=_agente_que_falha)
    assert plan.tasks[1].retry_count == 3  # tentativa inicial + 2 retries
    assert plan.tasks[1].status == "FAILED"


def test_agent_invoker_e_usado_para_tasks_fora_do_template_padrao_e_persiste_resultado(brain_store):
    """Prova a integracao real com o AgentOrchestrator (via um invoker
    fake aqui -- a integracao real e feita pelas Tools, ver
    `tools/execution_engine_tools.py`): uma task SEM executor deterministico
    embutido usa `agent_invoker(agent, objective, session)`, e o resultado
    devolvido e persistido em `task.result`."""
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    plan.tasks[1].title = "Tarefa customizada via agente especialista"

    chamadas = []

    def _invoker(agent, texto, session):
        chamadas.append((agent, texto, session))
        return "Resultado real devolvido pelo agente especialista."

    resultado = executar_plano(brain, agent_invoker=_invoker)
    assert len(chamadas) == 1
    assert chamadas[0][0] == plan.tasks[1].agent
    assert resultado.tasks[1].status == "COMPLETED"
    assert resultado.tasks[1].result == "Resultado real devolvido pelo agente especialista."


def test_contexto_da_task_vem_de_input_refs_persistidos_nao_so_do_texto(brain_store):
    """O contrato de entrada de uma task usa `input_refs` (referencias a
    artefatos JA PERSISTIDOS no Project Brain) -- nunca depende apenas do
    historico textual do Telegram."""
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    assert plan.tasks[0].input_refs  # referencia ao artefato de origem, nao a uma mensagem
    assert plan.source_artifact_id in plan.tasks[0].input_refs


def test_nao_existe_retry_infinito(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    plan.tasks[1].title = "Tarefa customizada sem executor padrão"
    plan.tasks[1].max_retries = 1

    chamadas = []

    def _agente_que_sempre_falha(agent, texto, session):
        chamadas.append(1)
        raise RuntimeError("sempre falha")

    executar_plano(brain, agent_invoker=_agente_que_sempre_falha)
    # 1 tentativa inicial + 1 retry = 2 chamadas, nunca mais que isso
    assert len(chamadas) == 2
    assert plan.tasks[1].status == "FAILED"


# ---------------------------------------------------------------------------
# PAUSE / RESUME / CANCEL
# ---------------------------------------------------------------------------

def test_pause_impede_novas_tasks(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)  # roda T1-T3, T4 fica READY aguardando aprovacao

    ok, _ = pausar_plano(plan)
    assert ok is True
    assert plan.status == "PAUSED"

    plan.tasks[3].approved = True  # mesmo aprovada, nao deve rodar em PAUSED
    resultado = executar_plano(brain)
    assert resultado.tasks[3].status != "COMPLETED"
    assert resultado.status == "PAUSED"


def test_resume_continua_corretamente(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)
    pausar_plano(plan)

    ok, _ = retomar_plano(plan)
    assert ok is True
    assert plan.status == "RUNNING"

    plan.tasks[3].approved = True
    plan = executar_plano(brain)
    assert plan.tasks[3].status == "COMPLETED"
    assert plan.status == "COMPLETED"


def test_cancel_impede_novas_tasks_mas_preserva_completadas(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)  # T1-T3 COMPLETED, T4 READY

    ok, _ = cancelar_plano(plan)
    assert ok is True
    assert plan.status == "CANCELLED"
    assert plan.tasks[0].status == "COMPLETED"  # nunca desfeita
    assert plan.tasks[1].status == "COMPLETED"
    assert plan.tasks[2].status == "COMPLETED"
    assert plan.tasks[3].status == "CANCELLED"

    plan.tasks[3].approved = True
    resultado = executar_plano(brain)  # nao deveria processar mais nada
    assert resultado.status == "CANCELLED"


def test_cancel_de_plano_ja_encerrado_falha(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "COMPLETED"
    ok, mensagem = cancelar_plano(plan)
    assert ok is False


# ---------------------------------------------------------------------------
# Anti-hallucination -- nunca campo pra metrica/URL/venda inventada
# ---------------------------------------------------------------------------

def test_task_e_execution_plan_nao_tem_campo_para_dado_inventado():
    from dataclasses import fields
    from memory.project_brain import ExecutionPlan
    nomes = {f.name for f in fields(Task)} | {f.name for f in fields(ExecutionPlan)}
    proibidos = {"vendas", "receita", "revenue", "cpa", "roas", "conversao",
                 "url_publicada", "published_url", "external_id_real"}
    assert not (nomes & proibidos)


# ---------------------------------------------------------------------------
# Handoff estruturado (Fase 9)
# ---------------------------------------------------------------------------

def test_handoff_none_sem_plano():
    from memory.project_brain import Identidade, ProjectBrain
    brain = ProjectBrain(identidade=Identidade(project_id="p1", name="x"))
    assert gerar_execution_handoff(brain) is None


def test_handoff_estruturado_apos_execucao_parcial(brain_store):
    brain = _brain_com_business_plan_aprovado(brain_store)
    plan = criar_execution_plan(brain, objetivo="lançar")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)

    handoff = gerar_execution_handoff(brain)
    assert handoff["project_id"] == brain.project_id
    assert handoff["execution_id"] == plan.execution_id
    assert len(handoff["tasks"]) == 4
    assert handoff["pending_approvals"] == [plan.tasks[3].task_id]
    assert handoff["statuses"]["completed_tasks"] == 3
