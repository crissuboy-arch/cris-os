"""
Testes do Agent Builder (models, store, DynamicAgent, facade, import/export).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from agent_builder import AgentBuilder, AgentConfig, AgentDefinition, AgentStatus, AgentStore, CapabilityBinding, DynamicAgent
from agent_builder.models import MemoryConfig, PermissionConfig
from core.contracts.agent import AgentContext
from core.models import AgentResult, Task

ROOT = Path(__file__).resolve().parent.parent.parent


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def tmp_store():
    with tempfile.TemporaryDirectory() as td:
        yield AgentStore(td)


@pytest.fixture
def sample_binding():
    return CapabilityBinding(
        keyword="criar nota",
        capability="notes.create",
        input_template={"title": "Nota: {instruction}", "content": "{instruction}"},
    )


@pytest.fixture
def sample_echo_binding():
    return CapabilityBinding(
        keyword="echo",
        capability="demo.echo",
        input_template={"message": "{instruction}"},
    )


@pytest.fixture
def sample_definition(sample_binding):
    return AgentDefinition(
        agent_id="test-agent-001",
        name="test-agent",
        version="1.0.0",
        description="Agente de teste",
        bindings=[sample_binding],
    )


@pytest.fixture
def mock_registry():
    reg = MagicMock()
    reg._items = {}
    reg.register = lambda item: reg._items.__setitem__(item.name, item)
    reg.get = lambda name: reg._items.get(name)
    reg.unregister = lambda name: reg._items.pop(name, None)
    return reg


@pytest.fixture
def mock_runtime():
    rt = MagicMock()
    rt.execute.return_value = AgentResult(agent="test-agent", output="OK", success=True)
    return rt


# ======================================================================
# Models
# ======================================================================


class TestAgentDefinition:
    def test_to_dict_roundtrip(self, sample_definition):
        d = sample_definition.to_dict()
        restored = AgentDefinition.from_dict(d)
        assert restored.agent_id == sample_definition.agent_id
        assert restored.name == sample_definition.name
        assert restored.version == "1.0.0"
        assert len(restored.bindings) == 1
        assert restored.bindings[0].keyword == "criar nota"
        assert restored.bindings[0].capability == "notes.create"

    def test_default_status_is_draft(self):
        defn = AgentDefinition(agent_id="x", name="x", version="1.0.0", description="")
        assert defn.status == AgentStatus.DRAFT

    def test_status_enum_values(self):
        assert AgentStatus.DRAFT == "draft"
        assert AgentStatus.PUBLISHED == "published"
        assert AgentStatus.DEACTIVATED == "deactivated"
        assert AgentStatus.ARCHIVED == "archived"

    def test_binding_with_template(self):
        b = CapabilityBinding(keyword="ping", capability="demo.echo", input_template={"msg": "{instruction}"})
        assert "{instruction}" in b.input_template["msg"]


# ======================================================================
# AgentStore
# ======================================================================


class TestAgentStore:
    def test_save_and_load(self, tmp_store, sample_definition):
        tmp_store.save(sample_definition)
        loaded = tmp_store.load("test-agent-001")
        assert loaded is not None
        assert loaded.name == "test-agent"
        assert loaded.version == "1.0.0"

    def test_load_nonexistent(self, tmp_store):
        assert tmp_store.load("ghost") is None

    def test_delete(self, tmp_store, sample_definition):
        tmp_store.save(sample_definition)
        assert tmp_store.exists("test-agent-001")
        assert tmp_store.delete("test-agent-001") is True
        assert not tmp_store.exists("test-agent-001")

    def test_delete_nonexistent(self, tmp_store):
        assert tmp_store.delete("ghost") is False

    def test_list_ids(self, tmp_store):
        a1 = AgentDefinition(agent_id="a1", name="A1", version="1.0.0", description="")
        a2 = AgentDefinition(agent_id="a2", name="A2", version="1.0.0", description="")
        tmp_store.save(a1)
        tmp_store.save(a2)
        ids = tmp_store.list_ids()
        assert "a1" in ids
        assert "a2" in ids

    def test_list_all(self, tmp_store):
        a1 = AgentDefinition(agent_id="a1", name="A1", version="1.0.0", description="")
        tmp_store.save(a1)
        all_a = tmp_store.list_all()
        assert len(all_a) == 1
        assert all_a[0].name == "A1"

    def test_version_snapshot(self, tmp_store, sample_definition):
        tmp_store.save(sample_definition)
        tmp_store.save_version_snapshot(sample_definition)
        versions = tmp_store.list_versions("test-agent-001")
        assert "1.0.0" in versions
        loaded = tmp_store.load_version("test-agent-001", "1.0.0")
        assert loaded is not None
        assert loaded.name == "test-agent"

    def test_version_snapshot_nonexistent(self, tmp_store):
        assert tmp_store.load_version("ghost", "1.0.0") is None

    def test_export_import(self, tmp_store, sample_definition):
        tmp_store.save(sample_definition)
        with tempfile.TemporaryDirectory() as export_dir:
            exported_path = tmp_store.export_to("test-agent-001", export_dir)
            assert (exported_path / "manifest.json").exists()

            # Import em outro store
            with tempfile.TemporaryDirectory() as import_base:
                store2 = AgentStore(import_base)
                imported_id = store2.import_from(exported_path)
                assert imported_id == "test-agent-001"
                imported = store2.load("test-agent-001")
                assert imported is not None
                assert imported.name == "test-agent"

    def test_import_without_manifest_raises(self, tmp_store):
        with tempfile.TemporaryDirectory() as empty_dir:
            with pytest.raises(FileNotFoundError):
                tmp_store.import_from(empty_dir)


# ======================================================================
# DynamicAgent
# ======================================================================


class TestDynamicAgent:
    def test_handle_matching_binding(self, sample_definition):
        agent = DynamicAgent(sample_definition)
        mock_api = MagicMock()
        mock_api.execute.return_value = {"success": True, "id": "abc", "title": "Nota do builder"}
        from core.contracts.agent import AgentContext
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="test-agent", instruction="criar nota sobre reuniao")

        result = agent.handle(task, context)

        assert result.success is True
        assert "abc" in result.output
        mock_api.execute.assert_called_once_with(
            "notes.create",
            {"title": "Nota: criar nota sobre reuniao", "content": "criar nota sobre reuniao"},
        )

    def test_handle_no_match(self, sample_definition):
        agent = DynamicAgent(sample_definition)
        mock_api = MagicMock()
        from core.contracts.agent import AgentContext
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="test-agent", instruction="fazer calculo matematico")

        result = agent.handle(task, context)

        assert result.success is False
        assert "Nenhuma capability" in result.output

    def test_handle_no_core_api(self, sample_definition):
        agent = DynamicAgent(sample_definition)
        from core.contracts.agent import AgentContext
        context = AgentContext(session="test")
        task = Task(agent="test-agent", instruction="criar nota")

        result = agent.handle(task, context)

        assert result.success is True
        assert "CoreAPI nao disponivel" in result.output

    def test_handle_binding_priority(self, sample_echo_binding):
        b1 = CapabilityBinding(keyword="eco", capability="demo.echo", input_template={"message": "{instruction}"}, priority=10)
        b2 = CapabilityBinding(keyword="echo", capability="demo.echo", input_template={"message": "{instruction}"}, priority=100)
        defn = AgentDefinition(
            agent_id="priority-test", name="priority-test", version="1.0.0",
            description="", bindings=[b1, b2],
        )
        agent = DynamicAgent(defn)
        mock_api = MagicMock()
        mock_api.execute.return_value = {"success": True, "echo": "ok"}
        from core.contracts.agent import AgentContext
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="priority-test", instruction="echo test")

        agent.handle(task, context)

        # binding de maior priority (100) deve ser testado primeiro
        assert mock_api.execute.call_args[0][0] == "demo.echo"

    def test_handle_capability_failure(self, sample_definition):
        agent = DynamicAgent(sample_definition)
        mock_api = MagicMock()
        mock_api.execute.return_value = {"success": False, "error": "erro de teste"}
        from core.contracts.agent import AgentContext
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="test-agent", instruction="criar nota")

        result = agent.handle(task, context)

        assert result.success is False
        assert "erro de teste" in result.output


# ======================================================================
# AgentBuilder
# ======================================================================


class TestAgentBuilder:
    def test_create(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        defn = builder.create("meu-agente", "Meu agente de teste")

        assert defn.name == "meu-agente"
        assert defn.description == "Meu agente de teste"
        assert defn.status == AgentStatus.DRAFT
        assert defn.version == "1.0.0"
        assert tmp_store.exists(defn.agent_id)

    def test_create_with_bindings(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        bindings = [CapabilityBinding(keyword="echo", capability="demo.echo")]
        defn = builder.create("echo-agent", "Echo agent", bindings=bindings)
        assert len(defn.bindings) == 1

    def test_get(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        created = builder.create("get-test")
        loaded = builder.get(created.agent_id)
        assert loaded is not None
        assert loaded.name == "get-test"

    def test_get_nonexistent(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        assert builder.get("ghost") is None

    def test_update(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        defn = builder.create("update-test", "Original")
        updated = builder.update(defn.agent_id, description="Atualizado")
        assert updated is not None
        assert updated.description == "Atualizado"

    def test_update_published_bumps_version(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        defn = builder.create("version-test")
        defn.status = AgentStatus.PUBLISHED
        tmp_store.save(defn)

        updated = builder.update(defn.agent_id, description="Nova versao")
        assert updated is not None
        assert updated.status == AgentStatus.DRAFT
        assert updated.version == "1.0.1"

    def test_delete(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        defn = builder.create("delete-test")
        assert builder.delete(defn.agent_id) is True
        assert not tmp_store.exists(defn.agent_id)

    def test_list(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        builder.create("list-a")
        builder.create("list-b")
        all_a = builder.list()
        names = [a.name for a in all_a]
        assert "list-a" in names
        assert "list-b" in names

    def test_list_filter_by_status(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        a1 = builder.create("draft-agent")
        a2 = builder.create("pub-agent")
        a2.status = AgentStatus.PUBLISHED
        tmp_store.save(a2)

        drafts = builder.list(status=AgentStatus.DRAFT)
        assert all(a.status == AgentStatus.DRAFT for a in drafts)

    def test_publish_registers_agent(self, tmp_store, mock_registry, mock_runtime):
        builder = AgentBuilder(
            store=tmp_store, agent_registry=mock_registry,
            runtime=mock_runtime,
        )
        defn = builder.create("pub-agent", bindings=[CapabilityBinding(keyword="echo", capability="demo.echo")])
        published = builder.publish(defn.agent_id)

        assert published is not None
        assert published.status == AgentStatus.PUBLISHED
        assert published.published_at is not None
        # Deve estar registrado no AgentRegistry
        assert mock_registry.get("pub-agent") is not None

    def test_deactivate_unregisters_agent(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        defn = builder.create("deact-agent")
        defn.status = AgentStatus.PUBLISHED
        tmp_store.save(defn)
        mock_registry.register(DynamicAgent(defn))

        deactivated = builder.deactivate(defn.agent_id)
        assert deactivated is not None
        assert deactivated.status == AgentStatus.DEACTIVATED
        assert mock_registry.get("deact-agent") is None

    def test_duplicate(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        original = builder.create(
            "original",
            bindings=[CapabilityBinding(keyword="echo", capability="demo.echo")],
        )
        dup = builder.duplicate(original.agent_id, "minha-copia")
        assert dup is not None
        assert dup.name == "minha-copia"
        assert dup.version == "1.0.0"
        assert dup.status == AgentStatus.DRAFT
        assert len(dup.bindings) == 1

    def test_duplicate_default_name(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        original = builder.create("orig")
        dup = builder.duplicate(original.agent_id)
        assert dup is not None
        assert "copia" in dup.name

    def test_test_executes_via_runtime(self, tmp_store, mock_registry, mock_runtime):
        builder = AgentBuilder(
            store=tmp_store, agent_registry=mock_registry,
            runtime=mock_runtime,
        )
        defn = builder.create("test-agent", bindings=[CapabilityBinding(keyword="echo", capability="demo.echo")])
        result = builder.test(defn.agent_id, "echo hello")
        assert result.success is True
        mock_runtime.execute.assert_called_once()

    def test_export_import(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        defn = builder.create("export-test", "Para exportar")

        with tempfile.TemporaryDirectory() as export_dir:
            exported = builder.export(defn.agent_id, export_dir)
            exported_path = Path(exported)
            assert (exported_path / "manifest.json").exists()

            # Import em outro builder
            with tempfile.TemporaryDirectory() as import_base:
                store2 = AgentStore(import_base)
                builder2 = AgentBuilder(store=store2, agent_registry=MagicMock())
                imported = builder2.import_agent(exported_path)
                assert imported is not None
                assert imported.name == "export-test"

    def test_version_listing(self, tmp_store, mock_registry):
        builder = AgentBuilder(store=tmp_store, agent_registry=mock_registry)
        defn = builder.create("ver-test")
        tmp_store.save_version_snapshot(defn)

        versions = builder.list_versions(defn.agent_id)
        assert "1.0.0" in versions

        loaded = builder.get_version(defn.agent_id, "1.0.0")
        assert loaded is not None
        assert loaded.name == "ver-test"

    def test_full_lifecycle(self, tmp_store, mock_registry, mock_runtime):
        """Cria -> publica -> executa -> desativa -> remove."""
        builder = AgentBuilder(
            store=tmp_store, agent_registry=mock_registry,
            runtime=mock_runtime,
        )

        # 1. Criar
        defn = builder.create(
            "lifecycle-agent",
            bindings=[CapabilityBinding(keyword="echo", capability="demo.echo")],
        )
        assert defn.status == AgentStatus.DRAFT

        # 2. Publicar
        published = builder.publish(defn.agent_id)
        assert published.status == AgentStatus.PUBLISHED

        # 3. Executar
        result = builder.test(defn.agent_id, "echo oi")
        assert result.success is True

        # 4. Desativar
        deactivated = builder.deactivate(defn.agent_id)
        assert deactivated.status == AgentStatus.DEACTIVATED

        # 5. Remover
        assert builder.delete(defn.agent_id) is True
        assert not tmp_store.exists(defn.agent_id)


# ======================================================================
# Teste com plugins reais (integracao)
# ======================================================================


class TestAgentBuilderIntegration:
    @pytest.fixture
    def real_infra(self):
        from core.agent import AgentRuntime
        from core.capability import CapabilityRegistry
        from core.events import InProcessEventBus, InMemoryEventLog
        from core.plugins.loader import PluginLoader
        from core.registry import AgentRegistry

        registry = CapabilityRegistry()
        event_log = InMemoryEventLog()
        event_bus = InProcessEventBus(event_log=event_log)
        loader = PluginLoader(registry=registry, event_bus=event_bus, plugins_dir=str(
            Path(__file__).resolve().parent.parent.parent / "plugins"
        ))
        loaded = loader.load_all()
        loader.start_all()

        agent_reg = AgentRegistry()
        runtime = AgentRuntime(agent_registry=agent_reg, plugin_loader=loader, event_bus=event_bus)

        with tempfile.TemporaryDirectory() as td:
            store = AgentStore(td)
            builder = AgentBuilder(store=store, agent_registry=agent_reg, runtime=runtime, plugin_loader=loader)
            yield builder, agent_reg, runtime

    def test_create_publish_execute_on_real_plugins(self, real_infra):
        """Cria agente com binding para demo.echo -> publica -> executa no runtime real."""
        builder, agent_reg, runtime = real_infra

        defn = builder.create(
            "meu-primeiro-agente",
            "Agente criado pelo Agent Builder",
            bindings=[
                CapabilityBinding(
                    keyword="echo",
                    capability="demo.echo",
                    input_template={"message": "{instruction}"},
                ),
            ],
        )
        assert defn.status == AgentStatus.DRAFT

        # Publica (registra no AgentRegistry)
        published = builder.publish(defn.agent_id)
        assert published.status == AgentStatus.PUBLISHED
        assert agent_reg.get("meu-primeiro-agente") is not None

        # Executa pelo AgentRuntime
        result = runtime.execute("meu-primeiro-agente", "echo ola mundo")
        assert result.success is True
        assert "ola mundo" in result.output

        # Desativa
        builder.deactivate(defn.agent_id)
        assert agent_reg.get("meu-primeiro-agente") is None

        # Remove
        builder.delete(defn.agent_id)

    def test_multiple_bindings_with_real_plugins(self, real_infra):
        """Agente com 2 bindings funciona com plugins reais."""
        builder, agent_reg, runtime = real_infra

        defn = builder.create(
            "multi-agent",
            bindings=[
                CapabilityBinding(keyword="criar", capability="notes.create", input_template={"title": "Nota do Builder", "content": "{instruction}"}),
                CapabilityBinding(keyword="echo", capability="demo.echo", input_template={"message": "{instruction}"}),
            ],
        )
        builder.publish(defn.agent_id)

        # Testa echo
        result = runtime.execute("multi-agent", "echo testando")
        assert result.success is True

        # Testa notes.create (cris_notes deve estar carregado)
        result2 = runtime.execute("multi-agent", "criar nota de teste")
        assert result2.success is True
        assert "Nota do Builder" in result2.output

        builder.delete(defn.agent_id)


# ======================================================================
# Fase 3: bindings, context, memory, permissions, execution
# ======================================================================


class TestFase3Bindings:
    """Cenarios de binding: fixed, input, context, previous_result."""

    def test_binding_fixed_value(self):
        """Binding com valor fixo — usa default_value."""
        from agent_builder.models import BindingSource
        agent_def = AgentDefinition(
            agent_id="fixed-test", name="fixed-agent", version="1.0.0",
            description="",
            bindings=[CapabilityBinding(
                keyword="eco", capability="demo.echo",
                input_template={"message": "static"},
                source=BindingSource.FIXED, default_value="valor fixo",
            )],
        )
        agent = DynamicAgent(agent_def)
        mock_api = MagicMock()
        mock_api.execute.return_value = {"success": True, "echo": "ok"}
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="fixed-agent", instruction="eco qualquer coisa")

        result = agent.handle(task, context)

        assert result.success is True
        call_params = mock_api.execute.call_args[0][1]
        assert call_params["message"] == "valor fixo"

    def test_binding_input_source(self):
        """Binding com input — interpola {instruction}."""
        from agent_builder.models import BindingSource
        agent_def = AgentDefinition(
            agent_id="input-test", name="input-agent", version="1.0.0",
            description="",
            bindings=[CapabilityBinding(
                keyword="criar", capability="notes.create",
                input_template={"title": "Nota: {instruction}", "content": "{instruction}"},
                source=BindingSource.INPUT,
            )],
        )
        agent = DynamicAgent(agent_def)
        mock_api = MagicMock()
        mock_api.execute.return_value = {"success": True, "id": "n1", "title": "Nota: criar X"}
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="input-agent", instruction="criar nota sobre projeto")

        result = agent.handle(task, context)

        assert result.success is True
        call_params = mock_api.execute.call_args[0][1]
        assert call_params["title"] == "Nota: criar nota sobre projeto"
        assert call_params["content"] == "criar nota sobre projeto"

    def test_binding_context_source(self):
        """Binding com context — interpola {context.session}."""
        from agent_builder.models import BindingSource
        agent_def = AgentDefinition(
            agent_id="ctx-test", name="ctx-agent", version="1.0.0",
            description="",
            bindings=[CapabilityBinding(
                keyword="session", capability="demo.echo",
                input_template={"message": "Session: {context.session}"},
                source=BindingSource.CONTEXT,
            )],
        )
        agent = DynamicAgent(agent_def)
        mock_api = MagicMock()
        mock_api.execute.return_value = {"success": True, "echo": "ok"}
        context = AgentContext(session="telegram:12345", core_api=mock_api)
        task = Task(agent="ctx-agent", instruction="session info")

        result = agent.handle(task, context)

        assert result.success is True
        call_params = mock_api.execute.call_args[0][1]
        assert "telegram:12345" in call_params["message"]

    def test_context_absent(self):
        """Context ausente — placeholders ficam vazios, nao crasha."""
        from agent_builder.models import BindingSource
        agent_def = AgentDefinition(
            agent_id="ctx-absent", name="ctx-absent-agent", version="1.0.0",
            description="",
            bindings=[CapabilityBinding(
                keyword="info", capability="demo.echo",
                input_template={"message": "{context.session} - {context.missing.nested}"},
                source=BindingSource.CONTEXT,
            )],
        )
        agent = DynamicAgent(agent_def)
        mock_api = MagicMock()
        mock_api.execute.return_value = {"success": True, "echo": "ok"}
        context = AgentContext(session="test-session", core_api=mock_api)
        task = Task(agent="ctx-absent-agent", instruction="info")

        result = agent.handle(task, context)

        assert result.success is True
        call_params = mock_api.execute.call_args[0][1]
        assert "test-session" in call_params["message"]

    def test_binding_previous_result(self):
        """Binding com previous_result — interpola resultado anterior."""
        from agent_builder.models import BindingSource
        b1 = CapabilityBinding(
            keyword="echo", capability="demo.echo",
            input_template={"message": "{instruction}"},
            source=BindingSource.INPUT, priority=100,
        )
        b2 = CapabilityBinding(
            keyword="echo", capability="demo.echo",
            input_template={"message": "Previous: {previous.output}"},
            source=BindingSource.PREVIOUS_RESULT, priority=50,
        )
        agent_def = AgentDefinition(
            agent_id="prev-test", name="prev-agent", version="1.0.0",
            description="", bindings=[b1, b2],
        )
        agent = DynamicAgent(agent_def)
        mock_api = MagicMock()
        mock_api.execute.side_effect = [
            {"success": True, "output": "first result"},
            {"success": True, "echo": "ok"},
        ]
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="prev-agent", instruction="echo test")

        result = agent.handle(task, context)
        assert result.success is True


class TestFase3Memory:
    """Cenarios de memoria: session, agent, project, read/write."""

    def test_memory_session_read(self):
        """Memoria de sessao — le conversation e temporary."""
        from agent_builder.models import MemoryType
        agent_def = AgentDefinition(
            agent_id="mem-session", name="mem-session-agent", version="1.0.0",
            description="",
            memory=MemoryConfig(memory_type=MemoryType.SESSION, read_enabled=True),
            bindings=[CapabilityBinding(keyword="echo", capability="demo.echo")],
        )
        agent = DynamicAgent(agent_def)
        context = AgentContext(
            session="test",
            conversation=[{"role": "user", "content": "ola"}, {"role": "assistant", "content": "oi"}],
            temporary=["reuniao as 14h"],
        )
        task = Task(agent="mem-session-agent", instruction="echo test")

        result = agent.handle(task, context)
        assert result.success is True

    def test_memory_agent_write(self):
        """Memoria do agente — escreve resultado apos execucao."""
        from agent_builder.models import MemoryType
        agent_def = AgentDefinition(
            agent_id="mem-write", name="mem-write-agent", version="1.0.0",
            description="",
            memory=MemoryConfig(memory_type=MemoryType.AGENT, write_enabled=True),
            bindings=[CapabilityBinding(keyword="echo", capability="demo.echo")],
        )
        agent = DynamicAgent(agent_def)
        mock_api = MagicMock()
        mock_api.execute.return_value = {"success": True, "echo": "resultado"}
        mock_api.set_config = MagicMock()
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="mem-write-agent", instruction="echo test")

        result = agent.handle(task, context)

        assert result.success is True
        mock_api.set_config.assert_called_once()
        call_args = mock_api.set_config.call_args[0]
        assert "memory.mem-write-agent.last_result" == call_args[0]

    def test_memory_disabled_no_write(self):
        """Memoria desabilitada — nao escreve nada."""
        from agent_builder.models import MemoryType
        agent_def = AgentDefinition(
            agent_id="mem-disabled", name="mem-disabled-agent", version="1.0.0",
            description="",
            memory=MemoryConfig(memory_type=MemoryType.NONE),
            bindings=[CapabilityBinding(keyword="echo", capability="demo.echo")],
        )
        agent = DynamicAgent(agent_def)
        mock_api = MagicMock()
        mock_api.execute.return_value = {"success": True, "echo": "ok"}
        mock_api.set_config = MagicMock()
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="mem-disabled-agent", instruction="echo test")

        result = agent.handle(task, context)

        assert result.success is True
        mock_api.set_config.assert_not_called()

    def test_memory_project_scope(self):
        """Memoria de projeto — scope de projetos configurado."""
        from agent_builder.models import MemoryType
        agent_def = AgentDefinition(
            agent_id="mem-proj", name="mem-proj-agent", version="1.0.0",
            description="",
            memory=MemoryConfig(
                memory_type=MemoryType.PROJECT,
                scope=["projeto-a", "projeto-b"],
                read_enabled=True,
            ),
            bindings=[CapabilityBinding(keyword="echo", capability="demo.echo")],
        )
        agent = DynamicAgent(agent_def)
        from core.models import KnowledgeItem
        proj_items = [
            KnowledgeItem(type="note", title="Nota A", content="Conteudo A"),
            KnowledgeItem(type="note", title="Nota B", content="Conteudo B"),
        ]
        context = AgentContext(
            session="test",
            project_memory=proj_items,
            core_api=MagicMock(execute=MagicMock(return_value={"success": True, "echo": "ok"})),
        )
        task = Task(agent="mem-proj-agent", instruction="echo test")

        result = agent.handle(task, context)
        assert result.success is True


class TestFase3Permissions:
    """Cenarios de permissao: allowed, denied, confirmation required."""

    def test_permission_allowed(self):
        """Permissao permitida — capability na allowlist executa."""
        agent_def = AgentDefinition(
            agent_id="perm-ok", name="perm-ok-agent", version="1.0.0",
            description="",
            permissions=PermissionConfig(allowed_capabilities=["notes.create"]),
            bindings=[CapabilityBinding(keyword="criar", capability="notes.create")],
        )
        agent = DynamicAgent(agent_def)
        mock_api = MagicMock()
        mock_api.execute.return_value = {"success": True, "id": "n1"}
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="perm-ok-agent", instruction="criar nota")

        result = agent.handle(task, context)
        assert result.success is True
        mock_api.execute.assert_called_once()

    def test_permission_denied(self):
        """Permissao negada — capability na denylist retorna erro."""
        agent_def = AgentDefinition(
            agent_id="perm-deny", name="perm-deny-agent", version="1.0.0",
            description="",
            permissions=PermissionConfig(denied_capabilities=["notes.create"]),
            bindings=[CapabilityBinding(keyword="criar", capability="notes.create")],
        )
        agent = DynamicAgent(agent_def)
        mock_api = MagicMock()
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="perm-deny-agent", instruction="criar nota")

        result = agent.handle(task, context)
        assert result.success is False
        assert "negada" in result.output.lower()
        mock_api.execute.assert_not_called()

    def test_permission_confirmation_required(self):
        """Confirmacao obrigatoria — capability exige confirmacao."""
        agent_def = AgentDefinition(
            agent_id="perm-confirm", name="perm-confirm-agent", version="1.0.0",
            description="",
            permissions=PermissionConfig(require_confirmation=["notes.create"]),
            bindings=[CapabilityBinding(keyword="criar", capability="notes.create")],
        )
        agent = DynamicAgent(agent_def)
        mock_api = MagicMock()
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="perm-confirm-agent", instruction="criar nota")

        result = agent.handle(task, context)
        assert result.success is False
        assert "confirmacao" in result.output.lower()
        assert result.metadata.get("confirmation_required") is True
        mock_api.execute.assert_not_called()

    def test_permission_wildcard_allow(self):
        """Wildcard allow — 'notes.*' permite todas notes.*."""
        agent_def = AgentDefinition(
            agent_id="perm-wild", name="perm-wild-agent", version="1.0.0",
            description="",
            permissions=PermissionConfig(allowed_capabilities=["notes.*"]),
            bindings=[CapabilityBinding(keyword="criar", capability="notes.create")],
        )
        agent = DynamicAgent(agent_def)
        mock_api = MagicMock()
        mock_api.execute.return_value = {"success": True, "id": "n1"}
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="perm-wild-agent", instruction="criar nota")

        result = agent.handle(task, context)
        assert result.success is True


class TestFase3CapabilityErrors:
    """Cenarios de erro: capability inexistente, ferramenta HTTP/MCP."""

    def test_capability_not_found(self):
        """Capability inexistente — retorna erro claro."""
        agent_def = AgentDefinition(
            agent_id="cap-missing", name="cap-missing-agent", version="1.0.0",
            description="",
            bindings=[CapabilityBinding(keyword="test", capability="nonexistent.cap")],
        )
        agent = DynamicAgent(agent_def)
        mock_api = MagicMock()
        mock_api.registry = MagicMock()
        mock_api.registry.resolve.return_value = None
        context = AgentContext(session="test", core_api=mock_api)
        task = Task(agent="cap-missing-agent", instruction="test something")

        result = agent.handle(task, context)
        assert result.success is False
        assert "indisponivel" in result.output.lower() or "inexistente" in result.output.lower()

    def test_http_tool_config(self):
        """Ferramenta HTTP configurada — registra no tools config."""
        from agent_builder.models import ToolsConfig
        agent_def = AgentDefinition(
            agent_id="http-tool", name="http-tool-agent", version="1.0.0",
            description="",
            tools=ToolsConfig(http=[{"name": "weather", "url": "https://api.weather.com", "method": "GET"}]),
            bindings=[CapabilityBinding(keyword="clima", capability="demo.echo")],
        )
        d = agent_def.to_dict()
        assert len(d["tools"]["http"]) == 1
        assert d["tools"]["http"][0]["name"] == "weather"

        restored = AgentDefinition.from_dict(d)
        assert len(restored.tools.http) == 1
        assert restored.tools.http[0]["name"] == "weather"

    def test_mcp_tool_config(self):
        """Ferramenta MCP configurada — registra no tools config."""
        from agent_builder.models import ToolsConfig
        agent_def = AgentDefinition(
            agent_id="mcp-tool", name="mcp-tool-agent", version="1.0.0",
            description="",
            tools=ToolsConfig(mcp=[{"name": "github", "server": "github-mcp", "tool": "list_repos"}]),
            bindings=[CapabilityBinding(keyword="repo", capability="demo.echo")],
        )
        d = agent_def.to_dict()
        assert len(d["tools"]["mcp"]) == 1
        assert d["tools"]["mcp"][0]["server"] == "github-mcp"

        restored = AgentDefinition.from_dict(d)
        assert len(restored.tools.mcp) == 1
        assert restored.tools.mcp[0]["tool"] == "list_repos"


class TestFase3Instructions:
    """System prompt montado a partir de AgentInstructions."""

    def test_system_prompt_basic(self):
        """Prompt basico com role + objective."""
        from agent_builder.models import AgentInstructions
        agent_def = AgentDefinition(
            agent_id="prompt-test", name="prompt-agent", version="1.0.0",
            description="",
            instructions=AgentInstructions(
                role="Assistente de notas",
                objective="Criar e gerenciar notas",
            ),
            bindings=[],
        )
        agent = DynamicAgent(agent_def)
        prompt = agent._build_system_prompt()
        assert "Assistente de notas" in prompt
        assert "Criar e gerenciar notas" in prompt

    def test_system_prompt_rules_restrictions(self):
        """Prompt com regras e restricoes."""
        from agent_builder.models import AgentInstructions
        agent_def = AgentDefinition(
            agent_id="rules-test", name="rules-agent", version="1.0.0",
            description="",
            instructions=AgentInstructions(
                rules=["Sempre ser educado", "Nao inventar dados"],
                restrictions=["Nao acessar internet", "Nao executar codigo"],
                output_format="JSON",
            ),
            bindings=[],
        )
        agent = DynamicAgent(agent_def)
        prompt = agent._build_system_prompt()
        assert "Regras:" in prompt
        assert "1. Sempre ser educado" in prompt
        assert "Restricoes:" in prompt
        assert "1. Nao acessar internet" in prompt
        assert "JSON" in prompt

    def test_system_prompt_custom(self):
        """Prompt customizado."""
        from agent_builder.models import AgentInstructions
        agent_def = AgentDefinition(
            agent_id="custom-test", name="custom-agent", version="1.0.0",
            description="",
            instructions=AgentInstructions(custom_prompt="Voce e o melhor assistente."),
            bindings=[],
        )
        agent = DynamicAgent(agent_def)
        prompt = agent._build_system_prompt()
        assert "Voce e o melhor assistente." in prompt


class TestFase3ExecutionLog:
    """Testes do ExecutionLog para observabilidade."""

    def test_create_and_retrieve(self):
        """Criar registro e recuperar."""
        from agent_builder.execution_log import StudioExecutionLog
        log = StudioExecutionLog()
        record = log.create_record("agent-1", "test-agent", "echo hello")
        assert record.id.startswith("exec-")
        assert record.agent_name == "test-agent"
        assert record.status == "running"
        record.status = "success"
        record.duration_ms = 42.5
        log.add(record)

        retrieved = log.get(record.id)
        assert retrieved is not None
        assert retrieved.status == "success"
        assert retrieved.duration_ms == 42.5

    def test_stats(self):
        """Metricas de execucao."""
        from agent_builder.execution_log import StudioExecutionLog
        log = StudioExecutionLog()
        for i in range(5):
            r = log.create_record(f"a-{i}", "agent", f"instr {i}")
            r.status = "success" if i < 3 else "error"
            r.duration_ms = 10.0 * (i + 1)
            log.add(r)

        stats = log.stats()
        assert stats["total"] == 5
        assert stats["success"] == 3
        assert stats["error"] == 2
        assert stats["avg_duration_ms"] > 0

    def test_list_limit(self):
        """List com limite."""
        from agent_builder.execution_log import StudioExecutionLog
        log = StudioExecutionLog()
        for i in range(10):
            r = log.create_record("a", "agent", f"instr {i}")
            r.status = "success"
            log.add(r)

        result = log.list_all(limit=3)
        assert len(result) == 3


class TestFase3FullEndToEnd:
    """Execucao completa criada pelo Studio — ponta a ponta."""

    def test_full_studio_flow(self):
        """Cria -> configura instructions/memory/permissions -> publica -> executa -> log."""
        from agent_builder.models import AgentInstructions, MemoryConfig, PermissionConfig, ToolsConfig, MemoryType
        from agent_builder.execution_log import StudioExecutionLog

        with tempfile.TemporaryDirectory() as td:
            store = AgentStore(td)
            mock_reg = MagicMock()
            mock_reg._items = {}
            mock_reg.register = lambda item: mock_reg._items.__setitem__(item.name, item)
            mock_reg.get = lambda name: mock_reg._items.get(name)

            builder = AgentBuilder(store=store, agent_registry=mock_reg)

            # 1. Create
            defn = builder.create(
                "studio-agent",
                "Agente completo do Studio",
                bindings=[CapabilityBinding(keyword="echo", capability="demo.echo")],
            )
            assert defn.status == AgentStatus.DRAFT

            # 2. Update with Fase 3 fields
            updated = builder.update(
                defn.agent_id,
                instructions=AgentInstructions(
                    role="Assistente de teste",
                    objective="Testar o fluxo completo",
                    rules=["Ser preciso"],
                    restrictions=["Nao inventar dados"],
                    output_format="Texto simples",
                ),
                memory=MemoryConfig(memory_type=MemoryType.SESSION, read_enabled=True),
                permissions=PermissionConfig(allowed_capabilities=["demo.echo"]),
                tools=ToolsConfig(internal=["weather"], http=[{"name": "api", "url": "http://x"}]),
            )
            assert updated.instructions.role == "Assistente de teste"
            assert updated.memory.memory_type == MemoryType.SESSION
            assert updated.permissions.allowed_capabilities == ["demo.echo"]
            assert len(updated.tools.http) == 1

            # 3. Publish
            published = builder.publish(defn.agent_id)
            assert published.status == AgentStatus.PUBLISHED

            # 4. Execute via runtime
            from core.agent import AgentRuntime
            from core.capability import CapabilityRegistry
            from core.events import InProcessEventBus, InMemoryEventLog
            from core.plugins.loader import PluginLoader

            cap_reg = CapabilityRegistry()
            event_log = InMemoryEventLog()
            bus = InProcessEventBus(event_log=event_log)
            loader = PluginLoader(registry=cap_reg, event_bus=bus, plugins_dir=str(ROOT / "plugins"))
            loader.load_all()
            loader.start_all()

            runtime = AgentRuntime(agent_registry=mock_reg, plugin_loader=loader, event_bus=bus)
            result = runtime.execute("studio-agent", "echo teste completo", session="studio:test")
            assert result.success is True

            # 5. Verify execution log metadata
            exec_log = result.metadata.get("execution_log", {})
            assert "echo" in exec_log.get("bindings_attempted", [])
            assert len(exec_log.get("capabilities_called", [])) > 0

            # 6. Verify system prompt was built
            assert result.metadata.get("system_prompt") != ""

            # 7. Log recording
            log = StudioExecutionLog()
            record = log.create_record(defn.agent_id, defn.name, "echo teste completo")
            record.status = "success"
            record.duration_ms = 15.0
            log.add(record)
            assert log.stats()["total"] == 1

            # 8. Verify manifest serialization roundtrip
            manifest = published.to_dict()
            restored = AgentDefinition.from_dict(manifest)
            assert restored.instructions.role == "Assistente de teste"
            assert restored.memory.memory_type == MemoryType.SESSION
            assert restored.permissions.allowed_capabilities == ["demo.echo"]
            assert len(restored.tools.http) == 1
            assert len(restored.tools.mcp) == 0

            builder.delete(defn.agent_id)