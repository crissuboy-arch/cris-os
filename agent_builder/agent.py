"""
DynamicAgent — agente criado dinamicamente a partir de um AgentDefinition.

Implementa o contrato Agent (Protocol) sem heranca, permitindo que agentes
definidos no Agent Builder sejam executados pelo AgentRuntime sem tocar no Core.
"""

from __future__ import annotations

import logging

from agent_builder.models import AgentDefinition, CapabilityBinding
from core.contracts.agent import AgentContext
from core.models import AgentResult, Task

logger = logging.getLogger(__name__)

_FALLBACK_KEYWORD = "__fallback__"


class DynamicAgent:
    """Agente gerado dinamicamente de um AgentDefinition.

    Attributes:
        name: Nome do agente (para o AgentRegistry).
        description: Descricao (para o AgentRegistry).
    """

    def __init__(self, definition: AgentDefinition) -> None:
        self._def = definition
        self.name = definition.name
        self.description = definition.description

    # ------------------------------------------------------------------
    # Contrato Agent
    # ------------------------------------------------------------------

    def handle(self, task: Task, context: AgentContext) -> AgentResult:
        instruction = task.instruction.strip()
        logger.info("[DynamicAgent:%s] Instrucao: '%s'", self.name, instruction[:120])

        if context.core_api is None:
            logger.warning("[DynamicAgent:%s] CoreAPI nao disponivel", self.name)
            return AgentResult(
                agent=self.name,
                output=f"Recebido: '{instruction}'. CoreAPI nao disponivel para executar capabilities.",
                success=True,
            )

        # Ordena bindings por prioridade (maior primeiro)
        sorted_bindings = sorted(
            self._def.bindings,
            key=lambda b: b.priority,
            reverse=True,
        )

        for binding in sorted_bindings:
            if self._matches(instruction, binding):
                params = self._build_params(instruction, binding)
                logger.info(
                    "[DynamicAgent:%s] Chamando %s com params=%s",
                    self.name, binding.capability, params,
                )
                result = context.core_api.execute(binding.capability, params)

                if isinstance(result, dict) and result.get("success"):
                    return AgentResult(agent=self.name, output=self._format(binding, result), success=True)

                error = result.get("error", "falha desconhecida") if isinstance(result, dict) else str(result)
                logger.error("[DynamicAgent:%s] Capability '%s' falhou: %s", self.name, binding.capability, error)
                return AgentResult(agent=self.name, output=f"Falha ao executar '{binding.capability}': {error}", success=False)

        # Nenhum binding correspondeu
        logger.info("[DynamicAgent:%s] Nenhum binding para: '%s'", self.name, instruction[:80])
        return AgentResult(
            agent=self.name,
            output=f"Nenhuma capability configurada para: '{instruction}'",
            success=False,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _matches(self, instruction: str, binding: CapabilityBinding) -> bool:
        """Verifica se a instrucao corresponde ao keyword do binding."""
        if binding.keyword == _FALLBACK_KEYWORD:
            return True
        return binding.keyword.lower() in instruction.lower()

    def _build_params(self, instruction: str, binding: CapabilityBinding) -> dict:
        """Constrói parametros a partir do template com interpolacao."""
        params: dict = {}
        for key, value in binding.input_template.items():
            if isinstance(value, str) and "{instruction}" in value:
                params[key] = value.replace("{instruction}", instruction)
            else:
                params[key] = value
        return params

    def _format(self, binding: CapabilityBinding, result: dict) -> str:
        """Formata resultado da capability em texto legivel."""
        cap = binding.capability
        if "create" in cap or "criar" in cap:
            return f"{binding.description or 'Criado'}: {result.get('id', '')} — {result.get('title', result.get('name', ''))}"
        if "echo" in cap:
            return f"Eco: {result.get('echo', result.get('message', ''))}"
        # generico
        return str(result.get("output", result.get("message", result)))