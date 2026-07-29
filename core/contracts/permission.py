"""
Porta: PermissionChecker.

Define como o Core verifica se um caller tem permissao para
executar uma capability. A implementacao pode variar de regras
estaticas (simples allow/deny) ate RBAC completo — o contrato
protege o plugin de ambas.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.capability.errors import CapabilityPermissionError


@runtime_checkable
class PermissionChecker(Protocol):
    """Verificador de permissoes para chamadas de capability.

    Metodos:
        check: Retorna True/False sem levantar excecao.
        require: Levanta CapabilityPermissionError se negado.
    """

    def check(self, caller_plugin_id: str, capability_name: str) -> bool:
        """Verifica se o caller tem permissao para chamar a capability.

        Args:
            caller_plugin_id: Plugin que esta chamando.
            capability_name: Nome da capability.

        Returns:
            True se permitido, False se negado.
        """
        ...

    def require(self, caller_plugin_id: str, capability_name: str) -> None:
        """Verifica e levanta CapabilityPermissionError se negado.

        Args:
            caller_plugin_id: Plugin que esta chamando.
            capability_name: Nome da capability.

        Raises:
            CapabilityPermissionError: Se o caller nao tem permissao.
        """
        ...