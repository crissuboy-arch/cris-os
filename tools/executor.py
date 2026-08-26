"""
ToolExecutor — executor central de ferramentas de sistema.

Registra ferramentas pelo catalogo, expoe schemas para LLM function-calling
e executa ferramentas por nome + argumentos. Usado pelo BaseAgent para o
tool-calling loop (multi-turno: LLM -> tool -> LLM -> tool -> ... -> resposta).
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executor central de ferramentas."""

    def __init__(self, catalog: list[dict] | None = None) -> None:
        self._tools: dict[str, dict] = {}
        if catalog:
            for t in catalog:
                self.register(t)

    def register(self, tool_def: dict) -> None:
        name = tool_def["name"]
        self._tools[name] = tool_def
        logger.info("=== [TOOL_EXECUTOR] Ferramenta registrada: '%s' ===", name)

    def get_schemas(self) -> list[dict]:
        """Retorna schemas no formato OpenAI function-calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": info["name"],
                    "description": info["description"],
                    "parameters": info["schema"](),
                },
            }
            for info in self._tools.values()
        ]

    def get_schemas_filtered(self, allowed: list[str] | None = None,
                             forbidden: list[str] | None = None) -> list[dict]:
        """Retorna schemas filtrados por permissao."""
        schemas = self.get_schemas()
        if not allowed and not forbidden:
            return schemas
        forbidden_set = set(forbidden or [])
        allowed_set = set(allowed or [])
        result = []
        for s in schemas:
            name = s["function"]["name"]
            if name in forbidden_set:
                continue
            if allowed and name not in allowed_set:
                continue
            result.append(s)
        return result

    def execute(self, name: str, **kwargs) -> str:
        """Executa uma ferramenta registrada."""
        info = self._tools.get(name)
        if not info:
            return f"[TOOL] Ferramenta '{name}' nao encontrada."

        logger.info("=== [TOOL_EXECUTOR] Executando '%s' args=%s ===", name, kwargs)
        t0 = time.perf_counter()
        try:
            resultado = info["run"](**kwargs)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info("=== [TOOL_EXECUTOR] '%s' concluido em %.0fms (%d chars) ===",
                        name, elapsed_ms, len(resultado))
            return resultado
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.warning("=== [TOOL_EXECUTOR] '%s' FALHOU em %.0fms: %s ===",
                           name, elapsed_ms, e)
            return f"[TOOL] Erro ao executar '{name}': {e}"

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


def create_executor() -> ToolExecutor:
    """Cria o ToolExecutor padrao com todas as ferramentas de sistema."""
    from tools.executor_tools import get_tool_catalog
    return ToolExecutor(get_tool_catalog())
