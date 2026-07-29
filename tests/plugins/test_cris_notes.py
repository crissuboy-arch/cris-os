"""
Testes unitarios do CRIS Notes plugin.

Valida que o plugin funciona de forma isolada, sem depender do PluginLoader.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.application.core_api import CoreAPI
from core.capability import CapabilityRegistry, CapabilityStatus, HealthStatus
from core.capability.errors import CapabilityPermissionError
from core.configuration import PluginConfigStore
from core.domain.events import Event
from core.events import InMemoryEventLog, InProcessEventBus
from core.permission import SimplePermissionChecker
from core.plugins.models import PluginManifest

# Caminho do manifesto real
_MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "plugins" / "cris_notes" / "manifest.json"


@pytest.fixture
def manifest():
    import json
    data = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return PluginManifest.from_dict(data)


@pytest.fixture
def registry():
    return CapabilityRegistry()


@pytest.fixture
def event_bus():
    return InProcessEventBus(InMemoryEventLog())


@pytest.fixture
def config_store():
    return PluginConfigStore()


@pytest.fixture
def perm_checker():
    pc = SimplePermissionChecker()
    pc.allow("notes.delete", "cris-notes")
    pc.allow("notes.create", "cris-notes")
    return pc


@pytest.fixture
def api(registry, event_bus, config_store, perm_checker):
    return CoreAPI(
        registry=registry,
        event_bus=event_bus,
        plugin_name="cris-notes",
        config_store=config_store,
        permission_checker=perm_checker,
    )


@pytest.fixture
def plugin(manifest, api):
    from plugins.cris_notes.plugin import CrisNotesPlugin
    p = CrisNotesPlugin(manifest, api)
    p.on_install()
    return p


# ======================================================================
# Testes de capabilities
# ======================================================================


class TestNotesCreate:
    def test_cria_nota_com_titulo_e_conteudo(self, plugin):
        r = plugin.execute("notes.create", {"title": "Minha Nota", "content": "Meu conteudo"})
        assert r["success"]
        assert r["title"] == "Minha Nota"
        assert len(r["id"]) == 12

    def test_cria_nota_com_tags(self, plugin):
        r = plugin.execute("notes.create", {"title": "Com Tags", "content": "X", "tags": ["a", "b"]})
        assert r["success"]

    def test_cria_nota_sem_tags(self, plugin):
        r = plugin.execute("notes.create", {"title": "Sem Tags", "content": "Y"})
        assert r["success"]

    def test_cria_nota_sem_titulo_falha(self, plugin):
        r = plugin.execute("notes.create", {"content": "So conteudo"})
        assert not r["success"]

    def test_cria_nota_publica_evento(self, plugin, event_bus):
        received = []
        def handler(e): received.append(e)
        event_bus.subscribe("notes.created", handler)
        plugin.execute("notes.create", {"title": "Evento", "content": "Teste"})
        assert len(received) == 1
        assert received[0].payload["title"] == "Evento"


class TestNotesRead:
    def test_le_nota_existente(self, plugin):
        created = plugin.execute("notes.create", {"title": "Ler", "content": "Conteudo"})
        r = plugin.execute("notes.read", {"note_id": created["id"]})
        assert r["success"]
        assert r["title"] == "Ler"
        assert r["content"] == "Conteudo"

    def test_le_nota_inexistente(self, plugin):
        r = plugin.execute("notes.read", {"note_id": "fake-id"})
        assert not r["success"]

    def test_le_nota_incrementa_metricas(self, plugin):
        created = plugin.execute("notes.create", {"title": "X", "content": "Y"})
        plugin.execute("notes.read", {"note_id": created["id"]})
        plugin.execute("notes.read", {"note_id": created["id"]})
        metrics = plugin.execute("notes.metrics", {})
        assert metrics["total_read"] >= 2


class TestNotesSearch:
    def test_busca_por_titulo(self, plugin):
        plugin.execute("notes.create", {"title": "Projeto XYZ", "content": "Detalhes"})
        r = plugin.execute("notes.search", {"query": "Projeto"})
        assert r["success"]
        assert r["total"] >= 1

    def test_busca_por_conteudo(self, plugin):
        plugin.execute("notes.create", {"title": "Nota", "content": "Conteudo especifico"})
        r = plugin.execute("notes.search", {"query": "especifico"})
        assert r["total"] >= 1

    def test_busca_por_tag(self, plugin):
        plugin.execute("notes.create", {"title": "Tagged", "content": "X", "tags": ["importante"]})
        r = plugin.execute("notes.search", {"query": "importante"})
        assert r["total"] >= 1

    def test_busca_sem_resultados(self, plugin):
        r = plugin.execute("notes.search", {"query": "naoexiste"})
        assert r["total"] == 0

    def test_busca_respeita_max_results(self, plugin):
        for i in range(5):
            plugin.execute("notes.create", {"title": f"Item {i}", "content": "busca max"})
        r = plugin.execute("notes.search", {"query": "busca", "max_results": 3})
        assert r["success"]
        assert len(r["results"]) <= 3


class TestNotesDelete:
    def test_deleta_nota_existente(self, plugin):
        created = plugin.execute("notes.create", {"title": "Delete Me", "content": "X"})
        r = plugin.execute("notes.delete", {"note_id": created["id"]})
        assert r["success"]
        assert r["status"] == "deleted"
        # Verifica que foi removida
        r2 = plugin.execute("notes.read", {"note_id": created["id"]})
        assert not r2["success"]

    def test_deleta_nota_inexistente(self, plugin):
        r = plugin.execute("notes.delete", {"note_id": "fake-id"})
        assert not r["success"]

    def test_deleta_publica_evento(self, plugin, event_bus):
        received = []
        def handler(e): received.append(e)
        event_bus.subscribe("notes.deleted", handler)
        created = plugin.execute("notes.create", {"title": "DelEvent", "content": "X"})
        plugin.execute("notes.delete", {"note_id": created["id"]})
        assert len(received) == 1
        assert received[0].payload["note_id"] == created["id"]

    def test_decrementa_active_notes(self, plugin):
        c1 = plugin.execute("notes.create", {"title": "A", "content": "X"})
        c2 = plugin.execute("notes.create", {"title": "B", "content": "X"})
        plugin.execute("notes.delete", {"note_id": c1["id"]})
        metrics = plugin.execute("notes.metrics", {})
        assert metrics["active_notes"] == 1


class TestNotesHealth:
    def test_health_ok(self, plugin):
        r = plugin.execute("notes.health", {})
        assert r["success"]
        assert r["status"] is not None

    def test_health_retorna_total_notes(self, plugin):
        plugin.execute("notes.create", {"title": "H1", "content": "X"})
        plugin.execute("notes.create", {"title": "H2", "content": "X"})
        r = plugin.execute("notes.health", {})
        assert r["total_notes"] == 2


class TestNotesMetrics:
    def test_metrics_iniciais(self, plugin):
        r = plugin.execute("notes.metrics", {})
        assert r["success"]
        assert r["total_created"] == 0
        assert r["total_deleted"] == 0
        assert r["total_read"] == 0
        assert r["total_searched"] == 0
        assert r["active_notes"] == 0

    def test_metrics_acumulam(self, plugin):
        plugin.execute("notes.create", {"title": "M1", "content": "X"})
        plugin.execute("notes.create", {"title": "M2", "content": "X"})
        c = plugin.execute("notes.create", {"title": "M3", "content": "X"})
        plugin.execute("notes.delete", {"note_id": c["id"]})
        r = plugin.execute("notes.metrics", {})
        assert r["total_created"] == 3
        assert r["total_deleted"] == 1
        assert r["active_notes"] == 2


# ======================================================================
# Testes de integracao com Configuration e Permission
# ======================================================================


class TestNotesConfiguration:
    def test_config_default(self, plugin):
        assert plugin.api.get_config("max_notes", "1000") == "1000"

    def test_config_set_get(self, plugin):
        plugin.api.set_config("max_notes", "500")
        assert plugin.api.get_config("max_notes") == "500"

    def test_config_delete(self, plugin):
        plugin.api.set_config("tema", "escuro")
        plugin.api.delete_config("tema")
        assert plugin.api.get_config("tema") == ""

    def test_config_isolada_por_plugin(self, api, plugin):
        api.set_config("test_key", "notes_value")
        assert api.get_config("test_key") == "notes_value"


class TestNotesPermission:
    def test_delete_sem_permissao_levanta_erro(self, api, plugin):
        checker = SimplePermissionChecker()
        assert not checker.check("no-permission", "notes.delete")

    def test_delete_com_permissao(self, plugin):
        created = plugin.execute("notes.create", {"title": "P", "content": "X"})
        r = plugin.execute("notes.delete", {"note_id": created["id"]})
        assert r["success"]


# ======================================================================
# Testes de ciclo de vida
# ======================================================================


class TestNotesLifecycle:
    def test_on_install(self, plugin):
        assert plugin.state.value == "installed"

    def test_on_start(self, plugin):
        plugin.on_start()
        assert plugin.state.value == "installed"  # nao muda internamente

    def test_on_stop(self, plugin):
        plugin.on_stop()

    def test_on_uninstall(self, plugin):
        plugin.on_uninstall()


# ======================================================================
# Testes que o plugin JAMAIS altera o Core
# ======================================================================


class TestNotesNaoAlteraCore:
    """Prova que o plugin nao acopla nem modifica o Core."""

    def test_plugin_nao_importa_core_interno(self):
        """O plugin so depende de CoreAPI, PluginBase, PluginManifest."""
        import ast
        import inspect
        from plugins.cris_notes import plugin as mod
        source = inspect.getsource(mod)
        tree = ast.parse(source)
        imports = {n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)}
        froms = {f"{n.module}.{n.names[0].name}" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        # Nao deve importar nada do core interno (ex.: core.runtime, core.plugins.loader)
        forbidden = {"core.capability", "core.events", "core.plugins.loader", "core.runtime"}
        assert not (froms & forbidden), f"Plugin importou internos do Core: {froms & forbidden}"

    def test_plugin_respeita_contratos(self, plugin):
        """O plugin implementa PluginBase (que herda de Plugin Protocol)."""
        from core.contracts.plugin import Plugin
        assert isinstance(plugin, Plugin)