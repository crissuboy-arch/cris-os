"""Testes de integração do Capability Registry.

Testa o fluxo completo: registro, resolução, fallback, health,
métricas, cache e publicação de eventos.
"""

from __future__ import annotations

import threading
import time

import pytest

from core.capability import (
    Capability,
    CapabilityNotFoundError,
    CapabilityRegistry,
    CapabilityUnavailableError,
    ConflictStrategy,
    HealthStatus,
    ResolveContext,
)
from core.domain.events import Event, EventType


class SpyEventBus:
    """EventBus de teste que captura eventos publicados."""

    def __init__(self) -> None:
        self.events: list[Event] = []
        self._lock = threading.Lock()

    def publish(self, event: Event) -> None:
        with self._lock:
            self.events.append(event)

    def subscribe(self, event_type: str, handler) -> None:
        pass

    def published(self, event_type: str) -> list[Event]:
        return [e for e in self.events if e.type == event_type]

    def reset(self) -> None:
        with self._lock:
            self.events.clear()


class TestIntegracaoCicloVida:
    """Fluxo completo: registrar → resolver → fallback → metrics → remover."""

    def test_ciclo_vida_completo(self):
        """Registra dois providers, usa fallback, verifica metrics, remove."""
        bus = SpyEventBus()
        reg = CapabilityRegistry(event_bus=bus, conflict_strategy=ConflictStrategy.HIGHEST_PRIORITY)

        # 1. Provider principal
        p1 = Capability(
            name="email.send", version="1.0.0", plugin_id="cris-inbox",
            priority=80, health=HealthStatus.OK,
        )
        reg.register(p1)

        # 2. Provider alternativo (menor prioridade)
        p2 = Capability(
            name="email.send", version="1.0.0", plugin_id="cris-fallback",
            priority=30, health=HealthStatus.OK,
        )
        reg.register(p2)

        # 3. Resolve — deve escolher cris-inbox (maior prioridade)
        resolved = reg.resolve("email.send")
        assert resolved.capability.plugin_id == "cris-inbox"

        # 4. Evento de registro foi publicado
        registered = bus.published(EventType.CAPABILITY_REGISTERED)
        assert len(registered) == 2

        # 5. Força DOWN no provider principal
        for _ in range(5):
            reg.record_failure("email.send", "cris-inbox")
        assert reg.get_health("email.send", "cris-inbox") == HealthStatus.DOWN

        # 6. Resolve com fallback automático
        resolved = reg.resolve("email.send")
        assert resolved.capability.plugin_id == "cris-fallback"

        # 7. Evento de fallback foi publicado
        fallback_events = bus.published(EventType.CAPABILITY_FALLBACK)
        assert len(fallback_events) >= 1
        assert fallback_events[0].payload["original_plugin"] == "cris-inbox"

        # 8. Métricas
        reg.record_call("email.send", "cris-fallback", 150, True)
        metrics = reg.get_metrics("email.send", "cris-fallback")
        assert metrics.call_count == 1
        assert metrics.avg_duration_ms == 150.0

        # 9. Health change events
        health_events = bus.published(EventType.CAPABILITY_HEALTH_CHANGED)
        assert len(health_events) >= 1

        # 10. Remove provider principal
        reg.unregister("email.send", "cris-inbox")
        assert reg.get("email.send", "cris-inbox") is None

        # 11. Evento de unregister
        unreg = bus.published(EventType.CAPABILITY_UNREGISTERED)
        assert len(unreg) >= 1

        # 12. Resolve ainda funciona com o provider restante
        resolved = reg.resolve("email.send")
        assert resolved.capability.plugin_id == "cris-fallback"

        # 13. Remove o último provider
        reg.unregister_plugin("cris-fallback")
        with pytest.raises(CapabilityNotFoundError):
            reg.resolve("email.send")

    def test_cache_eh_invalidado_apos_registro(self):
        """Cache é invalidado quando novo provider é registrado."""
        reg = CapabilityRegistry()

        reg.register(Capability(
            name="cache.test", version="1.0.0", plugin_id="p1",
            priority=50, health=HealthStatus.OK,
        ))
        r1 = reg.resolve("cache.test")

        reg.register(Capability(
            name="cache.test", version="2.0.0", plugin_id="p2",
            priority=90, health=HealthStatus.OK,
        ))
        r2 = reg.resolve("cache.test")
        assert r2.capability.plugin_id == "p2"

    def test_todos_down_levanta_unavailable(self):
        """Se todos os providers estão DOWN, levanta CapabilityUnavailableError."""
        reg = CapabilityRegistry()
        reg.register(Capability(
            name="email.send", version="1.0.0", plugin_id="cris-inbox",
            health=HealthStatus.DOWN,
        ))
        with pytest.raises(CapabilityUnavailableError):
            reg.resolve("email.send")

    def test_resolve_com_mesma_prioridade(self):
        """Dois providers com mesma prioridade — qualquer um é aceitável."""
        reg = CapabilityRegistry()
        reg.register(Capability(
            name="email.send", version="1.0.0", plugin_id="p1",
            priority=50, health=HealthStatus.OK,
        ))
        reg.register(Capability(
            name="email.send", version="1.0.0", plugin_id="p2",
            priority=50, health=HealthStatus.OK,
        ))
        resolved = reg.resolve("email.send")
        assert resolved.capability.plugin_id in ("p1", "p2")

    def test_busca_por_dominio_retorna_subcapacidades(self):
        """find_by_domain com prefixo 'email' retorna email.send e email.read."""
        reg = CapabilityRegistry()
        reg.register(Capability(name="email.send", version="1.0.0", plugin_id="p1"))
        reg.register(Capability(name="email.read", version="1.0.0", plugin_id="p1"))
        reg.register(Capability(name="image.generate", version="1.0.0", plugin_id="p2"))

        caps = reg.find_by_domain("email")
        assert len(caps) == 2
        assert {c.name for c in caps} == {"email.send", "email.read"}

    def test_unregister_plugin_remove_todas(self):
        """unregister_plugin remove todas as capabilities de um plugin."""
        reg = CapabilityRegistry()
        reg.register(Capability(name="a", version="1.0.0", plugin_id="p1"))
        reg.register(Capability(name="b", version="1.0.0", plugin_id="p1"))
        reg.register(Capability(name="c", version="1.0.0", plugin_id="p2"))
        reg.unregister_plugin("p1")
        assert len(reg.find_by_plugin("p1")) == 0
        assert len(reg.list_all()) == 1

    def test_stats_aggregam_metricas(self):
        """get_stats retorna contagens corretas."""
        reg = CapabilityRegistry()
        reg.register(Capability(name="a", version="1.0.0", plugin_id="p1", health=HealthStatus.OK))
        reg.register(Capability(name="b", version="1.0.0", plugin_id="p1", health=HealthStatus.DEGRADED))
        reg.record_call("a", "p1", 100, True)
        reg.record_call("a", "p1", 200, True)
        reg.record_call("b", "p1", 50, False)

        stats = reg.get_stats()
        assert stats.total_capabilities == 2
        assert stats.total_plugins == 1
        assert stats.total_calls == 3
        assert stats.total_errors == 1

    def test_eventos_publicados_no_bus(self):
        """Verifica publicação de todos os tipos de evento."""
        bus = SpyEventBus()
        reg = CapabilityRegistry(event_bus=bus)

        # register
        reg.register(Capability(name="test.event", version="1.0.0", plugin_id="p1"))
        assert len(bus.published(EventType.CAPABILITY_REGISTERED)) == 1

        # health change (5 failures)
        for _ in range(5):
            reg.record_failure("test.event", "p1")
        health_events = bus.published(EventType.CAPABILITY_HEALTH_CHANGED)
        assert len(health_events) >= 1

        # call started + completed
        reg.record_call("test.event", "p1", 100, True)
        assert len(bus.published(EventType.CAPABILITY_CALL_STARTED)) == 1
        assert len(bus.published(EventType.CAPABILITY_CALL_COMPLETED)) == 1

        # call failed
        reg.record_call("test.event", "p1", 50, False)
        assert len(bus.published(EventType.CAPABILITY_CALL_FAILED)) == 1

        # unregister
        reg.unregister("test.event", "p1")
        assert len(bus.published(EventType.CAPABILITY_UNREGISTERED)) == 1

        # not found
        with pytest.raises(CapabilityNotFoundError):
            reg.resolve("nao.existe")
        assert len(bus.published(EventType.CAPABILITY_NOT_FOUND)) == 1

    def test_event_bus_none_nao_quebra(self):
        """Registry sem event_bus não levanta exceção."""
        reg = CapabilityRegistry(event_bus=None)
        reg.register(Capability(name="x", version="1.0.0", plugin_id="p1"))
        reg.resolve("x")
        reg.record_call("x", "p1", 100, True)
        reg.unregister("x", "p1")

    def test_conflito_entre_plugins_publica_evento(self):
        """Duas capabilities com mesmo nome/versão de plugins diferentes."""
        bus = SpyEventBus()
        reg = CapabilityRegistry(event_bus=bus)

        reg.register(Capability(name="conflict.test", version="1.0.0", plugin_id="p1"))
        reg.register(Capability(name="conflict.test", version="1.0.0", plugin_id="p2"))

        conflicts = bus.published(EventType.CAPABILITY_CONFLICT_DETECTED)
        assert len(conflicts) == 1
        assert conflicts[0].payload["name"] == "conflict.test"
        assert conflicts[0].payload["existing_plugin"] == "p1"
        assert conflicts[0].payload["new_plugin"] == "p2"

    def test_fallback_publica_evento(self):
        """Fallback automatico publica CAPABILITY_FALLBACK."""
        bus = SpyEventBus()
        reg = CapabilityRegistry(event_bus=bus, conflict_strategy=ConflictStrategy.HIGHEST_PRIORITY)

        reg.register(Capability(
            name="fallback.test", version="1.0.0", plugin_id="main",
            priority=80, health=HealthStatus.OK,
        ))
        reg.register(Capability(
            name="fallback.test", version="1.0.0", plugin_id="backup",
            priority=30, health=HealthStatus.OK,
        ))

        for _ in range(5):
            reg.record_failure("fallback.test", "main")

        resolved = reg.resolve("fallback.test")
        assert resolved.capability.plugin_id == "backup"

        fallbacks = bus.published(EventType.CAPABILITY_FALLBACK)
        assert len(fallbacks) == 1
        assert fallbacks[0].payload["original_plugin"] == "main"
        assert fallbacks[0].payload["fallback_plugin"] == "backup"

    def test_cenario_paralelo_misto(self):
        """Registra, resolve e chama em múltiplas capacidades simultâneas."""
        reg = CapabilityRegistry()
        plugins = ["p1", "p2", "p3"]
        names = ["alpha", "beta", "gamma"]

        for p in plugins:
            for n in names:
                reg.register(Capability(name=n, version="1.0.0", plugin_id=p, priority=50))

        for n in names:
            resolved = reg.resolve(n)
            assert resolved.capability.plugin_id in plugins
            assert resolved.capability.name == n
            for p in plugins:
                reg.record_call(n, p, 100, True)

        stats = reg.get_stats()
        assert stats.total_capabilities == len(plugins) * len(names)
        assert stats.total_calls == len(plugins) * len(names)