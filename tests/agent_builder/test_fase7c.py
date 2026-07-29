"""
Testes para Fase 7.3 - Conversa natural do Telegram com CRIS OS.
Testa: interpretacao de linguagem natural, selecao de agentes,
contexto por utilizador, historico, fallback, e integracao completa.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _load_conversation():
    mod_name = "channels.telegram.conversation_test"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    mod_path = Path(__file__).resolve().parent.parent.parent / "channels" / "telegram" / "conversation.py"
    spec = importlib.util.spec_from_file_location(mod_name, str(mod_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


conv_mod = _load_conversation()

NaturalLanguageInterpreter = conv_mod.NaturalLanguageInterpreter
AgentSelector = conv_mod.AgentSelector
UserContextManager = conv_mod.UserContextManager
UserContext = conv_mod.UserContext
ConversationManager = conv_mod.ConversationManager
Interpretation = conv_mod.Interpretation


def _make_mock_agent(name: str, description: str = "", response: str = "ok") -> MagicMock:
    agent = MagicMock()
    agent.name = name
    agent.description = description or f"Agente {name}"
    agent.generate.return_value = response
    return agent


class TestNaturalLanguageInterpreter:
    @pytest.fixture
    def interp(self):
        return NaturalLanguageInterpreter()

    def test_empty_message(self, interp):
        result = interp.interpret("")
        assert result.intent == "empty"
        assert result.confidence == 0.0

    def test_command_detection(self, interp):
        result = interp.interpret("/agent")
        assert result.is_command is True
        assert result.intent == "command"

    def test_marketing_keywords(self, interp):
        result = interp.interpret("Crie uma campanha de marketing para o Natal")
        assert result.intent == "agent_request"
        assert result.agent_hint == "marketing"
        assert "campanha" in result.keywords

    def test_social_media_keywords(self, interp):
        result = interp.interpret("Preciso de uma legenda para Instagram")
        assert result.intent == "agent_request"
        assert result.agent_hint == "social_media"

    def test_programador_keywords(self, interp):
        result = interp.interpret("Me ajuda com um bug no meu codigo Python")
        assert result.intent == "agent_request"
        assert result.agent_hint == "programador"

    def test_vendas_keywords(self, interp):
        result = interp.interpret("Elabore uma proposta comercial para o cliente X")
        assert result.intent == "agent_request"
        assert result.agent_hint == "vendas"

    def test_atendimento_keywords(self, interp):
        result = interp.interpret("Cliente esta com reclamacao sobre cancelamento")
        assert result.intent == "agent_request"
        assert result.agent_hint == "atendimento"

    def test_pesquisador_keywords(self, interp):
        result = interp.interpret("Preciso de uma analise de concorrentes")
        assert result.intent == "agent_request"
        assert result.agent_hint == "pesquisador"

    def test_copywriter_keywords(self, interp):
        result = interp.interpret("Escreva uma landing page persuasiva")
        assert result.intent == "agent_request"
        assert result.agent_hint == "copywriter"

    def test_produtividade_keywords(self, interp):
        result = interp.interpret("Ajude me a organizar minha rotina diaria")
        assert result.intent == "agent_request"
        assert result.agent_hint == "produtividade"

    def test_general_question(self, interp):
        result = interp.interpret("Como funciona o sistema de precos?")
        assert result.intent == "general_question"
        assert result.confidence > 0.0

    def test_general_message(self, interp):
        result = interp.interpret("Bom dia")
        assert result.intent == "general"

    def test_multiple_keywords_same_agent(self, interp):
        result = interp.interpret("Campanha de marketing digital com anuncios")
        assert result.agent_hint == "marketing"
        assert len(result.keywords) >= 2

    def test_followup_detection(self, interp):
        ctx = UserContext(user_id="123", last_agent="marketing", last_activity=time.time())
        result = interp.interpret("Continue", ctx)
        assert result.is_followup is True
        assert result.agent_hint == "marketing"

    def test_followup_expired(self, interp):
        ctx = UserContext(user_id="123", last_agent="marketing", last_activity=time.time() - 600)
        result = interp.interpret("Continue", ctx)
        assert result.is_followup is False

    def test_followup_too_long(self, interp):
        ctx = UserContext(user_id="123", last_agent="marketing", last_activity=time.time())
        result = interp.interpret("Isso e muito importante para mim", ctx)
        assert result.is_followup is False


class TestAgentSelector:
    @pytest.fixture
    def agents(self):
        return {
            "marketing": _make_mock_agent("marketing", "Marketing"),
            "social_media": _make_mock_agent("social_media", "Social Media"),
            "programador": _make_mock_agent("programador", "Programador"),
        }

    @pytest.fixture
    def selector(self, agents):
        general = _make_mock_agent("geral", "Geral")
        return AgentSelector(agents, general)

    def test_select_by_interpretation(self, selector):
        interp = Interpretation(intent="agent_request", agent_hint="marketing", confidence=0.8)
        agent = selector.select(interp)
        assert agent.name == "marketing"

    def test_select_followup_with_context(self, selector):
        ctx = UserContext(user_id="123", last_agent="programador")
        interp = Interpretation(intent="followup", confidence=0.8, is_followup=True, agent_hint="programador")
        agent = selector.select(interp, ctx)
        assert agent.name == "programador"

    def test_select_fallback_to_general(self, selector):
        interp = Interpretation(intent="general", confidence=0.3)
        agent = selector.select(interp)
        assert agent.name == "geral"

    def test_select_with_active_agent(self, selector):
        ctx = UserContext(user_id="123", active_agent="social_media")
        interp = Interpretation(intent="general", confidence=0.3)
        agent = selector.select(interp, ctx)
        assert agent.name == "social_media"

    def test_list_agents(self, selector):
        agents = selector.list_agents()
        assert "marketing" in agents
        assert "programador" in agents


class TestUserContextManager:
    @pytest.fixture
    def mgr(self):
        return UserContextManager(max_history=10)

    def test_get_creates_context(self, mgr):
        ctx = mgr.get("user1")
        assert ctx.user_id == "user1"
        assert ctx.conversation_history == []

    def test_get_returns_same_context(self, mgr):
        ctx1 = mgr.get("user1")
        ctx2 = mgr.get("user1")
        assert ctx1 is ctx2

    def test_update_activity(self, mgr):
        ctx = mgr.update_activity("user1", "marketing")
        assert ctx.last_agent == "marketing"
        assert ctx.last_activity > 0

    def test_add_to_history(self, mgr):
        mgr.add_to_history("user1", "user", "Ola", "geral")
        mgr.add_to_history("user1", "assistant", "Ola Cris!", "geral")
        history = mgr.get_history("user1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    def test_history_limit(self, mgr):
        for i in range(15):
            mgr.add_to_history("user1", "user", f"Msg {i}", "geral")
        history = mgr.get_history("user1", limit=5)
        assert len(history) == 5
        assert history[0]["content"] == "Msg 10"

    def test_clear_history(self, mgr):
        mgr.add_to_history("user1", "user", "Ola", "geral")
        mgr.clear_history("user1")
        history = mgr.get_history("user1")
        assert len(history) == 0

    def test_set_active_agent(self, mgr):
        mgr.set_active_agent("user1", "marketing")
        assert mgr.get_active_agent("user1") == "marketing"

    def test_set_active_agent_none(self, mgr):
        mgr.set_active_agent("user1", "marketing")
        mgr.set_active_agent("user1", None)
        assert mgr.get_active_agent("user1") is None


class TestConversationManager:
    @pytest.fixture
    def agents(self):
        return {
            "marketing": _make_mock_agent("marketing", "Marketing", "Resposta de marketing"),
            "social_media": _make_mock_agent("social_media", "Social Media", "Resposta de social media"),
            "programador": _make_mock_agent("programador", "Programador", "Resposta de programador"),
        }

    @pytest.fixture
    def cm(self, agents):
        general = _make_mock_agent("geral", "Geral", "Resposta geral")
        return ConversationManager(agents, general)

    def test_handle_message_routes_to_agent(self, cm):
        response, agent_name = cm.handle_message("user1", "Crie uma campanha de marketing")
        assert agent_name == "marketing"
        assert response == "Resposta de marketing"

    def test_handle_message_general(self, cm):
        response, agent_name = cm.handle_message("user1", "Bom dia")
        assert agent_name == "geral"
        assert response == "Resposta geral"

    def test_handle_message_no_agent_found(self, cm):
        cm_no_general = ConversationManager(cm._agents, None)
        response, agent_name = cm_no_general.handle_message("user1", "xyz123")
        assert agent_name is None
        assert "Nao encontrei" in response

    def test_format_response_with_agent(self, cm):
        formatted = cm.format_response("Resposta", "marketing")
        assert "[Marketing]" in formatted
        assert "Resposta" in formatted

    def test_format_response_without_agent(self, cm):
        formatted = cm.format_response("Resposta", None)
        assert formatted == "Resposta"

    def test_set_active_agent(self, cm):
        result = cm.set_active_agent("user1", "marketing")
        assert "fixado" in result

    def test_set_active_agent_auto(self, cm):
        result = cm.set_active_agent("user1", None)
        assert "automatico" in result

    def test_set_active_agent_not_found(self, cm):
        result = cm.set_active_agent("user1", "naoexiste")
        assert "nao encontrado" in result

    def test_get_status(self, cm):
        cm.handle_message("user1", " teste marketing ")
        status = cm.get_status("user1")
        assert status["last_agent"] == "marketing"
        assert status["history_size"] >= 2

    def test_context_persists_across_messages(self, cm):
        cm.handle_message("user1", "Campanha de marketing")
        cm.handle_message("user1", "Continue")
        ctx = cm.context_manager.get("user1")
        assert ctx.last_agent == "marketing"
        assert len(ctx.conversation_history) == 4

    def test_history_saved_per_user(self, cm):
        cm.handle_message("user1", "teste marketing")
        cm.handle_message("user2", "teste programador")
        assert len(cm.context_manager.get_history("user1")) >= 2
        assert len(cm.context_manager.get_history("user2")) >= 2

    def test_agent_generate_called(self, cm):
        cm.handle_message("user1", "Campanha de marketing")
        cm._agents["marketing"].generate.assert_called_once_with("Campanha de marketing")

    def test_followup_reuses_agent(self, cm):
        cm.handle_message("user1", "Campanha de marketing")
        cm._agents["marketing"].generate.reset_mock()
        cm.handle_message("user1", "Continue")
        cm._agents["marketing"].generate.assert_called_once()

    def test_multiple_keywords_best_match(self, cm):
        response, agent_name = cm.handle_message(
            "user1", "Campanha de marketing digital com anuncios no Google"
        )
        assert agent_name == "marketing"