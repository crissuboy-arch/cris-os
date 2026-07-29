"""
HelloAgent — agente de prova de conceito do Agent Runtime.

Nao usa LLM. Fluxo:
  1. Recebe instrucao via Task
  2. Determina qual capability chamar (notes.create ou demo.echo)
  3. Chama a capability via CoreAPI (injetado no AgentContext)
  4. Retorna resultado estruturado

O AgentRuntime gerencia eventos, metricas e logs externamente.
"""

from __future__ import annotations

import re
import logging

from core.contracts.agent import AgentContext
from core.models import AgentResult, Task

logger = logging.getLogger(__name__)

_CAPABILITY_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?:criar|crie|cria|create|nova|new)\s+(?:nota|note|anotac)"), "notes.create"),
    (re.compile(r"(?:echo|eco|repete|repita|diga|fale)\s"), "demo.echo"),
    (re.compile(r"(?:nota|note|anotac)"), "notes.create"),
]


class HelloAgent:
    """Agente de exemplo que chama capabilities sem usar LLM."""

    name: str = "hello_agent"
    description: str = "Agente de prova de conceito — chama capabilities por keywords"

    def handle(self, task: Task, context: AgentContext) -> AgentResult:
        instruction = task.instruction.strip().lower()
        logger.info("[HelloAgent] Instrucao recebida: '%s'", instruction)

        # --- 1. Determinar qual capability chamar ---
        capability, params = self._resolve_capability(instruction)

        # --- 2. Chamar a capability via CoreAPI ---
        if context.core_api is None:
            logger.warning("[HelloAgent] CoreAPI nao disponivel — pulando capability")
            output = f"Instrucao reconhecida: '{task.instruction}'. Nao ha CoreAPI para executar capabilities."
            return AgentResult(agent=self.name, output=output, success=True)

        result = context.core_api.execute(capability, params)

        # --- 3. Montar resposta ---
        if isinstance(result, dict) and result.get("success"):
            output = self._format_success(capability, result)
            return AgentResult(agent=self.name, output=output, success=True)

        error = result.get("error", "falha desconhecida") if isinstance(result, dict) else str(result)
        logger.error("[HelloAgent] Capability '%s' falhou: %s", capability, error)
        return AgentResult(
            agent=self.name,
            output=f"Nao consegui executar '{capability}': {error}",
            success=False,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_capability(self, instruction: str) -> tuple[str, dict]:
        """Mapeia instrucao para (capability_name, params)."""
        for pattern, cap_name in _CAPABILITY_PATTERNS:
            match = pattern.search(instruction)
            if match:
                if cap_name == "notes.create":
                    return cap_name, {"title": "Nota do HelloAgent", "content": instruction}
                if cap_name == "demo.echo":
                    rest = instruction[match.end():].strip()
                    return cap_name, {"message": rest or "Hello do CRIS OS!"}
                return cap_name, {}

        # fallback: demo.echo com a instrucao original
        return "demo.echo", {"message": instruction}

    def _format_success(self, capability: str, result: dict) -> str:
        """Formata o resultado da capability em texto legivel."""
        if capability == "notes.create":
            return f"Nota criada com sucesso! ID: {result.get('id')}, titulo: '{result.get('title')}'"
        if capability == "demo.echo":
            return f'Eco: {result.get("echo", result.get("message", ""))}'
        return str(result)