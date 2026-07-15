"""
Onda 3 / B0 — contratos de roteamento (RouteCandidate / ScoredRoute / RouteScorer).

Sem implementar scorer real (isso é B1/B2). Valida a FORMA do contrato:
defaults do candidato, conformidade estrutural do scorer e o shape do ranking.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.contracts.routing import RouteCandidate, RouteScorer, ScoredRoute  # noqa: E402
from core.domain.execution import ExecutionType  # noqa: E402


class FakeScorer:
    """Scorer-fake de TESTE (não é implementação de produção): conta keywords."""

    def score(self, message, candidates):
        m = (message or "").lower()
        ranked = [ScoredRoute(c, float(sum(k.lower() in m for k in c.keywords))) for c in candidates]
        return sorted(ranked, key=lambda r: r.score, reverse=True)


def test_candidate_defaults():
    c = RouteCandidate(name="session-handoff")
    assert c.type is None and c.keywords == [] and c.examples == [] and c.description == ""


def test_scorer_cumpre_a_porta():
    assert isinstance(FakeScorer(), RouteScorer)


def test_ranking_shape_e_ordem():
    cands = [
        RouteCandidate("secretary", keywords=["agenda"], type=ExecutionType.AGENT),
        RouteCandidate("session-handoff", keywords=["handoff"], type=ExecutionType.SKILL),
    ]
    ranked = FakeScorer().score("faça o handoff desta sessão", cands)
    assert all(isinstance(r, ScoredRoute) for r in ranked)
    assert ranked[0].candidate.name == "session-handoff" and ranked[0].score == 1.0
    assert ranked[-1].candidate.name == "secretary" and ranked[-1].score == 0.0


def test_sem_candidatos():
    assert FakeScorer().score("qualquer", []) == []


if __name__ == "__main__":
    test_candidate_defaults()
    test_scorer_cumpre_a_porta()
    test_ranking_shape_e_ordem()
    test_sem_candidatos()
    print("OK - test_routing")
