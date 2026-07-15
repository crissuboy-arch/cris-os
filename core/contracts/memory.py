"""
Portas da memória em 4 camadas (Interface Segregation — cada porta é pequena e
focada, princípio ISP do SOLID).

  L1 ConversationStore  -> histórico do diálogo (contexto do modelo)
  L1 TemporaryStore     -> tarefas/itens do dia (efêmeros)
  L2 ProjectMemoryStore -> memória própria de cada projeto
  L3 PermanentStore     -> quem é a Cris, objetivos, preferências, estratégias
  L4 KnowledgeBase      -> documentos/PDF/markdown/repos (recuperação por relevância)

O backend SQLiteMemory implementa as cinco. Os agentes NÃO dependem destas portas
diretamente: recebem um AgentContext já montado e ESCOPADO pelo MemoryFacade.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.models import KnowledgeItem, Passage


@runtime_checkable
class ConversationStore(Protocol):
    def add_message(self, session: str, role: str, content: str) -> None: ...
    def recent_messages(self, session: str, limit: int) -> list[dict]: ...


@runtime_checkable
class TemporaryStore(Protocol):
    def add_item(self, session: str, content: str, day: str) -> None: ...
    def list_items(self, session: str, day: str) -> list[str]: ...
    def clear_before(self, day: str) -> None: ...


@runtime_checkable
class ProjectMemoryStore(Protocol):
    def remember_project(self, project: str, item: KnowledgeItem) -> None: ...
    def recall_project(self, project: str) -> list[KnowledgeItem]: ...
    def projects(self) -> list[str]: ...


@runtime_checkable
class PermanentStore(Protocol):
    def remember_permanent(self, item: KnowledgeItem) -> None: ...
    def recall_permanent(self, type: str | None = None) -> list[KnowledgeItem]: ...
    def count_permanent(self) -> int: ...


@runtime_checkable
class KnowledgeBase(Protocol):
    def ingest(self, source: str, text: str, tags: list[str] | None = None) -> None: ...
    def search(self, query: str, limit: int = 4) -> list[Passage]: ...
    def count_kb(self) -> int: ...
