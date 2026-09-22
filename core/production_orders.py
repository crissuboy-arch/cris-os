"""
Production Orders -- transforma `required_assets` (Task 3 do Execution
Engine, "Preparar handoff de ativos necessários") em `ProductionWorkOrder`s
rastreáveis, idempotentes, sem NUNCA produzir o ativo em si nem chamar
nenhum executor externo.

DECISÃO ARQUITETURAL: a Task 3 (`core/execution_engine.py`, Fase 8, SEM
alteração) já consolida `required_assets` do BusinessPlan em
`task.evidence` (ver `_executar_task_handoff`) -- esta é a MESMA lista, já
persistida, que este módulo usa como entrada. Nenhuma segunda leitura do
BusinessPlan é necessária; `source_task_id` aponta exatamente para a Task
que originou cada WorkOrder, preservando a cadeia handoff_id -> project_id
-> BusinessPlan -> ExecutionPlan -> Task -> WorkOrder.

IDEMPOTÊNCIA (Seção 5 da missão): a chave lógica é
`(execution_plan_id, source_task_id, asset_type normalizado)` -- reprocessar
a mesma Task, ou chamar isto de novo após um restart, NUNCA cria uma
WorkOrder duplicada; reaproveita a existente.
"""

from __future__ import annotations

from core.production_router import classificar_requisito
from memory.project_brain import ProductionWorkOrder, ProjectBrain, Task


def _work_order_existente(brain: ProjectBrain, execution_plan_id: str, source_task_id: str, asset_type: str) -> ProductionWorkOrder | None:
    return next(
        (
            wo for wo in brain.production_work_orders
            if wo.execution_plan_id == execution_plan_id
            and wo.source_task_id == source_task_id
            and wo.asset_type == asset_type
        ),
        None,
    )


def gerar_work_orders_da_task(brain: ProjectBrain, task: Task) -> list[ProductionWorkOrder]:
    """
    A partir de uma Task JÁ `COMPLETED` cuja `evidence` contém os requisitos
    de ativo (ex.: a Task "Preparar handoff de ativos necessários"), cria ou
    reaproveita uma `ProductionWorkOrder` por requisito.

    NUNCA lança exceção -- uma Task sem `execution_plan`/sem evidência
    simplesmente não gera nada (lista vazia). Função PURA quanto a I/O: só
    modifica `brain.production_work_orders` em memória -- quem chama decide
    quando persistir (mesmo princípio de `core/business_builder.py`/
    `core/product_architect.py`).
    """
    plan = brain.execution_plan
    if not plan or task.status != "COMPLETED":
        return []

    requisitos = [r for r in (task.evidence or []) if r and r.strip()]
    handoff_id = brain.market_intelligence[-1].handoff_id if brain.market_intelligence else None

    resultado: list[ProductionWorkOrder] = []
    for requisito in requisitos:
        asset_type, executor_type = classificar_requisito(requisito)

        existente = _work_order_existente(brain, plan.execution_id, task.task_id, asset_type)
        if existente:
            resultado.append(existente)
            continue

        status_inicial = "NEEDS_ROUTING" if executor_type == "NEEDS_ROUTING" else "READY"
        nova = ProductionWorkOrder(
            project_id=brain.project_id,
            handoff_id=handoff_id,
            execution_plan_id=plan.execution_id,
            source_task_id=task.task_id,
            asset_type=asset_type,
            executor_type=executor_type,
            title=requisito,
            objective=f"Produzir: {requisito}",
            requirements=[requisito],
            input_refs=list(task.output_refs),
            status=status_inicial,
            metadata={"origem": "task_required_assets", "requisito_original": requisito, "task_title": task.title},
        )
        brain.production_work_orders.append(nova)
        resultado.append(nova)

    return resultado


def sincronizar_producao_do_plano(brain: ProjectBrain) -> list[ProductionWorkOrder]:
    """
    Varre TODAS as tasks do `execution_plan` atual e materializa WorkOrders
    para qualquer task já `COMPLETED` que tenha produzido uma lista de
    ativos necessários (hoje, só "Preparar handoff de ativos necessários" --
    ver `core/execution_engine.py:criar_execution_plan`). Idempotente:
    chamar isto repetidamente (ex.: toda vez que `executar_plano` roda)
    nunca duplica nada.
    """
    plan = brain.execution_plan
    if not plan:
        return []
    resultado: list[ProductionWorkOrder] = []
    for task in plan.tasks:
        if task.title == "Preparar handoff de ativos necessários":
            resultado.extend(gerar_work_orders_da_task(brain, task))
    return resultado


_ASSET_TYPES_QUE_EXIGEM_ARTEFATO = frozenset({"LANDING_PAGE", "APP", "EBOOK", "CAROUSEL", "MARKETING_MATERIAL"})


def pode_marcar_completed(work_order: ProductionWorkOrder) -> bool:
    """
    Gate de segurança (Seção 8 da missão): uma WorkOrder cujo `asset_type`
    exige um artefato real (todos, exceto os puramente logísticos/roteados
    como `DISTRIBUTION`/`CRM`/`UNKNOWN`) NUNCA pode ser marcada `COMPLETED`
    sem pelo menos um `output_refs` real -- nenhum executor (nem futuro, nem
    o stub atual) tem permissão de "completar" uma ordem sem evidência.
    Chamado por qualquer código (futuro) que for transicionar uma WorkOrder
    para `COMPLETED` -- nenhum caminho hoje faz essa transição sozinho.
    """
    if work_order.asset_type in _ASSET_TYPES_QUE_EXIGEM_ARTEFATO:
        return bool(work_order.output_refs)
    return True
