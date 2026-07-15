"""
Wrappers de domínio para as 4 camadas de memória.

Dão uma API amigável sobre o backend (SQLiteMemory) e cuidam de detalhes como a
"data de hoje" da camada temporária e a renderização para prompt. Os agentes e o
orquestrador usam estes wrappers (ou o MemoryFacade), nunca o banco direto.
"""

from __future__ import annotations

from datetime import date

from core.models import KnowledgeItem


def hoje() -> str:
    return date.today().isoformat()


class ConversationMemory:
    """L1 — histórico do diálogo."""

    def __init__(self, backend, max_context: int = 12) -> None:
        self.backend = backend
        self.max_context = max_context

    def add(self, session: str, role: str, content: str) -> None:
        self.backend.add_message(session, role, content)

    def recent(self, session: str) -> list[dict]:
        return self.backend.recent_messages(session, self.max_context)


class TemporaryMemory:
    """L1 — itens/tarefas do dia."""

    def __init__(self, backend) -> None:
        self.backend = backend

    def add(self, session: str, content: str) -> None:
        self.backend.add_item(session, content, hoje())

    def today(self, session: str) -> list[str]:
        return self.backend.list_items(session, hoje())

    def purge_old(self) -> None:
        self.backend.clear_before(hoje())


class ProjectMemory:
    """L2 — memória própria de cada projeto."""

    def __init__(self, backend) -> None:
        self.backend = backend

    def remember(self, project: str, type: str, title: str, content: str,
                 tags: list[str] | None = None) -> KnowledgeItem:
        item = KnowledgeItem(type=type, title=title, content=content, tags=tags or [])
        self.backend.remember_project(project, item)
        return item

    def recall(self, project: str) -> list[KnowledgeItem]:
        return self.backend.recall_project(project)

    def recall_many(self, projects: list[str]) -> list[KnowledgeItem]:
        itens: list[KnowledgeItem] = []
        for p in projects:
            itens.extend(self.backend.recall_project(p))
        return itens

    def all_projects(self) -> list[str]:
        return self.backend.projects()


class PermanentMemory:
    """L3 — quem é a Cris, objetivos, preferências, estratégias."""

    def __init__(self, backend) -> None:
        self.backend = backend

    def remember(self, type: str, title: str, content: str,
                 tags: list[str] | None = None) -> KnowledgeItem:
        item = KnowledgeItem(type=type, title=title, content=content, tags=tags or [])
        self.backend.remember_permanent(item)
        return item

    def recall(self, type: str | None = None) -> list[KnowledgeItem]:
        return self.backend.recall_permanent(type)

    def is_empty(self) -> bool:
        return self.backend.count_permanent() == 0


class KnowledgeBaseMemory:
    """L4 — base de conhecimento (documentos/PDF/markdown/repos)."""

    def __init__(self, backend) -> None:
        self.backend = backend

    def ingest(self, source: str, text: str, tags: list[str] | None = None) -> None:
        self.backend.ingest(source, text, tags)

    def search(self, query: str, limit: int = 4):
        return self.backend.search(query, limit)

    def is_empty(self) -> bool:
        return self.backend.count_kb() == 0
