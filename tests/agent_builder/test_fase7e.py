from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from channels.telegram.conversation import (
    ConfirmationGateway,
    ConversationManager,
    UserContextManager,
)
from channels.telegram.persistence import TelegramPersistenceService


@pytest.fixture
def mock_memory():
    m = MagicMock()
    m.salvar_conversa.return_value = 1
    m.historico.return_value = [
        {"papel": "user", "conteudo": "Ola", "agente": "", "criado_em": "2024-01-01T00:00:00"},
        {"papel": "assistant", "conteudo": "Oi!", "agente": "geral", "criado_em": "2024-01-01T00:00:01"},
    ]
    m.contexto_recente.return_value = "user: Ola\nassistant (geral): Oi!"
    m.limpar_conversas.return_value = True
    return m


@pytest.fixture
def mock_logger():
    m = MagicMock()
    m.log.return_value = 1
    m.ultimos.return_value = []
    return m


@pytest.fixture
def mock_metrics():
    m = MagicMock()
    m.record.return_value = None
    m.summary.return_value = {"total": 0}
    return m


@pytest.fixture
def persistence(mock_memory, mock_logger, mock_metrics):
    with (
        patch("channels.telegram.persistence.MemoryManager") as mm_cls,
        patch("channels.telegram.persistence.ActivityLogger") as al_cls,
        patch("channels.telegram.persistence.get_metrics") as gm_cls,
        patch("channels.telegram.persistence.get_connection") as gc_cls,
    ):
        mm_cls.return_value = mock_memory
        al_cls.return_value = mock_logger
        gm_cls.return_value = mock_metrics
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        gc_cls.return_value = mock_conn
        p = TelegramPersistenceService()
        yield p


@pytest.fixture
def agents():
    m = MagicMock()
    m.name = "marketing"
    m.description = "Agente de marketing"
    m.generate.return_value = "Resposta de marketing"
    return {"marketing": m}


@pytest.fixture
def cm_with_persistence(agents, persistence):
    general = MagicMock()
    general.name = "geral"
    general.description = "Agente geral"
    general.generate.return_value = "Resposta geral"
    return ConversationManager(agents, general, persistence_service=persistence)


class TestTelegramPersistenceService:
    def test_save_conversation(self, persistence, mock_memory):
        persistence.save_conversation("user1", "user", "Ola", "")
        mock_memory.salvar_conversa.assert_called_once_with("user1", "user", "Ola", "")

    def test_load_recent_context(self, persistence, mock_memory):
        result = persistence.load_recent_context("user1")
        mock_memory.historico.assert_called_once_with("user1", 10)
        assert len(result) == 2

    def test_restore_context_text(self, persistence, mock_memory):
        result = persistence.restore_context_text("user1")
        mock_memory.contexto_recente.assert_called_once_with("user1", 10)
        assert "user: Ola" in result
        assert "Oi!" in result

    def test_log_execution(self, persistence, mock_logger):
        persistence.log_execution("user1", "marketing", 150)
        mock_logger.log.assert_called_once_with(
            usuario_id="user1", agente="marketing",
            ferramenta="telegram_message", duracao_ms=150, erro="",
        )

    def test_log_execution_with_error(self, persistence, mock_logger):
        persistence.log_execution("user1", "marketing", 200, "timeout")
        mock_logger.log.assert_called_once_with(
            usuario_id="user1", agente="marketing",
            ferramenta="telegram_message", duracao_ms=200, erro="timeout",
        )

    def test_record_message_metric(self, persistence, mock_metrics):
        persistence.record_message_metric("marketing", True, 100.0)
        mock_metrics.record.assert_called_once()
        entry = mock_metrics.record.call_args[0][0]
        assert entry.agent_name == "marketing"
        assert entry.capability == "telegram.message"
        assert entry.success is True
        assert entry.duration_ms == 100.0

    def test_record_confirmation_metric_approve(self, persistence, mock_metrics):
        persistence.record_confirmation_metric("user1", "approve", "enviar_email")
        mock_metrics.record.assert_called_once()
        entry = mock_metrics.record.call_args[0][0]
        assert entry.capability == "telegram.confirmation.approve"
        assert entry.success is True

    def test_record_confirmation_metric_reject(self, persistence, mock_metrics):
        persistence.record_confirmation_metric("user1", "reject", "enviar_email")
        mock_metrics.record.assert_called_once()
        entry = mock_metrics.record.call_args[0][0]
        assert entry.capability == "telegram.confirmation.reject"
        assert entry.success is True

    def test_get_execution_history(self, persistence, mock_logger):
        persistence.get_execution_history("user1")
        mock_logger.ultimos.assert_called_once_with(20)

    def test_get_metrics_summary(self, persistence, mock_metrics):
        result = persistence.get_metrics_summary()
        mock_metrics.summary.assert_called_once()
        assert result == {"total": 0}

    def test_get_conversation_history(self, persistence, mock_memory):
        result = persistence.get_conversation_history("user1", 5)
        mock_memory.historico.assert_called_once_with("user1", 5)
        assert len(result) == 2

    def test_clear_user_history(self, persistence, mock_memory):
        result = persistence.clear_user_history("user1")
        mock_memory.limpar_conversas.assert_called_once_with("user1")
        assert result is True

    def test_save_context_flag(self, persistence):
        with patch("channels.telegram.persistence.get_connection") as gc:
            mock_conn = MagicMock()
            gc.return_value = mock_conn
            persistence.save_context_flag("user1", "active_agent", "marketing")
            assert mock_conn.execute.called

    def test_load_context_flag_default(self, persistence):
        result = persistence.load_context_flag("user1", "active_agent")
        assert result == ""

    def test_format_history_for_context(self, persistence, mock_memory):
        result = persistence.format_history_for_context("user1")
        mock_memory.contexto_recente.assert_called_with("user1", 10)
        assert "Ola" in result


class TestConversationManagerWithPersistence:
    def test_handle_message_persists(self, cm_with_persistence, persistence):
        with patch.object(persistence, 'save_conversation') as mock_save:
            response, agent_name = cm_with_persistence.handle_message(
                "user1", "Crie uma campanha de marketing",
            )
            assert agent_name == "marketing"
            assert mock_save.call_count == 2

    def test_handle_message_saves_user_and_assistant(self, cm_with_persistence, persistence):
        with patch.object(persistence, 'save_conversation') as mock_save:
            cm_with_persistence.handle_message("user1", "Campanha de marketing")
            user_call = mock_save.call_args_list[0]
            asst_call = mock_save.call_args_list[1]
            assert user_call[0][1] == "user"
            assert asst_call[0][1] == "assistant"

    def test_get_status_with_persistence(self, cm_with_persistence):
        status = cm_with_persistence.get_status("user1")
        assert "history_size" in status
        assert "available_agents" in status

    def test_restore_context(self, cm_with_persistence):
        restored = cm_with_persistence.restore_context("user1")
        assert restored >= 0

    def test_get_persistence_stats(self, cm_with_persistence):
        stats = cm_with_persistence.get_persistence_stats("user1")
        assert stats["enabled"] is True


class TestConversationManagerWithoutPersistence:
    @pytest.fixture
    def cm(self):
        agents = {"test": MagicMock(name="test", generate=MagicMock(return_value="ok"))}
        general = MagicMock(name="geral", generate=MagicMock(return_value="ok"))
        return ConversationManager(agents, general)

    def test_handle_message_works_without_persistence(self, cm):
        response, agent = cm.handle_message("user1", "test message")
        assert response is not None

    def test_restore_context_returns_zero_without_persistence(self, cm):
        restored = cm.restore_context("user1")
        assert restored == 0

    def test_get_persistence_stats_disabled(self, cm):
        stats = cm.get_persistence_stats("user1")
        assert stats["enabled"] is False

    def test_get_status_still_works(self, cm):
        status = cm.get_status("user1")
        assert "history_size" in status
        assert "persisted_history" not in status


class TestUserContextManager:
    @pytest.fixture
    def mgr(self):
        return UserContextManager(max_history=10)

    def test_get_creates_context(self, mgr):
        ctx = mgr.get("user1")
        assert ctx.user_id == "user1"
        assert ctx.conversation_history == []

    def test_add_to_history(self, mgr):
        mgr.add_to_history("user1", "user", "Ola", "geral")
        mgr.add_to_history("user1", "assistant", "Oi!", "geral")
        history = mgr.get_history("user1")
        assert len(history) == 2

    def test_history_limit(self, mgr):
        for i in range(15):
            mgr.add_to_history("user1", "user", f"Msg {i}", "geral")
        history = mgr.get_history("user1", limit=5)
        assert len(history) == 5

    def test_clear_history(self, mgr):
        mgr.add_to_history("user1", "user", "Ola", "geral")
        mgr.clear_history("user1")
        assert len(mgr.get_history("user1")) == 0


class TestIntegrationPersistenceAndConfirmation:
    @pytest.fixture
    def gateway(self):
        g = ConfirmationGateway()
        g._timer.cancel()
        return g

    def test_persists_and_confirms(self, gateway, persistence):
        entry = gateway.create_confirmation(
            "user1", "enviar_email", "sensitive", "Enviar email",
        )
        success, status, _ = gateway.approve_confirmation(
            entry.confirmation_id, "user1",
        )
        assert success is True

    def test_gateway_record_adds_history(self, gateway):
        entry = gateway.create_confirmation(
            "user1", "enviar_email", "sensitive", "Enviar email",
        )
        gateway.approve_confirmation(entry.confirmation_id, "user1")
        history = gateway.get_history()
        assert any(h["status"] == "approved" for h in history)


class TestUserIsolation:
    @pytest.fixture
    def persistence(self, mock_memory, mock_logger, mock_metrics):
        with (
            patch("channels.telegram.persistence.MemoryManager") as mm_cls,
            patch("channels.telegram.persistence.ActivityLogger") as al_cls,
            patch("channels.telegram.persistence.get_metrics") as gm_cls,
            patch("channels.telegram.persistence.get_connection") as gc_cls,
        ):
            mm_cls.return_value = mock_memory
            al_cls.return_value = mock_logger
            gm_cls.return_value = mock_metrics
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = None
            gc_cls.return_value = mock_conn
            p = TelegramPersistenceService()
            yield p

    def test_user_isolation_in_messages(self):
        ctx_mgr = UserContextManager()
        ctx1 = ctx_mgr.get("user_a")
        ctx2 = ctx_mgr.get("user_b")
        ctx_mgr.add_to_history("user_a", "user", "msg_a", "geral")
        ctx_mgr.add_to_history("user_b", "user", "msg_b", "marketing")
        assert len(ctx1.conversation_history) == 1
        assert len(ctx2.conversation_history) == 1
        assert ctx1.conversation_history[0]["content"] == "msg_a"
        assert ctx2.conversation_history[0]["content"] == "msg_b"

    def test_user_isolation_in_persistence(self, persistence, mock_memory):
        mock_memory.historico.side_effect = lambda uid, limit: (
            [{"papel": "user", "conteudo": f"msg_{uid}", "agente": ""}]
        )
        h_a = persistence.get_conversation_history("user_a")
        h_b = persistence.get_conversation_history("user_b")
        assert h_a[0]["conteudo"] == "msg_user_a"
        assert h_b[0]["conteudo"] == "msg_user_b"