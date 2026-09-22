"""
PageForge Adapter -- implementação REAL do contrato `ExecutorAdapter`
(`core/executor_adapter.py`) para o executor PAGEFORGE.

Lado PageForge já validado em produção (repo
crissuboy-arch/forge-sales-page-skill, commit a4219d3, deploy
https://pageforge-ai-woad.vercel.app):
    POST /api/integrations/cris-os/work-orders
    GET  /api/integrations/cris-os/work-orders/{work_order_id}

NENHUMA chamada real acontece automaticamente -- nada no resto do Cris OS
chama `PageForgeAdapter.dispatch()` sozinho. O primeiro dispatch real de
`wo_d0ad992898fe` (WorkOrder da Carla) é uma decisão humana explícita, fora
desta missão.

AUTENTICAÇÃO: `Authorization: Bearer <PAGEFORGE_BRIDGE_TOKEN>` -- mesmo
padrão já usado por `CRIS_OS_INTEGRATION_TOKEN` neste repositório
(`web/backend/routes/market_intelligence.py`). `PAGEFORGE_BRIDGE_TOKEN`
precisa ter EXATAMENTE o mesmo valor configurado na Vercel do PageForge
como `CRIS_OS_BRIDGE_TOKEN`. O token NUNCA é logado, incluído em
`last_error`, em `metadata` ou em qualquer resposta.

AVISO HONESTO: o formato exato do payload/resposta abaixo é o desenho MAIS
PROVÁVEL a partir do contrato descrito (nenhuma chamada real foi feita para
confirmar nomes de campo exatos -- esta missão NUNCA chama a API de
verdade). Antes do primeiro dispatch real, confirme `_montar_payload`/
`_CAMPOS_OUTPUT_CANDIDATOS` contra o contrato real do PageForge.

IDEMPOTÊNCIA: `work_order.work_order_id` é enviado tanto no corpo quanto no
header `Idempotency-Key` -- nunca um ID novo é gerado por tentativa, e
`dispatch()` sempre modifica a MESMA WorkOrder (nunca cria uma segunda).

MAPEAMENTO DE ESTADOS (nunca perde informação -- o status bruto do
PageForge fica sempre em `metadata["pageforge_status"]`, mesmo quando o
vocabulário do Cris OS não tem equivalente exato):
    RECEIVED / QUEUED -> DISPATCHED
    RUNNING           -> RUNNING
    COMPLETED         -> COMPLETED (SOMENTE com output real -- ver
                         `core.production_orders.pode_marcar_completed`)
    FAILED            -> FAILED
    NEEDS_INPUT       -> WAITING_APPROVAL
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from config.settings import settings
from core.production_orders import pode_marcar_completed
from memory.project_brain import ProductionWorkOrder

logger = logging.getLogger(__name__)

_ENDPOINT_CRIAR = "/api/integrations/cris-os/work-orders"
_ENDPOINT_STATUS = "/api/integrations/cris-os/work-orders/{work_order_id}"

_MAPA_STATUS_PAGEFORGE = {
    "RECEIVED": "DISPATCHED",
    "QUEUED": "DISPATCHED",
    "RUNNING": "RUNNING",
    "COMPLETED": "COMPLETED",
    "FAILED": "FAILED",
    "NEEDS_INPUT": "WAITING_APPROVAL",
}

# Campos candidatos de resultado -- qualquer um presente na resposta vira
# um output_ref rastreável ("campo:valor"). Ver AVISO HONESTO no docstring.
_CAMPOS_OUTPUT_CANDIDATOS = (
    "artifact_id", "repository_url", "preview_url", "deployment_url",
    "file_ref", "version", "checksum", "executor_job_id",
)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_configurado() -> bool:
    return bool(settings.PAGEFORGE_BRIDGE_TOKEN)


def _montar_payload(work_order: ProductionWorkOrder) -> dict:
    """Nenhum segredo aqui -- só dados do próprio WorkOrder, já persistidos
    e não sensíveis."""
    return {
        "work_order_id": work_order.work_order_id,
        "project_id": work_order.project_id,
        "asset_type": work_order.asset_type,
        "executor_type": work_order.executor_type,
        "title": work_order.title,
        "objective": work_order.objective,
        "requirements": list(work_order.requirements),
        "metadata": dict(work_order.metadata),
    }


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.PAGEFORGE_BRIDGE_TOKEN}",
        "Content-Type": "application/json",
    }


class PageForgeAdapter:
    """Implementação real de `ExecutorAdapter` (ver `core/executor_adapter.py`
    para o Protocol) para o executor PAGEFORGE."""

    def can_handle(self, work_order: ProductionWorkOrder) -> bool:
        return work_order.executor_type == "PAGEFORGE"

    def dispatch(self, work_order: ProductionWorkOrder) -> ProductionWorkOrder:
        """Envia a WorkOrder ao PageForge. NUNCA cria uma segunda WorkOrder
        -- sempre modifica e devolve a MESMA instância. NUNCA marca
        `COMPLETED` aqui (um 2xx só significa "aceito", não "concluído")."""
        if not self.can_handle(work_order):
            work_order.last_error = f"PageForgeAdapter não processa executor_type={work_order.executor_type!r}."
            return work_order

        if work_order.status not in {"READY", "DISPATCHED"}:
            # Idempotência por ESTADO -- nunca redespacha uma ordem já
            # concluída/falhada/cancelada, mesmo que chamado de novo.
            return work_order

        if not _token_configurado():
            work_order.last_error = "PAGEFORGE_BRIDGE_TOKEN não configurado -- dispatch não realizado."
            logger.warning("=== [PAGEFORGE_ADAPTER] %s (work_order=%s) ===", work_order.last_error, work_order.work_order_id)
            return work_order

        import requests

        url = f"{settings.PAGEFORGE_API_URL}{_ENDPOINT_CRIAR}"
        headers = {**_headers(), "Idempotency-Key": work_order.work_order_id}
        work_order.attempts += 1

        try:
            resposta = requests.post(url, json=_montar_payload(work_order), headers=headers, timeout=settings.PAGEFORGE_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            work_order.last_error = f"Falha de rede ao despachar para PageForge: {exc.__class__.__name__}"
            work_order.updated_at = _agora()
            logger.warning("=== [PAGEFORGE_ADAPTER] Dispatch falhou (rede) para %s: %s ===", work_order.work_order_id, exc.__class__.__name__)
            return work_order  # transitorio -- status permanece READY, pode tentar de novo

        if resposta.status_code in (401, 403):
            work_order.last_error = "PageForge rejeitou a autenticação (token inválido/ausente)."
            work_order.updated_at = _agora()
            logger.warning("=== [PAGEFORGE_ADAPTER] Autenticação rejeitada (work_order=%s) ===", work_order.work_order_id)
            return work_order  # nunca expõe o token; status permanece READY

        if resposta.status_code == 429 or resposta.status_code >= 500:
            work_order.last_error = f"PageForge indisponível/sobrecarregado (HTTP {resposta.status_code})."
            work_order.updated_at = _agora()
            return work_order  # transitorio -- status permanece READY

        if resposta.status_code >= 400:
            work_order.status = "FAILED"
            work_order.last_error = f"PageForge rejeitou a ordem (HTTP {resposta.status_code})."
            work_order.updated_at = _agora()
            return work_order

        # 2xx -- ACEITO pelo PageForge, NUNCA concluído nesta chamada.
        work_order.status = "DISPATCHED"
        work_order.last_error = None
        try:
            corpo = resposta.json()
        except ValueError:
            corpo = {}
        if isinstance(corpo, dict) and corpo.get("job_id"):
            work_order.metadata["pageforge_job_id"] = corpo["job_id"]
        work_order.updated_at = _agora()
        return work_order

    def get_status(self, work_order: ProductionWorkOrder) -> str:
        """Só consulta -- nunca modifica a WorkOrder (ver `collect_result`
        para persistir o resultado)."""
        if not _token_configurado():
            return work_order.status
        import requests

        url = f"{settings.PAGEFORGE_API_URL}{_ENDPOINT_STATUS.format(work_order_id=work_order.work_order_id)}"
        try:
            resposta = requests.get(url, headers=_headers(), timeout=settings.PAGEFORGE_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            logger.warning("=== [PAGEFORGE_ADAPTER] Consulta de status falhou para %s: %s ===", work_order.work_order_id, exc.__class__.__name__)
            return work_order.status
        if resposta.status_code != 200:
            return work_order.status
        try:
            corpo = resposta.json()
        except ValueError:
            return work_order.status
        return str(corpo.get("status", "")).upper()

    def collect_result(self, work_order: ProductionWorkOrder) -> ProductionWorkOrder:
        """Consulta o PageForge e persiste SOMENTE resultado real -- nunca
        marca `COMPLETED` sem pelo menos um output reconhecível (gate
        reaproveitado de `core/production_orders.py`, não duplicado)."""
        if not _token_configurado():
            return work_order

        import requests

        url = f"{settings.PAGEFORGE_API_URL}{_ENDPOINT_STATUS.format(work_order_id=work_order.work_order_id)}"
        try:
            resposta = requests.get(url, headers=_headers(), timeout=settings.PAGEFORGE_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            work_order.last_error = f"Falha de rede ao consultar resultado: {exc.__class__.__name__}"
            work_order.updated_at = _agora()
            return work_order

        if resposta.status_code != 200:
            work_order.last_error = f"Consulta de status falhou (HTTP {resposta.status_code})."
            work_order.updated_at = _agora()
            return work_order

        try:
            corpo = resposta.json()
        except ValueError:
            work_order.last_error = "Resposta de status do PageForge não é JSON válido."
            work_order.updated_at = _agora()
            return work_order

        status_bruto = str(corpo.get("status", "")).upper()
        work_order.metadata["pageforge_status"] = status_bruto  # nunca perde a informação original

        outputs = [f"{campo}:{corpo[campo]}" for campo in _CAMPOS_OUTPUT_CANDIDATOS if corpo.get(campo)]
        if outputs:
            work_order.output_refs = outputs

        novo_status = _MAPA_STATUS_PAGEFORGE.get(status_bruto)
        if novo_status == "COMPLETED":
            if pode_marcar_completed(work_order):
                work_order.status = "COMPLETED"
                work_order.last_error = None
            else:
                # PageForge disse "concluído" mas sem nenhum output
                # reconhecível -- NUNCA aceita conclusão sem evidência.
                work_order.status = "RUNNING"
                work_order.last_error = "PageForge sinalizou conclusão sem nenhum artefato reconhecível na resposta."
        elif novo_status:
            work_order.status = novo_status
            if novo_status == "FAILED":
                work_order.last_error = str(corpo.get("error") or corpo.get("message") or "PageForge reportou falha.")

        work_order.updated_at = _agora()
        return work_order
