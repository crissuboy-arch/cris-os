"""
StudioNotifier — notificacoes via Telegram para confirmacoes e eventos do Studio.

Suporta: confirmacao pendente, aprovacao, rejeicao, execucao concluida.
Usa a API do Telegram via HTTP (sem dependencia externa).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_API = "https://api.telegram.org"


@dataclass
class Notification:
    """Uma notificacao enviada."""
    id: str
    type: str  # confirmation | approval | rejection | execution | error
    title: str
    message: str
    data: dict = field(default_factory=dict)
    sent: bool = False
    error: str = ""


class StudioNotifier:
    """Envia notificacoes via Telegram."""

    def __init__(self, token: str = "", chat_id: str = "") -> None:
        self._token = token or TELEGRAM_TOKEN
        self._chat_id = chat_id or TELEGRAM_CHAT_ID
        self._history: list[Notification] = []
        self._counter = 0
        self._enabled = bool(self._token and self._chat_id)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def configure(self, token: str, chat_id: str) -> None:
        self._token = token
        self._chat_id = chat_id
        self._enabled = bool(token and chat_id)

    def notify_confirmation_pending(
        self, confirmation_id: str, agent_name: str, capability: str, instruction: str,
    ) -> Notification:
        """Notifica sobre confirmacao pendente."""
        title = f"Confirmacao Pendente: {agent_name}"
        message = (
            f"*{capability}*\n"
            f"Instrucao: {instruction}\n"
            f"ID: `{confirmation_id}`\n\n"
            f"Responda /confirm_{confirmation_id} ou /reject_{confirmation_id}"
        )
        return self._send("confirmation", title, message, {
            "confirmation_id": confirmation_id,
            "agent_name": agent_name,
            "capability": capability,
        })

    def notify_approval(self, confirmation_id: str, agent_name: str) -> Notification:
        """Notifica sobre aprovacao."""
        title = f"Aprovado: {agent_name}"
        message = f"Acao `{confirmation_id}` foi aprovada."
        return self._send("approval", title, message, {"confirmation_id": confirmation_id})

    def notify_rejection(self, confirmation_id: str, agent_name: str, notes: str = "") -> Notification:
        """Notifica sobre rejeicao."""
        title = f"Rejeitado: {agent_name}"
        message = f"Acao `{confirmation_id}` foi rejeitada."
        if notes:
            message += f"\nMotivo: {notes}"
        return self._send("rejection", title, message, {"confirmation_id": confirmation_id})

    def notify_execution_complete(
        self, agent_name: str, success: bool, duration_ms: float, output: str = "",
    ) -> Notification:
        """Notifica sobre execucao concluida."""
        status = "OK" if success else "FALHA"
        title = f"Execucao {status}: {agent_name}"
        message = f"Duracao: {duration_ms:.1f}ms"
        if output:
            message += f"\n{output[:200]}"
        ntype = "execution" if success else "error"
        return self._send(ntype, title, message, {
            "agent_name": agent_name,
            "success": success,
            "duration_ms": duration_ms,
        })

    def _send(self, ntype: str, title: str, message: str, data: dict | None = None) -> Notification:
        """Envia mensagem via Telegram."""
        self._counter += 1
        notif = Notification(
            id=f"notif-{self._counter:06d}",
            type=ntype,
            title=title,
            message=message,
            data=data or {},
        )

        if not self._enabled:
            notif.error = "Telegram not configured"
            self._history.append(notif)
            return notif

        text = f"*{title}*\n\n{message}"
        payload = json.dumps({
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }).encode("utf-8")

        try:
            url = f"{TELEGRAM_API}/bot{self._token}/sendMessage"
            req = urllib.request.Request(url, data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                notif.sent = result.get("ok", False)
                if not notif.sent:
                    notif.error = result.get("description", "Unknown error")
        except Exception as exc:
            notif.error = str(exc)
            logger.warning("Telegram notification failed: %s", exc)

        self._history.append(notif)
        return notif

    def list_history(self, limit: int = 50) -> list[dict]:
        """Historico de notificacoes."""
        sorted_items = sorted(self._history, key=lambda n: n.id, reverse=True)
        return [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "sent": n.sent,
                "error": n.error,
                "data": n.data,
            }
            for n in sorted_items[:limit]
        ]

    def stats(self) -> dict:
        total = len(self._history)
        sent = sum(1 for n in self._history if n.sent)
        failed = sum(1 for n in self._history if n.error)
        return {
            "total": total,
            "sent": sent,
            "failed": failed,
            "enabled": self._enabled,
        }


# Singleton
_notifier: StudioNotifier | None = None


def get_notifier() -> StudioNotifier:
    global _notifier
    if _notifier is None:
        _notifier = StudioNotifier()
    return _notifier
