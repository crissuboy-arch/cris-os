"""
Caracterização (Onda 1 / B0) — carregar_agentes.
Fixa: 11 agentes, pula 'orchestrator', escopo/status presentes.
Protege a inversão de dependência (N4/B4) e a unificação de descoberta (N2/B3).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agents.loader import carregar_agentes  # noqa: E402


class _LLM:
    """Stub: o loader só guarda o llm; não o chama."""

    def is_alive(self):
        return True

    def chat(self, messages, tools=None):
        return None


def test_loads_11_skips_orchestrator():
    agentes = carregar_agentes(RAIZ / "agents", llm=_LLM())
    nomes = {a.name for a in agentes}
    assert "secretary" in nomes
    assert "orchestrator" not in nomes
    assert len(agentes) == 11


def test_agents_have_scope_and_status():
    agentes = carregar_agentes(RAIZ / "agents", llm=_LLM())
    sec = next(a for a in agentes if a.name == "secretary")
    assert hasattr(sec, "projects") and hasattr(sec, "status")
    assert sec.status == "production"


def test_agents_load_domain():
    by_name = {a.name: a for a in carregar_agentes(RAIZ / "agents", llm=_LLM())}
    assert by_name["secretary"].domain == "pessoal"
    assert by_name["zavix"].domain == "zavix"
    assert by_name["financeiro"].domain == "financeiro"


if __name__ == "__main__":
    test_loads_11_skips_orchestrator()
    test_agents_have_scope_and_status()
    test_agents_load_domain()
    print("OK - test_loader")
