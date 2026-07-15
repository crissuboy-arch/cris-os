"""
Porta: MCP (Model Context Protocol).

Define como o CRIS OS vai, no futuro, falar MCP nos dois sentidos:
  - como CLIENTE: consumir servidores MCP externos e expor suas capacidades
    como ferramentas (Tool) para os agentes;
  - como SERVIDOR: expor as ferramentas do CRIS para outros clientes MCP.

Status: contrato definido (design). Implementação concreta numa fase futura
(ver mcp/). Deixar a porta pronta evita refatorar o núcleo quando o MCP chegar.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.contracts.tool import Tool


@runtime_checkable
class MCPClient(Protocol):
    def list_tools(self) -> list[Tool]:
        """Lista as ferramentas expostas por um servidor MCP externo."""
        ...

    def call(self, tool_name: str, arguments: dict) -> str:
        """Invoca uma ferramenta remota via MCP."""
        ...
