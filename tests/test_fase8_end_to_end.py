"""
Teste end-to-end da Fase 8, exatamente conforme o cenário pedido no
kickoff:

  Projeto: "Produto educacional sobre automação com IA"
  BusinessPlan: APPROVED
  Objetivo: "Preparar estratégia para lançamento."

  TASK 1 analisar BusinessPlan
  TASK 2 definir requisitos de aquisição (depende TASK 1)
  TASK 3 preparar handoff de ativos necessários (depende TASK 2)
  TASK 4 simular ação externa (depende TASK 3, requires_approval=True,
         external_action=True)

Valida: TASK 1/2/3 -> COMPLETED; TASK 4 não executa sem aprovação; após
aprovação em ambiente MOCK/DRY_RUN, TASK 4 conclui como SIMULATED/COMPLETED;
publicação real: NÃO; gasto: US$0. Inclui também o teste de restart
explicitamente exigido (criar plano, concluir task, persistir, simular
restart, recarregar, confirmar task concluída, continuar execução,
confirmar que a task anterior NÃO foi repetida).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.approval_router import resolver_aprovacao_contextual
from core.execution_engine import criar_execution_plan, executar_plano
from memory.layers import ProjectMemory
from memory.project_brain import BusinessPlan, PendingApprovalStore, ProductBlueprint, ProjectBrainStore
from storage import SQLiteMemory


def _projeto_automacao_ia(store):
    brain = store.create(name="Produto educacional sobre automação com IA", tipo="opportunity")
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id, recommended_product_type="curso",
        decision_status="APPROVED", target_audience="Profissionais que querem aprender automação com IA",
        market="educação online",
    )
    brain.business_plan = BusinessPlan(
        project_id=brain.project_id, approval_status="APPROVED",
        positioning="O curso mais prático de automação com IA para quem já trabalha",
        target_audience="Profissionais que querem aprender automação com IA",
        main_offer="Curso + comunidade de prática",
        acquisition_channels=["LinkedIn", "YouTube", "Instagram"],
        primary_channel="LinkedIn",
        required_assets=["Landing page com prova social e CTA claro", "5 vídeos de aula piloto"],
        kpis=["Taxa de conversão da lista de espera", "CAC por canal"],
        risks=["Mercado de cursos de IA está saturado"],
        assumptions=["Público tem interesse real em automação, não só curiosidade"],
    )
    store.save(brain)
    return brain


def test_cenario_end_to_end_completo(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_fase8_e2e.db")
    store = ProjectBrainStore(ProjectMemory(backend))
    pending = PendingApprovalStore(store.project_memory)
    try:
        brain = _projeto_automacao_ia(store)
        session = "telegram:e2e"

        # ---- criação do plano ----
        plan = criar_execution_plan(brain, objetivo="Preparar estratégia para lançamento.")
        assert plan.status == "READY_FOR_APPROVAL"
        assert len(plan.tasks) == 4
        t1, t2, t3, t4 = plan.tasks
        assert t2.dependencies == [t1.task_id]
        assert t3.dependencies == [t2.task_id]
        assert t4.dependencies == [t3.task_id]
        assert t4.requires_approval is True
        assert t4.external_action is True
        brain.execution_plan = plan
        store.save(brain)

        # ---- aprovação humana do PLANO ----
        pending.set_pending(session, brain.project_id, "EXECUTION_PLAN", "APPROVE")
        resposta_aprovacao_plano = resolver_aprovacao_contextual("Aprovado", session, pending, store)
        assert "Status: APPROVED" in resposta_aprovacao_plano
        brain = store.load(brain.project_id)
        assert brain.execution_plan.status == "APPROVED"

        # ---- execução ----
        plan = executar_plano(brain)
        store.save(brain)
        assert plan.tasks[0].status == "COMPLETED"
        assert plan.tasks[1].status == "COMPLETED"
        assert plan.tasks[2].status == "COMPLETED"
        assert plan.tasks[3].status == "READY"  # NAO executa sem aprovacao
        assert plan.tasks[3].approved is False

        # ---- aprovação humana da TASK 4 (identifica exatamente a task) ----
        pending.set_pending(session, brain.project_id, "EXECUTION_TASK", "APPROVE", task_id=plan.tasks[3].task_id)
        resposta_aprovacao_task = resolver_aprovacao_contextual("Aprovado", session, pending, store)
        assert plan.tasks[3].task_id in resposta_aprovacao_task
        assert plan.execution_id in resposta_aprovacao_task

        # ---- conclusão em MOCK/DRY_RUN ----
        brain = store.load(brain.project_id)
        plan = executar_plano(brain)
        store.save(brain)
        assert plan.tasks[3].status == "COMPLETED"
        assert plan.tasks[3].simulated is True
        assert plan.status == "COMPLETED"

        # ---- confirmações finais explícitas ----
        assert "SIMULADO" in plan.tasks[3].result or "DRY_RUN" in plan.tasks[3].result
        assert plan.tasks[3].actual_cost is None  # gasto: US$0 -- nenhum custo real registrado
    finally:
        backend.close()


def test_restart_test_explicito(tmp_path):
    """Passo a passo EXATAMENTE conforme pedido: criar ExecutionPlan,
    concluir pelo menos uma task, persistir, simular restart, carregar
    novamente, confirmar task concluída, continuar execução, confirmar
    que a task anterior NÃO foi repetida."""
    db_path = tmp_path / "test_fase8_restart.db"

    # 1. criar ExecutionPlan e concluir pelo menos uma task
    backend = SQLiteMemory(db_path)
    store = ProjectBrainStore(ProjectMemory(backend))
    brain = _projeto_automacao_ia(store)
    plan = criar_execution_plan(brain, objetivo="Preparar estratégia para lançamento.")
    plan.status = "APPROVED"
    brain.execution_plan = plan
    executar_plano(brain)  # completa T1, T2, T3
    assert plan.tasks[0].status == "COMPLETED"
    resultado_t1_antes = plan.tasks[0].result
    updated_at_t1_antes = plan.tasks[0].updated_at

    # 2. persistir
    store.save(brain)
    backend.close()

    # 3. simular restart (novo processo, nova conexão)
    novo_backend = SQLiteMemory(db_path)
    novo_store = ProjectBrainStore(ProjectMemory(novo_backend))
    try:
        # 4. carregar novamente
        recarregado = novo_store.load(brain.project_id)

        # 5. confirmar task concluída
        assert recarregado.execution_plan.tasks[0].status == "COMPLETED"
        assert recarregado.execution_plan.tasks[0].result == resultado_t1_antes

        # 6. continuar execução
        plan_continuado = executar_plano(recarregado)
        novo_store.save(recarregado)

        # 7. confirmar que a task anterior NAO foi repetida
        assert plan_continuado.tasks[0].updated_at == updated_at_t1_antes
        assert plan_continuado.tasks[0].result == resultado_t1_antes
        # e que o restante do plano continuou de onde parou (T2/T3 completas,
        # T4 pronta aguardando aprovacao -- nunca recriada do zero)
        assert plan_continuado.tasks[1].status == "COMPLETED"
        assert plan_continuado.tasks[2].status == "COMPLETED"
        assert plan_continuado.tasks[3].status == "READY"
    finally:
        novo_backend.close()


def test_confirmacao_publicacao_real_nao_e_gasto_zero(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_fase8_seguranca.db")
    store = ProjectBrainStore(ProjectMemory(backend))
    pending = PendingApprovalStore(store.project_memory)
    try:
        brain = _projeto_automacao_ia(store)
        plan = criar_execution_plan(brain, objetivo="Preparar estratégia para lançamento.")
        plan.status = "APPROVED"
        brain.execution_plan = plan
        executar_plano(brain)
        store.save(brain)

        pending.set_pending("telegram:1", brain.project_id, "EXECUTION_TASK", "APPROVE", task_id=plan.tasks[3].task_id)
        resolver_aprovacao_contextual("Aprovado", "telegram:1", pending, store)
        brain = store.load(brain.project_id)
        plan = executar_plano(brain)
        store.save(brain)

        # PUBLICACAO REAL: NAO
        assert plan.tasks[3].simulated is True
        assert "publicad" not in (plan.tasks[3].result or "").lower() or "nenhuma" in (plan.tasks[3].result or "").lower()
        # GASTO: US$0
        for t in plan.tasks:
            assert t.actual_cost is None
    finally:
        backend.close()
