"""
Receptor HTTP de inteligência de mercado do ScalaFlow (Fase 9 -- fronteira
de integração ScalaFlow -> CRIS OS).

Autenticação por TOKEN ESTÁTICO compartilhado (`CRIS_OS_INTEGRATION_TOKEN`)
-- NUNCA o JWT de usuário da Studio (`agent_builder/auth.py`): este endpoint
é service-to-service (ScalaFlow -> CRIS OS), não uma sessão humana.

Este endpoint NUNCA aprova, executa, publica ou gasta nada -- ele só
recebe, valida e persiste, delegando toda a lógica real (validação,
verification-before-trust, deduplicação, resolução de projeto) para
`core/market_intelligence.py:receive_intelligence`, a MESMA função já
testada em `tests/test_market_intelligence.py`/`tests/test_fase9_end_to_end.py`.
Nenhuma lógica de negócio nova vive aqui -- esta rota é só o transporte.
"""

from __future__ import annotations

import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Margem sobre o limite real de `core/market_intelligence.py:_TAMANHO_MAXIMO_PAYLOAD_BYTES`
# (256 KB) -- rejeita corpo bruto excessivo ANTES de tentar decodificar/
# parsear JSON (defesa em profundidade contra payload excessivo).
_TAMANHO_MAXIMO_BODY_BRUTO = 256 * 1024 + 4096

# Códigos HTTP nos quais o cliente ScalaFlow (fire-and-forget, retry
# limitado) deve considerar a falha TRANSITÓRIA e tentar de novo. Uma
# rejeição definitiva (400/401/403) nunca deve ser retentada.
_STATUS_INTERNO_PARA_HTTP = {
    "PERSISTED": 200,
    "DUPLICATE": 200,
    "NEEDS_REVIEW": 202,  # aceito, mas exige revisão humana -- nao e erro
    "REJECTED": 400,
}


def _require_integration_token(request: Request) -> None:
    """Autenticação por token estático -- comparação em tempo constante
    (mesmo princípio já usado em `agent_builder/auth.py` para verificação
    de assinatura JWT). Token ausente na configuração = integração
    desabilitada (503), nunca um endpoint aberto sem autenticação."""
    from config.settings import settings

    esperado = (settings.CRIS_OS_INTEGRATION_TOKEN or "").strip()
    if not esperado:
        raise HTTPException(status_code=503, detail="Integração com o ScalaFlow não está configurada neste ambiente.")

    cabecalho = request.headers.get("authorization", "")
    token = cabecalho[7:] if cabecalho.lower().startswith("bearer ") else cabecalho
    if not token or not hmac.compare_digest(token, esperado):
        # Nunca loga o token recebido nem o esperado -- so o fato da falha.
        logger.warning("=== [MARKET_INTELLIGENCE_API] Tentativa com token de integração inválido ===")
        raise HTTPException(status_code=401, detail="Token de integração inválido ou ausente.")


def _obter_stores():
    from memory.project_brain import IntelligenceHandoffStore
    from tools.opportunity_tools import get_project_brain_store

    brain_store = get_project_brain_store()
    handoff_store = IntelligenceHandoffStore(brain_store.project_memory)
    return brain_store, handoff_store


@router.post("/integrations/scalaflow/intelligence")
async def receber_intelligence(request: Request):
    """
    Recebe um `MarketIntelligenceHandoff` (ver `docs/SCALAFLOW_CRIS_OS_INTEGRATION.md`)
    via POST, autenticado por `Authorization: Bearer <CRIS_OS_INTEGRATION_TOKEN>`.

    Respostas:
      200 -- PERSISTED ou DUPLICATE (idempotente, nunca reprocessa).
      202 -- NEEDS_REVIEW (aceito, mas precisa de revisão humana -- nunca
             vira fato automaticamente).
      400 -- REJECTED (payload inválido -- NÃO tentar de novo sem corrigir).
      401 -- token inválido/ausente (NÃO tentar de novo sem corrigir o token).
      413 -- corpo excede o tamanho máximo permitido.
      503 -- integração não configurada neste ambiente (token vazio).
    """
    _require_integration_token(request)

    corpo_bruto = await request.body()
    if len(corpo_bruto) > _TAMANHO_MAXIMO_BODY_BRUTO:
        raise HTTPException(status_code=413, detail="Payload excede o tamanho máximo permitido.")

    try:
        payload = json.loads(corpo_bruto) if corpo_bruto else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Payload malformado: JSON inválido.")

    from core.market_intelligence import receive_intelligence

    brain_store, handoff_store = _obter_stores()
    try:
        resultado = receive_intelligence(payload, brain_store, handoff_store)
    except Exception:
        # NUNCA expõe stack trace/segredo pro chamador -- so um erro
        # generico. O detalhe real fica so no log do servidor.
        logger.exception("=== [MARKET_INTELLIGENCE_API] Falha inesperada ao processar handoff ===")
        raise HTTPException(status_code=500, detail="Falha interna ao processar o handoff.")

    status_http = _STATUS_INTERNO_PARA_HTTP.get(resultado["status"], 200)
    return JSONResponse(status_code=status_http, content=resultado)
