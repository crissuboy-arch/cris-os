"""
Caracterização (Onda 1 / B0) — AgentRegistry e ToolRegistry.
Fixa o comportamento atual antes das refatorações de unificação (N2/B3).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.registry import AgentRegistry, ToolRegistry  # noqa: E402


class _Unit:
    def __init__(self, name):
        self.name = name


def test_agent_registry_crud():
    r = AgentRegistry()
    a = _Unit("alpha")
    r.register(a)
    assert r.get("alpha") is a
    assert r.get("missing") is None
    assert r.all() == [a]
    assert r.names() == ["alpha"]


def test_tool_registry_crud():
    r = ToolRegistry()
    t = _Unit("calc")
    r.register(t)
    assert r.get("calc") is t
    assert r.all() == [t]


if __name__ == "__main__":
    test_agent_registry_crud()
    test_tool_registry_crud()
    print("OK - test_registries")
