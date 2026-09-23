"""
Production Runner -- processa `ProductionWorkOrder`s ELEGÍVEIS
automaticamente, sem exigir um comando manual "execute essa WorkOrder" a
cada vez.

DESLIGADO POR PADRÃO (`settings.PRODUCTION_RUNNER_ENABLED = False`, ver
`config/settings.py`) -- construir e testar esta capacidade NÃO a ativa
sozinha. Ligar o runner na fila real de produção é uma decisão explícita
separada, tomada depois desta etapa (ver `channels/telegram/bot.py` para
onde o loop periódico seria acionado).

NÃO é um sistema de fila novo -- reaproveita 100% do que já existe:
`memory.project_brain.ProjectBrainStore`/`ProductionWorkOrder`,
`core.executor_adapter.EXECUTOR_REGISTRY`/`obter_adapter`. Nenhum
dispatcher/worker/broker paralelo.

REGRAS DE ELEGIBILIDADE (nunca fail-open):
  - SOMENTE `status == "READY"` -- nunca redespacha `DISPATCHED`/
    `COMPLETED`/`FAILED`/`CANCELLED`/`WAITING_APPROVAL`/`NEEDS_ROUTING`/
    `CREATED`. `FAILED` está EXPLICITAMENTE fora do escopo desta fase
    (política de retry automático fica para uma fase futura).
  - `requires_approval=True` e `approved=False` -- NUNCA despachado (gate
    humano sempre respeitado, nunca contornado).
  - Executor sem adapter REAL conectado (ainda no stub
    `AdapterNaoConectado`) -- NUNCA despachado (não adianta nada, e evita
    "processar" silenciosamente sem nenhum efeito real).

CONCORRÊNCIA: este runner é sequencial, single-threaded, dentro de UM
único processo (mesma premissa já estabelecida em toda a operação do Cris
OS: nunca dois processos do bot rodando ao mesmo tempo). A proteção contra
redespacho concorrente é o próprio campo `status` -- ele é alterado por
`adapter.dispatch()` ANTES de qualquer chamada de rede terminar, então uma
segunda passada pelo mesmo processo (ou um restart no meio) nunca encontra
a WorkOrder ainda em `READY` depois de um dispatch bem-sucedido. A
idempotência do lado do executor (`work_order_id` como chave/Idempotency-
Key, já implementada no PageForge) cobre o caso de um restart acontecer
NO MEIO de um dispatch em andamento -- repetir com o mesmo id nunca gera
trabalho duplicado do lado de lá.
"""

from __future__ import annotations

import logging

from core.executor_adapter import AdapterNaoConectado, obter_adapter
from memory.project_brain import ProductionWorkOrder, ProjectBrain

logger = logging.getLogger(__name__)

# Único estado de origem elegível para dispatch automático -- fechado de
# propósito (nunca uma string solta espalhada pelo resto do código).
_STATUS_ELEGIVEL = "READY"


def elegivel_para_dispatch_automatico(wo: ProductionWorkOrder) -> tuple[bool, str]:
    """
    Devolve `(elegível, motivo)` -- nunca lança exceção, nunca adivinha.
    `motivo` é sempre preenchido (tanto no caso elegível quanto não), útil
    para diagnóstico/log sem precisar reconstruir a lógica de fora.
    """
    if wo.status != _STATUS_ELEGIVEL:
        return False, f"status={wo.status!r} (só {_STATUS_ELEGIVEL!r} é elegível para dispatch automático)"
    if wo.requires_approval and not wo.approved:
        return False, "aguardando aprovação humana explícita (requires_approval=True, approved=False)"
    adapter = obter_adapter(wo.executor_type)
    if adapter is None:
        return False, f"nenhum adapter registrado para executor_type={wo.executor_type!r}"
    if isinstance(adapter, AdapterNaoConectado):
        return False, f"executor {wo.executor_type!r} ainda não tem adapter real conectado (stub)"
    return True, "elegível"


def processar_work_orders_do_projeto(brain: ProjectBrain) -> list[dict]:
    """
    Percorre as WorkOrders de UM projeto e despacha, UMA a UMA e
    sequencialmente, somente as elegíveis. Função PURA quanto a I/O externo
    do Cris OS: só muta `brain.production_work_orders` em memória -- quem
    chama decide quando persistir (mesmo princípio de
    `core/production_orders.py`). A chamada de rede real acontece dentro
    de `adapter.dispatch()` (já existente, não duplicado aqui).

    NUNCA lança exceção -- uma falha inesperada de um adapter é capturada,
    registrada em `last_error` e logada; o runner continua para a próxima
    WorkOrder (uma falha nunca derruba o processamento das demais).
    """
    resultados: list[dict] = []
    for wo in brain.production_work_orders:
        elegivel, motivo = elegivel_para_dispatch_automatico(wo)
        if not elegivel:
            continue
        adapter = obter_adapter(wo.executor_type)
        status_antes = wo.status
        try:
            adapter.dispatch(wo)
        except Exception as exc:  # nunca derruba o runner -- registra e segue
            wo.last_error = f"Falha inesperada no runner: {exc.__class__.__name__}: {exc}"
            logger.exception("=== [PRODUCTION_RUNNER] Falha ao despachar %s ===", wo.work_order_id)
        resultados.append({
            "project_id": brain.project_id,
            "work_order_id": wo.work_order_id,
            "status_antes": status_antes,
            "status_depois": wo.status,
            "motivo_elegibilidade": motivo,
        })
    return resultados


def processar_fila_elegivel(brain_store) -> list[dict]:
    """
    Ponto de entrada do runner: varre TODOS os projetos via
    `brain_store.list_all()`, processa as WorkOrders elegíveis de cada um e
    persiste (`brain_store.save`) SOMENTE os projetos onde algo realmente
    foi processado -- nunca escreve um projeto que não mudou.

    Idempotente por construção: chamar isto repetidamente nunca duplica
    nada (uma WorkOrder já despachada deixa de ser `READY`, logo deixa de
    ser elegível na próxima varredura).
    """
    resultados: list[dict] = []
    for brain in brain_store.list_all():
        parciais = processar_work_orders_do_projeto(brain)
        if parciais:
            brain_store.save(brain)
            resultados.extend(parciais)
    return resultados
