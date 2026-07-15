"""
Porta: Skill (capacidade empacotada e reutilizável).

Uma Skill é um JOB repetível e versionado — fica **acima** de uma Tool (ação
atômica) e **abaixo** de um Agent (papel com julgamento):
    "Agentes orquestram Skills; Skills usam Tools."

Esta porta define o contrato de **EXECUÇÃO** de uma skill: `execute(payload, context)`.
O retorno é um `SkillResult` (padrão) — mas um `dict` é **tolerado** por
compatibilidade; o SkillRunner normaliza qualquer um dos dois.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from core.models import KnowledgeItem, SkillResult


@runtime_checkable
class SkillExecutor(Protocol):
    """Contrato de execução de uma Skill."""

    name: str
    version: str

    def execute(self, payload: dict, context) -> "SkillResult | dict":
        """
        Executa a skill e devolve o resultado.

        Deve devolver um `SkillResult` (padrão); um `dict` é tolerado por
        compatibilidade (o SkillRunner normaliza).
        """
        ...


@runtime_checkable
class SkillMemory(Protocol):
    """
    Memória como uma Skill a enxerga — porta **estreita** (ISP).

    A Skill depende só destas 4 operações; NÃO conhece `MemoryFacade`, as
    camadas nem o SQLite. Um adaptador (`memory/skill_memory.py`) liga esta
    porta ao backend concreto — Dependency Inversion na fronteira da skill.
    """

    def recent_conversation(self, session: str) -> list[dict]:
        """L1 — últimas mensagens do diálogo desta sessão."""
        ...

    def today_items(self, session: str) -> list[str]:
        """L1 — itens/tarefas de hoje desta sessão."""
        ...

    def remember(self, type: str, title: str, content: str,
                 tags: "list[str] | None" = None) -> "KnowledgeItem":
        """L3 — grava um item na memória permanente e o devolve (com `id`)."""
        ...

    def recall(self, type: "str | None" = None) -> "list[KnowledgeItem]":
        """L3 — recupera itens permanentes (opcionalmente por tipo), ordenados por criação."""
        ...
