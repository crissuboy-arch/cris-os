"""
Testes do AgentRuntime + HelloAgent.

Testa:
  - AgentRuntime.execute() com HelloAgent
  - HelloAgent.resolve_capability()
  - AgentRuntime com plugin_loader real (cris_demo carregado)
  - Erro quando agente nao existe
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from agents.hello_agent.hello_agent import HelloAgent
from core.agent.runtime import AgentRuntime
from core.contracts.agent import AgentContext
from core.models import AgentResult, Task


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def hello_agent():
    return HelloAgent()


@pytest.fixture
def mock_registry(hello_agent):
    reg = MagicMock()
    reg.get.return_value = hello_agent
    return reg


@pytest.fixture
def mock_core_api():
    api = MagicMock()
    return api


@pytest.fixture
def mock_event_bus():
    return MagicMock()


# ======================================================================
# HelloAgent: resolucao de capabilities
# ======================================================================


class TestHelloAgentResolution:
    def test_resolve_notes_create_pt(self, hello_agent):
        cap, params = hello_agent._resolve_capability("criar uma nota sobre reuniao")
        assert cap == "notes.create"
        assert params["title"] == "Nota do HelloAgent"

    def test_resolve_notes_create_en(self, hello_agent):
        cap, params = hello_agent._resolve_capability("create a new note")
        assert cap == "notes.create"

    def test_resolve_demo_echo(self, hello_agent):
        cap, params = hello_agent._resolve_capability("echo Hello World")
        assert cap == "demo.echo"
        assert params["message"] == "Hello World"

    def test_resolve_demo_echo_fallback(self, hello_agent):
        cap, params = hello_agent._resolve_capability("alguma coisa qualquer")
        assert cap == "demo.echo"
        assert "alguma coisa qualquer" in params["message"]


# ======================================================================
# HelloAgent: execucao com CoreAPI mockado
# ======================================================================


class TestHelloAgentExecution:
    def test_notes_create_success(self, hello_agent, mock_core_api):
        mock_core_api.execute.return_value = {
            "success": True,
            "id": "abc123",
            "title": "Nota do HelloAgent",
        }
        context = AgentContext(session="test", core_api=mock_core_api)
        task = Task(agent="hello_agent", instruction="criar uma nota de teste")

        result = hello_agent.handle(task, context)

        assert result.success is True
        assert "Nota criada" in result.output
        assert "abc123" in result.output
        mock_core_api.execute.assert_called_once_with(
            "notes.create",
            {"title": "Nota do HelloAgent", "content": "criar uma nota de teste"},
        )

    def test_demo_echo_success(self, hello_agent, mock_core_api):
        mock_core_api.execute.return_value = {
            "success": True,
            "echo": "teste echo",
        }
        context = AgentContext(session="test", core_api=mock_core_api)
        task = Task(agent="hello_agent", instruction="echo teste echo")

        result = hello_agent.handle(task, context)

        assert result.success is True
        assert "teste echo" in result.output

    def test_capability_failure(self, hello_agent, mock_core_api):
        mock_core_api.execute.return_value = {
            "success": False,
            "error": "algo deu errado",
        }
        context = AgentContext(session="test", core_api=mock_core_api)
        task = Task(agent="hello_agent", instruction="criar uma nota")

        result = hello_agent.handle(task, context)

        assert result.success is False
        assert "algo deu errado" in result.output

    def test_no_core_api(self, hello_agent):
        context = AgentContext(session="test")
        task = Task(agent="hello_agent", instruction="criar uma nota")

        result = hello_agent.handle(task, context)

        assert result.success is True
        assert "Nao ha CoreAPI" in result.output


# ======================================================================
# AgentRuntime
# ======================================================================


class TestAgentRuntime:
    def test_execute_success(self, mock_registry, mock_core_api, mock_event_bus):
        mock_core_api.execute.return_value = {
            "success": True,
            "id": "abc",
            "title": "Nota do HelloAgent",
        }

        def factory(_name):
            return mock_core_api

        runtime = AgentRuntime(
            agent_registry=mock_registry,
            core_api_factory=factory,
            event_bus=mock_event_bus,
        )
        result = runtime.execute(
            agent_name="hello_agent",
            instruction="criar uma nota de boas-vindas",
            session="test-session",
            correlation_id="corr-001",
        )

        assert result.success is True
        assert "Nota criada" in result.output
        assert mock_event_bus.publish.call_count >= 2

    def test_execute_agent_not_found(self, mock_event_bus):
        reg = MagicMock()
        reg.get.return_value = None

        runtime = AgentRuntime(
            agent_registry=reg,
            event_bus=mock_event_bus,
        )
        result = runtime.execute(
            agent_name="nonexistent",
            instruction="teste",
        )

        assert result.success is False
        assert "nao encontrado" in result.output

    def test_execute_agent_error(self, mock_registry, mock_event_bus):
        broken_agent = MagicMock()
        broken_agent.handle.side_effect = RuntimeError("crash!")
        broken_agent.name = "broken"
        mock_registry.get.return_value = broken_agent

        runtime = AgentRuntime(
            agent_registry=mock_registry,
            event_bus=mock_event_bus,
        )
        result = runtime.execute(
            agent_name="broken",
            instruction="causar erro",
        )

        assert result.success is False
        assert "crash!" in result.output

    def test_execute_no_handle_method(self, mock_registry, mock_event_bus):
        """Agente sem handle() deve gerar erro."""
        invalid_agent = object()
        mock_registry.get.return_value = invalid_agent

        runtime = AgentRuntime(
            agent_registry=mock_registry,
            event_bus=mock_event_bus,
        )
        result = runtime.execute(
            agent_name="no_handle",
            instruction="teste",
        )

        assert result.success is False
        assert "nao implementa handle" in result.output.lower() or "erro" in result.output.lower()


# ======================================================================
# Integracao: AgentRuntime + PluginLoader real com plugin demo
# ======================================================================


class TestAgentRuntimeWithRealPlugin:
    @pytest.fixture
    def runtime_with_demo(self):
        from core.capability import CapabilityRegistry
        from core.events import InProcessEventBus, InMemoryEventLog
        from core.plugins.loader import PluginLoader

        event_log = InMemoryEventLog()
        registry = CapabilityRegistry()
        event_bus = InProcessEventBus(event_log=event_log)
        loader = PluginLoader(registry=registry, event_bus=event_bus, plugins_dir=str(
            Path(__file__).resolve().parent.parent.parent / "plugins"
        ))
        loaded = loader.load_all()
        loader.start_all()

        hello = HelloAgent()
        agent_reg = MagicMock()
        agent_reg.get.return_value = hello

        runtime = AgentRuntime(
            agent_registry=agent_reg,
            plugin_loader=loader,
            event_bus=event_bus,
        )
        return runtime, loaded

    def test_echo_with_real_demo_plugin(self, runtime_with_demo):
        runtime, loaded = runtime_with_demo
        assert "cris-demo" in loaded, "Plugin demo deve estar carregado"

        result = runtime.execute(
            agent_name="hello_agent",
            instruction="echo oi mundo",
            session="test",
            correlation_id="demo-test",
        )

        assert result.success is True
        assert "oi mundo" in result.output or "Eco" in result.output

    def test_notes_create_with_real_notes_plugin(self, runtime_with_demo):
        runtime, loaded = runtime_with_demo
        assert "cris-notes" in loaded, "Plugin notes deve estar carregado"

        result = runtime.execute(
            agent_name="hello_agent",
            instruction="criar uma nota de teste",
            session="test",
            correlation_id="notes-test",
        )

        assert result.success is True
        assert "Nota criada" in result.output