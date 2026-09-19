"""
Approval Gate central (Fase 6) -- funcao UNICA de reconhecimento de
aprovacao/rejeicao humana explicita, para NAO espalhar "if 'aprovado' in
mensagem" por cada novo modulo (pedido explicito da Fase 6).

Fases anteriores (Product Architect, Business Builder, Paid Traffic
Architect) ja tinham seu proprio conjunto local de palavras/frases -- NAO
foram retrofitadas para usar este gate (fora de escopo da Fase 6: "nao
reestruture o sistema"). Todo modulo NOVO da Fase 6 (Campaign Executor) usa
este gate central.

IMPORTANTE: este gate autoriza SOMENTE mudanca de estado INTERNO (ex.:
`CampaignSpec.status` DRAFT -> APPROVED) -- NUNCA autoriza nenhuma execucao
externa. Nesta fase nao existe nenhum caminho de codigo que transforme uma
aprovacao (`eh_aprovacao` == True) em chamada de API externa, publicacao de
campanha ou gasto real.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

PALAVRAS_APROVACAO = frozenset({
    "aprovado", "aprovada", "aprovo", "autorizado", "autorizo",
    "confirmado", "confirmo",
})
FRASES_APROVACAO = ("pode criar", "pode seguir", "pode comecar", "pode começar")

PALAVRAS_REJEICAO = frozenset({"rejeitado", "rejeitada", "rejeito"})
FRASES_REJEICAO = ("nao gostei", "não gostei", "quero outro", "outro plano")


def _contains_any(texto: str, palavras: frozenset[str], frases: tuple = ()) -> bool:
    texto_lower = texto.lower()
    tokens = set(texto_lower.split())
    if tokens & palavras:
        return True
    if any(p in texto_lower for p in palavras):
        return True
    return any(f in texto_lower for f in frases)


def eh_aprovacao(texto: str) -> bool:
    """True se `texto` contem uma aprovacao humana EXPLICITA (conjunto
    fechado de palavras/frases) -- frases de consulta ("esta bom?", "qual o
    status?") NUNCA contam como aprovacao."""
    return _contains_any(texto or "", PALAVRAS_APROVACAO, FRASES_APROVACAO)


def eh_rejeicao(texto: str) -> bool:
    return _contains_any(texto or "", PALAVRAS_REJEICAO, FRASES_REJEICAO)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuthorizationRecord:
    """
    Metadado de UMA autorizacao -- pronto para quando uma fase futura
    precisar de auditoria completa (quem aprovou o que, quando, para qual
    plataforma/campanha). Nesta fase, registrar um `AuthorizationRecord`
    autoriza SOMENTE uma mudanca de estado INTERNO -- nunca dispara, por si
    so, nenhuma execucao externa (isso continua exigindo um conector real,
    que nao existe nesta fase -- ver `core/campaign_platform_adapter.py`).
    """

    project_id: str
    action: str  # ex.: "CAMPAIGN_SPEC_APPROVED"
    platform: str | None = None
    campaign_id: str | None = None
    requested_at: str = field(default_factory=_agora)
    approved_at: str | None = None
    approved_by: str | None = None
