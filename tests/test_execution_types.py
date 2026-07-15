"""
Onda 2 / B5 — ExecutionType (tipo forte) + ExecutionStep (entrada universal).
Verifica membros, serialização como string e os campos reservados do step.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.domain.execution import ExecutionType  # noqa: E402
from core.models import ExecutionStep  # noqa: E402


def test_membros_e_string():
    for nome in ("AGENT", "SKILL", "TOOL", "MCP", "PLANNER", "WORKFLOW"):
        assert hasattr(ExecutionType, nome)
    # herda de str -> serializa como "agent"
    assert ExecutionType.AGENT == "agent"
    assert f"{ExecutionType.SKILL}" == "skill"
    assert str(ExecutionType.TOOL) == "tool"


def test_execution_step_defaults():
    s = ExecutionStep(name="x")
    assert s.type == ExecutionType.AGENT and s.instruction == "" and s.payload == {}
    # campos reservados p/ workflows futuros
    assert s.priority == 0 and s.parallel is False and s.depends_on == [] and s.timeout is None


def test_execution_step_skill():
    s = ExecutionStep(name="session-handoff", type=ExecutionType.SKILL, payload={"action": "save"})
    assert s.type == ExecutionType.SKILL and s.payload["action"] == "save"


if __name__ == "__main__":
    test_membros_e_string()
    test_execution_step_defaults()
    test_execution_step_skill()
    print("OK - test_execution_types")
