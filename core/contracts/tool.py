"""
Porta: ferramenta (capacidade no mundo real).

Google Calendar, Drive, GitHub, n8n, busca na web, renderização de vídeo...
São as "mãos" dos agentes. Separadas dos canais de propósito: canal = como a
Cris fala com o sistema; ferramenta = o que os agentes fazem no mundo.

Status: contrato definido. Nenhuma ferramenta concreta na Fase 1 (ver tools/).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Tool(Protocol):
    """Contrato de uma ferramenta usável por um agente."""

    name: str
    description: str

    def schema(self) -> dict:
        """JSON schema (estilo function-calling) descrevendo os parâmetros."""
        ...

    def run(self, **kwargs: Any) -> str:
        """Executa a ferramenta e devolve um resultado em texto."""
        ...
