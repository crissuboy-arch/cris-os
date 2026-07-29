"""Demonstracao do AgentRuntime + HelloAgent.

Uso:
    python examples/agent_runtime_demo.py

Pre-requisito: plugins carregados (demo, cris_notes, etc.)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.agent import AgentRuntime
from core.capability import CapabilityRegistry
from core.events import InProcessEventBus, InMemoryEventLog
from core.plugins.loader import PluginLoader


def _setup_hello_agent(loader):
    """Carrega HelloAgent como agente no registry."""
    from agents.hello_agent.hello_agent import HelloAgent

    hello = HelloAgent()

    agent_reg = MagicMock()
    agent_reg.get.return_value = hello
    agent_reg.get_all = lambda: [hello]
    return agent_reg


def main():
    print("=" * 60)
    print("AgentRuntime + HelloAgent — Demonstracao")
    print("=" * 60)

    # --- Setup ---
    registry = CapabilityRegistry()
    event_log = InMemoryEventLog()
    event_bus = InProcessEventBus(event_log=event_log)

    loader = PluginLoader(
        registry=registry,
        event_bus=event_bus,
        plugins_dir=str(RAIZ / "plugins"),
    )
    loaded = loader.load_all()
    loader.start_all()

    print(f"\nPlugins carregados: {list(loaded.keys())}")

    agent_reg = _setup_hello_agent(loader)

    runtime = AgentRuntime(
        agent_registry=agent_reg,
        plugin_loader=loader,
        event_bus=event_bus,
    )

    # --- Teste 1: echo ---
    print("\n--- Teste 1: echo via demo.echo ---")
    resultado = runtime.execute(
        agent_name="hello_agent",
        instruction="echo Olá CRIS OS!",
        session="demo-session",
        correlation_id="demo-001",
    )
    print(f"  Resultado: {resultado.output}")
    print(f"  Sucesso: {resultado.success}")

    # --- Teste 2: notas (deve falhar se cris_notes nao estiver carregado) ---
    print("\n--- Teste 2: criar nota (cris_notes) ---")
    resultado = runtime.execute(
        agent_name="hello_agent",
        instruction="criar uma nota de boas-vindas",
        session="demo-session",
        correlation_id="demo-002",
    )
    print(f"  Resultado: {resultado.output}")
    print(f"  Sucesso: {resultado.success}")

    # --- Teste 3: agente inexistente ---
    print("\n--- Teste 3: agente inexistente ---")
    resultado = runtime.execute(
        agent_name="ghost",
        instruction="teste",
    )
    print(f"  Resultado: {resultado.output}")
    print(f"  Sucesso: {resultado.success}")

    print("\n" + "=" * 60)
    print("Demonstracao concluida!")
    print("=" * 60)


if __name__ == "__main__":
    main()