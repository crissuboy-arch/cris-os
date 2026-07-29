"""
DynamicAgent — agente criado dinamicamente a partir de um AgentDefinition.

Fase 3: system prompt, binding sources (fixed/input/context/previous_result),
permission checks, memory read/write, context interpolation.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from agent_builder.models import (
    AgentDefinition,
    BindingSource,
    CapabilityBinding,
)
from core.capability.errors import CapabilityPermissionError
from core.contracts.agent import AgentContext
from core.models import AgentResult, Task

logger = logging.getLogger(__name__)

_FALLBACK_KEYWORD = "__fallback__"

# Regex for {context.xxx} placeholders
_CONTEXT_RE = re.compile(r"\{context\.([^}]+)\}")
_PREV_RE = re.compile(r"\{previous\.([^}]+)\}")


class DynamicAgent:
    """Agente gerado dinamicamente de um AgentDefinition.

    Fase 3:
    - Monta system prompt a partir de AgentInstructions
    - Resolve bindings com 4 fontes: fixed, input, context, previous_result
    - Verifica permissoes antes de cada chamada
    - Le/escreve memoria conforme MemoryConfig
    - Registra logs de execucao
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
        t0 = time.perf_counter()
        execution_log: dict[str, Any] = {
            "agent": self.name,
            "instruction": instruction,
            "bindings_attempted": [],
            "permissions_checked": [],
            "permissions_denied": [],
            "memory_reads": [],
            "memory_writes": [],
            "capabilities_called": [],
            "errors": [],
        }

        logger.info("[DynamicAgent:%s] Instrucao: '%s'", self.name, instruction[:120])

        # --- Build system prompt ---
        system_prompt = self._build_system_prompt()

        # --- Check CoreAPI ---
        if context.core_api is None:
            logger.warning("[DynamicAgent:%s] CoreAPI nao disponivel", self.name)
            return AgentResult(
                agent=self.name,
                output=f"Recebido: '{instruction}'. CoreAPI nao disponivel para executar capabilities.",
                success=True,
                metadata={"execution_log": execution_log, "system_prompt": system_prompt},
            )

        # --- Resolve context for binding interpolation ---
        resolved_context = self._resolve_context(context)

        # --- Sort bindings by priority ---
        sorted_bindings = sorted(
            self._def.bindings,
            key=lambda b: b.priority,
            reverse=True,
        )

        # --- Try each binding ---
        previous_result: dict | None = None
        for binding in sorted_bindings:
            execution_log["bindings_attempted"].append(binding.keyword)

            if not self._matches(instruction, binding):
                continue

            # --- Permission check ---
            perm_result = self._check_permission(binding, context, execution_log)
            if perm_result == "denied":
                return AgentResult(
                    agent=self.name,
                    output=f"Permissao negada para capability '{binding.capability}'. "
                           f"Esta capability esta na lista de negacao do agente.",
                    success=False,
                    metadata={"execution_log": execution_log, "system_prompt": system_prompt},
                )
            if perm_result == "confirmation_required":
                return AgentResult(
                    agent=self.name,
                    output=f"Confirmacao necessaria para '{binding.capability}'. "
                           f"Acao sensivel — execute com --confirm para prosseguir.",
                    success=False,
                    metadata={
                        "execution_log": execution_log,
                        "system_prompt": system_prompt,
                        "confirmation_required": True,
                        "capability": binding.capability,
                    },
                )

            # --- Check if capability exists ---
            resolved = context.core_api.registry.resolve(binding.capability)
            if resolved is None:
                error_msg = f"Capability '{binding.capability}' indisponivel ou inexistente"
                execution_log["errors"].append(error_msg)
                logger.warning("[DynamicAgent:%s] %s", self.name, error_msg)
                return AgentResult(
                    agent=self.name,
                    output=error_msg,
                    success=False,
                    metadata={"execution_log": execution_log, "system_prompt": system_prompt},
                )

            # --- Build params from binding source ---
            params = self._resolve_binding_params(
                instruction, binding, resolved_context, previous_result, execution_log
            )

            # --- Execute capability ---
            logger.info(
                "[DynamicAgent:%s] Chamando %s com params=%s",
                self.name, binding.capability, params,
            )
            execution_log["capabilities_called"].append({
                "capability": binding.capability,
                "params": params,
                "timestamp": time.time(),
            })

            try:
                result = context.core_api.execute(binding.capability, params)
            except CapabilityPermissionError as e:
                error_msg = f"Permissao negada pelo sistema para '{binding.capability}': {e}"
                execution_log["permissions_denied"].append(binding.capability)
                execution_log["errors"].append(error_msg)
                logger.error("[DynamicAgent:%s] %s", self.name, error_msg)
                return AgentResult(
                    agent=self.name,
                    output=error_msg,
                    success=False,
                    metadata={"execution_log": execution_log, "system_prompt": system_prompt},
                )
            except Exception as e:
                error_msg = f"Erro ao executar '{binding.capability}': {e}"
                execution_log["errors"].append(error_msg)
                logger.exception("[DynamicAgent:%s] %s", self.name, error_msg)
                return AgentResult(
                    agent=self.name,
                    output=error_msg,
                    success=False,
                    metadata={"execution_log": execution_log, "system_prompt": system_prompt},
                )

            # --- Store previous result for NEXT binding ---
            if isinstance(result, dict):
                previous_result = result

            if isinstance(result, dict) and result.get("success"):
                # --- Memory write (post-execution) ---
                self._memory_write(context, instruction, result, execution_log)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                execution_log["duration_ms"] = elapsed_ms
                return AgentResult(
                    agent=self.name,
                    output=self._format(binding, result),
                    success=True,
                    metadata={"execution_log": execution_log, "system_prompt": system_prompt},
                )

            error = result.get("error", "falha desconhecida") if isinstance(result, dict) else str(result)
            execution_log["errors"].append(error)
            logger.error("[DynamicAgent:%s] Capability '%s' falhou: %s", self.name, binding.capability, error)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            execution_log["duration_ms"] = elapsed_ms
            return AgentResult(
                agent=self.name,
                output=f"Falha ao executar '{binding.capability}': {error}",
                success=False,
                metadata={"execution_log": execution_log, "system_prompt": system_prompt},
            )

        # --- No binding matched ---
        logger.info("[DynamicAgent:%s] Nenhum binding para: '%s'", self.name, instruction[:80])
        elapsed_ms = (time.perf_counter() - t0) * 1000
        execution_log["duration_ms"] = elapsed_ms
        return AgentResult(
            agent=self.name,
            output=f"Nenhuma capability configurada para: '{instruction}'",
            success=False,
            metadata={"execution_log": execution_log, "system_prompt": system_prompt},
        )

    # ------------------------------------------------------------------
    # System prompt (Fase 3)
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        """Monta system prompt a partir de AgentInstructions."""
        instructions = self._def.instructions
        parts: list[str] = []

        # Role
        if instructions.role:
            parts.append(f"Voce e: {instructions.role}")

        # Objective
        if instructions.objective:
            parts.append(f"Objetivo: {instructions.objective}")

        # Custom prompt (raw)
        if instructions.custom_prompt:
            parts.append(instructions.custom_prompt)

        # Rules
        if instructions.rules:
            parts.append("Regras:")
            for i, rule in enumerate(instructions.rules, 1):
                parts.append(f"  {i}. {rule}")

        # Restrictions
        if instructions.restrictions:
            parts.append("Restricoes:")
            for i, rest in enumerate(instructions.restrictions, 1):
                parts.append(f"  {i}. {rest}")

        # Output format
        if instructions.output_format:
            parts.append(f"Formato de saida: {instructions.output_format}")

        # Agent description as fallback
        if not parts and self._def.description:
            parts.append(self._def.description)

        return "\n".join(parts) if parts else ""

    # ------------------------------------------------------------------
    # Binding resolution (Fase 3)
    # ------------------------------------------------------------------

    def _resolve_context(self, context: AgentContext) -> dict:
        """Extrai dados do AgentContext para interpolacao de bindings."""
        resolved: dict[str, Any] = {}

        # Session
        resolved["session"] = context.session

        # Conversation (last message)
        if context.conversation:
            last = context.conversation[-1]
            resolved["last_message"] = last.get("content", "")
            resolved["role"] = last.get("role", "")

        # Temporary items
        if context.temporary:
            resolved["temporary"] = context.temporary

        # Project memory
        if context.project_memory:
            resolved["project_count"] = len(context.project_memory)
            resolved["project_items"] = [
                {"title": item.title, "content": item.content, "type": item.type}
                for item in context.project_memory[:5]
            ]

        # Permanent memory
        if context.permanent:
            resolved["permanent_count"] = len(context.permanent)

        # Knowledge base
        if context.knowledge:
            resolved["knowledge_count"] = len(context.knowledge)
            resolved["knowledge_snippets"] = [
                {"source": p.source, "text": p.text[:200]} for p in context.knowledge[:3]
            ]

        return resolved

    def _resolve_binding_params(
        self,
        instruction: str,
        binding: CapabilityBinding,
        resolved_context: dict,
        previous_result: dict | None,
        execution_log: dict,
    ) -> dict:
        """Resolve parametros do binding conforme a fonte (source)."""
        source = binding.source if isinstance(binding.source, str) else binding.source.value
        params: dict = {}

        for key, template in binding.input_template.items():
            if not isinstance(template, str):
                params[key] = template
                continue

            if source == BindingSource.FIXED:
                params[key] = binding.default_value or template

            elif source == BindingSource.PREVIOUS_RESULT:
                if previous_result and isinstance(previous_result, dict):
                    params[key] = self._interpolate_previous(template, previous_result)
                else:
                    params[key] = self._interpolate_template(template, instruction, resolved_context)

            elif source == BindingSource.CONTEXT:
                params[key] = self._interpolate_context(template, resolved_context)

            else:
                # INPUT (default) — interpolate {instruction} and {context.*}
                params[key] = self._interpolate_template(template, instruction, resolved_context)

        return params

    def _interpolate_template(self, template: str, instruction: str, context: dict) -> str:
        """Interpola {instruction}, {context.xxx} e {previous.xxx} no template."""
        result = template.replace("{instruction}", instruction)
        # Context interpolation
        for match in _CONTEXT_RE.finditer(result):
            path = match.group(1)
            value = self._resolve_path(context, path)
            result = result.replace(match.group(0), str(value))
        return result

    def _interpolate_context(self, template: str, context: dict) -> str:
        """Interpola apenas {context.xxx} no template (sem {instruction})."""
        result = template
        for match in _CONTEXT_RE.finditer(result):
            path = match.group(1)
            value = self._resolve_path(context, path)
            result = result.replace(match.group(0), str(value))
        # Also replace {instruction} with empty if present
        result = result.replace("{instruction}", "")
        return result

    def _interpolate_previous(self, template: str, previous: dict) -> str:
        """Interpola {previous.xxx} no template."""
        result = template
        for match in _PREV_RE.finditer(result):
            path = match.group(1)
            value = self._resolve_path(previous, path)
            result = result.replace(match.group(0), str(value))
        # Also replace {instruction} and {context.xxx}
        result = result.replace("{instruction}", "")
        for match in _CONTEXT_RE.finditer(result):
            result = result.replace(match.group(0), "")
        return result

    @staticmethod
    def _resolve_path(data: dict, path: str) -> str:
        """Resolve 'a.b.c' em data['a']['b']['c']."""
        parts = path.split(".")
        current: Any = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part, "")
            else:
                current = ""
                break
        return str(current) if current is not None else ""

    # ------------------------------------------------------------------
    # Permission checks (Fase 3)
    # ------------------------------------------------------------------

    def _check_permission(
        self,
        binding: CapabilityBinding,
        context: AgentContext,
        execution_log: dict,
    ) -> str:
        """Verifica permissoes antes de executar capability.

        Returns:
            "ok" — pode executar
            "denied" — capability negada
            "confirmation_required" — precisa de confirmacao
        """
        perms = self._def.permissions
        cap_name = binding.capability

        # Explicit deny
        if cap_name in perms.denied_capabilities or "*" in perms.denied_capabilities:
            execution_log["permissions_denied"].append(cap_name)
            logger.warning(
                "[DynamicAgent:%s] Permissao negada para '%s' (nao autorizado)",
                self.name, cap_name,
            )
            return "denied"

        # Check explicit allow (if allowlist is non-empty, capability must be listed)
        if perms.allowed_capabilities and cap_name not in perms.allowed_capabilities:
            # Check wildcard
            allowed_wildcards = [a for a in perms.allowed_capabilities if a.endswith("*")]
            if not any(cap_name.startswith(w.rstrip("*")) for w in allowed_wildcards):
                execution_log["permissions_denied"].append(cap_name)
                logger.warning(
                    "[DynamicAgent:%s] Permissao negada para '%s' (nao esta na allowlist)",
                    self.name, cap_name,
                )
                return "denied"

        # Confirmation required
        if cap_name in perms.require_confirmation:
            execution_log["permissions_checked"].append({"capability": cap_name, "status": "confirmation_required"})
            return "confirmation_required"

        execution_log["permissions_checked"].append({"capability": cap_name, "status": "ok"})
        return "ok"

    # ------------------------------------------------------------------
    # Memory (Fase 3)
    # ------------------------------------------------------------------

    def _memory_write(
        self,
        context: AgentContext,
        instruction: str,
        result: dict,
        execution_log: dict,
    ) -> None:
        """Escreve na memoria apos execucao bem-sucedida (se habilitado)."""
        mem_config = self._def.memory
        if not mem_config.write_enabled:
            return
        if mem_config.memory_type in ("none",):
            return

        try:
            if context.core_api is None:
                return

            # Store execution result in context via core_api config
            key = f"memory.{self.name}.last_result"
            output_text = result.get("output", result.get("message", str(result)))
            context.core_api.set_config(key, output_text[:500])
            execution_log["memory_writes"].append({
                "type": mem_config.memory_type,
                "key": key,
                "size": len(output_text),
            })
            logger.info("[DynamicAgent:%s] Memory write: %s", self.name, key)
        except Exception as exc:
            logger.warning("[DynamicAgent:%s] Falha ao escrever memoria: %s", self.name, exc)

    def _memory_read(self, context: AgentContext, execution_log: dict) -> str:
        """Le dados da memoria do agente para enriquecer contexto."""
        mem_config = self._def.memory
        if not mem_config.read_enabled:
            return ""
        if mem_config.memory_type in ("none",):
            return ""

        parts: list[str] = []

        # L1: conversation
        if context.conversation and mem_config.memory_type in ("session", "agent", "project"):
            recent = context.conversation[-3:]
            parts.append("Historico recente:")
            for msg in recent:
                parts.append(f"  {msg.get('role', '?')}: {msg.get('content', '')}")

        # L1: temporary
        if context.temporary and mem_config.memory_type in ("session", "agent", "project"):
            parts.append(f"Itens do dia: {', '.join(context.temporary[:5])}")

        # L2: project memory
        if context.project_memory and mem_config.memory_type in ("agent", "project"):
            parts.append(f"Memoria do projeto ({len(context.project_memory)} itens):")
            for item in context.project_memory[:3]:
                parts.append(f"  [{item.type}] {item.title}: {item.content[:100]}")

        # L3: permanent
        if context.permanent and mem_config.memory_type in ("agent", "project"):
            parts.append(f"Memoria permanente ({len(context.permanent)} itens):")
            for item in context.permanent[:3]:
                parts.append(f"  [{item.type}] {item.title}: {item.content[:100]}")

        # L4: knowledge base
        if context.knowledge:
            parts.append(f"Base de conhecimento ({len(context.knowledge)} trechos):")
            for p in context.knowledge[:3]:
                parts.append(f"  [{p.source}] {p.text[:150]}")

        if parts:
            execution_log["memory_reads"].append({
                "type": mem_config.memory_type,
                "items": len(parts),
            })

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _matches(self, instruction: str, binding: CapabilityBinding) -> bool:
        """Verifica se a instrucao corresponde ao keyword do binding."""
        if binding.keyword == _FALLBACK_KEYWORD:
            return True
        return binding.keyword.lower() in instruction.lower()

    def _format(self, binding: CapabilityBinding, result: dict) -> str:
        """Formata resultado da capability em texto legivel."""
        cap = binding.capability
        if "create" in cap or "criar" in cap:
            return f"{binding.description or 'Criado'}: {result.get('id', '')} — {result.get('title', result.get('name', ''))}"
        if "echo" in cap:
            return f"Eco: {result.get('echo', result.get('message', ''))}"
        return str(result.get("output", result.get("message", result)))
