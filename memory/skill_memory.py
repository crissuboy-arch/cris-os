"""
Adaptador: MemoryFacade -> porta estreita `SkillMemory`.

Uma Skill só enxerga `core.contracts.skill.SkillMemory` (4 operações). Este
adaptador TRADUZ essas operações para o `MemoryFacade` concreto (que por sua vez
fala com o SQLite), sem que a skill conheça facade, camadas ou banco.

É a peça de "Adapters" do Ports & Adapters na fronteira da skill: trocar o
backend de memória vira plugar outro adaptador, sem tocar a skill.
"""

from __future__ import annotations

from core.models import KnowledgeItem


class FacadeSkillMemory:
    """Expõe o `MemoryFacade` como a porta estreita `SkillMemory`."""

    def __init__(self, facade) -> None:
        self._facade = facade

    def recent_conversation(self, session: str) -> list[dict]:
        return self._facade.conversation.recent(session)

    def today_items(self, session: str) -> list[str]:
        return self._facade.temporary.today(session)

    def remember(self, type: str, title: str, content: str,
                 tags: list[str] | None = None) -> KnowledgeItem:
        return self._facade.permanent.remember(type, title, content, tags=tags)

    def recall(self, type: str | None = None) -> list[KnowledgeItem]:
        return self._facade.permanent.recall(type)
