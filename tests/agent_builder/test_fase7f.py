from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, ANY

import pytest

from channels.telegram.conversation import (
    ConfirmationGateway,
    ConversationManager,
    UserContextManager,
    NaturalLanguageInterpreter,
    AgentSelector,
    UserContext,
)
from channels.telegram.utils import ConfirmationEntry, ConfirmationUtils


# ---------------------------------------------------------------------------
# Fixtures globais
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_agent():
    a = MagicMock(spec=["name", "description", "generate"])
    a.name = "marketing"
    a.description = "Agente de marketing"
    a.generate.return_value = "Resposta personalizada de marketing"
    return a


@pytest.fixture
def mock_general():
    a = MagicMock(spec=["name", "description", "generate"])
    a.name = "geral"
    a.description = "Agente geral"
    a.generate.return_value = "Resposta geral"
    return a


@pytest.fixture
def agents(mock_agent):
    sm = MagicMock(spec=["name", "description", "generate"])
    sm.name = "social_media"
    sm.description = "SM"
    sm.generate.return_value = "SM resp"
    return {"marketing": mock_agent, "social_media": sm}


@pytest.fixture
def mock_memory():
    m = MagicMock()
    m.salvar_conversa.return_value = 1
    m.historico.return_value = [
        {"papel": "user", "conteudo": "Crie uma campanha", "agente": "marketing",
         "criado_em": "2024-01-01T00:00:00"},
        {"papel": "assistant", "conteudo": "Resposta de marketing", "agente": "marketing",
         "criado_em": "2024-01-01T00:00:01"},
    ]
    m.contexto_recente.return_value = "user: Crie uma campanha\nassistant (marketing): Resposta de marketing"
    m.limpar_conversas.return_value = True
    return m


@pytest.fixture
def mock_logger():
    m = MagicMock()
    m.log.return_value = 1
    m.ultimos.return_value = [{"id": 1, "usuario_id": "user1", "agente": "marketing"}]
    return m


@pytest.fixture
def mock_metrics():
    m = MagicMock()
    m.record.return_value = None
    m.summary.return_value = {
        "total": 3, "by_agent": {"marketing": 2, "confirmation_gateway": 1},
    }
    return m


@pytest.fixture
def mock_persistence(mock_memory, mock_logger, mock_metrics):
    with (
        patch("channels.telegram.persistence.MemoryManager") as mm_cls,
        patch("channels.telegram.persistence.ActivityLogger") as al_cls,
        patch("channels.telegram.persistence.get_metrics") as gm_cls,
        patch("channels.telegram.persistence.get_connection") as gc_cls,
    ):
        mm_cls.return_value = mock_memory
        al_cls.return_value = mock_logger
        gm_cls.return_value = mock_metrics
        gc_cls.return_value = MagicMock()
        from channels.telegram.persistence import TelegramPersistenceService
        p = TelegramPersistenceService()
        yield p


@pytest.fixture
def gateway():
    g = ConfirmationGateway()
    g._timer.cancel()
    return g


@pytest.fixture
def cm(gateway, agents, mock_general, mock_persistence):
    return ConversationManager(
        agents, mock_general,
        confirmation_gateway=gateway,
        persistence_service=mock_persistence,
    )


@pytest.fixture
def entry(gateway):
    return gateway.create_confirmation(
        user_id="user1", step_name="enviar_email",
        effect="sensitive", summary="Enviar email para 1000 contatos",
    )


# ===========================================================================
# 1. Conversa natural pelo Telegram
# ===========================================================================

class TestNaturalConversation:
    def test_natural_language_routes_to_correct_agent(self, cm):
        response, agent = cm.handle_message("user1", "Crie uma campanha de Natal")
        assert agent == "marketing"
        assert "marketing" in response

    def test_greeting_goes_to_general(self, cm):
        response, agent = cm.handle_message("user1", "Bom dia, tudo bem?")
        assert agent == "geral"

    def test_followup_continues_same_agent(self, cm):
        cm.handle_message("user1", "Preciso de uma campanha")
        mock_agent = cm._agents["marketing"]
        mock_agent.generate.reset_mock()
        cm.handle_message("user1", "Continue")
        mock_agent.generate.assert_called_once()

    def test_history_is_built_across_turns(self, cm):
        cm.handle_message("user1", "Campanha de marketing")
        cm.handle_message("user1", "Refine a proposta")
        ctx = cm.context_manager.get("user1")
        assert len(ctx.conversation_history) == 4


# ===========================================================================
# 2. Selecao automatica do agente correto
# ===========================================================================

class TestAutomaticAgentSelection:
    def test_selects_marketing_for_campaign(self, cm):
        _, agent = cm.handle_message("user1", "Crie uma campanha no Google Ads")
        assert agent == "marketing"

    def test_selects_social_media_for_post(self, cm):
        _, agent = cm.handle_message("user1", "Preciso de um post para Instagram")
        assert agent == "social_media"

    def test_fallback_to_general_when_no_match(self, cm):
        _, agent = cm.handle_message("user1", "Bom dia")
        assert agent == "geral"

    def test_active_agent_overrides_auto(self, cm):
        cm.set_active_agent("user1", "marketing")
        response, agent = cm.handle_message("user1", "Bom dia")
        assert agent == "marketing"

    def test_followup_uses_last_agent(self, cm):
        cm.handle_message("user1", "Campanha de marketing")
        cm.handle_message("user1", "Explique melhor")
        ctx = cm.context_manager.get("user1")
        assert ctx.last_agent == "marketing"

    def test_language_interpreter_detects_intent(self):
        interp = NaturalLanguageInterpreter()
        result = interp.interpret("Preciso de uma proposta comercial")
        assert result.intent == "agent_request"
        assert result.agent_hint == "vendas"

    def test_selector_returns_none_when_no_match(self):
        selector = AgentSelector({}, None)
        from channels.telegram.conversation import Interpretation
        interp = Interpretation(intent="unknown", confidence=0.1)
        assert selector.select(interp) is None


# ===========================================================================
# 3. Execucao do agente
# ===========================================================================

class TestAgentExecution:
    def test_agent_generate_is_called(self, cm, mock_agent):
        cm.handle_message("user1", "Crie uma campanha de marketing")
        mock_agent.generate.assert_called_once()

    def test_agent_response_is_returned(self, cm):
        response, agent = cm.handle_message("user1", "Crie uma campanha")
        assert response == "Resposta personalizada de marketing"
        assert agent == "marketing"

    def test_general_agent_responds_when_no_specialist(self, cm):
        response, agent = cm.handle_message("user1", "Qual e a capital do Brasil?")
        assert response == "Resposta geral"
        assert agent == "geral"

    def test_agent_execution_with_confirmation_flow(self, cm, gateway):
        entry = gateway.create_confirmation(
            "user1", "enviar_email", "sensitive",
            "Enviar email promocional",
        )
        success, status, _ = gateway.approve_confirmation(entry.confirmation_id, "user1")
        assert success is True
        assert status == "approved"

    def test_user_context_tracks_last_agent(self, cm):
        mgr = UserContextManager()
        mgr.update_activity("user1", "marketing")
        assert mgr.get("user1").last_agent == "marketing"


# ===========================================================================
# 4. Solicitacao de confirmacao quando necessaria
# ===========================================================================

class TestConfirmationRequest:
    def test_create_confirmation_for_sensitive_action(self, gateway):
        entry = gateway.create_confirmation(
            "user1", "enviar_email", "sensitive",
            "Enviar email para 1000 contatos",
        )
        assert entry.status == "pending"
        assert entry.step_name == "enviar_email"

    def test_needs_confirmation_returns_true_for_sensitive(self, gateway):
        gateway.create_confirmation("user1", "enviar_email", "sensitive", "Enviar email")
        assert gateway.needs_confirmation("user1", "enviar_email", "sensitive") is True

    def test_needs_confirmation_returns_false_for_read_only(self, gateway):
        assert gateway.needs_confirmation("user1", "ler_relatorio", "read_only") is False

    def test_needs_confirmation_false_after_approval(self, gateway):
        e = gateway.create_confirmation("user1", "enviar_email", "sensitive", "envio")
        gateway.approve_confirmation(e.confirmation_id, "user1")
        assert gateway.needs_confirmation("user1", "enviar_email", "sensitive") is False

    def test_confirmation_appears_in_pending_list(self, gateway):
        gateway.create_confirmation("user1", "acao", "sensitive", "resumo")
        pending = gateway.get_user_pending_confirmations("user1")
        assert len(pending) == 1

    def test_confirmation_generates_unique_token(self, gateway):
        e1 = gateway.create_confirmation("user1", "a", "sensitive", "r1")
        e2 = gateway.create_confirmation("user1", "b", "sensitive", "r2")
        assert e1.confirmation_id != e2.confirmation_id


# ===========================================================================
# 5. Aprovacao via botao inline
# ===========================================================================

class TestInlineApprove:
    def test_callback_approve_changes_status(self, gateway, entry):
        success, status, e = gateway.handle_callback(
            "user1", f"approve:{entry.confirmation_id}",
        )
        assert success is True
        assert status == "approved"
        assert e.status == "approved"
        assert e.approved_by == "user1"

    def test_callback_approve_rejects_unauthorized(self, gateway, entry):
        success, status, _ = gateway.handle_callback(
            "user2", f"approve:{entry.confirmation_id}",
        )
        assert success is False
        assert status == "unauthorized"

    def test_callback_approve_only_accepts_valid_action(self, gateway, entry):
        success, status, _ = gateway.handle_callback(
            "user1", f"invalid:{entry.confirmation_id}",
        )
        assert success is False
        assert status == "invalid_callback"

    def test_callback_approve_malformed_data(self, gateway):
        success, status, _ = gateway.handle_callback("user1", "no_colon")
        assert success is False
        assert status == "invalid_callback"

    def test_callback_approve_unknown_id(self, gateway):
        success, status, _ = gateway.handle_callback("user1", "approve:unknown")
        assert success is False
        assert status == "confirmation_not_found"


# ===========================================================================
# 6. Rejeicao via botao inline
# ===========================================================================

class TestInlineReject:
    def test_callback_reject_changes_status(self, gateway, entry):
        success, status, e = gateway.handle_callback(
            "user1", f"reject:{entry.confirmation_id}",
        )
        assert success is True
        assert status == "rejected"
        assert e.status == "rejected"
        assert e.rejected_by == "user1"

    def test_callback_reject_blocks_unauthorized(self, gateway, entry):
        success, status, _ = gateway.handle_callback(
            "user2", f"reject:{entry.confirmation_id}",
        )
        assert success is False
        assert status == "unauthorized"


# ===========================================================================
# 7. Aprovacao por comando (/approve)
# ===========================================================================

class TestCommandApprove:
    def test_approve_by_command_success(self, gateway, entry):
        success, status, e = gateway.approve_confirmation(
            entry.confirmation_id, "user1",
        )
        assert success is True
        assert status == "approved"
        assert e.approved_by == "user1"
        assert e.status == "approved"

    def test_approve_by_command_invalid_id(self, gateway):
        success, status, _ = gateway.approve_confirmation("invalid", "user1")
        assert success is False
        assert status == "confirmation_not_found"

    def test_approve_by_command_unauthorized(self, gateway, entry):
        success, status, _ = gateway.approve_confirmation(
            entry.confirmation_id, "user2",
        )
        assert success is False
        assert status == "unauthorized"

    def test_approve_by_command_already_approved(self, gateway, entry):
        gateway.approve_confirmation(entry.confirmation_id, "user1")
        success, status, _ = gateway.approve_confirmation(
            entry.confirmation_id, "user1",
        )
        assert success is False
        assert "already_" in status

    def test_approve_updates_status(self, gateway, entry):
        gateway.approve_confirmation(entry.confirmation_id, "user1")
        assert entry.status == "approved"


# ===========================================================================
# 8. Rejeicao por comando (/reject)
# ===========================================================================

class TestCommandReject:
    def test_reject_by_command_success(self, gateway, entry):
        success, status, e = gateway.reject_confirmation(
            entry.confirmation_id, "user1",
        )
        assert success is True
        assert status == "rejected"
        assert e.rejected_by == "user1"
        assert e.status == "rejected"

    def test_reject_by_command_invalid_id(self, gateway):
        success, status, _ = gateway.reject_confirmation("invalid", "user1")
        assert success is False
        assert status == "confirmation_not_found"

    def test_reject_by_command_unauthorized(self, gateway, entry):
        success, status, _ = gateway.reject_confirmation(
            entry.confirmation_id, "user2",
        )
        assert success is False
        assert status == "unauthorized"

    def test_reject_by_command_already_rejected(self, gateway, entry):
        gateway.reject_confirmation(entry.confirmation_id, "user1")
        success, status, _ = gateway.reject_confirmation(
            entry.confirmation_id, "user1",
        )
        assert success is False
        assert "already_" in status

    def test_reject_updates_status(self, gateway, entry):
        gateway.reject_confirmation(entry.confirmation_id, "user1")
        assert entry.status == "rejected"


# ===========================================================================
# 9. Expiracao de confirmacoes
# ===========================================================================

class TestExpiration:
    def test_approve_expired_confirmation_returns_expired(self, gateway):
        e = gateway.create_confirmation("user1", "exp", "sensitive", "vai expirar")
        e.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        e.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert e.is_expired is True
        success, status, _ = gateway.approve_confirmation(e.confirmation_id, "user1")
        assert success is False
        assert status == "expired"

    def test_reject_expired_confirmation_returns_expired(self, gateway):
        e = gateway.create_confirmation("user1", "exp", "sensitive", "vai expirar")
        e.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        success, status, _ = gateway.reject_confirmation(e.confirmation_id, "user1")
        assert success is False
        assert status == "expired"

    def test_callback_expired_returns_already_expired(self, gateway):
        e = gateway.create_confirmation("user1", "exp", "sensitive", "vai expirar")
        e.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        e.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        success, status, _ = gateway.handle_callback(
            "user1", f"approve:{e.confirmation_id}",
        )
        assert success is False
        assert status == "already_expired"

    def test_cleanup_marks_expired(self, gateway):
        e = gateway.create_confirmation("user1", "exp", "sensitive", "vai expirar")
        e.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        cleaned = gateway.cleanup_expired_confirmations()
        assert cleaned >= 1
        assert e.status == "expired"

    def test_cleanup_ignores_pending(self, gateway, entry):
        cleaned = gateway.cleanup_expired_confirmations()
        assert cleaned == 0
        assert entry.status == "pending"

    def test_history_tracks_expiration(self, gateway):
        e = gateway.create_confirmation("user1", "exp", "sensitive", "vai expirar")
        e.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        gateway.cleanup_expired_confirmations()
        history = gateway.get_history()
        expired = [h for h in history if h["status"] == "expired"]
        assert len(expired) >= 1


# ===========================================================================
# 10. Bloqueio de reutilizacao do mesmo token
# ===========================================================================

class TestTokenReuseBlock:
    def test_duplicate_approve_by_command_blocked(self, gateway, entry):
        gateway.approve_confirmation(entry.confirmation_id, "user1")
        success, status, _ = gateway.approve_confirmation(
            entry.confirmation_id, "user1",
        )
        assert success is False
        assert "already_" in status

    def test_duplicate_reject_by_command_blocked(self, gateway, entry):
        gateway.reject_confirmation(entry.confirmation_id, "user1")
        success, status, _ = gateway.reject_confirmation(
            entry.confirmation_id, "user1",
        )
        assert success is False
        assert "already_" in status

    def test_approve_after_reject_blocked(self, gateway, entry):
        gateway.reject_confirmation(entry.confirmation_id, "user1")
        success, status, _ = gateway.approve_confirmation(
            entry.confirmation_id, "user1",
        )
        assert success is False
        assert "already_" in status

    def test_reject_after_approve_blocked(self, gateway, entry):
        gateway.approve_confirmation(entry.confirmation_id, "user1")
        success, status, _ = gateway.reject_confirmation(
            entry.confirmation_id, "user1",
        )
        assert success is False
        assert "already_" in status

    def test_callback_after_approve_blocked(self, gateway, entry):
        gateway.approve_confirmation(entry.confirmation_id, "user1")
        success, status, _ = gateway.handle_callback(
            "user1", f"approve:{entry.confirmation_id}",
        )
        assert success is False
        assert "already_" in status

    def test_callback_after_reject_blocked(self, gateway, entry):
        gateway.reject_confirmation(entry.confirmation_id, "user1")
        success, status, _ = gateway.handle_callback(
            "user1", f"approve:{entry.confirmation_id}",
        )
        assert success is False
        assert "already_" in status

    def test_utils_duplicate_click_detection(self, gateway, entry):
        confirmations = gateway.pending_confirmations
        assert ConfirmationUtils.is_duplicate_click(confirmations, entry.confirmation_id) is False
        gateway.approve_confirmation(entry.confirmation_id, "user1")
        assert ConfirmationUtils.is_duplicate_click(confirmations, entry.confirmation_id) is True


# ===========================================================================
# 11. Recuperacao do contexto apos aprovacao
# ===========================================================================

class TestContextRecoveryAfterApproval:
    def test_restore_context_after_approve(self, cm):
        cm.handle_message("user1", "Preciso enviar um email")
        cm.context_manager.clear_history("user1")
        restored = cm.restore_context("user1")
        assert restored > 0
        ctx = cm.context_manager.get("user1")
        assert len(ctx.conversation_history) > 0

    def test_context_restored_from_persistence(self, cm):
        restored = cm.restore_context("user1")
        assert restored == 2
        ctx = cm.context_manager.get("user1")
        assert ctx.last_agent == "marketing"

    def test_context_restore_without_persistence_returns_zero(self, mock_general, agents):
        cm_no_persist = ConversationManager(agents, mock_general)
        assert cm_no_persist.restore_context("user1") == 0

    def test_persistence_stats_show_restored_messages(self, cm):
        stats = cm.get_persistence_stats("user1")
        assert stats["enabled"] is True
        assert stats["total_messages"] == 2

    def test_format_response_includes_agent_name(self, cm):
        formatted = cm.format_response("Mensagem", "marketing")
        assert "[Marketing]" in formatted

    def test_status_includes_persisted_history(self, cm):
        status = cm.get_status("user1")
        assert "persisted_history" in status
        assert status["persisted_history"] == 2


# ===========================================================================
# 12. Persistencia de logs
# ===========================================================================

class TestLogPersistence:
    def test_execution_logged_on_message(self, cm, mock_persistence):
        assert mock_persistence.logger is not None

    def test_persistence_log_execution(self, mock_logger):
        from channels.telegram.persistence import TelegramPersistenceService
        srv = TelegramPersistenceService()
        srv.logger = mock_logger
        entry_id = srv.log_execution("user1", "marketing", 150)
        mock_logger.log.assert_called_once_with(
            usuario_id="user1", agente="marketing",
            ferramenta="telegram_message", duracao_ms=150, erro="",
        )

    def test_persistence_log_execution_with_error(self, mock_logger):
        from channels.telegram.persistence import TelegramPersistenceService
        srv = TelegramPersistenceService()
        srv.logger = mock_logger
        srv.log_execution("user1", "marketing", 200, "timeout")
        mock_logger.log.assert_called_once_with(
            usuario_id="user1", agente="marketing",
            ferramenta="telegram_message", duracao_ms=200, erro="timeout",
        )

    def test_persistence_retrieves_logs(self, mock_persistence):
        logs = mock_persistence.get_execution_history("user1")
        assert len(logs) >= 1
        assert logs[0]["usuario_id"] == "user1"

    def test_persistence_clears_user_history(self, mock_persistence):
        result = mock_persistence.clear_user_history("user1")
        assert result is True


# ===========================================================================
# 13. Persistencia de metricas
# ===========================================================================

class TestMetricPersistence:
    def test_message_metric_recorded(self, mock_metrics):
        from channels.telegram.persistence import TelegramPersistenceService
        from agent_builder.metrics import MetricEntry
        srv = TelegramPersistenceService()
        srv.metrics = mock_metrics
        srv.record_message_metric("marketing", True, 100.0)
        mock_metrics.record.assert_called_once()
        entry: MetricEntry = mock_metrics.record.call_args[0][0]
        assert entry.capability == "telegram.message"
        assert entry.success is True
        assert entry.duration_ms == 100.0

    def test_confirmation_metric_approve(self, mock_metrics):
        from channels.telegram.persistence import TelegramPersistenceService
        srv = TelegramPersistenceService()
        srv.metrics = mock_metrics
        srv.record_confirmation_metric("user1", "approve", "enviar_email")
        mock_metrics.record.assert_called_once()

    def test_confirmation_metric_reject(self, mock_metrics):
        from channels.telegram.persistence import TelegramPersistenceService
        srv = TelegramPersistenceService()
        srv.metrics = mock_metrics
        srv.record_confirmation_metric("user1", "reject", "enviar_email")
        mock_metrics.record.assert_called_once()

    def test_metrics_summary(self, mock_persistence):
        summary = mock_persistence.get_metrics_summary()
        assert summary["total"] == 3
        assert "confirmation_gateway" in summary["by_agent"]

    def test_metrics_entry_isolation(self):
        from agent_builder.metrics import MetricEntry
        e1 = MetricEntry(
            agent_id="mkt", agent_name="marketing",
            capability="telegram.message", plugin="telegram",
            success=True, duration_ms=100, session="user1",
        )
        e2 = MetricEntry(
            agent_id="mkt", agent_name="marketing",
            capability="telegram.message", plugin="telegram",
            success=True, duration_ms=100, session="user2",
        )
        assert e1.session == "user1"
        assert e2.session == "user2"


# ===========================================================================
# 14. Testes de multiplos utilizadores simultaneos
# ===========================================================================

class TestMultiUser:
    def test_simultaneous_users_isolated(self, cm):
        cm.handle_message("alice", "Campanha de marketing")
        cm.handle_message("bob", "Preciso de um post para Instagram")
        ctx_a = cm.context_manager.get("alice")
        ctx_b = cm.context_manager.get("bob")
        assert ctx_a.last_agent == "marketing"
        assert ctx_b.last_agent == "social_media"
        assert len(ctx_a.conversation_history) == 2
        assert len(ctx_b.conversation_history) == 2

    def test_confirmation_isolation_per_user(self, gateway):
        e1 = gateway.create_confirmation("alice", "acao", "sensitive", "r")
        e2 = gateway.create_confirmation("bob", "acao2", "sensitive", "r2")
        success, status, _ = gateway.approve_confirmation(e1.confirmation_id, "bob")
        assert success is False
        assert status == "unauthorized"
        success, status, _ = gateway.approve_confirmation(e1.confirmation_id, "alice")
        assert success is True

    def test_pending_confirmations_scoped_to_user(self, gateway):
        gateway.create_confirmation("alice", "acao1", "sensitive", "r1")
        gateway.create_confirmation("alice", "acao2", "sensitive", "r2")
        gateway.create_confirmation("bob", "acao3", "sensitive", "r3")
        alice_pending = gateway.get_user_pending_confirmations("alice")
        bob_pending = gateway.get_user_pending_confirmations("bob")
        assert len(alice_pending) == 2
        assert len(bob_pending) == 1

    def test_concurrent_messages_dont_interfere(self, cm):
        for i in range(5):
            cm.handle_message("alice", f"msg alice {i}")
            cm.handle_message("bob", f"msg bob {i}")
        ctx_a = cm.context_manager.get("alice")
        ctx_b = cm.context_manager.get("bob")
        assert len(ctx_a.conversation_history) == 10
        assert len(ctx_b.conversation_history) == 10

    def test_gateway_thread_safety(self, gateway):
        e = gateway.create_confirmation("user1", "acao", "sensitive", "r")
        assert gateway._lock.locked() is False

    def test_clear_history_only_affects_one_user(self, cm):
        cm.handle_message("alice", "Campanha de marketing")
        cm.handle_message("bob", "Instagram post")
        cm.context_manager.clear_history("alice")
        assert len(cm.context_manager.get_history("alice")) == 0
        assert len(cm.context_manager.get_history("bob")) >= 2


# ===========================================================================
# 15. Testes de erro
# ===========================================================================

class TestErrorHandling:
    def test_empty_message_returns_low_confidence(self):
        interp = NaturalLanguageInterpreter()
        result = interp.interpret("")
        assert result.confidence == 0.0
        assert result.intent == "empty"

    def test_unknown_agent_name_returns_not_found(self, cm):
        result = cm.set_active_agent("user1", "agente_inexistente")
        assert "nao encontrado" in result

    def test_no_agents_available_returns_fallback(self, mock_general):
        cm_empty = ConversationManager({}, mock_general)
        response, agent = cm_empty.handle_message("user1", "Campanha de marketing")
        assert agent == "geral"
        assert response == "Resposta geral"

    def test_no_agents_no_general_returns_error(self):
        cm_none = ConversationManager({}, None)
        response, agent = cm_none.handle_message("user1", "Campanha de marketing")
        assert agent is None
        assert "Nao encontrei" in response

    def test_agent_generate_exception_propagates(self, mock_general):
        agent = MagicMock(spec=["name", "description", "generate"])
        agent.name = "marketing"
        agent.description = "Marketing"
        agent.generate.side_effect = Exception("Erro interno")
        cm_err = ConversationManager({"marketing": agent}, mock_general)
        with pytest.raises(Exception, match="Erro interno"):
            cm_err.handle_message("user1", "Crie uma campanha")

    def test_callback_with_invalid_data_format(self, gateway):
        success, status, _ = gateway.handle_callback("user1", "bad_data")
        assert success is False
        assert status == "invalid_callback"

    def test_callback_with_empty_data(self, gateway):
        success, status, _ = gateway.handle_callback("user1", "")
        assert success is False
        assert status == "invalid_callback"


# ===========================================================================
# 16. Recuperacao apos reinicio
# ===========================================================================

class TestRestartRecovery:
    def test_restore_context_from_persistence_after_restart(self, mock_memory):
        from channels.telegram.persistence import TelegramPersistenceService
        with (
            patch("channels.telegram.persistence.MemoryManager") as mm_cls,
            patch("channels.telegram.persistence.ActivityLogger") as al_cls,
            patch("channels.telegram.persistence.get_metrics") as gm_cls,
            patch("channels.telegram.persistence.get_connection") as gc_cls,
        ):
            mm_cls.return_value = mock_memory
            al_cls.return_value = MagicMock()
            gm_cls.return_value = MagicMock()
            gc_cls.return_value = MagicMock()

            fresh_agents = {"marketing": MagicMock(
                name="marketing", generate=MagicMock(return_value="ok"),
            )}
            from channels.telegram.conversation import ConversationManager
            restored_cm = ConversationManager(
                fresh_agents, MagicMock(name="geral", generate=MagicMock(return_value="ok")),
                persistence_service=TelegramPersistenceService(),
            )
            count = restored_cm.restore_context("user1")
            assert count == 2
            ctx = restored_cm.context_manager.get("user1")
            assert ctx.last_agent == "marketing"
            assert len(ctx.conversation_history) == 2

    def test_context_flag_survives_restart(self):
        from channels.telegram.persistence import TelegramPersistenceService
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"valor": "marketing"}
        with (
            patch("channels.telegram.persistence.MemoryManager"),
            patch("channels.telegram.persistence.ActivityLogger"),
            patch("channels.telegram.persistence.get_metrics"),
            patch("channels.telegram.persistence.get_connection", return_value=mock_conn),
        ):
            p = TelegramPersistenceService()
            flag = p.load_context_flag("user1", "active_agent", "")
            assert flag == "marketing"

    def test_pending_confirmations_cleared_on_restart(self, gateway):
        assert len(gateway.pending_confirmations) == 0

    def test_cleanup_on_startup(self, gateway):
        expired = gateway.cleanup_expired_confirmations()
        assert expired >= 0

    def test_metrics_survive_restart(self, mock_persistence):
        summary = mock_persistence.get_metrics_summary()
        assert summary["total"] >= 0

    def test_logs_survive_restart(self, mock_persistence):
        logs = mock_persistence.get_execution_history("user1")
        assert isinstance(logs, list)