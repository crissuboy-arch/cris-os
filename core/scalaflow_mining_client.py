"""
ScalaFlow Mining Client (Etapa 23) -- cliente HTTP mínimo, server-to-server,
para o endpoint de mineração já em produção no ScalaFlow:

    POST https://escalaflow-insights.vercel.app/api/integrations/mining/run
    Authorization: Bearer <CRIS_OS_MINING_SECRET>
    { "source": "tiktok"|"instagram"|"youtube"|"google_trends", "term": "...", "limit": N }

NÃO duplica nenhum minerador -- o ScalaFlow já reaproveita os próprios
mineradores reais (TikTok/Instagram/YouTube/Google Trends, ver
`mine*Fn` em `escalaflow-insights/src/lib/*-radar.functions.ts`) e persiste
o resultado na MESMA fonte de verdade (tabelas `*_minerados`, Supabase do
ScalaFlow) que `tools/scalaflow_tools.py` já lê. Este módulo só PEDE a
mineração -- nunca minera nada aqui dentro, nunca chama Apify diretamente.

CLASSIFICAÇÃO DE ERRO (mesmo vocabulário de `core/pageforge_adapter.py` --
nenhuma segunda política de retry criada):
    2xx              -> SUCCESS
    400              -> INVALID_REQUEST -- NUNCA retryable
    401/403          -> AUTH_ERROR -- NUNCA retryable (nunca expõe o secret
                        em log/erro)
    429              -> RATE_LIMITED -- NUNCA retryable automaticamente
                        aqui; este módulo nunca tenta contornar o rate
                        limit, quem chama decide esperar
    5xx/timeout/rede -> TRANSIENT_ERROR -- `retryable=True` (a DECISÃO de
                        tentar de novo fica para quem chama, exatamente
                        como no PageForge; este módulo nunca faz retry
                        sozinho, nunca faz loop)

NENHUMA chamada acontece automaticamente -- precisa de um chamador
explícito. Nada neste módulo é registrado no Production Runner nem em
nenhum outro loop automático.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config.settings import settings

logger = logging.getLogger(__name__)

# Vocabulário FECHADO de fontes -- o ÚNICO lugar onde isso é definido no
# Cris OS (nunca duplicado em outro módulo).
FONTES_MINERACAO_VALIDAS = frozenset({"tiktok", "instagram", "youtube", "google_trends"})


@dataclass
class ResultadoMineracao:
    """Resultado estruturado de UMA solicitação de mineração -- nunca uma
    exceção, sempre um valor que quem chama pode inspecionar."""

    ok: bool
    status: str  # SUCCESS | INVALID_REQUEST | AUTH_ERROR | RATE_LIMITED | TRANSIENT_ERROR | NOT_CONFIGURED
    retryable: bool
    http_status: int | None = None
    dados: dict | None = None
    erro: str | None = None


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.CRIS_OS_MINING_SECRET}",
    }


def _configurado() -> bool:
    return bool(settings.SCALAFLOW_MINING_URL and settings.CRIS_OS_MINING_SECRET)


def solicitar_mineracao(source: str, term: str, limit: int = 20) -> ResultadoMineracao:
    """
    Pede ao ScalaFlow para minerar `term` na fonte `source`. NUNCA lança
    exceção -- qualquer falha vira um `ResultadoMineracao` classificado.
    NUNCA faz retry/loop automático aqui dentro (ver docstring do módulo).
    """
    if source not in FONTES_MINERACAO_VALIDAS:
        return ResultadoMineracao(
            ok=False, status="INVALID_REQUEST", retryable=False,
            erro=f"Fonte inválida: {source!r} (válidas: {sorted(FONTES_MINERACAO_VALIDAS)}).",
        )
    if not term or not term.strip():
        return ResultadoMineracao(ok=False, status="INVALID_REQUEST", retryable=False, erro="Termo de busca vazio.")

    if not _configurado():
        return ResultadoMineracao(
            ok=False, status="NOT_CONFIGURED", retryable=False,
            erro="SCALAFLOW_MINING_URL/CRIS_OS_MINING_SECRET não configurados -- mineração não solicitada.",
        )

    import requests

    payload = {"source": source, "term": term.strip(), "limit": limit}

    try:
        resposta = requests.post(
            settings.SCALAFLOW_MINING_URL, json=payload, headers=_headers(),
            timeout=settings.SCALAFLOW_MINING_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        logger.warning(
            "=== [SCALAFLOW_MINING] Falha de rede ao solicitar mineração (%s/%s): %s ===",
            source, term, exc.__class__.__name__,
        )
        return ResultadoMineracao(
            ok=False, status="TRANSIENT_ERROR", retryable=True,
            erro=f"Falha de rede ao solicitar mineração: {exc.__class__.__name__}",
        )

    if resposta.status_code == 400:
        return ResultadoMineracao(ok=False, status="INVALID_REQUEST", retryable=False, http_status=400, erro="ScalaFlow rejeitou a requisição (HTTP 400).")

    if resposta.status_code in (401, 403):
        # NUNCA loga/expõe o secret -- só o fato de que foi rejeitado.
        logger.warning("=== [SCALAFLOW_MINING] Autenticação rejeitada pelo ScalaFlow (HTTP %s) -- verifique CRIS_OS_MINING_SECRET ===", resposta.status_code)
        return ResultadoMineracao(
            ok=False, status="AUTH_ERROR", retryable=False, http_status=resposta.status_code,
            erro="Autenticação/configuração rejeitada pelo ScalaFlow -- não é retryable.",
        )

    if resposta.status_code == 429:
        return ResultadoMineracao(
            ok=False, status="RATE_LIMITED", retryable=False, http_status=429,
            erro="Rate limit do ScalaFlow atingido -- aguarde antes de solicitar de novo (nenhuma tentativa automática).",
        )

    if resposta.status_code >= 500:
        return ResultadoMineracao(
            ok=False, status="TRANSIENT_ERROR", retryable=True, http_status=resposta.status_code,
            erro=f"ScalaFlow indisponível (HTTP {resposta.status_code}).",
        )

    if resposta.status_code >= 400:
        return ResultadoMineracao(
            ok=False, status="INVALID_REQUEST", retryable=False, http_status=resposta.status_code,
            erro=f"ScalaFlow rejeitou a requisição (HTTP {resposta.status_code}).",
        )

    try:
        corpo = resposta.json()
    except ValueError:
        corpo = {}
    return ResultadoMineracao(
        ok=True, status="SUCCESS", retryable=False, http_status=resposta.status_code,
        dados=corpo if isinstance(corpo, dict) else {},
    )
