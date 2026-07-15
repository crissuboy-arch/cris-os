"""
QualitySupervisor — SUPERVISIONA a qualidade.

Responsabilidade única: receber o ExecutionReport, avaliar a qualidade dos
resultados, conferir se o Objective foi atingido e emitir um QualityVerdict. Se
reprovar, pede nova execução (com instruções de refação). **Somente respostas
aprovadas chegam à Cris.**

Eventos que publicará (via Event Bus):
  QUALITY_EVALUATED · QUALITY_APPROVED · QUALITY_REJECTED · REEXECUTION_REQUESTED

⚠️ ESQUELETO: `review()` levanta NotImplementedError de propósito.
"""

from __future__ import annotations

from core.domain.planning import ExecutionReport, Plan, QualityVerdict


class QualitySupervisor:
    def __init__(self, llm, event_bus, min_score: float = 0.7) -> None:
        self.llm = llm
        self.event_bus = event_bus
        self.min_score = min_score

    def review(self, plan: Plan, report: ExecutionReport) -> QualityVerdict:
        """
        TODO (pós-revisão):
          - avaliar cada resultado x o objetivo (LLM como juiz + regras) -> score;
          - publicar QUALITY_EVALUATED;
          - se score >= min_score e sem falhas críticas -> approved=True
              -> publicar QUALITY_APPROVED;
          - senão -> approved=False, revision_request com o que melhorar
              -> publicar QUALITY_REJECTED + REEXECUTION_REQUESTED;
          - devolver o QualityVerdict.
        """
        raise NotImplementedError(
            "QualitySupervisor.review ainda não implementado (camada de cognição em "
            "evolução arquitetural)."
        )
