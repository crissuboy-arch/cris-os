"""
Testes para Fase 7.2 - Plugin oficial CRIS Telegram.
10 capabilities testadas: send, reply, notify, confirm, reject, health, metrics, execute_agent, get_status, get_logs.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch
from typing import Any

from channels.telegram.client import TelegramClient
from core.application.core_api import CoreAPI
from core.capability.registry import CapabilityRegistry
from core.configuration import PluginConfigStore
from core.domain.events import Event
from core.events import InMemoryEventLog, InProcessEventBus
from core.permission import SimplePermissionChecker
from core.plugins.models import PluginManifest


def _load_plugin_class():
    """Load CrisTelegramPlugin directly from file to avoid PluginLoader module pollution."""
    mod_name = "plugins.cris_telegram_plugin_test"
    if mod_name in sys.modules:
        return getattr(sys.modules[mod_name], "CrisTelegramPlugin")
    plugin_path = Path(__file__).resolve().parent.parent.parent / "plugins" / "cris_telegram" / "plugin.py"
    spec = importlib.util.spec_from_file_location(mod_name, str(plugin_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod.CrisTelegramPlugin


CrisTelegramPlugin = _load_plugin_class()


def _make_manifest() -> PluginManifest:
    return PluginManifest.from_dict({
        "name": "cris-telegram",
        "version": "1.0.0",
        "description": "Plugin Telegram do CRIS OS",
        "kind": "plugin",
        "author": "CRIS OS Core Team",
        "min_core_version": "1.0.0",
        "capabilities": [
            {"name": "telegram.send", "version": "1.0.0", "description": "Enviar mensagem", "priority": 50,
             "input_schema": {"type": "object"}, "output_schema": {"type": "object"}, "timeout_ms": 10000, "idempotent": False},
            {"name": "telegram.reply", "version": "1.0.0", "description": "Responder mensagem", "priority": 50,
             "input_schema": {"type": "object"}, "output_schema": {"type": "object"}, "timeout_ms": 10000, "idempotent": False},
            {"name": "telegram.notify", "version": "1.0.0", "description": "Notificar", "priority": 50,
             "input_schema": {"type": "object"}, "output_schema": {"type": "object"}, "timeout_ms": 10000, "idempotent": False},
            {"name": "telegram.confirm", "version": "1.0.0", "description": "Confirmar", "priority": 50,
             "input_schema": {"type": "object"}, "output_schema": {"type": "object"}, "timeout_ms": 10000, "idempotent": False},
            {"name": "telegram.reject", "version": "1.0.0", "description": "Rejeitar", "priority": 50,
             "input_schema": {"type": "object"}, "output_schema": {"type": "object"}, "timeout_ms": 10000, "idempotent": False},
            {"name": "telegram.health", "version": "1.0.0", "description": "Health", "priority": 10,
             "input_schema": {"type": "object"}, "output_schema": {"type": "object"}, "timeout_ms": 3000, "idempotent": True},
            {"name": "telegram.metrics", "version": "1.0.0", "description": "Metrics", "priority": 10,
             "input_schema": {"type": "object"}, "output_schema": {"type": "object"}, "timeout_ms": 3000, "idempotent": True},
            {"name": "telegram.execute_agent", "version": "1.0.0", "description": "Executar agente", "priority": 50,
             "input_schema": {"type": "object"}, "output_schema": {"type": "object"}, "timeout_ms": 30000, "idempotent": False},
            {"name": "telegram.get_status", "version": "1.0.0", "description": "Status", "priority": 10,
             "input_schema": {"type": "object"}, "output_schema": {"type": "object"}, "timeout_ms": 5000, "idempotent": True},
            {"name": "telegram.get_logs", "version": "1.0.0", "description": "Logs", "priority": 10,
             "input_schema": {"type": "object"}, "output_schema": {"type": "object"}, "timeout_ms": 5000, "idempotent": True},
        ],
        "subscriptions": [],
    })


def _make_api() -> CoreAPI:
    return CoreAPI(
        registry=CapabilityRegistry(),
        event_bus=InProcessEventBus(event_log=InMemoryEventLog()),
        plugin_name="cris-telegram",
        config_store=PluginConfigStore(),
        permission_checker=SimplePermissionChecker(),
    )


class TestCrisTelegramPlugin:
    """Testes do plugin CRIS Telegram."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock(spec=TelegramClient)
        client.enabled = True
        client.token = "test-token-123"
        client.chat_id = "123456789"
        client.send_message.return_value = {
            "ok": True,
            "result": {"message_id": 42, "chat": {"id": 123456789}},
        }
        client.send_message_with_keyboard.return_value = {
            "ok": True,
            "result": {"message_id": 43, "chat": {"id": 123456789}},
        }
        client.answer_callback.return_value = {"ok": True}
        return client

    @pytest.fixture
    def plugin(self, mock_client):
        manifest = _make_manifest()
        api = _make_api()
        p = CrisTelegramPlugin(manifest, api)
        p._client = mock_client
        return p

    def test_send_success(self, plugin, mock_client):
        result = plugin.execute("telegram.send", {"text": "Hello World"})
        assert result["success"] is True
        assert result["message_id"] == 42
        mock_client.send_message.assert_called_once()

    def test_send_failure(self, plugin, mock_client):
        mock_client.send_message.return_value = {"ok": False, "error": "Forbidden"}
        result = plugin.execute("telegram.send", {"text": "Hello"})
        assert result["success"] is False
        assert "Forbidden" in result["error"]

    def test_reply_success(self, plugin, mock_client):
        result = plugin.execute("telegram.reply", {"text": "Reply", "reply_to_message_id": 10})
        assert result["success"] is True
        assert result["message_id"] == 42

    def test_reply_missing_id(self, plugin):
        result = plugin.execute("telegram.reply", {"text": "Reply"})
        assert result["success"] is False
        assert "reply_to_message_id" in result["error"]

    def test_notify_success(self, plugin, mock_client):
        result = plugin.execute("telegram.notify", {"text": "Alert!", "priority": "high"})
        assert result["success"] is True
        assert "notification_id" in result

    def test_notify_default_priority(self, plugin, mock_client):
        result = plugin.execute("telegram.notify", {"text": "Info"})
        assert result["success"] is True
        call_args = mock_client.send_message.call_args
        assert "Notificacao" in call_args[1]["text"]

    def test_confirm_success(self, plugin, mock_client):
        result = plugin.execute("telegram.confirm", {"text": "Confirm action?", "confirm_id": "act-001"})
        assert result["success"] is True
        assert result["confirm_id"] == "act-001"
        assert "act-001" in plugin._pending_confirms

    def test_confirm_with_keyboard(self, plugin, mock_client):
        plugin.execute("telegram.confirm", {"text": "Do it?", "confirm_id": "act-002"})
        mock_client.send_message_with_keyboard.assert_called_once()
        call_args = mock_client.send_message_with_keyboard.call_args
        assert len(call_args[1]["buttons"][0]) == 2

    def test_reject_success(self, plugin, mock_client):
        plugin._pending_confirms["act-003"] = {"text": "test", "status": "pending"}
        result = plugin.execute("telegram.reject", {"confirm_id": "act-003", "reason": "Too risky"})
        assert result["success"] is True
        assert result["status"] == "rejected"
        assert "act-003" not in plugin._pending_confirms

    def test_reject_nonexistent(self, plugin, mock_client):
        result = plugin.execute("telegram.reject", {"confirm_id": "nonexistent"})
        assert result["success"] is True
        assert result["status"] == "rejected"

    def test_health(self, plugin):
        result = plugin.execute("telegram.health", {})
        assert result["success"] is True
        assert result["connected"] is True
        assert result["token_configured"] is True
        assert result["chat_id_configured"] is True
        assert result["uptime_ms"] >= 0

    def test_health_not_connected(self, plugin, mock_client):
        mock_client.enabled = False
        mock_client.token = ""
        mock_client.chat_id = ""
        result = plugin.execute("telegram.health", {})
        assert result["success"] is True
        assert result["connected"] is False

    def test_metrics_initial(self, plugin):
        result = plugin.execute("telegram.metrics", {})
        assert result["success"] is True
        assert result["total_sent"] == 0
        assert result["total_errors"] == 0

    def test_metrics_after_send(self, plugin, mock_client):
        plugin.execute("telegram.send", {"text": "Test"})
        result = plugin.execute("telegram.metrics", {})
        assert result["total_sent"] == 1

    def test_execute_agent_success(self, plugin, mock_client):
        plugin.api._capability_executor = MagicMock(return_value={
            "success": True,
            "response": "Agent response here",
        })
        result = plugin.execute("telegram.execute_agent", {
            "agent_name": "test-agent",
            "input_text": "do something",
        })
        assert result["success"] is True
        assert result["agent_name"] == "test-agent"
        assert result["response"] == "Agent response here"

    def test_execute_agent_missing_params(self, plugin):
        result = plugin.execute("telegram.execute_agent", {})
        assert result["success"] is False
        assert "agent_name" in result["error"]

    def test_execute_agent_failure(self, plugin, mock_client):
        plugin.api._capability_executor = MagicMock(return_value={
            "success": False,
            "error": "Agent not found",
        })
        result = plugin.execute("telegram.execute_agent", {
            "agent_name": "missing-agent",
            "input_text": "test",
        })
        assert result["success"] is False

    def test_get_status(self, plugin):
        result = plugin.execute("telegram.get_status", {})
        assert result["success"] is True
        assert result["connected"] is True
        assert result["token_valid"] is True
        assert "api_url" in result

    def test_get_logs_empty(self, plugin):
        result = plugin.execute("telegram.get_logs", {})
        assert result["success"] is True
        assert result["logs"] == []
        assert result["total"] == 0

    def test_get_logs_after_activity(self, plugin, mock_client):
        plugin.execute("telegram.send", {"text": "Test"})
        result = plugin.execute("telegram.get_logs", {})
        assert result["success"] is True
        assert result["total"] >= 1

    def test_get_logs_with_level_filter(self, plugin, mock_client):
        plugin.execute("telegram.send", {"text": "Test"})
        mock_client.send_message.return_value = {"ok": False, "error": "Fail"}
        plugin.execute("telegram.send", {"text": "Fail"})
        result = plugin.execute("telegram.get_logs", {"level": "error"})
        assert result["success"] is True
        for log in result["logs"]:
            assert log["level"] == "error"

    def test_get_logs_with_limit(self, plugin, mock_client):
        for i in range(5):
            plugin.execute("telegram.send", {"text": f"Msg {i}"})
        result = plugin.execute("telegram.get_logs", {"limit": 2})
        assert result["success"] is True
        assert len(result["logs"]) == 2

    def test_unknown_capability(self, plugin):
        result = plugin.execute("telegram.unknown", {})
        assert result["success"] is False
        assert "desconhecida" in result["error"]

    def test_lifecycle(self, plugin):
        plugin.on_install()
        plugin.on_start()
        plugin.on_stop()
        plugin.on_uninstall()
        assert plugin._logs == []

    def test_logs_capped_at_500(self, plugin, mock_client):
        for i in range(600):
            plugin.execute("telegram.send", {"text": f"Msg {i}"})
        assert len(plugin._logs) <= 500

    def test_event_publish_on_send(self, plugin, mock_client):
        events = []
        def capture(event):
            events.append(event)
        plugin.api._event_bus.subscribe("telegram.message.sent", capture)
        plugin.execute("telegram.send", {"text": "Event test"})
        assert len(events) == 1


class TestCrisTelegramPluginIntegration:
    """Testes de integracao do plugin com CoreAPI real."""

    def test_register_capabilities(self):
        manifest = _make_manifest()
        api = _make_api()
        plugin = CrisTelegramPlugin(manifest, api)
        plugin.on_install()

        for cap in manifest.capabilities:
            api.register_capability(
                name=cap.name,
                version=cap.version,
                priority=cap.priority,
                description=cap.description,
            )

        all_caps = api.registry.list_all()
        telegram_caps = [c for c in all_caps if c.name.startswith("telegram.")]
        assert len(telegram_caps) == 10

    def test_full_flow_send_and_metrics(self):
        manifest = _make_manifest()
        api = _make_api()
        plugin = CrisTelegramPlugin(manifest, api)
        plugin._client = MagicMock(spec=TelegramClient)
        plugin._client.enabled = True
        plugin._client.token = "test"
        plugin._client.chat_id = "123"
        plugin._client.send_message.return_value = {
            "ok": True,
            "result": {"message_id": 99},
        }
        plugin.on_start()

        plugin.execute("telegram.send", {"text": "Flow test"})
        metrics = plugin.execute("telegram.metrics", {})
        assert metrics["total_sent"] == 1

        health = plugin.execute("telegram.health", {})
        assert health["connected"] is True

        logs = plugin.execute("telegram.get_logs", {})
        assert logs["total"] >= 1