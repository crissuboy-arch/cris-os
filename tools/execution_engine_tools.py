"""
Ferramentas do agente Execution Engine (Fase 8).

Fluxo: BusinessPlan/TrafficPlan/CampaignSpec/ProductBlueprint APROVADO ->
EXECUTION ENGINE -> ExecutionPlan + Tasks -> AgentOrchestrator (quando uma
task exigir um agente especialista) -> Project Brain -> resposta.

GATE MAIS IMPORTANTE: `gerenciar_execucao` chama `avaliar_prontidao_execucao`
ANTES de criar qualquer plano -- sem nenhum artefato aprovado, a resposta é
DETERMINÍSTICA (nenhum LLM, nenhum ExecutionPlan criado).

Reaproveita o MESMO foco por sessão (`tools/opportunity_tools.py`) e o
Approval Router central (`core/approval_router.py`, Fases 6/7) -- nenhum
sistema de aprovação novo, nenhuma memória paralela.
"""

from __future__ import annotations

import logging

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
from memory.project_brain import ExecutionPlan, ProjectBrain, Task
from tools.base import Tool
from tools.opportunity_tools import get_foco_atual, get_project_brain_store

logger = logging.getLogger(__name__)

_FRASES_STATUS = (
    "qual o andamento deste projeto", "andamento deste projeto",
    "status da execução", "status da execucao", "como está a execução",
    "como esta a execucao", "status do plano de execução",
)
_FRASES_EXECUTAR = (
    "execute o plano aprovado", "execute o plano", "execute a execução",
    "inicie a execução", "inicie a execucao", "rode o plano aprovado",
    "prepare a execução deste projeto", "prepare a execucao deste projeto",
)
_FRASES_PAUSE = ("pause a execução", "pause a execucao", "pausar a execução", "pausar a execucao")
_FRASES_RESUME = ("continue a execução", "continue a execucao", "retome a execução", "retomar a execução", "resume a execução")
_FRASES_CANCEL = ("cancele a execução", "cancele a execucao", "cancelar a execução", "cancelar execução")
_FRASES_HANDOFF = ("execution handoff", "handoff da execução", "handoff de execução")


def _get_pending_approval_store():
    """Mesmo princípio de `tools/paid_traffic_tools.py`/`tools/campaign_executor_tools.py`/
    `tools/business_builder_tools.py` (Fases 6/7): constrói o
    `PendingApprovalStore` a partir do `get_project_brain_store()` DESTE
    módulo (monkeypatchável em teste), nunca de um singleton separado --
    evita usar o banco de produção real durante testes."""
    from memory.project_brain import PendingApprovalStore

    return PendingApprovalStore(get_project_brain_store().project_memory)


def _sincronizar_pendencia_plano(session: str, project_id: str, plan: ExecutionPlan) -> None:
    if plan.status == "READY_FOR_APPROVAL":
        _get_pending_approval_store().set_pending(session, project_id, "EXECUTION_PLAN", "APPROVE")


def _sincronizar_pendencia_task(session: str, project_id: str, task: Task) -> None:
    if task.requires_approval and not task.approved and task.status in {"PENDING", "READY"}:
        _get_pending_approval_store().set_pending(
            session, project_id, "EXECUTION_TASK", "APPROVE", task_id=task.task_id,
        )


def _sincronizar_producao(brain: ProjectBrain) -> None:
    """Integração aditiva (ponte Cris OS -> executores especializados):
    depois de processar o plano, materializa `ProductionWorkOrder`s
    idempotentes a partir de qualquer task de "handoff de ativos" já
    concluída -- ver `core/production_orders.py`. NUNCA despacha nada
    externo, NUNCA executa a Task 4 -- só cria/reaproveita as ordens
    internas rastreáveis."""
    from core.production_orders import sincronizar_producao_do_plano

    sincronizar_producao_do_plano(brain)


def _contains_any(texto: str, frases: tuple) -> bool:
    return any(f in texto for f in frases)


def _resolver_projeto(session: str) -> ProjectBrain | str:
    foco = get_foco_atual(session)
    if not foco:
        return (
            "Não sei a qual projeto você se refere -- investigue uma "
            "oportunidade e aprove um formato de produto primeiro."
        )
    brain = get_project_brain_store().load(foco)
    if not brain:
        return "Não consegui recuperar o projeto em foco."
    return brain


_MARCADOR_STATUS = {
    "PENDING": "⏳ pendente", "READY": "🟡 pronta (aguardando aprovação)",
    "RUNNING": "🔄 em execução", "BLOCKED": "⛔ bloqueada",
    "COMPLETED": "✅ concluída", "FAILED": "❌ falhou",
    "SKIPPED": "⏭️ pulada", "CANCELLED": "🚫 cancelada",
}


def _formatar_status(brain: ProjectBrain, plan: ExecutionPlan) -> str:
    resumo = plan.resumo()
    linhas = [
        f"EXECUÇÃO — projeto {brain.project_id}",
        "",
        f"Execução: {plan.execution_id} | Versão: {plan.version} | Status: {plan.status}",
    ]
    if plan.objective:
        linhas.append(f"Objetivo: {plan.objective}")
    linhas.append("")
    linhas.append(
        f"Concluídas: {resumo['completed_tasks']}/{resumo['total_tasks']} | "
        f"Executando: {resumo['running_tasks']} | "
        f"Pendentes: {resumo['pending_tasks']} | "
        f"Bloqueadas: {resumo['blocked_tasks']} | "
        f"Falhas: {resumo['failed_tasks']}",
    )
    linhas.append("")
    linhas.append("TAREFAS")
    for t in plan.tasks:
        marcador = _MARCADOR_STATUS.get(t.status, t.status)
        linhas.append(f"  {marcador} — {t.title} [{t.task_id}]")
        if t.requires_approval and not t.approved and t.status in {"PENDING", "READY"}:
            linhas.append("      aguardando aprovação humana explícita")
        if t.error:
            linhas.append(f"      erro: {t.error}")

    proxima = next((t for t in plan.tasks if t.requires_approval and not t.approved and t.status in {"PENDING", "READY"}), None)
    linhas.append("")
    if proxima:
        linhas.append(f'Próxima ação: aguardando aprovação da tarefa "{proxima.title}".')
    elif plan.status == "READY_FOR_APPROVAL":
        linhas.append('Próxima ação: aguardando aprovação do plano de execução (responda "Aprovado").')
    elif plan.status == "COMPLETED":
        linhas.append("Próxima ação: nenhuma -- execução concluída.")
    elif plan.status == "PAUSED":
        linhas.append('Próxima ação: peça "continue a execução" para retomar.')
    elif plan.status == "CANCELLED":
        linhas.append("Próxima ação: nenhuma -- execução cancelada.")
    else:
        linhas.append('Próxima ação: peça "execute o plano" para continuar.')

    linhas.append("")
    linhas.append("Nenhuma ação externa real foi executada. Nenhum valor foi gasto.")
    return "\n".join(linhas)


def _formatar_bloqueio_criacao(lacunas: list[str], brain: ProjectBrain) -> str:
    linhas = ["Ainda não é possível criar um plano de execução para este projeto:", ""]
    for lacuna in lacunas:
        linhas.append(f"  - {lacuna}")
    linhas.append("")
    linhas.append(f"Projeto: {brain.project_id}")
    return "\n".join(linhas)


def _formatar_handoff(handoff: dict) -> str:
    linhas = [
        "📦 EXECUTION HANDOFF (contrato de dados -- nenhuma ação executada)",
        "",
        f"project_id: {handoff['project_id']}",
        f"execution_id: {handoff['execution_id']}",
        f"objective: {handoff['objective']}",
    ]
    if handoff["source_artifacts"]:
        origem = handoff["source_artifacts"][0]
        linhas.append(f"source_artifact: {origem['type']} ({origem['id']})")
    linhas.append(f"statuses: {handoff['statuses']}")
    if handoff["outputs"]:
        linhas.append("outputs: " + ", ".join(handoff["outputs"]))
    if handoff["pending_approvals"]:
        linhas.append("pending_approvals: " + ", ".join(handoff["pending_approvals"]))
    if handoff["blockers"]:
        linhas.append(f"blockers: {handoff['blockers']}")
    if handoff["next_actions"]:
        linhas.append("next_actions: " + "; ".join(handoff["next_actions"]))
    return "\n".join(linhas)


def gerenciar_execucao(entrada: str, session: str = "") -> str:
    """Ponto de entrada único da Tool (criar / executar / status / pausar /
    retomar / cancelar / handoff do plano de execução)."""
    texto_original = (entrada or "").strip()
    texto = texto_original.lower()
    if not texto:
        return ""

    brain = _resolver_projeto(session)
    if isinstance(brain, str):
        return brain

    plan = brain.execution_plan
    store = get_project_brain_store()

    if _contains_any(texto, _FRASES_HANDOFF):
        handoff = gerar_execution_handoff(brain)
        if not handoff:
            return f"Ainda não há um plano de execução para este projeto.\n\nProjeto: {brain.project_id}"
        return _formatar_handoff(handoff)

    if _contains_any(texto, _FRASES_STATUS):
        if not plan:
            return f"Ainda não há um plano de execução para este projeto.\n\nProjeto: {brain.project_id}"
        return _formatar_status(brain, plan)

    if _contains_any(texto, _FRASES_PAUSE):
        if not plan:
            return f"Ainda não há um plano de execução para este projeto.\n\nProjeto: {brain.project_id}"
        ok, mensagem = pausar_plano(plan)
        if ok:
            brain.registrar_run("execution_engine", "Execução pausada")
            store.save(brain)
        return mensagem

    if _contains_any(texto, _FRASES_CANCEL):
        if not plan:
            return f"Ainda não há um plano de execução para este projeto.\n\nProjeto: {brain.project_id}"
        ok, mensagem = cancelar_plano(plan)
        if ok:
            brain.registrar_run("execution_engine", "Execução cancelada")
            store.save(brain)
        return mensagem

    if _contains_any(texto, _FRASES_RESUME):
        if not plan:
            return f"Ainda não há um plano de execução para este projeto.\n\nProjeto: {brain.project_id}"
        ok, mensagem = retomar_plano(plan)
        if ok:
            plan = executar_plano(brain)
            brain.registrar_run("execution_engine", f"Execução retomada (status {plan.status})")
            _sincronizar_producao(brain)
            store.save(brain)
            for t in plan.tasks:
                _sincronizar_pendencia_task(session, brain.project_id, t)
            return _formatar_status(brain, plan)
        return mensagem

    # Default: CREATE_OR_RUN ("execute o plano aprovado deste projeto" e
    # qualquer outra mensagem que chegue ate aqui, ja roteada pro agente).
    if not plan:
        lacunas = avaliar_prontidao_execucao(brain)
        if lacunas:
            return _formatar_bloqueio_criacao(lacunas, brain)
        novo_plan = criar_execution_plan(brain, objetivo=texto_original)
        if detectar_ciclo(novo_plan.tasks):
            # Nunca deveria acontecer com o template padrao (sem ciclos por
            # construcao), mas o plano e REJEITADO antes de persistir se,
            # por qualquer motivo futuro, uma dependencia circular existir.
            return (
                "O plano de execução gerado contém uma dependência circular "
                "entre tarefas e foi rejeitado antes de ser salvo."
            )
        brain.execution_plan = novo_plan
        brain.registrar_run("execution_engine", f"Criou plano de execução (status {novo_plan.status})")
        store.save(brain)
        _sincronizar_pendencia_plano(session, brain.project_id, novo_plan)
        return _formatar_status(brain, novo_plan)

    if plan.status == "READY_FOR_APPROVAL":
        _sincronizar_pendencia_plano(session, brain.project_id, plan)
        return _formatar_status(brain, plan)

    if plan.esta_liberado_para_rodar():
        plan = executar_plano(brain)
        brain.registrar_run("execution_engine", f"Processou plano de execução (status {plan.status})")
        _sincronizar_producao(brain)
        store.save(brain)
        for t in plan.tasks:
            _sincronizar_pendencia_task(session, brain.project_id, t)
        return _formatar_status(brain, plan)

    # PAUSED/CANCELLED/COMPLETED/FAILED/BLOCKED -- so mostra status, nunca
    # tenta rodar de novo as cegas.
    return _formatar_status(brain, plan)


def get_tools() -> list[Tool]:
    return [
        Tool(
            "execution_engine",
            "Transforma um artefato já aprovado em um plano de execução "
            "com tarefas dependentes, sem executar nenhuma ação externa real",
            [
                "execução", "execucao", "plano de execução", "plano de execucao",
                "execute o plano", "execute a execução",
                "andamento", "andamento do projeto",
                "pause a execução", "continue a execução", "cancele a execução",
                "execution handoff", "handoff da execução",
                # continuacao (aprovacao/rejeicao) -- superset do Approval Gate.
                "aprovado", "aprovada", "aprovo", "autorizado", "autorizo",
                "confirmado", "confirmo", "rejeitado", "rejeitada", "rejeito",
            ],
            gerenciar_execucao,
        ),
    ]
