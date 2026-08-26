"""
Testes do Tool Executor + integracao com BaseAgent.

Cobre:
  - Executor com catalogo de 10 ferramentas
  - Execucao de cada ferramenta (github, files, terminal, sqlite, search, browser, docgen, http, prospector)
  - Filtros allowed/forbidden
  - Schemas OpenAI function-calling
  - Loop tool-calling no BaseAgent
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from agents.base import BaseAgent
from core.contracts.llm import LLMResponse, ToolCall
from tools.executor import ToolExecutor, create_executor
from tools.executor_tools import get_tool_catalog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FakeLLMTools:
    """LLM fake que retorna tool_calls no primeiro turno e texto no segundo."""

    def __init__(self, tool_name="files", tool_args=None, final="resposta final apos ferramenta"):
        self.tool_name = tool_name
        self.tool_args = tool_args or {"action": "list", "path": "."}
        self.final = final
        self.call_count = 0

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse, ToolCall
        self.call_count += 1
        if self.call_count == 1:
            return LLMResponse(
                content="",
                tool_calls=[ToolCall(name=self.tool_name, arguments=self.tool_args)],
            )
        return LLMResponse(content=self.final)

    def is_alive(self):
        return True


class FakeLLMNoTools:
    """LLM fake que nunca retorna tool_calls."""

    def chat(self, messages, tools=None):
        return LLMResponse(content="resposta direta sem ferramentas")

    def is_alive(self):
        return True


class FakeLLMToolError:
    """LLM fake que retorna tool_calls ate o limite para testar cutoff."""

    def __init__(self):
        self.count = 0

    def chat(self, messages, tools=None):
        self.count += 1
        return LLMResponse(
            content="",
            tool_calls=[ToolCall(name="files", arguments={"action": "list", "path": "."})],
        )

    def is_alive(self):
        return True


# ---------------------------------------------------------------------------
# ToolExecutor basico
# ---------------------------------------------------------------------------


def test_executor_cria():
    executor = create_executor()
    assert len(executor.list_tools()) == 10
    assert "github" in executor.list_tools()
    assert "files" in executor.list_tools()
    assert "terminal" in executor.list_tools()
    assert "sqlite" in executor.list_tools()
    assert "browser" in executor.list_tools()
    assert "search" in executor.list_tools()
    assert "docgen" in executor.list_tools()
    assert "imggen" in executor.list_tools()
    assert "http" in executor.list_tools()
    assert "prospector" in executor.list_tools()


def test_executor_ferramenta_inexistente():
    executor = create_executor()
    resultado = executor.execute("nao_existe")
    assert "nao encontrada" in resultado


def test_executor_schemas():
    executor = create_executor()
    schemas = executor.get_schemas()
    assert len(schemas) == 10
    for s in schemas:
        assert s["type"] == "function"
        f = s["function"]
        assert "name" in f
        assert "description" in f
        assert "parameters" in f
        assert f["parameters"]["type"] == "object"
        assert "properties" in f["parameters"]


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------


def test_executor_filter_allowed():
    executor = create_executor()
    schemas = executor.get_schemas_filtered(allowed=["files", "terminal", "github"])
    nomes = {s["function"]["name"] for s in schemas}
    assert nomes == {"files", "terminal", "github"}


def test_executor_filter_forbidden():
    executor = create_executor()
    schemas = executor.get_schemas_filtered(forbidden=["terminal", "browser", "http"])
    nomes = {s["function"]["name"] for s in schemas}
    assert "terminal" not in nomes
    assert "browser" not in nomes
    assert "http" not in nomes
    assert "github" in nomes
    assert "files" in nomes


def test_executor_filter_allowed_and_forbidden():
    executor = create_executor()
    schemas = executor.get_schemas_filtered(allowed=["files", "terminal"], forbidden=["terminal"])
    nomes = {s["function"]["name"] for s in schemas}
    assert nomes == {"files"}


# ---------------------------------------------------------------------------
# Ferramentas individuais
# ---------------------------------------------------------------------------


def test_github_status(tmp_path):
    executor = create_executor()
    resultado = executor.execute("github", action="status", path=str(tmp_path))
    assert resultado.startswith("[GITHUB]")
    assert "status" in resultado


def test_files_write_read(tmp_path):
    executor = create_executor()
    arquivo = tmp_path / "teste.txt"
    resultado = executor.execute("files", action="write", path=str(arquivo), content="conteudo de teste")
    assert "[FILES] Arquivo criado" in resultado
    assert arquivo.exists()

    resultado = executor.execute("files", action="read", path=str(arquivo))
    assert "[FILES]" in resultado
    assert "conteudo de teste" in resultado


def test_files_list(tmp_path):
    executor = create_executor()
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    resultado = executor.execute("files", action="list", path=str(tmp_path))
    assert "[FILES]" in resultado
    assert "a.txt" in resultado
    assert "b.txt" in resultado


def test_files_delete(tmp_path):
    executor = create_executor()
    arquivo = tmp_path / "del.txt"
    arquivo.write_text("delete me")
    resultado = executor.execute("files", action="delete", path=str(arquivo))
    assert "[FILES] Removido" in resultado
    assert not arquivo.exists()


def test_terminal_echo():
    executor = create_executor()
    resultado = executor.execute("terminal", command="echo hello world")
    assert "[TERMINAL]" in resultado
    assert "hello world" in resultado


def test_terminal_falha():
    executor = create_executor()
    resultado = executor.execute("terminal", command="comando_que_nao_existe_12345")
    assert "[TERMINAL]" in resultado


def test_sqlite_query():
    executor = create_executor()
    db_path = RAIZ / "data" / "cris_os.db"
    if not db_path.exists():
        pytest.skip("Banco de dados nao encontrado. Execute 'python main.py --seed' primeiro.")
    resultado = executor.execute("sqlite", action="query", sql="SELECT name FROM sqlite_master WHERE type='table' LIMIT 5", db_path=str(db_path))
    assert "[SQLITE]" in resultado
    assert len(resultado) > 20


def test_search():
    executor = create_executor()
    resultado = executor.execute("search", query="Python programming language", max_results=3)
    assert "[SEARCH]" in resultado
    assert len(resultado) > 30


def test_browser():
    executor = create_executor()
    resultado = executor.execute("browser", url="https://example.com", extract="title")
    assert "[BROWSER]" in resultado
    assert "Example" in resultado or "Dominio" in resultado


def test_docgen():
    executor = create_executor()
    resultado = executor.execute("docgen", title="Teste", content="Conteudo de teste")
    assert "[DOCGEN]" in resultado
    assert "# Teste" in resultado


def test_docgen_com_arquivo(tmp_path):
    executor = create_executor()
    arquivo = tmp_path / "doc.md"
    resultado = executor.execute("docgen", title="Teste", content="# Conteudo", output_path=str(arquivo))
    assert "[DOCGEN] Documento salvo" in resultado
    assert arquivo.exists()


def test_imggen():
    executor = create_executor()
    resultado = executor.execute("imggen", prompt="Um gato astronauta", size="512x512")
    assert "[IMGGEN]" in resultado
    assert "Prompt recebido" in resultado


def test_http():
    executor = create_executor()
    resultado = executor.execute("http", url="https://httpbin.org/get", method="GET", timeout=15)
    assert "[HTTP]" in resultado


# ---------------------------------------------------------------------------
# BaseAgent + Tool loop
# ---------------------------------------------------------------------------


def test_agent_sem_tools_roda_normal():
    """Agente sem tool_executor funciona como antes."""
    agente = BaseAgent("teste", "Teste", "Seja util.", FakeLLMNoTools())
    from core.models import Task
    from core.contracts.agent import AgentContext
    ctx = AgentContext(session="test_session")
    resultado = agente.handle(Task(agent="teste", instruction="ola"), ctx)
    assert resultado.success
    assert "resposta direta" in resultado.output


def test_agent_tool_loop_executa_ferramenta():
    """Agente com tool_executor executa ferramenta e retorna texto final."""
    executor = create_executor()
    agente = BaseAgent("teste", "Teste", "Seja util.",
                       FakeLLMTools(tool_name="terminal", tool_args={"command": "echo tool_loop_ok"}),
                       tool_executor=executor)
    from core.models import Task
    from core.contracts.agent import AgentContext
    ctx = AgentContext(session="test_session")
    resultado = agente.handle(Task(agent="teste", instruction="roda comando"), ctx)
    assert resultado.success
    assert "resposta final apos ferramenta" in resultado.output


def test_agent_tool_loop_respeita_filter_allowed():
    """Agente com tools_allowed so expoe as ferramentas permitidas."""
    executor = create_executor()
    agente = BaseAgent("teste", "Teste", "Seja util.",
                       FakeLLMTools(tool_name="terminal", tool_args={"command": "echo ok"}),
                       tool_executor=executor,
                       tools_allowed=["files"])
    schemas = agente._ferramentas_schemas()
    nomes = {s["function"]["name"] for s in schemas}
    assert nomes == {"files"}


def test_agent_tool_loop_respeita_filter_forbidden():
    """Agente com tools_forbidden esconde ferramentas proibidas."""
    executor = create_executor()
    agente = BaseAgent("teste", "Teste", "Seja util.",
                       FakeLLMTools(tool_name="terminal", tool_args={"command": "echo ok"}),
                       tool_executor=executor,
                       tools_forbidden=["terminal", "browser", "sqlite", "search"])
    schemas = agente._ferramentas_schemas()
    nomes = {s["function"]["name"] for s in schemas}
    assert "terminal" not in nomes
    assert "files" in nomes


def test_agent_tool_loop_limite_turnos():
    """Agente que chama ferramentas sem parar atinge o limite."""
    executor = create_executor()
    agente = BaseAgent("teste", "Teste", "Seja util.",
                       FakeLLMToolError(),
                       tool_executor=executor)
    from core.models import Task
    from core.contracts.agent import AgentContext
    ctx = AgentContext(session="test_session")
    resultado = agente.handle(Task(agent="teste", instruction="loop infinito"), ctx)
    assert "limite" in resultado.output
    assert len(resultado.output) > 10


# ---------------------------------------------------------------------------
# Loader com tool_executor
# ---------------------------------------------------------------------------


def test_loader_passa_tool_executor():
    """Verifica que carregar_agentes passa tool_executor para os agentes."""
    from agents.loader import carregar_agentes
    executor = create_executor()

    class FakeLLMLoader:
        def chat(self, messages, tools=None):
            return LLMResponse(content="ok")
        def is_alive(self):
            return True

    agentes = carregar_agentes(RAIZ / "agents", FakeLLMLoader(), tool_executor=executor)
    for a in agentes:
        assert a.tool_executor is executor


# ---------------------------------------------------------------------------
# Execucao direta
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_executor_cria()
    test_executor_ferramenta_inexistente()
    test_executor_schemas()
    test_executor_filter_allowed()
    test_executor_filter_forbidden()
    test_executor_filter_allowed_and_forbidden()
    test_terminal_echo()
    test_terminal_falha()
    test_files_write_read(Path(RAIZ / "tmp_test"))
    test_files_list(Path(RAIZ / "tmp_test"))
    test_files_delete(Path(RAIZ / "tmp_test" / "del.txt"))
    test_sqlite_query()
    test_search()
    test_browser()
    test_docgen()
    test_docgen_com_arquivo(Path(RAIZ / "tmp_test"))
    test_imggen()
    test_http()
    test_agent_sem_tools_roda_normal()
    test_agent_tool_loop_executa_ferramenta()
    test_agent_tool_loop_respeita_filter_allowed()
    test_agent_tool_loop_respeita_filter_forbidden()
    test_agent_tool_loop_limite_turnos()
    test_loader_passa_tool_executor()
    print("\n=== TODOS OS TESTES DO TOOL EXECUTOR PASSARAM ===")
