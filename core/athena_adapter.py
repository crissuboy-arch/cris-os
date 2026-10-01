"""
Athena Adapter -- implementação REAL do contrato `ExecutorAdapter`
(`core/executor_adapter.py`) para o executor ATHENA (Athena/Hermes, mesma
VPS, camada de execução inteligente).

TRANSPORTE: ponte HTTP LOCAL da Athena, que escuta SOMENTE em 127.0.0.1
(o Cris OS nunca acessa os arquivos da Athena):
    POST {ATHENA_BRIDGE_URL}/v1/ordens                   {"work_order": {...}}
    GET  {ATHENA_BRIDGE_URL}/v1/ordens/{work_order_id}

AUTENTICAÇÃO: `Authorization: Bearer <ATHENA_BRIDGE_TOKEN>` -- mesmo padrão
do `PageForgeAdapter`. Sem token configurado o adapter NUNCA chama a rede e
nunca finge sucesso. O token nunca é logado, nem incluído em `last_error`,
`metadata` ou qualquer resposta.

IDENTIDADE (preservada ponta a ponta): `work_order_id` é a identidade da
missão na Athena (chave de idempotência; também vai no header
`Idempotency-Key`). `handoff_id` segue no corpo como CORRELAÇÃO com a origem
(ScalaFlow) -- várias WorkOrders do mesmo handoff viram várias missões.

CONTRATO DE RESPOSTA (2xx do POST e 200 do GET têm o MESMO formato, por
isso `dispatch()` e `collect_result()` usam a mesma interpretação):
    { work_order_id, mission_id, handoff_id, athena_status, cris_os_status,
      output_refs, summary, requires_human_approval, last_error, updated_at,
      duplicado? }
`cris_os_status` já vem no vocabulário do Cris OS (DISPATCHED / RUNNING /
WAITING_APPROVAL / COMPLETED / FAILED / CANCELLED). O status bruto da Athena
fica sempre em `metadata["athena_status"]` (nunca se perde informação).

`COMPLETED` só é aceito com output real (gate reaproveitado de
`core.production_orders.pode_marcar_completed`, não duplicado). A Athena
também nunca reporta COMPLETED sem artefato.

O POST da Athena é ASSÍNCRONO: ela recebe a ordem, planeja a missão e
responde (tipicamente RUNNING); o resultado vem depois por
`collect_result()`. Uma ordem de produção NUNCA dispara ação crítica na
Athena (publicar/gastar/campanha/envio em massa): isso exige checkpoint
humano + trava do lado da Athena, fora deste fluxo.

POLÍTICA DE ERROS (mesma do PageForge, Etapa 18):
    rede / 429 / 5xx          -> transitório: status inalterado (retry pelo runner)
    401 / 403                 -> FAILED permanente (token)
    409                       -> FAILED permanente (mesma work_order_id com conteúdo divergente)
    422 / outros 4xx          -> FAILED permanente (ordem recusada, motivo em last_error)
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone

from config.settings import settings
from core.production_orders import pode_marcar_completed
from memory.project_brain import ProductionWorkOrder

logger = logging.getLogger(__name__)

_ENDPOINT_CRIAR = "/v1/ordens"
_ENDPOINT_STATUS = "/v1/ordens/{work_order_id}"
_STATUS_ACEITOS = frozenset({"DISPATCHED", "RUNNING", "WAITING_APPROVAL", "COMPLETED", "FAILED", "CANCELLED"})
_ESTADOS_DESPACHAVEIS = frozenset({"READY", "DISPATCHED", "RUNNING"})
_LIMITE_MENSAGEM = 500


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_configurado() -> bool:
    return bool(settings.ATHENA_BRIDGE_TOKEN)


def _montar_payload(work_order: ProductionWorkOrder) -> dict:
    """A WorkOrder inteira (inclui `handoff_id`) -- nenhum segredo aqui, só
    dados da própria ordem, já persistidos e não sensíveis."""
    return {"work_order": asdict(work_order)}


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.ATHENA_BRIDGE_TOKEN}", "Content-Type": "application/json"}


def _motivo(corpo: object, padrao: str) -> str:
    if isinstance(corpo, dict):
        partes = [str(corpo[c]) for c in ("erro", "motivo") if corpo.get(c)]
        if corpo.get("detalhes"):
            partes.append(str(corpo["detalhes"]))
        if partes:
            return (padrao + " " + ": ".join(partes))[:_LIMITE_MENSAGEM]
    return padrao


def _aplicar_resultado_athena(work_order: ProductionWorkOrder, corpo: dict) -> bool:
    """Interpreta a visão devolvida pela Athena. Nunca inventa: status
    ausente/desconhecido NÃO altera `work_order.status` (o chamador decide o
    fallback). Devolve True se um status reconhecido foi aplicado."""
    if corpo.get("athena_status"):
        work_order.metadata["athena_status"] = str(corpo["athena_status"])
    if corpo.get("mission_id"):
        work_order.metadata["athena_mission_id"] = str(corpo["mission_id"])

    refs = [f"athena:{r}" for r in (corpo.get("output_refs") or []) if isinstance(r, str) and r]
    if refs:
        work_order.output_refs = refs

    novo = str(corpo.get("cris_os_status") or "").upper()
    if novo not in _STATUS_ACEITOS:
        return False

    if novo == "COMPLETED":
        if pode_marcar_completed(work_order):
            work_order.status = "COMPLETED"
            work_order.last_error = None
        else:
            work_order.status = "RUNNING"
            work_order.last_error = "Athena sinalizou conclusão sem nenhum artefato na resposta."
        return True

    work_order.status = novo
    if corpo.get("last_error"):
        work_order.last_error = str(corpo["last_error"])[:_LIMITE_MENSAGEM]
    return True


class AthenaAdapter:
    """Implementação real de `ExecutorAdapter` para o executor ATHENA."""

    def can_handle(self, work_order: ProductionWorkOrder) -> bool:
        return work_order.executor_type == "ATHENA"

    def dispatch(self, work_order: ProductionWorkOrder) -> ProductionWorkOrder:
        """Envia a WorkOrder à Athena. Sempre modifica e devolve a MESMA instância."""
        if not self.can_handle(work_order):
            work_order.last_error = f"AthenaAdapter não processa executor_type={work_order.executor_type!r}."
            return work_order

        if work_order.status not in _ESTADOS_DESPACHAVEIS:
            # idempotência por estado (RUNNING = marcador de crash-safety do production_runner)
            return work_order

        if not _token_configurado():
            work_order.last_error = "ATHENA_BRIDGE_TOKEN não configurado -- dispatch não realizado."
            logger.warning("=== [ATHENA_ADAPTER] %s (work_order=%s) ===", work_order.last_error, work_order.work_order_id)
            return work_order

        import requests

        url = f"{settings.ATHENA_BRIDGE_URL}{_ENDPOINT_CRIAR}"
        headers = {**_headers(), "Idempotency-Key": work_order.work_order_id}
        work_order.attempts += 1

        try:
            resposta = requests.post(url, json=_montar_payload(work_order), headers=headers, timeout=settings.ATHENA_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            work_order.last_error = f"Falha de rede ao despachar para a Athena: {exc.__class__.__name__}"
            work_order.updated_at = _agora()
            logger.warning("=== [ATHENA_ADAPTER] Dispatch falhou (rede) para %s: %s ===", work_order.work_order_id, exc.__class__.__name__)
            return work_order  # transitório

        if resposta.status_code in (401, 403):
            work_order.status = "FAILED"
            work_order.last_error = "Athena rejeitou a autenticação (token inválido/ausente) -- erro permanente, requer intervenção humana."
            work_order.updated_at = _agora()
            logger.warning("=== [ATHENA_ADAPTER] Autenticação rejeitada (work_order=%s) -- FAILED ===", work_order.work_order_id)
            return work_order

        if resposta.status_code == 429 or resposta.status_code >= 500:
            work_order.last_error = f"Athena indisponível/sobrecarregada (HTTP {resposta.status_code})."
            work_order.updated_at = _agora()
            return work_order  # transitório

        try:
            corpo = resposta.json()
        except ValueError:
            corpo = {}
        corpo = corpo if isinstance(corpo, dict) else {}

        if resposta.status_code == 409:
            work_order.status = "FAILED"
            work_order.last_error = _motivo(corpo, "Athena: a mesma work_order_id chegou com conteúdo diferente (HTTP 409).")
            work_order.updated_at = _agora()
            return work_order

        if resposta.status_code >= 400:
            work_order.status = "FAILED"
            work_order.last_error = _motivo(corpo, f"Athena recusou a ordem (HTTP {resposta.status_code}).")
            work_order.updated_at = _agora()
            return work_order

        work_order.last_error = None
        if not _aplicar_resultado_athena(work_order, corpo):
            work_order.status = "DISPATCHED"  # fallback seguro: nunca inventa COMPLETED
        work_order.updated_at = _agora()
        return work_order

    def get_status(self, work_order: ProductionWorkOrder) -> str:
        """Só consulta -- nunca modifica a WorkOrder."""
        if not _token_configurado():
            return work_order.status
        import requests

        url = f"{settings.ATHENA_BRIDGE_URL}{_ENDPOINT_STATUS.format(work_order_id=work_order.work_order_id)}"
        try:
            resposta = requests.get(url, headers=_headers(), timeout=settings.ATHENA_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            logger.warning("=== [ATHENA_ADAPTER] Consulta de status falhou para %s: %s ===", work_order.work_order_id, exc.__class__.__name__)
            return work_order.status
        if resposta.status_code != 200:
            return work_order.status
        try:
            corpo = resposta.json()
        except ValueError:
            return work_order.status
        status = str((corpo or {}).get("cris_os_status", "")).upper()
        return status if status in _STATUS_ACEITOS else work_order.status

    def collect_result(self, work_order: ProductionWorkOrder) -> ProductionWorkOrder:
        """Consulta a Athena e persiste SOMENTE resultado real (COMPLETED só com output)."""
        if not _token_configurado():
            return work_order
        import requests

        url = f"{settings.ATHENA_BRIDGE_URL}{_ENDPOINT_STATUS.format(work_order_id=work_order.work_order_id)}"
        try:
            resposta = requests.get(url, headers=_headers(), timeout=settings.ATHENA_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            work_order.last_error = f"Falha de rede ao consultar resultado na Athena: {exc.__class__.__name__}"
            work_order.updated_at = _agora()
            return work_order
        if resposta.status_code != 200:
            work_order.last_error = f"Consulta de status na Athena falhou (HTTP {resposta.status_code})."
            work_order.updated_at = _agora()
            return work_order
        try:
            corpo = resposta.json()
        except ValueError:
            work_order.last_error = "Resposta de status da Athena não é JSON válido."
            work_order.updated_at = _agora()
            return work_order
        _aplicar_resultado_athena(work_order, corpo if isinstance(corpo, dict) else {})
        work_order.updated_at = _agora()
        return work_order
