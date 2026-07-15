"""
ExecutionType — vocabulário FORTE dos tipos de execução do CRIS OS.

Espelha o `EventType` (core/domain/events.py): constantes tipadas em vez de
strings soltas. Herdar de `str` mantém a serialização trivial em payloads de
evento/JSON (uma instância JÁ é a string "agent", "skill", ...).

Um ExecutionType diz QUE tipo de executor roda um passo do plano. O Dispatcher
despacha por ele; múltiplos executores do mesmo tipo distinguem-se pelo `id`
estável do ExecutionTarget (ex.: browser.chrome, browser.mobile, browser.cloud).
"""

from __future__ import annotations

from enum import Enum


class ExecutionType(str, Enum):
    AGENT = "agent"
    SKILL = "skill"
    TOOL = "tool"
    MCP = "mcp"
    PLANNER = "planner"
    WORKFLOW = "workflow"

    def __str__(self) -> str:  # logs/payloads mostram "agent", não "ExecutionType.AGENT"
        return self.value


class Effect(str, Enum):
    """Efeito de um passo — decide se o gate de confirmação humana atua."""

    READ_ONLY = "read_only"   # leitura/consulta: NUNCA exige confirmação
    SENSITIVE = "sensitive"   # write/delete/publish/buy/send EXTERNO: exige confirmação da Cris

    def __str__(self) -> str:
        return self.value
