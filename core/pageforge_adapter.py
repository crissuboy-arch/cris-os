"""
PageForge Adapter -- implementação REAL do contrato `ExecutorAdapter`
(`core/executor_adapter.py`) para o executor PAGEFORGE.

Lado PageForge já validado em produção (repo
crissuboy-arch/forge-sales-page-skill, commit a4219d3, deploy
https://pageforge-ai-woad.vercel.app):
    POST /api/integrations/cris-os/work-orders
    GET  /api/integrations/cris-os/work-orders/{work_order_id}

NENHUMA chamada real acontece automaticamente -- nada no resto do Cris OS
chama `PageForgeAdapter.dispatch()` sozinho.

AUTENTICAÇÃO: `Authorization: Bearer <PAGEFORGE_BRIDGE_TOKEN>` -- mesmo
padrão já usado por `CRIS_OS_INTEGRATION_TOKEN` neste repositório
(`web/backend/routes/market_intelligence.py`). `PAGEFORGE_BRIDGE_TOKEN`
precisa ter EXATAMENTE o mesmo valor configurado na Vercel do PageForge
como `CRIS_OS_BRIDGE_TOKEN`. O token NUNCA é logado, incluído em
`last_error`, em `metadata` ou em qualquer resposta.

CONTRATO CONFIRMADO (lido do código-fonte real do PageForge, não mais
especulado): o `POST` é SÍNCRONO -- ele roda o pipeline completo (mapear
briefing -> gerar página -> publicar) e só então responde. O corpo 2xx já
contém o resultado real:
    { ok, work_order_id, project_id, executor, status,
      received_at, updated_at, completed_at?, error?, artifact?, idempotent? }
`status` é um de RECEIVED/RUNNING/NEEDS_INPUT/FAILED/COMPLETED -- NUNCA
existe um `job_id` separado (a chave é sempre o próprio `work_order_id`,
tanto para persistir quanto para consultar). `error` é um objeto
`{code, message, missing?}`. `artifact` (quando existe) contém
`artifact_id`/`artifact_type`/`page_id`/`version`/`checksum` e,
condicionalmente, `preview_url`/`deployment_url`.

O mesmo formato de corpo é devolvido pelo `GET` de status -- por isso
`dispatch()` e `collect_result()` reaproveitam a MESMA função de
interpretação (`_aplicar_resultado_pageforge`), nunca duas lógicas
paralelas para o mesmo contrato.

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
Um `status` ausente/não reconhecido (compatibilidade defensiva com um
ambiente antigo/resposta inesperada) NUNCA vira `COMPLETED` -- cai no
mesmo fallback seguro já usado antes desta correção (`DISPATCHED`).
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

# Campos reais do objeto `artifact` (confirmados no código-fonte do
# PageForge, `api/integrations/cris-os/work-orders.js`) -- qualquer um
# presente vira um output_ref rastreável ("campo:valor"). `file_ref`
# (backup durável do HTML, sempre gravado ANTES da publicação bonita --
# correção pós-incidente real) foi adicionado ao contrato do PageForge
# depois deste adapter existir; nunca falta mesmo que `preview_url`/
# `deployment_url` fiquem ausentes por falha de publicação.
_CAMPOS_OUTPUT_CANDIDATOS = (
    "artifact_id", "artifact_type", "page_id", "version", "checksum",
    "preview_url", "deployment_url", "file_ref",
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


def _extrair_output_refs(artifact: object) -> list[str]:
    if not isinstance(artifact, dict):
        return []
    return [f"{campo}:{artifact[campo]}" for campo in _CAMPOS_OUTPUT_CANDIDATOS if artifact.get(campo)]


def _extrair_mensagem_erro(erro: object) -> str:
    if isinstance(erro, dict):
        partes = [str(erro[campo]) for campo in ("code", "message") if erro.get(campo)]
        texto = ": ".join(partes) if partes else "PageForge reportou falha."
        faltando = erro.get("missing")
        if faltando:
            texto += " (faltando: " + ", ".join(str(x) for x in faltando) + ")"
        return texto
    return str(erro) if erro else "PageForge reportou falha."


def _aplicar_resultado_pageforge(work_order: ProductionWorkOrder, corpo: dict) -> bool:
    """
    Interpreta o corpo JSON de uma resposta 2xx do PageForge -- MESMO
    formato tanto na resposta síncrona do `POST` quanto no `GET` de status
    (ver docstring do módulo). Nunca inventa: um `status` ausente/não
    reconhecido NÃO altera `work_order.status` aqui -- cada chamador
    (`dispatch`/`collect_result`) decide seu próprio fallback seguro
    (comportamento pré-existente de cada um, preservado). `COMPLETED` só é
    aceito com output real (gate reaproveitado de
    `core/production_orders.py`, não duplicado).

    Devolve `True` se um status reconhecido foi aplicado, `False` caso
    contrário (status ausente/desconhecido).
    """
    status_bruto = str(corpo.get("status") or "").upper()
    if status_bruto:
        work_order.metadata["pageforge_status"] = status_bruto  # nunca perde a informação original

    outputs = _extrair_output_refs(corpo.get("artifact"))
    if outputs:
        work_order.output_refs = outputs

    novo_status = _MAPA_STATUS_PAGEFORGE.get(status_bruto)

    if novo_status == "COMPLETED":
        if pode_marcar_completed(work_order):
            work_order.status = "COMPLETED"
            work_order.last_error = None
        else:
            # PageForge disse "concluído" mas sem nenhum artefato
            # reconhecível -- NUNCA aceita conclusão sem evidência.
            work_order.status = "RUNNING"
            work_order.last_error = "PageForge sinalizou conclusão sem nenhum artefato reconhecível na resposta."
        return True

    if novo_status:
        work_order.status = novo_status
        if corpo.get("error"):
            work_order.last_error = _extrair_mensagem_erro(corpo.get("error"))
        return True

    return False  # status ausente/desconhecido -- chamador decide o fallback


class PageForgeAdapter:
    """Implementação real de `ExecutorAdapter` (ver `core/executor_adapter.py`
    para o Protocol) para o executor PAGEFORGE."""

    def can_handle(self, work_order: ProductionWorkOrder) -> bool:
        return work_order.executor_type == "PAGEFORGE"

    def dispatch(self, work_order: ProductionWorkOrder) -> ProductionWorkOrder:
        """Envia a WorkOrder ao PageForge. NUNCA cria uma segunda WorkOrder
        -- sempre modifica e devolve a MESMA instância. O `POST` do
        PageForge é SÍNCRONO: o corpo 2xx já pode conter o resultado
        terminal real (COMPLETED/FAILED/NEEDS_INPUT), interpretado por
        `_aplicar_resultado_pageforge` -- nunca é forçado para
        `DISPATCHED` às cegas quando o corpo já traz um status utilizável."""
        if not self.can_handle(work_order):
            work_order.last_error = f"PageForgeAdapter não processa executor_type={work_order.executor_type!r}."
            return work_order

        if work_order.status not in {"READY", "DISPATCHED", "RUNNING"}:
            # Idempotência por ESTADO -- nunca redespacha uma ordem já
            # concluída/falhada/cancelada, mesmo que chamado de novo.
            # RUNNING é aceito aqui (Etapa 18 -- crash-safety): é o marcador
            # que `core/production_runner.py` grava ANTES de chamar
            # `dispatch()` (para sobreviver a um crash no meio da chamada de
            # rede) -- sem isto, o próprio dispatch() rejeitaria seu marcador
            # de segurança e nunca despacharia nada de verdade.
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
            # Falha PERMANENTE (Etapa 18 -- política de retry): um token
            # inválido/ausente nunca se resolve sozinho tentando de novo --
            # ao contrário de erros transitórios, isto NUNCA fica READY
            # (nunca é elegível para retry automático do runner).
            work_order.status = "FAILED"
            work_order.last_error = "PageForge rejeitou a autenticação (token inválido/ausente) -- erro permanente, requer intervenção humana (não é retryable)."
            work_order.updated_at = _agora()
            logger.warning("=== [PAGEFORGE_ADAPTER] Autenticação rejeitada (work_order=%s) -- marcado FAILED, não é retryable ===", work_order.work_order_id)
            return work_order  # nunca expõe o token

        if resposta.status_code == 429 or resposta.status_code >= 500:
            work_order.last_error = f"PageForge indisponível/sobrecarregado (HTTP {resposta.status_code})."
            work_order.updated_at = _agora()
            return work_order  # transitorio -- status permanece READY

        if resposta.status_code >= 400:
            work_order.status = "FAILED"
            work_order.last_error = f"PageForge rejeitou a ordem (HTTP {resposta.status_code})."
            work_order.updated_at = _agora()
            return work_order

        # 2xx -- corpo síncrono já pode trazer o resultado real.
        try:
            corpo = resposta.json()
        except ValueError:
            corpo = {}
        work_order.last_error = None
        aplicado = _aplicar_resultado_pageforge(work_order, corpo if isinstance(corpo, dict) else {})
        if not aplicado:
            # Compatibilidade defensiva (Seção E): ambiente antigo/resposta
            # sem status utilizável -- mesmo fallback seguro já documentado
            # antes desta correção. NUNCA inventa COMPLETED.
            work_order.status = "DISPATCHED"
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
        marca `COMPLETED` sem pelo menos um output reconhecível (mesmo gate
        e mesma interpretação de corpo usados por `dispatch()`)."""
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

        _aplicar_resultado_pageforge(work_order, corpo if isinstance(corpo, dict) else {})
        work_order.updated_at = _agora()
        return work_order
