"""
AgentRuntime — executor generico de agentes.

Responsabilidades:
  1. Carregar agente do AgentRegistry
  2. Montar AgentContext com CoreAPI injetada
  3. Criar Task e disparar eventos (agent.started / agent.completed / agent.failed)
  4. Executar agent.handle(task, context)
  5. Registrar metricas (duracao, sucesso/falha)
  6. Tratar erros e retornar AgentResult estruturado
  7. Respeitar permissoes (delegado ao CoreAPI do agente)

Uso:
    runtime = AgentRuntime(agent_registry, capability_registry, event_bus, ...)
    resultado = runtime.execute("hello_agent", "crie uma nota de boas-vindas")
"""

from __future__ import annotations

import logging
import time
from typing import Any

from core.contracts.agent import Agent, AgentContext
from core.domain.events import Event
from core.models import AgentResult, Task

logger = logging.getLogger(__name__)


class AgentRuntime:
    """Executor generico de agentes no CRIS OS."""

    def __init__(
        self,
        agent_registry,
        core_api_factory: Any = None,
        event_bus: Any = None,
        plugin_loader: Any = None,
    ) -> None:
        """
        Args:
            agent_registry: AgentRegistry contendo os agentes carregados.
            core_api_factory: Callable que recebe (agent_name) e devolve CoreAPI.
            event_bus: EventBus para publicar eventos de ciclo de vida.
            plugin_loader: PluginLoader (opcional) para executar capabilities
                           quando core_api_factory nao for fornecido.
        """
        self._registry = agent_registry
        self._core_api_factory = core_api_factory
        self._event_bus = event_bus
        self._plugin_loader = plugin_loader

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def execute(
        self,
        agent_name: str,
        instruction: str,
        session: str = "",
        caller: str = "runtime",
        correlation_id: str = "",
        context_overrides: dict | None = None,
    ) -> AgentResult:
        """Executa um agente e retorna o resultado.

        Fluxo completo:
          1. Obtem agente do registro
          2. Monta AgentContext com CoreAPI
          3. Cria Task
          4. Publica evento agent.started
          5. Chama agent.handle(task, context)
          6. Publica evento agent.completed / agent.failed
          7. Retorna AgentResult
        """
        # --- 1. Obter agente ---
        agente = self._registry.get(agent_name)
        if agente is None:
            logger.error("Agente nao encontrado: %s", agent_name)
            return AgentResult(
                agent=agent_name,
                output=f"Agente '{agent_name}' nao encontrado",
                success=False,
            )

        # --- 2. Montar contexto ---
        core_api = self._build_core_api(agent_name)
        context = AgentContext(
            session=session,
            core_api=core_api,
            **(context_overrides or {}),
        )

        # --- 3. Criar Task ---
        task = Task(agent=agent_name, instruction=instruction, status="pending")

        # --- 4. Evento: started ---
        self._publish_event("agent.started", correlation_id, {
            "agent": agent_name,
            "instruction": instruction,
            "task_id": task.id,
        })

        # --- 5. Executar ---
        t0 = time.perf_counter()
        task.status = "running"

        try:
            if hasattr(agente, "handle") and callable(agente.handle):
                if isinstance(agente, Agent):
                    resultado = agente.handle(task, context)
                else:
                    resultado = agente.handle(task, context)
            else:
                raise TypeError(f"Agente {agent_name} nao implementa handle()")

            elapsed_ms = (time.perf_counter() - t0) * 1000
            success = resultado.success if hasattr(resultado, "success") else True

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.exception("Agente '%s' falhou durante execucao", agent_name)
            resultado = AgentResult(
                agent=agent_name,
                output=f"Erro ao executar agente: {exc}",
                success=False,
            )
            success = False

        # --- 6. Evento: completed / failed ---
        if success:
            task.status = "done"
            self._publish_event("agent.completed", correlation_id, {
                "agent": agent_name,
                "task_id": task.id,
                "duration_ms": elapsed_ms,
            })
        else:
            task.status = "error"
            self._publish_event("agent.failed", correlation_id, {
                "agent": agent_name,
                "task_id": task.id,
                "duration_ms": elapsed_ms,
                "error": resultado.output if hasattr(resultado, "output") else str(resultado),
            })

        self._record_metrics(agent_name, elapsed_ms, success)
        logger.info(
            "Agent '%s' executou em %.0fms: success=%s",
            agent_name, elapsed_ms, success,
        )

        return resultado

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _build_core_api(self, agent_name: str):
        """Cria ou obtem CoreAPI para o agente."""
        if self._core_api_factory is not None:
            return self._core_api_factory(agent_name)
        if self._plugin_loader is not None:
            from core.application.core_api import CoreAPI
            api = CoreAPI(
                registry=self._plugin_loader._registry,
                event_bus=self._plugin_loader._event_bus,
                plugin_name=agent_name,
                config_store=self._plugin_loader._config_store,
                permission_checker=self._plugin_loader._permission_checker,
                capability_executor=self._plugin_loader.execute_capability,
            )
            return api
        return None

    def _publish_event(self, event_type: str, correlation_id: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(
            Event(
                type=event_type,
                correlation_id=correlation_id,
                source="agent_runtime",
                payload=payload,
            )
        )

    def _record_metrics(self, agent_name: str, duration_ms: float, success: bool) -> None:
        """Hook para registro de metricas (pode ser estendido)."""
        logger.debug("Metrika: agent=%s duration=%.0fms success=%s", agent_name, duration_ms, success)