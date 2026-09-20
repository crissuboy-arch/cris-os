"""
Approval Router (Fase 6 -- correção estrutural de bug real).

BUG CORRIGIDO: uma aprovação curta ("Aprovado", "Sim, aprovo") não tinha
como saber A QUAL artefato (TrafficPlan? CampaignSpec?) ela se referia --
`AgentOrchestrator` não tinha nenhuma interceptação determinística pra
"Aprovado" sozinho fora do mecanismo de continuidade do Product Architect
(baseado em `last_agents`, em memória, não persistido), então a mensagem
caía no assistente genérico.

Fluxo: Orchestrator (ANTES de escolher agente) -> este módulo ->
`PendingApprovalStore` (contexto persistido: qual artefato está pendente,
POR sessão) + `ProjectBrainStore` -> aplica a aprovação/rejeição SOMENTE no
artefato pendente correspondente -> persiste -> limpa a pendência
consumida -> devolve a resposta final.

NUNCA aprova por adivinhação: sem pendência inequívoca, ou se o estado do
artefato mudou desde que a pendência foi registrada, devolve uma mensagem
clara em vez de aplicar qualquer coisa às cegas.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.approval_gate import eh_aprovacao, eh_rejeicao


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()

# Escopo original (Fase 6): TrafficPlan/CampaignSpec foram os dois artefatos
# do bug real que motivou este router -- Product Architect (Fase 3) continua
# usando seu próprio mecanismo de continuidade, já funcional, sem alteração
# (ver `agents/orchestrator.py:_resolver_aprovacao_contextual`, que
# deliberadamente NÃO intercepta quando o último agente foi o
# `product_architect` e a mensagem bate no padrão de continuidade dele).
#
# BUSINESS_PLAN (Fase 7) é o primeiro artefato NOVO a nascer já usando este
# gate central -- diferente de Paid Traffic Architect/Campaign Executor
# (que também mantêm um `_aprovar`/`_rejeitar` local próprio por
# compatibilidade com chamadas diretas em testes), o Business Builder NÃO
# ganhou um mecanismo de aprovação próprio: a ÚNICA forma de aprovar/
# rejeitar um BusinessPlan é via este router (pedido explícito da Fase 7:
# "Reutilizar o Approval Router central... NÃO criar outro sistema de
# aprovação").
_ARTEFATOS = {
    "TRAFFIC_PLAN": {
        "campo": "traffic_plan",
        "campo_status": "status",
        "estado_pronto": "READY_FOR_APPROVAL",
        "estado_rejeitado": "REJECTED",
        "nome_legivel": "plano de tráfego",
    },
    "CAMPAIGN_SPEC": {
        "campo": "campaign_spec",
        "campo_status": "status",
        "estado_pronto": "READY_FOR_APPROVAL",
        # CampaignSpec nao tem estado REJECTED no vocabulario (Fase 6) --
        # volta para NOT_STARTED (ver `memory/project_brain.py:CAMPAIGN_SPEC_ESTADOS_VALIDOS`).
        "estado_rejeitado": "NOT_STARTED",
        "nome_legivel": "especificação de campanha",
    },
    "BUSINESS_PLAN": {
        "campo": "business_plan",
        # BusinessPlan usa `approval_status`, NAO `status` (diferente de
        # TrafficPlan/CampaignSpec) -- por isso o nome do campo de status e
        # parametrizado por artefato, nunca hardcoded como `.status`.
        "campo_status": "approval_status",
        "estado_pronto": "READY_FOR_APPROVAL",
        "estado_rejeitado": "REJECTED",
        "nome_legivel": "plano de negócio",
    },
    "EXECUTION_PLAN": {
        "campo": "execution_plan",
        "campo_status": "status",
        "estado_pronto": "READY_FOR_APPROVAL",
        "estado_rejeitado": "CANCELLED",
        "nome_legivel": "plano de execução",
    },
}

# EXECUTION_TASK (Fase 8) e um caso ESPECIAL, NAO cabe no dicionario
# `_ARTEFATOS` acima: uma Task nao e um atributo direto do ProjectBrain --
# ela vive dentro de uma LISTA (`brain.execution_plan.tasks`), entao
# precisa ser localizada por `task_id`, nao por `getattr(brain, campo)`.
# Isso NAO e um segundo Approval Router -- e a MESMA funcao
# `resolver_aprovacao_contextual`, com um branch a mais para o UNICO
# artefato desta fase que e estruturalmente aninhado (pedido explicito da
# Fase 8: "identificar exatamente project_id, execution_id, task_id").

_SEM_PENDENCIA = (
    "Não há uma aprovação pendente inequívoca neste momento -- peça a "
    "criação/revisão do item que você quer aprovar primeiro."
)


def eh_mensagem_de_aprovacao_ou_rejeicao(texto: str) -> bool:
    return eh_aprovacao(texto) or eh_rejeicao(texto)


def resolver_aprovacao_contextual(texto: str, session: str, pending_store, brain_store) -> str | None:
    """
    Devolve a resposta final (string) se `texto` for uma aprovação/rejeição
    -- devolve `None` se `texto` não parecer uma aprovação/rejeição (nesse
    caso, quem chama segue o fluxo normal de seleção de agente).
    """
    if not eh_mensagem_de_aprovacao_ou_rejeicao(texto):
        return None

    pendente = pending_store.get_pending(session)
    if not pendente:
        return _SEM_PENDENCIA

    artefato_tipo = pendente.get("artifact_type")

    if artefato_tipo == "EXECUTION_TASK":
        return _resolver_aprovacao_task(texto, pendente, pending_store, brain_store, session)

    project_id = pendente.get("project_id")
    info = _ARTEFATOS.get(artefato_tipo)
    if not info or not project_id:
        # Pendencia corrompida/desconhecida -- nunca aplica as cegas.
        pending_store.clear_pending(session)
        return _SEM_PENDENCIA

    brain = brain_store.load(project_id)
    if not brain:
        pending_store.clear_pending(session)
        return "Não consegui recuperar o projeto da aprovação pendente."

    artefato = getattr(brain, info["campo"], None)
    campo_status = info["campo_status"]
    status_atual = getattr(artefato, campo_status, None) if artefato else None
    if not artefato or status_atual != info["estado_pronto"]:
        # O estado ja mudou desde que a pendencia foi registrada (ex.: ja
        # foi aprovado/rejeitado por outra via) -- nunca aplica as cegas.
        pending_store.clear_pending(session)
        return (
            f"Essa aprovação pendente não é mais válida (o {info['nome_legivel']} "
            f"não está mais aguardando aprovação -- status atual: "
            f"{status_atual if artefato else 'inexistente'})."
        )

    if eh_rejeicao(texto):
        setattr(artefato, campo_status, info["estado_rejeitado"])
        brain.registrar_aprovacao(f"{artefato_tipo}_REJECTED")
        brain_store.save(brain)
        pending_store.clear_pending(session)
        return f"Entendido, {info['nome_legivel']} rejeitado(a).\n\nProjeto: {project_id}"

    setattr(artefato, campo_status, "APPROVED")
    brain.registrar_aprovacao(f"{artefato_tipo}_APPROVED")
    brain_store.save(brain)
    pending_store.clear_pending(session)

    if artefato_tipo == "TRAFFIC_PLAN":
        return (
            "Plano de tráfego aprovado.\n\n"
            f"Projeto: {project_id}\n"
            "Status: APPROVED\n"
            "Nenhuma campanha foi criada ou publicada."
        )
    if artefato_tipo == "CAMPAIGN_SPEC":
        return (
            "✅ Especificação de campanha aprovada -- aprovada como "
            "ESPECIFICAÇÃO, não como execução.\n\n"
            "Nenhuma conta de anúncio foi conectada, nenhuma campanha foi "
            "publicada e nenhum valor foi gasto.\n\n"
            f"Projeto: {project_id} | Status: APPROVED | Modo: EXTERNAL_EXECUTION_DISABLED"
        )
    if artefato_tipo == "BUSINESS_PLAN":
        return (
            "Plano de negócio aprovado.\n\n"
            f"Projeto: {project_id}\n"
            "Status: APPROVED\n"
            "Nenhum conteúdo, ativo ou campanha foi criado/publicado "
            "automaticamente -- produção de ativos pertence a outro sistema "
            "(fora desta fase)."
        )
    return f"{info['nome_legivel'].capitalize()} aprovado(a).\n\nProjeto: {project_id}\nStatus: APPROVED"


def _resolver_aprovacao_task(texto: str, pendente: dict, pending_store, brain_store, session: str) -> str:
    """
    Resolve a aprovacao/rejeicao de UMA Task especifica dentro de
    `brain.execution_plan.tasks` (Fase 8). Identifica a task EXATA por
    `project_id` + `task_id` -- nunca por adivinhacao (se a pendencia nao
    tiver os dois, ou a task nao existir mais nesse estado, devolve a
    mesma mensagem de "sem pendencia inequivoca", nunca aplica as cegas).
    """
    project_id = pendente.get("project_id")
    task_id = pendente.get("task_id")
    if not project_id or not task_id:
        pending_store.clear_pending(session)
        return _SEM_PENDENCIA

    brain = brain_store.load(project_id)
    if not brain or not brain.execution_plan:
        pending_store.clear_pending(session)
        return "Não consegui recuperar o plano de execução da aprovação pendente."

    task = next((t for t in brain.execution_plan.tasks if t.task_id == task_id), None)
    if not task or not task.requires_approval or task.status not in {"PENDING", "READY"}:
        pending_store.clear_pending(session)
        return (
            f"Essa aprovação pendente não é mais válida (a tarefa '{task_id}' "
            f"não está mais aguardando aprovação -- status atual: "
            f"{task.status if task else 'inexistente'})."
        )

    execution_id = brain.execution_plan.execution_id

    if eh_rejeicao(texto):
        task.status = "CANCELLED"
        task.updated_at = _agora()
        brain.registrar_aprovacao("EXECUTION_TASK_REJECTED")
        brain_store.save(brain)
        pending_store.clear_pending(session)
        return (
            f"Entendido, tarefa '{task.title}' cancelada.\n\n"
            f"Projeto: {project_id} | Execução: {execution_id} | Tarefa: {task_id}"
        )

    task.approved = True
    task.approved_at = _agora()
    task.updated_at = _agora()
    brain.registrar_aprovacao("EXECUTION_TASK_APPROVED")
    brain_store.save(brain)
    pending_store.clear_pending(session)
    return (
        f"Tarefa aprovada: {task.title}.\n\n"
        f"Projeto: {project_id} | Execução: {execution_id} | Tarefa: {task_id}\n"
        "Nenhuma ação externa real foi executada -- a aprovação libera SOMENTE "
        "a execução simulada (DRY_RUN) desta tarefa. Peça para continuar a "
        "execução para concluí-la."
    )
