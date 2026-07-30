from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta

import pytest

from channels.telegram.conversation import ConfirmationGateway
from channels.telegram.utils import ConfirmationUtils, ConfirmationEntry


@pytest.fixture
def gateway():
    g = ConfirmationGateway()
    g._timer.cancel()
    yield g


@pytest.fixture
def pending_entry(gateway):
    return gateway.create_confirmation(
        user_id="user1",
        step_name="enviar_email",
        effect="sensitive",
        summary="Enviar email promocional para 1000 contatos",
    )


class TestCreateConfirmation:
    def test_create_confirmation_success(self, gateway):
        entry = gateway.create_confirmation(
            user_id="user1",
            step_name="enviar_email",
            effect="sensitive",
            summary="Enviar email promocional",
        )
        assert entry.confirmation_id.startswith("conf_")
        assert entry.user_id == "user1"
        assert entry.step_name == "enviar_email"
        assert entry.status == "pending"
        assert entry.is_pending is True
        assert entry.is_expired is False

    def test_confirmation_unique_token(self, gateway):
        e1 = gateway.create_confirmation("user1", "acao1", "sensitive", "resumo1")
        e2 = gateway.create_confirmation("user1", "acao2", "sensitive", "resumo2")
        assert e1.confirmation_id != e2.confirmation_id

    def test_confirmation_stored_in_gateway(self, gateway):
        entry = gateway.create_confirmation("user1", "acao", "sensitive", "resumo")
        assert entry.confirmation_id in gateway.pending_confirmations


class TestApproveConfirmation:
    def test_approve_by_command(self, gateway, pending_entry):
        success, status, entry = gateway.approve_confirmation(
            pending_entry.confirmation_id, "user1",
        )
        assert success is True
        assert status == "approved"
        assert entry.status == "approved"
        assert entry.approved_by == "user1"

    def test_approve_adds_to_history(self, gateway, pending_entry):
        gateway.approve_confirmation(pending_entry.confirmation_id, "user1")
        history = gateway.get_history()
        assert any(h["confirmation_id"] == pending_entry.confirmation_id for h in history)

    def test_approve_invalid_id_returns_not_found(self, gateway):
        success, status, entry = gateway.approve_confirmation("invalid_id", "user1")
        assert success is False
        assert status == "confirmation_not_found"
        assert entry is None

    def test_approve_unauthorized_user(self, gateway, pending_entry):
        success, status, entry = gateway.approve_confirmation(
            pending_entry.confirmation_id, "user2",
        )
        assert success is False
        assert status == "unauthorized"

    def test_approve_already_approved_blocks_duplicate(self, gateway, pending_entry):
        gateway.approve_confirmation(pending_entry.confirmation_id, "user1")
        success, status, entry = gateway.approve_confirmation(
            pending_entry.confirmation_id, "user1",
        )
        assert success is False
        assert "already_" in status

    def test_approve_already_rejected_blocks_duplicate(self, gateway, pending_entry):
        gateway.reject_confirmation(pending_entry.confirmation_id, "user1")
        success, status, entry = gateway.approve_confirmation(
            pending_entry.confirmation_id, "user1",
        )
        assert success is False
        assert "already_" in status


class TestRejectConfirmation:
    def test_reject_by_command(self, gateway, pending_entry):
        success, status, entry = gateway.reject_confirmation(
            pending_entry.confirmation_id, "user1",
        )
        assert success is True
        assert status == "rejected"
        assert entry.status == "rejected"
        assert entry.rejected_by == "user1"

    def test_reject_adds_to_history(self, gateway, pending_entry):
        gateway.reject_confirmation(pending_entry.confirmation_id, "user1")
        history = gateway.get_history()
        assert any(h["confirmation_id"] == pending_entry.confirmation_id for h in history)

    def test_reject_invalid_id_returns_not_found(self, gateway):
        success, status, entry = gateway.reject_confirmation("invalid_id", "user1")
        assert success is False
        assert status == "confirmation_not_found"
        assert entry is None

    def test_reject_unauthorized_user(self, gateway, pending_entry):
        success, status, entry = gateway.reject_confirmation(
            pending_entry.confirmation_id, "user2",
        )
        assert success is False
        assert status == "unauthorized"


class TestHandleCallback:
    def test_callback_approve(self, gateway, pending_entry):
        success, status, entry = gateway.handle_callback(
            "user1", f"approve:{pending_entry.confirmation_id}",
        )
        assert success is True
        assert status == "approved"
        assert entry.status == "approved"

    def test_callback_reject(self, gateway, pending_entry):
        success, status, entry = gateway.handle_callback(
            "user1", f"reject:{pending_entry.confirmation_id}",
        )
        assert success is True
        assert status == "rejected"
        assert entry.status == "rejected"

    def test_callback_invalid_action(self, gateway, pending_entry):
        success, status, entry = gateway.handle_callback(
            "user1", f"invalid:{pending_entry.confirmation_id}",
        )
        assert success is False
        assert status == "invalid_callback"

    def test_callback_malformed_data(self, gateway):
        success, status, entry = gateway.handle_callback("user1", "invalid_format")
        assert success is False
        assert status == "invalid_callback"

    def test_callback_unknown_id(self, gateway):
        success, status, entry = gateway.handle_callback("user1", "approve:unknown")
        assert success is False
        assert status == "confirmation_not_found"
        assert entry is None

    def test_callback_unauthorized_user(self, gateway, pending_entry):
        success, status, entry = gateway.handle_callback(
            "user2", f"approve:{pending_entry.confirmation_id}",
        )
        assert success is False
        assert status == "unauthorized"

    def test_callback_duplicate_click(self, gateway, pending_entry):
        gateway.approve_confirmation(pending_entry.confirmation_id, "user1")
        success, status, entry = gateway.handle_callback(
            "user1", f"approve:{pending_entry.confirmation_id}",
        )
        assert success is False
        assert "already_" in status


class TestExpiration:
    def test_expired_confirmation_rejected(self, gateway):
        entry = gateway.create_confirmation(
            user_id="user1",
            step_name="acao_expirada",
            effect="sensitive",
            summary="Acao que vai expirar",
        )
        entry.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        entry.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert entry.is_expired is True

        success, status, entry = gateway.approve_confirmation(
            entry.confirmation_id, "user1",
        )
        assert success is False
        assert status == "expired"

    def test_cleanup_expired(self, gateway):
        entry = gateway.create_confirmation(
            user_id="user1",
            step_name="vai_expirar",
            effect="sensitive",
            summary="Vai expirar",
        )
        entry.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        cleaned = gateway.cleanup_expired_confirmations()
        assert cleaned >= 1
        assert entry.status == "expired"

    def test_cleanup_ignores_active(self, gateway, pending_entry):
        cleaned = gateway.cleanup_expired_confirmations()
        assert cleaned == 0
        assert pending_entry.status == "pending"

    def test_expired_callback_rejected(self, gateway):
        entry = gateway.create_confirmation("user1", "exp", "sensitive", "exp")
        entry.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        entry.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        success, status, entry = gateway.handle_callback(
            "user1", f"approve:{entry.confirmation_id}",
        )
        assert success is False
        assert status == "already_expired"


class TestHistory:
    def test_history_tracks_all_events(self, gateway):
        e1 = gateway.create_confirmation("user1", "acao1", "sensitive", "resumo1")
        e2 = gateway.create_confirmation("user1", "acao2", "sensitive", "resumo2")
        gateway.approve_confirmation(e1.confirmation_id, "user1")
        gateway.reject_confirmation(e2.confirmation_id, "user1")
        history = gateway.get_history()
        assert len(history) >= 4
        statuses = [h["status"] for h in history if h["confirmation_id"] in (e1.confirmation_id, e2.confirmation_id)]
        assert "approved" in statuses
        assert "rejected" in statuses

    def test_history_includes_timestamp(self, gateway):
        gateway.create_confirmation("user1", "acao", "sensitive", "resumo")
        history = gateway.get_history()
        assert "timestamp" in history[-1]

    def test_history_includes_step_name(self, gateway):
        gateway.create_confirmation("user1", "minha_acao", "sensitive", "resumo")
        history = gateway.get_history()
        assert history[-1]["step_name"] == "minha_acao"


class TestPendingConfirmations:
    def test_get_user_pending(self, gateway):
        gateway.create_confirmation("user1", "acao1", "sensitive", "r1")
        gateway.create_confirmation("user1", "acao2", "sensitive", "r2")
        gateway.create_confirmation("user2", "acao3", "sensitive", "r3")
        pending = gateway.get_user_pending_confirmations("user1")
        assert len(pending) == 2

    def test_pending_excludes_approved(self, gateway):
        e = gateway.create_confirmation("user1", "acao", "sensitive", "r")
        gateway.approve_confirmation(e.confirmation_id, "user1")
        pending = gateway.get_user_pending_confirmations("user1")
        assert len(pending) == 0

    def test_pending_excludes_rejected(self, gateway):
        e = gateway.create_confirmation("user1", "acao", "sensitive", "r")
        gateway.reject_confirmation(e.confirmation_id, "user1")
        pending = gateway.get_user_pending_confirmations("user1")
        assert len(pending) == 0


class TestNeedsConfirmation:
    def test_needs_confirmation_sensitive(self, gateway):
        gateway.create_confirmation("user1", "acao", "sensitive", "r")
        assert gateway.needs_confirmation("user1", "acao", "sensitive") is True

    def test_needs_confirmation_read_only(self, gateway):
        assert gateway.needs_confirmation("user1", "acao", "read_only") is False

    def test_needs_confirmation_after_approval(self, gateway):
        e = gateway.create_confirmation("user1", "acao", "sensitive", "r")
        gateway.approve_confirmation(e.confirmation_id, "user1")
        assert gateway.needs_confirmation("user1", "acao", "sensitive") is False


class TestConfirmationUtils:
    def test_utils_create(self):
        entry = ConfirmationUtils.create_confirmation(
            "user1", "acao", "sensitive", "resumo", {"dado": 1},
        )
        assert isinstance(entry, ConfirmationEntry)
        assert entry.user_id == "user1"
        assert entry.data == {"dado": 1}

    def test_utils_approve_static(self):
        confirmations = {}
        entry = ConfirmationUtils.create_confirmation("user1", "acao", "sensitive", "r")
        confirmations[entry.confirmation_id] = entry
        success, msg = ConfirmationUtils.approve_confirmation(confirmations, entry.confirmation_id, "user1")
        assert success is True
        assert msg == "approved"

    def test_utils_reject_static(self):
        confirmations = {}
        entry = ConfirmationUtils.create_confirmation("user1", "acao", "sensitive", "r")
        confirmations[entry.confirmation_id] = entry
        success, msg = ConfirmationUtils.reject_confirmation(confirmations, entry.confirmation_id, "user1")
        assert success is True
        assert msg == "rejected"

    def test_utils_pending_count(self):
        confirmations = {}
        e1 = ConfirmationUtils.create_confirmation("user1", "a", "sensitive", "r")
        e2 = ConfirmationUtils.create_confirmation("user1", "b", "sensitive", "r")
        confirmations[e1.confirmation_id] = e1
        confirmations[e2.confirmation_id] = e2
        assert ConfirmationUtils.get_pending_count(confirmations, "user1") == 2

    def test_utils_cleanup_expired(self):
        confirmations = {}
        e = ConfirmationUtils.create_confirmation("user1", "a", "sensitive", "r")
        e.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        confirmations[e.confirmation_id] = e
        cleaned = ConfirmationUtils.cleanup_expired(confirmations)
        assert cleaned == 1

    def test_utils_is_duplicate_click(self):
        confirmations = {}
        e = ConfirmationUtils.create_confirmation("user1", "a", "sensitive", "r")
        confirmations[e.confirmation_id] = e
        assert ConfirmationUtils.is_duplicate_click(confirmations, e.confirmation_id) is False
        ConfirmationUtils.approve_confirmation(confirmations, e.confirmation_id, "user1")
        assert ConfirmationUtils.is_duplicate_click(confirmations, e.confirmation_id) is True

    def test_utils_build_keyboard(self):
        keyboard = ConfirmationUtils.build_approval_keyboard("conf_test123")
        assert "inline_keyboard" in keyboard
        assert len(keyboard["inline_keyboard"]) == 1
        assert len(keyboard["inline_keyboard"][0]) == 2
        labels = [b["text"] for b in keyboard["inline_keyboard"][0]]
        assert "✅ Aprovar" in labels
        assert "❌ Rejeitar" in labels

    def test_utils_build_message(self):
        msg = ConfirmationUtils.build_approval_message("Enviar email", "conf_test123")
        assert "Confirma" in msg
        assert "conf_test123" in msg
        assert "/approve" in msg
        assert "/reject" in msg