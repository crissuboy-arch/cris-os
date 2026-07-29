"""Testes de integracao do Event Bus com o Capability Registry."""

from core.capability import (
    Capability,
    CapabilityNotFoundError,
    CapabilityRegistry,
    ConflictStrategy,
    HealthStatus,
)
from core.domain.events import EventType
from core.events import InMemoryEventLog, InProcessEventBus


class TestIntegracaoEventBusRegistry:
    """Event Bus recebendo eventos do Capability Registry."""

    def test_registry_publica_eventos_no_bus(self):
        log = InMemoryEventLog()
        bus = InProcessEventBus(log)
        reg = CapabilityRegistry(event_bus=bus)

        collected = []
        bus.subscribe("*", lambda e: collected.append(e.type))

        reg.register(Capability(name="x", version="1.0.0", plugin_id="p1"))
        assert EventType.CAPABILITY_REGISTERED in collected

        reg.unregister("x", "p1")
        assert EventType.CAPABILITY_UNREGISTERED in collected

        # Nao encontrada
        try:
            reg.resolve("nao.existe")
        except CapabilityNotFoundError:
            pass
        assert EventType.CAPABILITY_NOT_FOUND in collected

    def test_registry_publica_health_change(self):
        log = InMemoryEventLog()
        bus = InProcessEventBus(log)
        reg = CapabilityRegistry(event_bus=bus)

        health_events = []
        bus.subscribe(EventType.CAPABILITY_HEALTH_CHANGED, lambda e: health_events.append(e))

        reg.register(Capability(name="h", version="1.0.0", plugin_id="p1", health=HealthStatus.OK))

        for _ in range(5):
            reg.record_failure("h", "p1")

        assert len(health_events) >= 1
        last = health_events[-1]
        assert last.payload["new_health"] == "down"
        assert last.payload["old_health"] == "ok" or last.payload["old_health"] == "degraded"

    def test_registry_publica_fallback_no_bus(self):
        log = InMemoryEventLog()
        bus = InProcessEventBus(log)
        reg = CapabilityRegistry(
            event_bus=bus,
            conflict_strategy=ConflictStrategy.HIGHEST_PRIORITY,
        )

        fallback_events = []
        bus.subscribe(EventType.CAPABILITY_FALLBACK, lambda e: fallback_events.append(e))

        reg.register(Capability(
            name="fb", version="1.0.0", plugin_id="main",
            priority=80, health=HealthStatus.OK,
        ))
        reg.register(Capability(
            name="fb", version="1.0.0", plugin_id="backup",
            priority=30, health=HealthStatus.OK,
        ))

        for _ in range(5):
            reg.record_failure("fb", "main")

        resolved = reg.resolve("fb")
        assert resolved.capability.plugin_id == "backup"

        assert len(fallback_events) == 1
        assert fallback_events[0].payload["original_plugin"] == "main"
        assert fallback_events[0].payload["fallback_plugin"] == "backup"

    def test_eventos_ficam_no_log(self):
        """Eventos persistem no log mesmo apos uso."""
        log = InMemoryEventLog()
        bus = InProcessEventBus(log)
        reg = CapabilityRegistry(event_bus=bus)

        reg.register(Capability(name="audit", version="1.0.0", plugin_id="p1"))
        reg.register(Capability(name="audit", version="2.0.0", plugin_id="p2"))

        # Log tem os eventos
        events = log.read_all()
        types = [e.type for _, e in events]
        assert EventType.CAPABILITY_REGISTERED in types

        # Pode ser reprocessado (failover)
        count = 0
        for seq, event in events:
            if event.type == EventType.CAPABILITY_REGISTERED:
                count += 1
        assert count == 2

    def test_multiplos_registries_mesmo_bus(self):
        """Dois registries compartilham o mesmo bus."""
        log = InMemoryEventLog()
        bus = InProcessEventBus(log)

        reg1 = CapabilityRegistry(event_bus=bus)
        reg2 = CapabilityRegistry(event_bus=bus)

        collected = []
        bus.subscribe(EventType.CAPABILITY_REGISTERED, lambda e: collected.append(e))

        reg1.register(Capability(name="a", version="1.0.0", plugin_id="p1"))
        reg2.register(Capability(name="b", version="1.0.0", plugin_id="p2"))

        assert len(collected) == 2
        assert log.count() == 2