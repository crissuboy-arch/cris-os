from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional


@dataclass
class ConfirmationEntry:
    confirmation_id: str
    user_id: str
    step_name: str
    effect: str
    summary: str
    data: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=15))
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    executed_at: Optional[datetime] = None
    status: str = "pending"

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_pending(self) -> bool:
        return self.status == "pending"


class ConfirmationUtils:
    @staticmethod
    def generate_confirmation_id() -> str:
        return f"conf_{secrets.token_urlsafe(8)}"

    @staticmethod
    def create_confirmation(
        user_id: str,
        step_name: str,
        effect: str,
        summary: str,
        data: dict | None = None,
    ) -> ConfirmationEntry:
        return ConfirmationEntry(
            confirmation_id=ConfirmationUtils.generate_confirmation_id(),
            user_id=user_id,
            step_name=step_name,
            effect=effect,
            summary=summary,
            data=data or {},
        )

    @staticmethod
    def get_confirmation(
        confirmations: Dict[str, ConfirmationEntry],
        confirmation_id: str,
    ) -> ConfirmationEntry | None:
        return confirmations.get(confirmation_id)

    @staticmethod
    def approve_confirmation(
        confirmations: Dict[str, ConfirmationEntry],
        confirmation_id: str,
        user_id: str,
    ) -> tuple[bool, str]:
        entry = confirmations.get(confirmation_id)
        if not entry:
            return False, "confirmation_not_found"
        if entry.status != "pending":
            return False, f"already_{entry.status}"
        if entry.is_expired:
            entry.status = "expired"
            return False, "expired"
        entry.approved_by = user_id
        entry.status = "approved"
        return True, "approved"

    @staticmethod
    def reject_confirmation(
        confirmations: Dict[str, ConfirmationEntry],
        confirmation_id: str,
        user_id: str,
    ) -> tuple[bool, str]:
        entry = confirmations.get(confirmation_id)
        if not entry:
            return False, "confirmation_not_found"
        if entry.status != "pending":
            return False, f"already_{entry.status}"
        if entry.is_expired:
            entry.status = "expired"
            return False, "expired"
        entry.rejected_by = user_id
        entry.status = "rejected"
        return True, "rejected"

    @staticmethod
    def is_expired(entry: ConfirmationEntry) -> bool:
        return entry.is_expired

    @staticmethod
    def is_duplicate_click(
        confirmations: Dict[str, ConfirmationEntry],
        confirmation_id: str,
    ) -> bool:
        entry = confirmations.get(confirmation_id)
        if not entry:
            return False
        return entry.status != "pending"

    @staticmethod
    def cleanup_expired(
        confirmations: Dict[str, ConfirmationEntry],
    ) -> int:
        now = datetime.now(timezone.utc)
        expired_ids = [
            cid for cid, entry in confirmations.items()
            if entry.is_expired and entry.status == "pending"
        ]
        for cid in expired_ids:
            confirmations[cid].status = "expired"
        return len(expired_ids)

    @staticmethod
    def get_pending_count(
        confirmations: Dict[str, ConfirmationEntry],
        user_id: str,
    ) -> int:
        return sum(
            1 for entry in confirmations.values()
            if entry.user_id == user_id and entry.status == "pending"
        )

    @staticmethod
    def build_approval_keyboard(confirmation_id: str) -> dict:
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Aprovar",
                        "callback_data": f"approve:{confirmation_id}",
                    },
                    {
                        "text": "❌ Rejeitar",
                        "callback_data": f"reject:{confirmation_id}",
                    },
                ]
            ]
        }

    @staticmethod
    def build_approval_message(summary: str, confirmation_id: str) -> str:
        return (
            f"*Confirmação Necessária*\n\n"
            f"*Ação:* {summary}\n"
            f"*ID:* {confirmation_id}\n\n"
            f"Use os botões abaixo ou os comandos:\n"
            f"/approve {confirmation_id}\n"
            f"/reject {confirmation_id}"
        )