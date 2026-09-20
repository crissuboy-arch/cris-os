"""
Execution Engine (Fase 8) -- converte um artefato JA APROVADO
(BusinessPlan/TrafficPlan/CampaignSpec/ProductBlueprint) num `ExecutionPlan`
com `Task`s dependentes, e processa essas tasks respeitando dependencias,
aprovacao humana por task e ausencia total de execucao externa real.

Principio de Skill (mesmo das Fases 5/6/7): este modulo NAO conhece
Telegram, nao conhece o AgentOrchestrator diretamente -- recebe um
`ProjectBrain` (e, opcionalmente, um `agent_invoker` para tasks que
genuinamente precisem de um agente especialista) e devolve/atualiza um
`ExecutionPlan`.

DECISAO ARQUITETURAL (documentada -- ver auditoria da Fase 8): o repositorio
ja tem um `WorkflowEngine`/`ExecutionDispatcher`/`InProcessEventBus`/
`core.domain.planning.Plan` (camada "v3"), mas nenhum deles esta no caminho
real de producao -- `core/runtime.py` monta esses componentes e depois
SOBRESCREVE `handler` com o `AgentOrchestrator` quando `DEFAULT_AGENT=auto`
(configuracao real do `.env`). Reaproveitar essa camada faria o Execution
Engine ficar tao invisivel em producao quanto a camada de "cognition" ja
esta hoje. Por isso, ESTE motor e novo, mas segue o MESMO padrao que TODAS
as fases anteriores usaram com sucesso: um agente/tool novo, consumido
diretamente pelo `AgentOrchestrator`, persistido no MESMO `ProjectBrain`
(nenhum banco/fila/event bus paralelo).

REGRA MAIS IMPORTANTE DESTA FASE -- NAO EXISTE EXECUCAO EXTERNA REAL: uma
task com `external_action=True` NUNCA e executada de verdade -- so pode ser
"concluida" via simulacao (DRY_RUN/MOCK), e mesmo assim exige aprovacao
humana explicita POR TASK (nao so aprovacao do plano inteiro).

ANTI-HALLUCINATION: uma task nunca e marcada COMPLETED sem um resultado
verificavel (derivado de dados REAIS ja persistidos no Project Brain).
Quando falta dado essencial, a task fica BLOCKED com um erro explicito --
nunca inventa metrica, URL, campanha, venda, arquivo ou ID externo.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from memory.project_brain import (
    EXECUTION_SOURCE_ARTIFACT_TIPOS,
    ExecutionPlan,
    ProjectBrain,
    Task,
    novo_execution_id,
)

logger = logging.getLogger(__name__)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Resolucao do artefato de origem -- SEMPRE precisa estar aprovado
# ---------------------------------------------------------------------------

_ORIGENS = {
    "BUSINESS_PLAN": lambda brain: brain.business_plan,
    "TRAFFIC_PLAN": lambda brain: brain.traffic_plan,
    "CAMPAIGN_SPEC": lambda brain: brain.campaign_spec,
    "PRODUCT_BLUEPRINT": lambda brain: brain.blueprint,
}
_NOMES_LEGIVEIS = {
    "BUSINESS_PLAN": "plano de negócio",
    "TRAFFIC_PLAN": "plano de tráfego",
    "CAMPAIGN_SPEC": "especificação de campanha",
    "PRODUCT_BLUEPRINT": "formato de produto",
}
# Ordem de preferencia quando o tipo de origem nao e informado explicitamente
# -- do mais "downstream" (negocio ja fechado) ao mais "upstream" (so o
# formato do produto).
_ORDEM_PADRAO = ("BUSINESS_PLAN", "TRAFFIC_PLAN", "CAMPAIGN_SPEC", "PRODUCT_BLUEPRINT")


def _resolver_origem(brain: ProjectBrain, source_artifact_type: str | None) -> tuple[str, object] | None:
    """Devolve `(tipo, artefato)` do PRIMEIRO artefato aprovado encontrado --
    nunca inventa uma origem quando nada esta aprovado ainda."""
    tipos = (source_artifact_type,) if source_artifact_type else _ORDEM_PADRAO
    for tipo in tipos:
        obter = _ORIGENS.get(tipo)
        if not obter:
            continue
        artefato = obter(brain)
        if artefato and artefato.esta_aprovado():
            return tipo, artefato
    return None


def avaliar_prontidao_execucao(brain: ProjectBrain, source_artifact_type: str | None = None) -> list[str]:
    """
    GATE central: um ExecutionPlan so pode ser criado quando existe pelo
    menos UM artefato aprovado (BusinessPlan/TrafficPlan/CampaignSpec/
    ProductBlueprint) para servir de origem. Devolve a lista de lacunas
    (vazia = pronto).
    """
    if source_artifact_type and source_artifact_type not in EXECUTION_SOURCE_ARTIFACT_TIPOS:
        return [f"Tipo de artefato de origem desconhecido: {source_artifact_type!r}."]
    if _resolver_origem(brain, source_artifact_type) is None:
        if source_artifact_type:
            nome = _NOMES_LEGIVEIS.get(source_artifact_type, source_artifact_type)
            return [f"O {nome} deste projeto ainda não foi aprovado -- aprove-o antes de criar um plano de execução."]
        return [
            "Nenhum artefato aprovado (plano de negócio, plano de tráfego, "
            "especificação de campanha ou formato de produto) foi encontrado "
            "para servir de origem do plano de execução.",
        ]
    return []


# ---------------------------------------------------------------------------
# Geracao DETERMINISTICA do plano -- nunca usa LLM (nada aqui e julgamento
# aberto; e sempre uma leitura estruturada de dados JA persistidos).
# ---------------------------------------------------------------------------

def _campos_de(tipo: str, artefato) -> dict:
    if tipo == "BUSINESS_PLAN":
        return {
            "acquisition_channels": list(artefato.acquisition_channels) or ([artefato.primary_channel] if artefato.primary_channel else []),
            "required_assets": list(artefato.required_assets),
            "target_audience": artefato.target_audience,
            "positioning": artefato.positioning,
        }
    if tipo == "TRAFFIC_PLAN":
        return {
            "acquisition_channels": [c.get("channel") for c in artefato.channels if c.get("channel")],
            "required_assets": [item.get("angle") for item in artefato.creative_matrix if item.get("angle")],
            "target_audience": artefato.audience_summary,
            "positioning": artefato.objective,
        }
    if tipo == "CAMPAIGN_SPEC":
        return {
            "acquisition_channels": [artefato.channel] if artefato.channel else [],
            "required_assets": list(artefato.creative_requirements),
            "target_audience": None,
            "positioning": artefato.objective,
        }
    return {  # PRODUCT_BLUEPRINT
        "acquisition_channels": [],
        "required_assets": [],
        "target_audience": artefato.target_audience,
        "positioning": artefato.differentiation,
    }


def criar_execution_plan(
    brain: ProjectBrain, objetivo: str, source_artifact_type: str | None = None,
) -> ExecutionPlan:
    """
    Gera um ExecutionPlan de 4 tasks padrao (analisar origem -> definir
    requisitos de aquisicao -> preparar handoff de ativos -> simular acao
    externa) a partir do PRIMEIRO artefato aprovado encontrado. NUNCA
    fabrica prontidao -- se `avaliar_prontidao_execucao` encontrar lacunas,
    devolve um ExecutionPlan vazio (0 tasks) com `status="BLOCKED"` e as
    lacunas registradas -- quem chama (`tools/execution_engine_tools.py`)
    normalmente intercepta a lacuna ANTES de chegar aqui e nunca persiste
    esse resultado, mas esta funcao nunca finge sucesso de qualquer forma.
    """
    lacunas = avaliar_prontidao_execucao(brain, source_artifact_type)
    if lacunas:
        return ExecutionPlan(
            project_id=brain.project_id, objective=objetivo, status="BLOCKED",
            tasks=[Task(title="Bloqueado -- sem artefato de origem aprovado", status="BLOCKED", error="; ".join(lacunas))],
        )

    tipo, artefato = _resolver_origem(brain, source_artifact_type)
    campos = _campos_de(tipo, artefato)
    nome = _NOMES_LEGIVEIS[tipo]
    source_id = getattr(artefato, "campaign_id", None) or f"{tipo.lower()}:{brain.project_id}"

    t1 = Task(
        title=f"Analisar {nome} aprovado",
        description=f"Ler os dados reais do {nome} já aprovado para embasar o restante do plano.",
        objective=f"Confirmar o conteúdo aprovado do {nome} do projeto {brain.project_id}.",
        agent="execution_engine",
        input_refs=[source_id],
        priority="alta",
    )
    t2 = Task(
        title="Definir requisitos de aquisição",
        description="Derivar os canais de aquisição/público a partir do artefato de origem.",
        objective="Definir por quais canais este produto/oferta será adquirido.",
        agent="business_builder" if tipo == "BUSINESS_PLAN" else "paid_traffic_architect",
        dependencies=[t1.task_id],
        input_refs=[source_id],
        priority="alta",
    )
    t3 = Task(
        title="Preparar handoff de ativos necessários",
        description="Consolidar quais ativos (landing page, criativos, etc.) precisam ser produzidos.",
        objective="Gerar a lista de ativos necessários para a próxima fase de produção.",
        agent="business_builder",
        dependencies=[t2.task_id],
        priority="media",
    )
    t4 = Task(
        title="Simular ação externa (DRY_RUN)",
        description="Simular, sem executar de verdade, a ação externa final (ex.: publicar/ativar).",
        objective="Confirmar que o fluxo de execução chega até a ação externa sem publicá-la de fato.",
        agent="campaign_executor",
        dependencies=[t3.task_id],
        priority="baixa",
        requires_approval=True,
        external_action=True,
    )

    return ExecutionPlan(
        project_id=brain.project_id,
        source_artifact_type=tipo,
        source_artifact_id=source_id,
        objective=objetivo,
        status="READY_FOR_APPROVAL",
        tasks=[t1, t2, t3, t4],
    )


# ---------------------------------------------------------------------------
# Deteccao de ciclo -- um ExecutionPlan com ciclo NUNCA e aceito
# ---------------------------------------------------------------------------

def detectar_ciclo(tasks: list[Task]) -> bool:
    """DFS com 3 cores (branco/cinza/preto) -- True se houver qualquer
    dependencia circular. Tambem detecta dependencia pra um `task_id`
    inexistente como um grafo invalido (tratado como ciclo -- nunca
    executavel com seguranca)."""
    por_id = {t.task_id: t for t in tasks}
    cor: dict[str, str] = {t.task_id: "branco" for t in tasks}

    def visitar(task_id: str) -> bool:
        if task_id not in por_id:
            return True  # dependencia pra task inexistente -- invalido
        if cor[task_id] == "cinza":
            return True  # ciclo encontrado
        if cor[task_id] == "preto":
            return False
        cor[task_id] = "cinza"
        for dep in por_id[task_id].dependencies:
            if visitar(dep):
                return True
        cor[task_id] = "preto"
        return False

    return any(visitar(t.task_id) for t in tasks)


# ---------------------------------------------------------------------------
# Propagacao de bloqueio -- falha de uma task bloqueia quem depende dela
# ---------------------------------------------------------------------------

def _propagar_bloqueio(plan: ExecutionPlan) -> None:
    por_id = {t.task_id: t for t in plan.tasks}
    problematicos = {t.task_id for t in plan.tasks if t.status in {"FAILED", "BLOCKED", "CANCELLED"}}
    mudou = True
    while mudou:
        mudou = False
        for t in plan.tasks:
            if t.status in {"COMPLETED", "FAILED", "BLOCKED", "CANCELLED", "SKIPPED"}:
                continue
            if any(dep in problematicos for dep in t.dependencies):
                t.status = "BLOCKED"
                if not t.error:
                    dep_problematica = next(d for d in t.dependencies if d in problematicos)
                    t.error = f"Bloqueada -- depende da task '{dep_problematica}', que não foi concluída."
                t.updated_at = _agora()
                problematicos.add(t.task_id)
                mudou = True


def _tarefas_prontas(plan: ExecutionPlan) -> list[Task]:
    completas = {t.task_id for t in plan.tasks if t.status == "COMPLETED"}
    prontas = []
    for t in plan.tasks:
        if t.status not in {"PENDING", "READY"}:
            continue
        if all(dep in completas for dep in t.dependencies):
            prontas.append(t)
    return prontas


def _pode_executar_agora(task: Task) -> bool:
    return not (task.requires_approval and not task.approved)


# ---------------------------------------------------------------------------
# Execucao das tasks padrao (deterministica, sem LLM, sem chamada externa)
# ---------------------------------------------------------------------------

def _executar_task_analise(brain: ProjectBrain, plan: ExecutionPlan, task: Task) -> tuple[bool, str, list[str]]:
    tipo = plan.source_artifact_type
    obter = _ORIGENS.get(tipo)
    artefato = obter(brain) if obter else None
    if not artefato or not artefato.esta_aprovado():
        return False, f"O artefato de origem ({tipo}) não está mais aprovado.", []
    campos = _campos_de(tipo, artefato)
    evidencia = [f"origem: {tipo}", f"posicionamento: {campos.get('positioning') or 'NÃO DEFINIDO'}"]
    if campos.get("target_audience"):
        evidencia.append(f"público-alvo: {campos['target_audience']}")
    return True, f"{_NOMES_LEGIVEIS[tipo]} confirmado como aprovado e analisado.", evidencia


def _executar_task_aquisicao(brain: ProjectBrain, plan: ExecutionPlan, task: Task) -> tuple[bool, str, list[str]]:
    tipo = plan.source_artifact_type
    obter = _ORIGENS.get(tipo)
    artefato = obter(brain) if obter else None
    campos = _campos_de(tipo, artefato) if artefato else {}
    canais = [c for c in campos.get("acquisition_channels", []) if c]
    if not canais:
        return False, "Nenhum canal de aquisição definido no artefato de origem.", []
    return True, "Canais de aquisição definidos: " + ", ".join(canais), [f"canal: {c}" for c in canais]


def _executar_task_handoff(brain: ProjectBrain, plan: ExecutionPlan, task: Task) -> tuple[bool, str, list[str]]:
    from core.business_builder import gerar_handoff

    if plan.source_artifact_type == "BUSINESS_PLAN":
        handoff = gerar_handoff(brain)
        if not handoff:
            return False, "Não foi possível gerar o handoff -- o plano de negócio não está mais aprovado.", []
        task.output_refs = [handoff["business_plan_id"]]
        ativos = handoff.get("required_assets") or []
        if not ativos:
            return True, "Nenhum ativo adicional necessário além do que já existe.", []
        return True, "Ativos necessários consolidados: " + "; ".join(ativos), list(ativos)

    tipo = plan.source_artifact_type
    obter = _ORIGENS.get(tipo)
    artefato = obter(brain) if obter else None
    campos = _campos_de(tipo, artefato) if artefato else {}
    ativos = [a for a in campos.get("required_assets", []) if a]
    task.output_refs = [f"{tipo.lower()}:{brain.project_id}"]
    if not ativos:
        return True, "Nenhum ativo adicional necessário registrado.", []
    return True, "Ativos necessários consolidados: " + "; ".join(ativos), list(ativos)


def _executar_task_simulacao_externa(brain: ProjectBrain, plan: ExecutionPlan, task: Task) -> tuple[bool, str, list[str]]:
    """NUNCA executa nada de verdade -- so pode ser chamada depois de
    `task.approved=True` (checado por `_pode_executar_agora` antes de
    chegar aqui). Marca `simulated=True` explicitamente."""
    task.simulated = True
    return (
        True,
        "SIMULADO (DRY_RUN) -- nenhuma ação externa real foi executada, "
        "nenhuma conta de anúncio conectada, nenhum valor gasto.",
        [f"execution_id: {plan.execution_id}", "modo: DRY_RUN"],
    )


def _selecionar_executor(task: Task):
    if task.title.startswith("Analisar ") and task.title.endswith("aprovado"):
        return _executar_task_analise
    if task.title == "Definir requisitos de aquisição":
        return _executar_task_aquisicao
    if task.title == "Preparar handoff de ativos necessários":
        return _executar_task_handoff
    if task.external_action:
        return _executar_task_simulacao_externa
    return None


def _executar_uma_task(brain: ProjectBrain, plan: ExecutionPlan, task: Task, agent_invoker=None) -> None:
    task.status = "RUNNING"
    task.updated_at = _agora()
    executor = _selecionar_executor(task)
    try:
        if executor:
            sucesso, resultado, evidencia = executor(brain, plan, task)
        elif agent_invoker and task.agent:
            resultado = agent_invoker(task.agent, task.objective or task.title, f"execution:{plan.execution_id}")
            sucesso, evidencia = True, [f"resposta do agente '{task.agent}' recebida"]
        else:
            sucesso, resultado, evidencia = False, "Nenhum executor disponível para esta task.", []
    except Exception as exc:  # falha de INFRAESTRUTURA -- candidata a retry
        task.retry_count += 1
        task.error = str(exc)
        task.updated_at = _agora()
        if task.retry_count <= task.max_retries:
            task.status = "READY"  # tenta de novo numa proxima chamada (nunca loop infinito -- respeita max_retries)
            logger.warning("=== [EXECUTION_ENGINE] Task '%s' falhou (tentativa %d/%d): %s ===", task.task_id, task.retry_count, task.max_retries, exc)
        else:
            task.status = "FAILED"
            logger.warning("=== [EXECUTION_ENGINE] Task '%s' FAILED apos %d tentativas: %s ===", task.task_id, task.retry_count, exc)
        return

    task.updated_at = _agora()
    if sucesso:
        task.status = "COMPLETED"
        task.result = resultado
        task.evidence = evidencia
        task.error = None
    else:
        # Falha LOGICA/de validacao (dado ausente) -- nunca retry automatico
        # (retry so serve pra falha transitoria de infraestrutura).
        task.status = "BLOCKED"
        task.error = resultado


def executar_plano(brain: ProjectBrain, agent_invoker=None) -> ExecutionPlan:
    """
    Processa todas as tasks PRONTAS (dependencias completas) do
    `brain.execution_plan` atual, em ordem topologica, ate nao conseguir
    mais progredir (proxima task exige aprovacao pendente, ou nao ha mais
    tasks prontas). NUNCA reexecuta uma task em estado TERMINAL --
    idempotente por construcao (chamar de novo so continua de onde parou,
    inclusive apos um restart do processo).
    """
    plan = brain.execution_plan
    if not plan:
        raise ValueError("Nenhum ExecutionPlan existe para este projeto.")
    if not plan.esta_liberado_para_rodar():
        return plan  # PAUSED/CANCELLED/DRAFT/READY_FOR_APPROVAL/COMPLETED/FAILED -- nao processa

    if plan.status == "APPROVED":
        plan.status = "RUNNING"
        plan.execution_started_at = plan.execution_started_at or _agora()

    progrediu = True
    while progrediu:
        progrediu = False
        for task in _tarefas_prontas(plan):
            if not _pode_executar_agora(task):
                if task.status != "READY":
                    task.status = "READY"
                    task.updated_at = _agora()
                continue
            _executar_uma_task(brain, plan, task, agent_invoker=agent_invoker)
            progrediu = True

    _propagar_bloqueio(plan)

    resumo = plan.resumo()
    if resumo["total_tasks"] and resumo["completed_tasks"] == resumo["total_tasks"]:
        plan.status = "COMPLETED"
        plan.execution_finished_at = plan.execution_finished_at or _agora()
    elif resumo["failed_tasks"] and resumo["blocked_tasks"] + resumo["failed_tasks"] == resumo["total_tasks"] - resumo["completed_tasks"]:
        # nada mais pode progredir e ha falha real -- encerra como FAILED
        plan.status = "FAILED"
        plan.execution_finished_at = plan.execution_finished_at or _agora()
    # senao, permanece RUNNING (aguardando aprovacao de alguma task, por exemplo)

    plan.updated_at = _agora()
    return plan


# ---------------------------------------------------------------------------
# Controle: PAUSE / RESUME / CANCEL
# ---------------------------------------------------------------------------

def pausar_plano(plan: ExecutionPlan) -> tuple[bool, str]:
    if plan.status != "RUNNING":
        return False, f"Só é possível pausar um plano em execução (status atual: {plan.status})."
    plan.status = "PAUSED"
    plan.updated_at = _agora()
    return True, "Execução pausada -- nenhuma nova task será iniciada até retomar."


def retomar_plano(plan: ExecutionPlan) -> tuple[bool, str]:
    if plan.status != "PAUSED":
        return False, f"Só é possível retomar um plano pausado (status atual: {plan.status})."
    plan.status = "RUNNING"
    plan.updated_at = _agora()
    return True, "Execução retomada."


def cancelar_plano(plan: ExecutionPlan) -> tuple[bool, str]:
    if plan.status in {"COMPLETED", "CANCELLED", "FAILED"}:
        return False, f"Este plano já está encerrado (status atual: {plan.status})."
    for t in plan.tasks:
        # NUNCA desfaz silenciosamente uma task ja concluida.
        if t.status not in {"COMPLETED", "FAILED", "SKIPPED", "CANCELLED"}:
            t.status = "CANCELLED"
            t.updated_at = _agora()
    plan.status = "CANCELLED"
    plan.updated_at = _agora()
    return True, "Execução cancelada -- nenhuma nova task será iniciada. Tasks já concluídas foram preservadas."


# ---------------------------------------------------------------------------
# Handoff estruturado para a Fase 9 (contrato de dados -- nunca executa nada)
# ---------------------------------------------------------------------------

def gerar_execution_handoff(brain: ProjectBrain) -> dict | None:
    plan = brain.execution_plan
    if not plan:
        return None
    resumo = plan.resumo()
    pendentes_aprovacao = [t.task_id for t in plan.tasks if t.requires_approval and not t.approved and t.status in {"PENDING", "READY"}]
    bloqueadas = [{"task_id": t.task_id, "title": t.title, "error": t.error} for t in plan.tasks if t.status == "BLOCKED"]
    evidencia = [e for t in plan.tasks for e in t.evidence]
    outputs = [o for t in plan.tasks for o in t.output_refs]
    proximas_acoes = []
    if pendentes_aprovacao:
        proximas_acoes.append(f"Aprovar {len(pendentes_aprovacao)} task(s) pendente(s) de aprovação.")
    if bloqueadas:
        proximas_acoes.append(f"Resolver {len(bloqueadas)} task(s) bloqueada(s).")
    if not proximas_acoes and resumo["total_tasks"] == resumo["completed_tasks"]:
        proximas_acoes.append("Execução concluída -- pronta para integração com a Fase 9.")

    return {
        "project_id": brain.project_id,
        "execution_id": plan.execution_id,
        "objective": plan.objective,
        "source_artifacts": [{"type": plan.source_artifact_type, "id": plan.source_artifact_id}],
        "tasks": [{"task_id": t.task_id, "title": t.title, "status": t.status} for t in plan.tasks],
        "statuses": resumo,
        "outputs": outputs,
        "pending_approvals": pendentes_aprovacao,
        "blockers": bloqueadas,
        "evidence": evidencia,
        "next_actions": proximas_acoes,
    }
