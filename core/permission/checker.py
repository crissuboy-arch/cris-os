"""
SimplePermissionChecker — implementacao minima de PermissionChecker.

Regras:
  - Toda capability com nome contendo "send", "archive", "delete", "write"
    e considerada SENSITIVE.
  - Apenas callers autorizados explicitamente podem chamar capabilities SENSITIVE.
  - Demais capabilities sao READ_ONLY e liberadas para qualquer caller.

Esta implementacao e intencionalmente simples para nao criar
um Permission Engine completo. Substituir no futuro sem quebrar plugins.
"""

from __future__ import annotations

from core.capability.errors import CapabilityPermissionError

# Prefixos de capabilities consideradas SENSITIVE
_SENSITIVE_PATTERNS = ("send", "archive", "delete", "write", "create", "update", "remove")


class SimplePermissionChecker:
    """PermissionChecker baseado em regras estaticas + allowlist.

    Permite configurar manualmente quais callers podem acessar
    quais capabilities SENSITIVE.
    """

    def __init__(self, default_allowed_callers: set[str] | None = None) -> None:
        self._rules: dict[str, set[str]] = {}
        if default_allowed_callers:
            self._rules["*"] = default_allowed_callers

    def allow(self, capability_name: str, caller_plugin_id: str) -> None:
        """Concede permissao explicita para um caller chamar uma capability."""
        if capability_name not in self._rules:
            self._rules[capability_name] = set()
        self._rules[capability_name].add(caller_plugin_id)

    def allow_all(self, caller_plugin_id: str) -> None:
        """Concede permissao para todas as capabilities."""
        self.allow("*", caller_plugin_id)

    def _is_sensitive(self, capability_name: str) -> bool:
        name_lower = capability_name.lower()
        return any(p in name_lower for p in _SENSITIVE_PATTERNS)

    def check(self, caller_plugin_id: str, capability_name: str) -> bool:
        if not self._is_sensitive(capability_name):
            return True

        # Verifica regra especifica
        callers = self._rules.get(capability_name, set())
        if caller_plugin_id in callers:
            return True

        # Verifica regra curinga
        all_callers = self._rules.get("*", set())
        if caller_plugin_id in all_callers:
            return True

        return False

    def require(self, caller_plugin_id: str, capability_name: str) -> None:
        if not self.check(caller_plugin_id, capability_name):
            raise CapabilityPermissionError(capability_name, caller_plugin_id)