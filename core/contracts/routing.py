"""
Portas de ROTEAMENTO — como o Orquestrador escolhe entre candidatos.

Um `RouteCandidate` é qualquer opção roteável (um domínio, um agente, uma skill
ou uma tool), com os metadados que permitem escolhê-lo. Um `RouteScorer` rankeia
esses candidatos para uma mensagem — o mesmo contrato serve para keyword, léxico
ou (futuro) embedding, sem mudar o `IntentRouter`.

Esta é a fronteira que a Onda 3 introduz (aditiva): o `IntentRouter` passa a
montar candidatos e delegar a escolha a scorers plugáveis. NÃO implementa nenhum
scorer aqui — só o contrato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from core.domain.execution import ExecutionType


@dataclass
class RouteCandidate:
    """Uma opção que o roteador pode escolher (domínio/agente/skill/tool)."""

    name: str
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    # None = domínio (nível intermediário); senão = alvo (agent/skill/tool).
    type: ExecutionType | None = None


@dataclass
class ScoredRoute:
    """Um candidato com sua pontuação (maior = melhor)."""

    candidate: RouteCandidate
    score: float


@runtime_checkable
class RouteScorer(Protocol):
    """Rankeia candidatos para uma mensagem — do melhor para o pior."""

    def score(self, message: str, candidates: list[RouteCandidate]) -> list[ScoredRoute]:
        """
        Devolve os candidatos rankeados (score >= 0, decrescente).

        Sem candidatos -> []. O roteador decide um limiar e a precedência entre
        scorers; este contrato só ordena.
        """
        ...
