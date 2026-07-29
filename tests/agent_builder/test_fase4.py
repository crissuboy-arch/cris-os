"""
Testes da Fase 4: HTTP executor, confirmation gateway, metrics, memory.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


# ======================================================================
# HTTP Executor
# ======================================================================


class TestStudioHttpExecutor:
    def test_register_and_list(self):
        from agent_builder.http_executor import StudioHttpExecutor
        exe = StudioHttpExecutor()
        req = exe.register({"name": "weather", "url": "https://api.weather.com", "method": "GET"})
        assert req.name == "weather"
        assert req.url == "https://api.weather.com"
        assert len(exe.list_registered()) == 1

    def test_register_no_url_raises(self):
        from agent_builder.http_executor import StudioHttpExecutor
        exe = StudioHttpExecutor()
        with pytest.raises(ValueError, match="URL"):
            exe.register({"name": "bad", "url": ""})

    def test_unregister(self):
        from agent_builder.http_executor import StudioHttpExecutor
        exe = StudioHttpExecutor()
        exe.register({"name": "test", "url": "https://example.com"})
        assert exe.unregister("test") is True
        assert exe.unregister("nonexistent") is False
        assert len(exe.list_registered()) == 0

    def test_execute_unregistered(self):
        from agent_builder.http_executor import StudioHttpExecutor
        exe = StudioHttpExecutor()
        result = exe.execute("nonexistent")
        assert result["success"] is False
        assert "nao registrada" in result["error"]

    def test_execute_http_error(self):
        from agent_builder.http_executor import StudioHttpExecutor
        exe = StudioHttpExecutor()
        exe.register({"name": "bad-url", "url": "http://localhost:19999/nonexistent", "timeout_s": 2})
        result = exe.execute("bad-url")
        assert result["success"] is False

    def test_to_dict_roundtrip(self):
        from agent_builder.http_executor import StudioHttpExecutor
        exe = StudioHttpExecutor()
        exe.register({"name": "api", "url": "https://api.test.com/data", "method": "POST"})
        tools = exe.list_registered()
        assert len(tools) == 1
        assert tools[0]["name"] == "api"
        assert tools[0]["method"] == "POST"


# ======================================================================
# Confirmation Gateway
# ======================================================================


class TestStudioConfirmationGateway:
    def test_create_and_list(self):
        from agent_builder.confirmation_gateway import StudioConfirmationGateway
        gw = StudioConfirmationGateway()
        conf = gw.create("a1", "test-agent", "notes.create", "criar nota")
        assert conf.id.startswith("confirm-")
        assert conf.status == "pending"
        pending = gw.list_pending()
        assert len(pending) == 1
        assert pending[0]["id"] == conf.id

    def test_confirm(self):
        from agent_builder.confirmation_gateway import StudioConfirmationGateway
        gw = StudioConfirmationGateway()
        conf = gw.create("a1", "test-agent", "notes.create", "criar nota")
        assert gw.confirm(conf.id, notes="ok") is True
        assert gw.confirm(conf.id) is False  # already resolved
        pending = gw.list_pending()
        assert len(pending) == 0

    def test_reject(self):
        from agent_builder.confirmation_gateway import StudioConfirmationGateway
        gw = StudioConfirmationGateway()
        conf = gw.create("a1", "test-agent", "notes.create", "criar nota")
        assert gw.reject(conf.id, notes="nao autorizado") is True
        pending = gw.list_pending()
        assert len(pending) == 0

    def test_confirm_nonexistent(self):
        from agent_builder.confirmation_gateway import StudioConfirmationGateway
        gw = StudioConfirmationGateway()
        assert gw.confirm("fake-id") is False
        assert gw.reject("fake-id") is False

    def test_stats(self):
        from agent_builder.confirmation_gateway import StudioConfirmationGateway
        gw = StudioConfirmationGateway()
        c1 = gw.create("a1", "agent", "cap1", "test")
        c2 = gw.create("a2", "agent", "cap2", "test")
        gw.confirm(c1.id)
        stats = gw.stats()
        assert stats["total"] == 2
        assert stats["confirmed"] == 1
        assert stats["pending"] == 1

    def test_list_all_limit(self):
        from agent_builder.confirmation_gateway import StudioConfirmationGateway
        gw = StudioConfirmationGateway()
        for i in range(10):
            gw.create(f"a-{i}", "agent", "cap", f"instr {i}")
        all_confs = gw.list_all(limit=3)
        assert len(all_confs) == 3


# ======================================================================
# Metrics Engine
# ======================================================================


class TestStudioMetrics:
    def test_record_and_summary(self):
        from agent_builder.metrics import StudioMetrics, MetricEntry
        m = StudioMetrics()
        m.record(MetricEntry(
            agent_id="a1", agent_name="agent-1", capability="echo",
            plugin="demo", success=True, duration_ms=42.0,
        ))
        m.record(MetricEntry(
            agent_id="a1", agent_name="agent-1", capability="echo",
            plugin="demo", success=False, duration_ms=100.0, error="fail",
        ))
        summary = m.summary()
        assert summary["total"] == 2
        assert summary["success"] == 1
        assert summary["error"] == 1
        assert summary["success_rate"] == 50.0
        assert "agent-1" in summary["by_agent"]
        assert "echo" in summary["by_capability"]

    def test_empty_summary(self):
        from agent_builder.metrics import StudioMetrics
        m = StudioMetrics()
        summary = m.summary()
        assert summary["total"] == 0

    def test_agent_summary(self):
        from agent_builder.metrics import StudioMetrics, MetricEntry
        m = StudioMetrics()
        m.record(MetricEntry(
            agent_id="a1", agent_name="agent-1", capability="echo",
            plugin="demo", success=True, duration_ms=10.0,
        ))
        m.record(MetricEntry(
            agent_id="a1", agent_name="agent-1", capability="echo",
            plugin="demo", success=True, duration_ms=20.0,
        ))
        agent_s = m.agent_summary("a1")
        assert agent_s["total"] == 2
        assert agent_s["success"] == 2
        assert agent_s["avg_duration_ms"] == 15.0

    def test_record_from_log(self):
        from agent_builder.metrics import StudioMetrics
        m = StudioMetrics()
        log_entry = {
            "agent_id": "a1", "agent_name": "agent-1", "status": "success",
            "duration_ms": 55.0, "session": "test",
            "capabilities_called": [{"capability": "demo.echo"}],
            "permissions_denied": [], "memory_reads": [{"type": "session"}],
            "memory_writes": [{"type": "agent"}], "errors": [],
        }
        m.record_from_log(log_entry)
        summary = m.summary()
        assert summary["total"] == 1
        assert summary["memory_reads"] == 1
        assert summary["memory_writes"] == 1

    def test_recent(self):
        from agent_builder.metrics import StudioMetrics, MetricEntry
        m = StudioMetrics()
        for i in range(5):
            m.record(MetricEntry(
                agent_id=f"a-{i}", agent_name="agent", capability="echo",
                plugin="demo", success=True, duration_ms=float(i),
            ))
        recent = m.recent(limit=3)
        assert len(recent) == 3

    def test_clear(self):
        from agent_builder.metrics import StudioMetrics, MetricEntry
        m = StudioMetrics()
        m.record(MetricEntry(
            agent_id="a1", agent_name="agent", capability="echo",
            plugin="demo", success=True, duration_ms=10.0,
        ))
        assert m.clear() == 1
        assert m.summary()["total"] == 0


# ======================================================================
# StudioMemory
# ======================================================================


class TestStudioMemory:
    def test_write_session(self):
        from agent_builder.studio_memory import StudioMemory
        with tempfile.TemporaryDirectory():
            mem = StudioMemory()
            ok = mem.write_session("test:session", "assistant", "hello world")
            # May fail if SQLiteMemory not available, but should not crash
            assert isinstance(ok, bool)

    def test_write_agent_result(self):
        from agent_builder.studio_memory import StudioMemory
        with tempfile.TemporaryDirectory():
            mem = StudioMemory()
            ok = mem.write_agent_result("test-agent", "echo test", "resultado ok")
            assert isinstance(ok, bool)

    def test_read_session_empty(self):
        from agent_builder.studio_memory import StudioMemory
        mem = StudioMemory()
        items = mem.read_session("nonexistent:session")
        assert isinstance(items, list)


# ======================================================================
# Models: Fase 3+4 serialization
# ======================================================================


class TestFase4Models:
    def test_binding_source_serialization(self):
        from agent_builder.models import CapabilityBinding, BindingSource
        b = CapabilityBinding(
            keyword="test", capability="demo.echo",
            source=BindingSource.CONTEXT, context_path="user.name",
            default_value="fallback", type_hint="str",
        )
        d = b.to_dict()
        assert d["source"] == "context"
        assert d["context_path"] == "user.name"
        restored = CapabilityBinding.from_dict(d)
        assert restored.source == "context"
        assert restored.context_path == "user.name"

    def test_instructions_serialization(self):
        from agent_builder.models import AgentInstructions
        ins = AgentInstructions(
            role="Tester", objective="Test things",
            rules=["rule1"], restrictions=["no1"],
            output_format="JSON", custom_prompt="custom",
        )
        d = ins.to_dict()
        restored = AgentInstructions.from_dict(d)
        assert restored.role == "Tester"
        assert restored.rules == ["rule1"]

    def test_memory_config_serialization(self):
        from agent_builder.models import MemoryConfig, MemoryType
        mc = MemoryConfig(
            memory_type=MemoryType.PROJECT,
            scope=["proj-a"], read_enabled=True, write_enabled=True, project="proj-a",
        )
        d = mc.to_dict()
        assert d["memory_type"] == "project"
        restored = MemoryConfig.from_dict(d)
        assert restored.scope == ["proj-a"]

    def test_permission_config_serialization(self):
        from agent_builder.models import PermissionConfig
        pc = PermissionConfig(
            allowed_capabilities=["a.*"],
            denied_capabilities=["b.delete"],
            require_confirmation=["c.create"],
        )
        d = pc.to_dict()
        restored = PermissionConfig.from_dict(d)
        assert restored.allowed_capabilities == ["a.*"]
        assert restored.denied_capabilities == ["b.delete"]

    def test_tools_config_serialization(self):
        from agent_builder.models import ToolsConfig
        tc = ToolsConfig(
            internal=["tool1"],
            http=[{"name": "api", "url": "https://x.com"}],
            mcp=[{"name": "gh", "server": "github"}],
        )
        d = tc.to_dict()
        restored = ToolsConfig.from_dict(d)
        assert len(restored.http) == 1
        assert len(restored.mcp) == 1

    def test_full_agent_definition_roundtrip(self):
        from agent_builder.models import (
            AgentDefinition, AgentInstructions, MemoryConfig, MemoryType,
            PermissionConfig, ToolsConfig, CapabilityBinding, BindingSource,
        )
        defn = AgentDefinition(
            agent_id="full-test", name="full-agent", version="1.0.0",
            description="Full test agent",
            bindings=[CapabilityBinding(
                keyword="echo", capability="demo.echo",
                source=BindingSource.INPUT,
            )],
            instructions=AgentInstructions(role="Bot", objective="Echo"),
            memory=MemoryConfig(memory_type=MemoryType.SESSION),
            permissions=PermissionConfig(allowed_capabilities=["demo.*"]),
            tools=ToolsConfig(http=[{"name": "api", "url": "https://x.com"}]),
        )
        d = defn.to_dict()
        restored = AgentDefinition.from_dict(d)
        assert restored.instructions.role == "Bot"
        assert restored.memory.memory_type == "session"
        assert restored.permissions.allowed_capabilities == ["demo.*"]
        assert len(restored.tools.http) == 1
        assert restored.bindings[0].source == "input"
