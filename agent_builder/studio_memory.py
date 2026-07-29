"""
StudioMemory — memoria persistente para agentes do Studio.

Usa SQLiteMemory real para escrita de memoria (session, agent, project).
Fornece read/write com isolamento por agente.
"""

from __future__ import annotations

import logging
from typing import Any

from core.models import KnowledgeItem

logger = logging.getLogger(__name__)


class StudioMemory:
    """Memoria persistente para agentes do Studio."""

    def __init__(self, backend: Any = None) -> None:
        """
        Args:
            backend: SQLiteMemory instance. If None, creates a new one.
        """
        self._backend = backend
        self._initialized = False

    def _ensure_backend(self) -> Any:
        if self._backend is not None:
            return self._backend
        try:
            from storage.sqlite_memory import SQLiteMemory
            self._backend = SQLiteMemory()
            self._initialized = True
            return self._backend
        except Exception as exc:
            logger.warning("Could not initialize SQLiteMemory: %s", exc)
            return None

    def write_session(self, session: str, role: str, content: str) -> bool:
        """Escreve na memoria de sessao (L1 conversation)."""
        backend = self._ensure_backend()
        if backend is None:
            return False
        try:
            backend.add_message(session, role, content)
            return True
        except Exception as exc:
            logger.warning("Session write failed: %s", exc)
            return False

    def write_temporary(self, session: str, content: str) -> bool:
        """Escreve na memoria temporaria (L1 items do dia)."""
        backend = self._ensure_backend()
        if backend is None:
            return False
        try:
            from memory.layers import hoje
            backend.add_item(session, content, hoje())
            return True
        except Exception as exc:
            logger.warning("Temporary write failed: %s", exc)
            return False

    def write_project(self, project: str, type_: str, title: str, content: str,
                      tags: list[str] | None = None) -> bool:
        """Escreve na memoria de projeto (L2)."""
        backend = self._ensure_backend()
        if backend is None:
            return False
        try:
            item = KnowledgeItem(type=type_, title=title, content=content, tags=tags or [])
            backend.remember_project(project, item)
            return True
        except Exception as exc:
            logger.warning("Project write failed: %s", exc)
            return False

    def write_permanent(self, type_: str, title: str, content: str,
                        tags: list[str] | None = None) -> bool:
        """Escreve na memoria permanente (L3)."""
        backend = self._ensure_backend()
        if backend is None:
            return False
        try:
            item = KnowledgeItem(type=type_, title=title, content=content, tags=tags or [])
            backend.remember_permanent(item)
            return True
        except Exception as exc:
            logger.warning("Permanent write failed: %s", exc)
            return False

    def write_agent_result(self, agent_name: str, instruction: str, result: str,
                           session: str = "studio") -> bool:
        """Escreve resultado de execucao do agente na memoria."""
        backend = self._ensure_backend()
        if backend is None:
            return False
        try:
            # Store as session message (assistant response)
            backend.add_message(session, "assistant", f"[{agent_name}] {result[:500]}")
            # Also store as temporary item for today
            from memory.layers import hoje
            backend.add_item(session, f"{agent_name}: {instruction[:100]}", hoje())
            return True
        except Exception as exc:
            logger.warning("Agent result write failed: %s", exc)
            return False

    def read_session(self, session: str, limit: int = 10) -> list[dict]:
        """Le mensagens da sessao."""
        backend = self._ensure_backend()
        if backend is None:
            return []
        try:
            return backend.recent_messages(session, limit)
        except Exception:
            return []

    def read_project(self, project: str) -> list[KnowledgeItem]:
        """Le itens do projeto."""
        backend = self._ensure_backend()
        if backend is None:
            return []
        try:
            return backend.recall_project(project)
        except Exception:
            return []

    def read_permanent(self, type_: str | None = None) -> list[KnowledgeItem]:
        """Le memoria permanente."""
        backend = self._ensure_backend()
        if backend is None:
            return []
        try:
            return backend.recall_permanent(type_)
        except Exception:
            return []
