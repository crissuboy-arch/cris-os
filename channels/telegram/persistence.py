from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from agent_builder.metrics import MetricEntry, get_metrics
from database.connection import get_connection
from services.activity_logger import ActivityLogger
from services.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class TelegramPersistenceService:
    def __init__(self) -> None:
        self.memory = MemoryManager()
        self.logger = ActivityLogger()
        self.metrics = get_metrics()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        from database.schema import criar_tabelas
        criar_tabelas()

    def save_conversation(
        self,
        user_id: str,
        role: str,
        content: str,
        agent: str = "",
    ) -> int:
        return self.memory.salvar_conversa(user_id, role, content, agent)

    def load_recent_context(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[dict]:
        return self.memory.historico(user_id, limit)

    def restore_context_text(
        self,
        user_id: str,
        limit: int = 10,
    ) -> str:
        return self.memory.contexto_recente(user_id, limit)

    def log_execution(
        self,
        user_id: str = "",
        agent: str = "",
        duration_ms: int = 0,
        error: str = "",
    ) -> int:
        return self.logger.log(
            usuario_id=user_id,
            agente=agent,
            ferramenta="telegram_message",
            duracao_ms=duration_ms,
            erro=error,
        )

    def record_message_metric(
        self,
        agent_name: str,
        success: bool,
        duration_ms: float,
    ) -> None:
        self.metrics.record(MetricEntry(
            agent_id=agent_name,
            agent_name=agent_name,
            capability="telegram.message",
            plugin="telegram",
            success=success,
            duration_ms=duration_ms,
        ))

    def record_confirmation_metric(
        self,
        user_id: str,
        action: str,
        step_name: str,
    ) -> None:
        self.metrics.record(MetricEntry(
            agent_id="confirmation_gateway",
            agent_name="confirmation_gateway",
            capability=f"telegram.confirmation.{action}",
            plugin="telegram",
            success=True,
            duration_ms=0,
            session=user_id,
        ))

    def get_execution_history(
        self,
        user_id: str,
        limit: int = 20,
    ) -> list[dict]:
        return self.logger.ultimos(limit)

    def get_metrics_summary(self) -> dict:
        return self.metrics.summary()

    def get_conversation_history(
        self,
        user_id: str,
        limit: int = 20,
    ) -> list[dict]:
        return self.memory.historico(user_id, limit)

    def clear_user_history(self, user_id: str) -> bool:
        return self.memory.limpar_conversas(user_id)

    def save_context_flag(
        self,
        user_id: str,
        key: str,
        value: str,
    ) -> None:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO contexto_recente (usuario_id, chave, valor) "
            "VALUES (?, ?, ?)",
            (user_id, key, value),
        )
        conn.commit()

    def load_context_flag(
        self,
        user_id: str,
        key: str,
        default: str = "",
    ) -> str:
        conn = get_connection()
        row = conn.execute(
            "SELECT valor FROM contexto_recente WHERE usuario_id=? AND chave=?",
            (user_id, key),
        ).fetchone()
        return row["valor"] if row else default

    def format_history_for_context(
        self,
        user_id: str,
        limit: int = 10,
    ) -> str:
        return self.memory.contexto_recente(user_id, limit)