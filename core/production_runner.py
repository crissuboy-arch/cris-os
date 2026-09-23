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
    `RUNNING`/`COMPLETED`/`FAILED`/`CANCELLED`/`WAITING_APPROVAL`/
    `NEEDS_ROUTING`/`CREATED`.
  - `requires_approval=True` e `approved=False` -- NUNCA despachado (gate
    humano sempre respeitado, nunca contornado).
  - Executor sem adapter REAL conectado (ainda no stub
    `AdapterNaoConectado`) -- NUNCA despachado.
  - `attempts >= MAX_TENTATIVAS_AUTOMATICAS` -- esgotada (ver "DEAD LETTER"
    abaixo), nunca mais elegível para dispatch automático.
  - Ainda dentro da janela de backoff da tentativa anterior -- ver
    "POLÍTICA DE RETRY" abaixo.

POLÍTICA DE RETRY (Etapa 18): a CLASSIFICAÇÃO erro-transitório-vs-permanente
NÃO vive aqui -- vive no adapter (`core/pageforge_adapter.py`), que é quem
conhece o protocolo de cada executor. Um erro permanente (400/401/403/
validação/NEEDS_INPUT) já sai do adapter com `status` FAILED/WAITING_APPROVAL
-- ou seja, deixa de ser `READY` e, por isso, automaticamente para de ser
elegível aqui. Um erro transitório (timeout/erro de rede/429/5xx) deixa a
WorkOrder em `READY` de propósito -- É esse status que autoriza uma nova
tentativa automática, sujeita a DUAS proteções adicionais só deste módulo:
  1. `MAX_TENTATIVAS_AUTOMATICAS` -- nunca retry infinito.
  2. Backoff (`_BACKOFF_SEGUNDOS`) -- nunca retry imediato em loop apertado.
Uma única fonte de verdade por responsabilidade: o adapter decide SE algo é
retryable (via `status`); o runner decide QUANDO e QUANTAS VEZES.

DEAD LETTER: quando `attempts` atinge `MAX_TENTATIVAS_AUTOMATICAS` e a
WorkOrder ainda está `READY` (falha transitória repetida, nunca resolvida),
`_marcar_dead_letter_se_esgotado` marca `FAILED` explicitamente -- nunca
deixa uma WorkOrder presa para sempre em `READY` fora do alcance do runner
sem nenhum sinal visível. `attempts`/`last_error` anterior NUNCA são
apagados -- o motivo do esgotamento é ANEXADO ao histórico existente.

CRASH-SAFETY / RECOVERY (Etapa 18): o `POST` do PageForge é síncrono -- todo
o trabalho acontece DENTRO da chamada de rede de `adapter.dispatch()`. Se o
processo (bot/VPS) morrer NO MEIO dessa chamada, sem a proteção abaixo a
WorkOrder ficaria com `status` ainda `READY` no armazenamento (só
`processar_fila_elegivel` persistia, e só ao FINAL do projeto inteiro) --
um restart trataria isso como "nunca tentado" e despacharia de novo,
arriscando gerar/gastar em duplicidade.
Por isso, ANTES de chamar `adapter.dispatch()`, este módulo:
  1. Marca `wo.status = "RUNNING"` (estado já existente no vocabulário --
     `memory/project_brain.py:PRODUCTION_WORK_ORDER_ESTADOS_VALIDOS`).
  2. Persiste ISSO imediatamente (`brain_store.save`), SEPARADO do save
     final do ciclo -- um crash logo depois encontra `RUNNING`, nunca
     `READY`, no restart.
Se o processo morre exatamente aqui, ou se `adapter.dispatch()` lança uma
exceção inesperada, a WorkOrder fica em `RUNNING` -- nunca é revertida às
cegas para `READY` (isso arriscaria um segundo dispatch real). Em vez disso,
`_recuperar_work_orders_travadas` roda no INÍCIO de cada ciclo seguinte:
para toda WorkOrder em `RUNNING`, chama `adapter.collect_result()` (SÓ
LEITURA, nunca despacha de novo) para tentar recuperar o resultado real da
tentativa anterior. Duas saídas possíveis, nunca uma terceira:
  - O executor confirma um resultado real (COMPLETED/FAILED/etc.) -> esse
    resultado é persistido, ponto final -- nunca inventado.
  - O executor não confirma nada reconhecível (ou nem existe mais adapter
    registrado) -> a WorkOrder é marcada `FAILED` com um `last_error`
    explícito de que precisa de revisão manual. NUNCA redespachada
    automaticamente -- dado que o próprio ledger de idempotência do
    PageForge (`jobs-store.js`, fora deste repositório) ainda tem uma falha
    conhecida e não corrigida nesta etapa (aponta para um Blob Store
    privado), não há como este runner PROVAR que um redispatch seria
    seguro/idempotente. Sem essa prova, a regra de proteção de custo desta
    etapa é: nunca redespachar.

CONCORRÊNCIA: este runner é sequencial, single-threaded, dentro de UM
único processo (mesma premissa já estabelecida em toda a operação do Cris
OS: nunca dois processos do bot rodando ao mesmo tempo).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from core.executor_adapter import AdapterNaoConectado, obter_adapter
from memory.project_brain import ProductionWorkOrder, ProjectBrain

logger = logging.getLogger(__name__)

# Único estado de origem elegível para dispatch automático -- fechado de
# propósito (nunca uma string solta espalhada pelo resto do código).
_STATUS_ELEGIVEL = "READY"

# Máximo de tentativas automáticas por WorkOrder (Etapa 18 -- nunca retry
# infinito). Valor conservador e explícito -- constante de código (não
# `.env`) de propósito: é uma proteção de custo/segurança, não um parâmetro
# operacional do dia a dia como o intervalo do loop.
MAX_TENTATIVAS_AUTOMATICAS = 3

# Backoff entre tentativas automáticas: chave = `wo.attempts` já registrado
# (após a tentativa Nº`chave`), valor = segundos mínimos de espera antes da
# PRÓXIMA tentativa. Ex.: depois da 1ª tentativa falhar, espera 60s antes da
# 2ª; depois da 2ª, espera 300s antes da 3ª (última permitida). Calculado a
# partir de `wo.updated_at` -- nenhum campo novo precisou ser inventado.
_BACKOFF_SEGUNDOS: dict[int, int] = {1: 60, 2: 300}


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _segundos_desde(timestamp_iso: str) -> float:
    """Nunca lança exceção -- um timestamp ausente/corrompido (não deveria
    acontecer, `_agora()` sempre grava ISO válido) é tratado como "ainda não
    passou tempo nenhum", o lado conservador (evita retry imediato em vez de
    arriscar um retry apressado por causa de um dado corrompido)."""
    if not timestamp_iso:
        return 0.0
    try:
        momento = datetime.fromisoformat(timestamp_iso)
    except ValueError:
        return 0.0
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - momento).total_seconds()


def _aguardando_backoff(wo: ProductionWorkOrder) -> tuple[bool, str]:
    espera = _BACKOFF_SEGUNDOS.get(wo.attempts)
    if espera is None:
        return False, ""
    decorrido = _segundos_desde(wo.updated_at)
    if decorrido < espera:
        faltam = espera - decorrido
        return True, f"aguardando backoff -- faltam {faltam:.0f}s antes da tentativa {wo.attempts + 1}/{MAX_TENTATIVAS_AUTOMATICAS}"
    return False, ""


def elegivel_para_dispatch_automatico(wo: ProductionWorkOrder) -> tuple[bool, str]:
    """
    Devolve `(elegível, motivo)` -- nunca lança exceção, nunca adivinha.
    `motivo` é sempre preenchido (tanto no caso elegível quanto não), útil
    para diagnóstico/log sem precisar reconstruir a lógica de fora.
    """
    if wo.status != _STATUS_ELEGIVEL:
        return False, f"status={wo.status!r} (só {_STATUS_ELEGIVEL!r} é elegível para dispatch automático)"
    if wo.attempts >= MAX_TENTATIVAS_AUTOMATICAS:
        return False, f"tentativas esgotadas ({wo.attempts}/{MAX_TENTATIVAS_AUTOMATICAS}) -- requer intervenção manual"
    aguardando, motivo_backoff = _aguardando_backoff(wo)
    if aguardando:
        return False, motivo_backoff
    if wo.requires_approval and not wo.approved:
        return False, "aguardando aprovação humana explícita (requires_approval=True, approved=False)"
    adapter = obter_adapter(wo.executor_type)
    if adapter is None:
        return False, f"nenhum adapter registrado para executor_type={wo.executor_type!r}"
    if isinstance(adapter, AdapterNaoConectado):
        return False, f"executor {wo.executor_type!r} ainda não tem adapter real conectado (stub)"
    return True, "elegível"


def _marcar_dead_letter_se_esgotado(wo: ProductionWorkOrder) -> bool:
    """
    Dead letter (Etapa 18): se as tentativas automáticas já esgotaram e a
    WorkOrder continua `READY` (falha transitória repetida, nunca
    resolvida), marca `FAILED` explicitamente -- nunca deixa uma WorkOrder
    presa para sempre em `READY`, invisível, fora do alcance do runner.
    NUNCA apaga histórico -- `attempts`/`last_error` anterior são
    preservados, só ANEXA o motivo do esgotamento.
    Devolve `True` quando marcou (e portanto NÃO deve mais ser processada
    neste ciclo como candidata a dispatch).
    """
    if wo.status != _STATUS_ELEGIVEL or wo.attempts < MAX_TENTATIVAS_AUTOMATICAS:
        return False
    erro_anterior = wo.last_error or "(nenhum erro anterior registrado)"
    wo.status = "FAILED"
    wo.last_error = (
        f"Tentativas automáticas esgotadas ({wo.attempts}/{MAX_TENTATIVAS_AUTOMATICAS}) -- "
        f"requer intervenção manual, nunca mais será redespachada automaticamente. "
        f"Último erro registrado: {erro_anterior}"
    )
    wo.updated_at = _agora()
    logger.warning(
        "=== [PRODUCTION_RUNNER] WorkOrder %s esgotou tentativas automáticas -- marcada FAILED (dead letter) ===",
        wo.work_order_id,
    )
    return True


def _recuperar_work_orders_travadas(brain: ProjectBrain) -> list[dict]:
    """
    Varredura de recuperação (Etapa 18): roda ANTES de qualquer dispatch
    novo neste projeto. Para toda WorkOrder presa em `RUNNING` (deixada
    assim por um crash/restart no meio de um dispatch anterior, ou por uma
    exceção inesperada do adapter), consulta o resultado real via
    `adapter.collect_result()` -- SEMPRE só leitura, NUNCA chama
    `dispatch()` de novo aqui.

    Duas saídas possíveis:
      - `collect_result` confirma um status terminal reconhecível -> esse
        resultado passa a ser o novo estado da WorkOrder, ponto final.
      - Nada reconhecível é confirmado (ou não há adapter registrado para
        aquele executor_type) -> marcada `FAILED`, preservando todo o
        histórico, com um `last_error` claro de que precisa revisão manual.
        NUNCA redespachada às cegas -- proteção de custo (ver docstring do
        módulo sobre o ledger do PageForge ainda não corrigido).
    """
    resultados: list[dict] = []
    for wo in brain.production_work_orders:
        if wo.status != "RUNNING":
            continue
        status_antes = wo.status
        adapter = obter_adapter(wo.executor_type)
        if adapter is None:
            wo.last_error = (
                f"{wo.last_error + ' ' if wo.last_error else ''}"
                f"Recuperação pós-restart impossível: nenhum adapter registrado para executor_type={wo.executor_type!r}."
            )
            wo.status = "FAILED"
            wo.updated_at = _agora()
        else:
            try:
                adapter.collect_result(wo)
            except Exception as exc:  # nunca derruba a recuperação das demais
                logger.exception("=== [PRODUCTION_RUNNER] Falha ao consultar resultado durante recuperação de %s ===", wo.work_order_id)
                wo.last_error = f"Falha ao consultar resultado durante recuperação pós-restart: {exc.__class__.__name__}: {exc}"
            if wo.status == "RUNNING":
                # collect_result não encontrou nenhum resultado reconhecível
                # -- nunca redespacha às cegas.
                erro_anterior = wo.last_error or "(nenhum erro anterior registrado)"
                wo.status = "FAILED"
                wo.last_error = (
                    "Recuperada após restart/interrupção em estado RUNNING sem resultado "
                    "confirmável no executor -- requer revisão manual, nunca redespachada "
                    f"automaticamente (proteção de custo). {erro_anterior}"
                )
        wo.updated_at = _agora()
        logger.warning(
            "=== [PRODUCTION_RUNNER] Recuperação pós-restart: %s RUNNING -> %s ===",
            wo.work_order_id, wo.status,
        )
        resultados.append({
            "project_id": brain.project_id,
            "work_order_id": wo.work_order_id,
            "status_antes": status_antes,
            "status_depois": wo.status,
            "motivo_elegibilidade": "recuperação pós-restart (WorkOrder encontrada em RUNNING)",
        })
    return resultados


def processar_work_orders_do_projeto(brain: ProjectBrain, brain_store=None) -> list[dict]:
    """
    Percorre as WorkOrders de UM projeto: primeiro RECUPERA qualquer uma
    presa em `RUNNING` (ver `_recuperar_work_orders_travadas`), depois
    despacha, UMA a UMA e sequencialmente, somente as elegíveis (WorkOrders
    com tentativas esgotadas são dead-lettered em vez de despachadas).

    `brain_store`, quando fornecido, é usado para persistir o marcador
    `RUNNING` IMEDIATAMENTE, antes de cada chamada de rede real (Etapa 18 --
    crash-safety) -- sem ele (chamada direta em teste, sem armazenamento),
    a função continua funcionando, só sem essa proteção extra de persistência
    intermediária (quem chama sem `brain_store` é responsável por persistir
    o resultado final, como sempre foi).

    NUNCA lança exceção -- uma falha inesperada de um adapter é capturada,
    registrada em `last_error` e logada; a WorkOrder fica em `RUNNING`
    (nunca revertida às cegas para `READY` -- ver docstring do módulo) para
    ser resolvida pela varredura de recuperação no próximo ciclo; o runner
    continua para a próxima WorkOrder.
    """
    resultados: list[dict] = _recuperar_work_orders_travadas(brain)

    for wo in brain.production_work_orders:
        if _marcar_dead_letter_se_esgotado(wo):
            resultados.append({
                "project_id": brain.project_id,
                "work_order_id": wo.work_order_id,
                "status_antes": _STATUS_ELEGIVEL,
                "status_depois": wo.status,
                "motivo_elegibilidade": "tentativas esgotadas (dead letter)",
            })
            continue

        elegivel, motivo = elegivel_para_dispatch_automatico(wo)
        if not elegivel:
            continue

        adapter = obter_adapter(wo.executor_type)
        status_antes = wo.status

        wo.status = "RUNNING"
        wo.updated_at = _agora()
        if brain_store is not None:
            brain_store.save(brain)  # crash-safety: persiste o marcador ANTES da chamada de rede

        try:
            adapter.dispatch(wo)
        except Exception as exc:
            # Estado indeterminado -- NUNCA reverte para READY às cegas
            # (arriscaria um segundo dispatch real). Fica em RUNNING; a
            # próxima varredura de recuperação decide o destino final.
            wo.last_error = (
                f"Falha inesperada no runner durante dispatch: {exc.__class__.__name__}: {exc} -- "
                "estado mantido RUNNING para revisão pela varredura de recuperação do próximo ciclo."
            )
            wo.updated_at = _agora()
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
    `brain_store.list_all()`, processa (recupera + despacha) as WorkOrders
    de cada um e persiste (`brain_store.save`) SOMENTE os projetos onde algo
    realmente foi processado -- nunca escreve um projeto que não mudou.

    Idempotente por construção: chamar isto repetidamente nunca duplica
    nada (uma WorkOrder já despachada deixa de ser `READY`, logo deixa de
    ser elegível na próxima varredura; uma presa em `RUNNING` é recuperada,
    nunca redespachada).
    """
    resultados: list[dict] = []
    for brain in brain_store.list_all():
        parciais = processar_work_orders_do_projeto(brain, brain_store=brain_store)
        if parciais:
            brain_store.save(brain)
            resultados.extend(parciais)
    return resultados
