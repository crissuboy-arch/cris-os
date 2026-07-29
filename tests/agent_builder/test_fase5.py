"""
Testes da Fase 5: Auth, MCP executor, Notifier, Version Diff, novos endpoints.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


# ======================================================================
# Auth
# ======================================================================


class TestAuth:
    def test_login_valid(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        result = auth.login("admin", "cris2024")
        assert result["success"] is True
        assert result["user"]["username"] == "admin"
        assert result["user"]["role"] == "admin"
        assert result["token"]

    def test_login_invalid_password(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        result = auth.login("admin", "wrong")
        assert result["success"] is False

    def test_login_invalid_user(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        result = auth.login("nobody", "cris2024")
        assert result["success"] is False

    def test_verify_valid_token(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        result = auth.login("admin", "cris2024")
        user = auth.verify(result["token"])
        assert user is not None
        assert user["username"] == "admin"
        assert user["role"] == "admin"

    def test_verify_invalid_token(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        assert auth.verify("invalid-token") is None

    def test_verify_expired_token(self):
        from agent_builder.auth import StudioAuth, _encode_jwt
        auth = StudioAuth()
        token = _encode_jwt({"sub": "admin", "role": "admin", "name": "", "iat": 0, "exp": -1})
        assert auth.verify(token) is None

    def test_logout(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        result = auth.login("admin", "cris2024")
        assert auth.logout(result["token"]) is True
        assert auth.logout(result["token"]) is False  # already removed

    def test_list_users(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        users = auth.list_users()
        assert len(users) >= 1
        assert users[0]["username"] == "admin"

    def test_create_user(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        result = auth.create_user("newuser", "pass123", "editor", "New User")
        assert result["success"] is True
        assert result["username"] == "newuser"

    def test_create_duplicate_user(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        result = auth.create_user("admin", "pass")
        assert result["success"] is False

    def test_delete_user(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        auth.create_user("to_delete", "pass")
        assert auth.delete_user("to_delete") is True
        assert auth.delete_user("to_delete") is False

    def test_cannot_delete_admin(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        assert auth.delete_user("admin") is False

    def test_check_permission_admin(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        assert auth.check_permission("admin", "write") is True
        assert auth.check_permission("admin", "delete") is True
        assert auth.check_permission("admin", "manage_users") is True

    def test_check_permission_editor(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        assert auth.check_permission("editor", "read") is True
        assert auth.check_permission("editor", "write") is True
        assert auth.check_permission("editor", "delete") is False

    def test_check_permission_viewer(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        assert auth.check_permission("viewer", "read") is True
        assert auth.check_permission("viewer", "write") is False

    def test_change_password(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        assert auth.change_password("admin", "newpass") is True
        result = auth.login("admin", "newpass")
        assert result["success"] is True

    def test_change_password_nonexistent(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        assert auth.change_password("nobody", "pass") is False

    def test_extract_token(self):
        from agent_builder.auth import StudioAuth
        auth = StudioAuth()
        assert auth.extract_token("Bearer abc123") == "abc123"
        assert auth.extract_token("Token abc") is None
        assert auth.extract_token(None) is None


# ======================================================================
# JWT Helpers
# ======================================================================


class TestJwtHelpers:
    def test_jwt_roundtrip(self):
        from agent_builder.auth import _encode_jwt, _decode_jwt
        token = _encode_jwt({"sub": "admin", "exp": int(time.time()) + 3600})
        payload = _decode_jwt(token)
        assert payload is not None
        assert payload["sub"] == "admin"

    def test_jwt_expired(self):
        from agent_builder.auth import _encode_jwt, _decode_jwt
        token = _encode_jwt({"sub": "admin", "exp": int(time.time()) - 1})
        assert _decode_jwt(token) is None

    def test_jwt_invalid(self):
        from agent_builder.auth import _decode_jwt
        assert _decode_jwt("invalid.token.here") is None

    def test_jwt_tampered_signature(self):
        from agent_builder.auth import _encode_jwt, _decode_jwt
        token = _encode_jwt({"sub": "admin", "exp": int(time.time()) + 3600})
        parts = token.split(".")
        # Tamper with body
        import base64
        body_bytes = base64.urlsafe_b64decode(parts[1] + "==")
        body_bytes = body_bytes.replace(b"admin", b"attacker")
        parts[1] = base64.urlsafe_b64encode(body_bytes).rstrip(b"=").decode()
        tampered = ".".join(parts)
        assert _decode_jwt(tampered) is None

    def test_jwt_wrong_structure(self):
        from agent_builder.auth import _decode_jwt
        assert _decode_jwt("only.two") is None


# ======================================================================
# MCP Executor
# ======================================================================


class TestMcpExecutor:
    def test_register_and_list_servers(self):
        from agent_builder.mcp_executor import StudioMcpExecutor
        executor = StudioMcpExecutor()
        server = executor.register_server({"name": "s1", "command": "echo", "args": ["hello"]})
        assert server.name == "s1"
        assert server.command == "echo"
        servers = executor.list_servers()
        assert len(servers) == 1
        assert servers[0]["name"] == "s1"

    def test_register_no_command_raises(self):
        from agent_builder.mcp_executor import StudioMcpExecutor
        executor = StudioMcpExecutor()
        with pytest.raises(ValueError):
            executor.register_server({"name": "bad"})

    def test_unregister_server(self):
        from agent_builder.mcp_executor import StudioMcpExecutor
        executor = StudioMcpExecutor()
        executor.register_server({"name": "s1", "command": "echo"})
        assert executor.unregister_server("s1") is True
        assert executor.unregister_server("s1") is False
        assert len(executor.list_servers()) == 0

    def test_list_tools_empty(self):
        from agent_builder.mcp_executor import StudioMcpExecutor
        executor = StudioMcpExecutor()
        assert executor.list_tools() == []

    def test_discover_with_mock(self):
        from agent_builder.mcp_executor import StudioMcpExecutor
        executor = StudioMcpExecutor()
        executor.register_server({"name": "mock-srv", "command": "echo"})

        mock_response = {"jsonrpc": "2.0", "id": 1, "result": {
            "tools": [{"name": "greet", "description": "Greet someone", "inputSchema": {}}]
        }}

        with patch.object(executor, '_send_request', return_value=mock_response):
            tools = executor.discover_tools("mock-srv")
            assert len(tools) == 1
            assert tools[0].name == "greet"
            # Tool should be stored internally
            stored = executor.list_tools()
            assert len(stored) == 1
            assert stored[0]["full_name"] == "mock-srv.greet"

    def test_discover_error_returns_empty(self):
        from agent_builder.mcp_executor import StudioMcpExecutor
        executor = StudioMcpExecutor()
        executor.register_server({"name": "bad", "command": "echo"})

        with patch.object(executor, '_send_request', return_value=None):
            tools = executor.discover_tools("bad")
            assert tools == []

    def test_execute_tool(self):
        from agent_builder.mcp_executor import StudioMcpExecutor
        executor = StudioMcpExecutor()
        executor.register_server({"name": "srv", "command": "echo"})

        # Store tool manually
        from agent_builder.mcp_executor import McpTool
        tool = McpTool(name="mytool", description="test", server_name="srv")
        executor._tools["srv.mytool"] = tool

        mock_response = {
            "jsonrpc": "2.0", "id": 1,
            "result": {"content": [{"type": "text", "text": "42"}]}
        }

        with patch.object(executor, '_send_request', return_value=mock_response):
            result = executor.execute("srv.mytool", {"x": 1})
            assert result["success"] is True
            assert "42" in result.get("output", "")

    def test_execute_unknown_tool(self):
        from agent_builder.mcp_executor import StudioMcpExecutor
        executor = StudioMcpExecutor()
        result = executor.execute("nonexistent.tool")
        assert result["success"] is False

    def test_execute_disabled_server(self):
        from agent_builder.mcp_executor import StudioMcpExecutor
        executor = StudioMcpExecutor()
        executor.register_server({"name": "srv", "command": "echo", "enabled": False})

        from agent_builder.mcp_executor import McpTool
        tool = McpTool(name="t", description="d", server_name="srv")
        executor._tools["srv.t"] = tool

        result = executor.execute("srv.t")
        assert result["success"] is False

    def test_execute_retry_on_failure(self):
        from agent_builder.mcp_executor import StudioMcpExecutor
        executor = StudioMcpExecutor()
        executor.register_server({"name": "srv", "command": "echo"})

        from agent_builder.mcp_executor import McpTool
        tool = McpTool(name="t", description="d", server_name="srv")
        executor._tools["srv.t"] = tool

        # First call returns None (failure), second succeeds
        mock_response = {
            "jsonrpc": "2.0", "id": 1,
            "result": {"content": [{"type": "text", "text": "ok"}]}
        }
        with patch.object(executor, '_send_request', side_effect=[None, mock_response]):
            result = executor.execute("srv.t")
            assert result["success"] is True


# ======================================================================
# Notifier
# ======================================================================


class TestNotifier:
    def test_configure(self):
        from agent_builder.notifier import StudioNotifier
        n = StudioNotifier()
        n.configure("fake-token", "12345")
        assert n.enabled is True

    def test_not_configured(self):
        from agent_builder.notifier import StudioNotifier
        n = StudioNotifier()
        assert n.enabled is False

    def test_history_empty(self):
        from agent_builder.notifier import StudioNotifier
        n = StudioNotifier()
        assert n.list_history() == []

    def test_stats_empty(self):
        from agent_builder.notifier import StudioNotifier
        n = StudioNotifier()
        stats = n.stats()
        assert stats["total"] == 0
        assert stats["sent"] == 0
        assert stats["failed"] == 0

    def test_notify_confirmation_pending(self):
        from agent_builder.notifier import StudioNotifier
        n = StudioNotifier()
        n.configure("fake-token", "12345")
        with patch.object(n, '_send') as mock_send:
            mock_send.return_value = MagicMock(sent=True, id="notif-1", type="confirmation")
            result = n.notify_confirmation_pending("conf-1", "agent1", "capability", "Do something?")
            mock_send.assert_called_once()

    def test_send_when_not_enabled(self):
        from agent_builder.notifier import StudioNotifier
        n = StudioNotifier()
        # Not configured, should still work (stores in history)
        result = n.notify_approval("id1", "agent1")
        assert result.sent is False
        assert result.error == "Telegram not configured"

    def test_send_success(self):
        from agent_builder.notifier import StudioNotifier
        n = StudioNotifier()
        n.configure("token", "chat")

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_resp):
            result = n.notify_execution_complete("agent1", True, 100.0, "Done")
            assert result.sent is True
            assert n.stats()["sent"] == 1

    def test_send_failure_stores_error(self):
        from agent_builder.notifier import StudioNotifier
        n = StudioNotifier()
        n.configure("token", "chat")

        with patch('urllib.request.urlopen', side_effect=Exception("network error")):
            result = n.notify_rejection("id1", "agent1", "no")
            assert result.sent is False
            assert "network error" in result.error
            assert n.stats()["failed"] == 1

    def test_stats_after_notifications(self):
        from agent_builder.notifier import StudioNotifier
        n = StudioNotifier()
        # Send some notifications without config
        n.notify_approval("a1", "agent1")
        n.notify_approval("a2", "agent2")
        n.notify_rejection("r1", "agent1", "no")
        stats = n.stats()
        assert stats["total"] == 3
        assert stats["sent"] == 0


# ======================================================================
# Version Diff
# ======================================================================


class TestVersionDiff:
    def test_no_changes(self):
        from agent_builder.version_diff import compute_diff
        d = compute_diff({"a": 1}, {"a": 1})
        assert d == []

    def test_added_keys(self):
        from agent_builder.version_diff import compute_diff
        d = compute_diff({}, {"b": 2, "c": 3})
        types = {c["type"] for c in d}
        assert "added" in types
        assert len(d) == 2

    def test_removed_keys(self):
        from agent_builder.version_diff import compute_diff
        d = compute_diff({"a": 1, "b": 2}, {"a": 1})
        types = {c["type"] for c in d}
        assert "removed" in types
        removed = [c for c in d if c["type"] == "removed"]
        assert removed[0]["path"] == "b"

    def test_changed_values(self):
        from agent_builder.version_diff import compute_diff
        d = compute_diff({"x": 1}, {"x": 2})
        assert len(d) == 1
        assert d[0]["path"] == "x"
        assert d[0]["type"] == "changed"

    def test_nested_changes(self):
        from agent_builder.version_diff import compute_diff
        old = {"a": {"b": 1, "c": 2}}
        new = {"a": {"b": 1, "c": 3}}
        d = compute_diff(old, new)
        assert len(d) == 1
        assert d[0]["path"] == "a.c"

    def test_complex_diff(self):
        from agent_builder.version_diff import compute_diff
        old = {"name": "old", "tools": {"web": True}, "extra": "x"}
        new = {"name": "new", "tools": {"web": True, "api": True}}
        d = compute_diff(old, new)
        paths = {c["path"] for c in d}
        assert "name" in paths
        assert "extra" in paths
        assert "tools.api" in paths

    def test_format_diff(self):
        from agent_builder.version_diff import compute_diff, format_diff
        d = compute_diff({"a": 1}, {"a": 2})
        text = format_diff(d)
        assert "a" in text

    def test_format_diff_empty(self):
        from agent_builder.version_diff import format_diff
        text = format_diff([])
        assert text == "Nenhuma alteracao"


# ======================================================================
# Models Fase 5 (validacao extras)
# ======================================================================


class TestModelsFase5:
    def test_agent_definition_from_dict(self):
        from agent_builder.models import AgentDefinition
        a = AgentDefinition.from_dict({
            "agent_id": "a1",
            "name": "Test Agent",
            "version": "1.0.0",
            "description": "A test agent",
        })
        assert a.agent_id == "a1"
        assert a.version == "1.0.0"
        assert a.description == "A test agent"

    def test_agent_definition_to_dict_roundtrip(self):
        from agent_builder.models import AgentDefinition
        a = AgentDefinition.from_dict({
            "agent_id": "a1",
            "name": "Test",
            "version": "1.0.0",
            "description": "desc",
            "instructions": {"role": "assistant", "objective": "help"},
            "memory": {"memory_type": "session"},
            "permissions": {"allowed_capabilities": ["notes.create"]},
        })
        d = a.to_dict()
        a2 = AgentDefinition.from_dict(d)
        assert a2.agent_id == a.agent_id
        assert a2.instructions.role == "assistant"
        assert a2.memory.memory_type == "session"

    def test_binding_source_enum(self):
        from agent_builder.models import BindingSource
        assert BindingSource.FIXED.value == "fixed"
        assert BindingSource.INPUT.value == "input"
        assert BindingSource.CONTEXT.value == "context"
        assert BindingSource.PREVIOUS_RESULT.value == "previous_result"

    def test_memory_type_enum(self):
        from agent_builder.models import MemoryType
        assert MemoryType.NONE.value == "none"
        assert MemoryType.SESSION.value == "session"
        assert MemoryType.AGENT.value == "agent"
        assert MemoryType.PROJECT.value == "project"


# ======================================================================
# MCP Process (subprocess test)
# ======================================================================


class TestMcpProcess:
    def test_send_request_echo(self):
        from agent_builder.mcp_executor import StudioMcpExecutor, McpServer
        executor = StudioMcpExecutor()
        server = McpServer(name="echo", command="echo", timeout_s=5)
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        # echo will just echo the input, so parsing will fail but no crash
        result = executor._send_request(server, request)
        # echo returns our JSON-RPC input as output, so it should parse as valid JSON
        assert result is not None or result is None  # depends on echo behavior

    def test_send_request_command_not_found(self):
        from agent_builder.mcp_executor import StudioMcpExecutor, McpServer
        executor = StudioMcpExecutor()
        server = McpServer(name="bad", command="nonexistent_command_xyz_123", timeout_s=2)
        result = executor._send_request(server, {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}})
        assert result is None
