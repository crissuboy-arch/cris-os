"""
Onda 2 / B5 — ExecutionResult (DTO universal).
Prova a convergência: AgentResult e SkillResult -> ExecutionResult, idempotência
de `of()` e tolerância a dict/valor cru.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.domain.execution import ExecutionType  # noqa: E402
from core.models import AgentResult, ExecutionResult, SkillResult  # noqa: E402


def test_from_agent():
    r = ExecutionResult.from_agent(AgentResult(agent="financeiro", output="pronto",
                                               success=True, metadata={"k": 1}))
    assert r.source == "financeiro" and r.type == ExecutionType.AGENT
    assert r.output == "pronto" and r.success and r.data == {"k": 1}


def test_from_skill_ok_e_erro():
    ok = ExecutionResult.from_skill(SkillResult(skill="session-handoff", ok=True,
                                                output="Sessão empacotada", data={"x": 1}))
    assert ok.source == "session-handoff" and ok.type == ExecutionType.SKILL
    assert ok.output == "Sessão empacotada" and ok.success and ok.data == {"x": 1}

    err = ExecutionResult.from_skill(SkillResult(skill="s", ok=False, error="falhou"))
    assert err.success is False and err.output == "falhou" and err.error == "falhou"


def test_of_idempotente_e_tolerante():
    er = ExecutionResult(source="x", output="oi")
    assert ExecutionResult.of(er) is er  # idempotente
    # converge AgentResult e SkillResult
    assert ExecutionResult.of(AgentResult(agent="a", output="o")).type == ExecutionType.AGENT
    assert ExecutionResult.of(SkillResult(skill="s", output="o")).type == ExecutionType.SKILL
    # valor cru
    assert ExecutionResult.of("texto", source="t").output == "texto"


if __name__ == "__main__":
    test_from_agent()
    test_from_skill_ok_e_erro()
    test_of_idempotente_e_tolerante()
    print("OK - test_execution_result")
