"""
Testes do agente Prospector — descoberta, manifest e SYSTEM.md.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agents.loader import carregar_agentes  # noqa: E402


class _LLM:
    def is_alive(self):
        return True

    def chat(self, messages, tools=None):
        return None


def test_agente_prospector_registrado():
    agentes = carregar_agentes(RAIZ / "agents", llm=_LLM())
    nomes = {a.name for a in agentes}
    assert "prospector" in nomes


def test_agente_prospector_campos():
    ag = next(a for a in carregar_agentes(RAIZ / "agents", llm=_LLM())
              if a.name == "prospector")
    assert ag.domain == "vendas"
    assert ag.status == "draft"
    assert "prospectar" in ag.keywords
    assert ag.tools_allowed == ["prospector"]


def test_agente_prospector_system_md():
    path = RAIZ / "agents" / "prospector" / "SYSTEM.md"
    assert path.exists()
    texto = path.read_text(encoding="utf-8")
    assert "Máquina de Leads" in texto
    assert "delega" in texto


def test_contagem_agentes_com_prospector():
    agentes = carregar_agentes(RAIZ / "agents", llm=_LLM())
    assert len(agentes) == 13
