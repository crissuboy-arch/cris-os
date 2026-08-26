"""
Testes da ferramenta `prospector` no catalogo do Tool Executor e do fallback
de IA (ProspectorLLM: AIsa primeiro, roteador do CRIS OS depois).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from tools.executor import create_executor  # noqa: E402
from tools.executor_tools import get_tool_catalog  # noqa: E402


def test_catalogo_inclui_prospector():
    nomes = {t["name"] for t in get_tool_catalog()}
    assert "prospector" in nomes
    assert len(get_tool_catalog()) == 10


def test_schema_prospector():
    tool = next(t for t in get_tool_catalog() if t["name"] == "prospector")
    schema = tool["schema"]()
    assert schema["type"] == "object"
    assert "action" in schema["properties"]
    assert "required" in schema and schema["required"] == ["action"]


def test_tool_prospector_status():
    executor = create_executor()
    out = executor.execute("prospector", {"action": "status"})
    assert "[PROSPECTOR] Status:" in out
    assert '"modo"' in out


def test_tool_prospector_sem_nicho():
    executor = create_executor()
    out = executor.execute("prospector", {"action": "prospectar"})
    assert "informe 'nicho' e 'cidade'" in out


def test_tool_prospector_acao_desconhecida():
    executor = create_executor()
    out = executor.execute("prospector", {"action": "zzz"})
    assert "Acao desconhecida" in out
