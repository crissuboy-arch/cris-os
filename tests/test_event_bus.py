"""Testes unitarios do Event Bus (InProcessEventBus + InMemoryEventLog)."""

import threading
import time

import pytest

from core.domain.events import Event, EventType
from core.events import (
    EventBusStats,
    InMemoryEventLog,
    InProcessEventBus,
    SubscriptionNotFoundError,
)
from core.events.log import EventLogStats


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def log():
    return InMemoryEventLog()


@pytest.fixture
def bus(log):
    return InProcessEventBus(log)


def _event(type_: str = "test.event", **kw) -> Event:
    return Event(type=type_, payload=kw)


# ======================================================================
# Event Log
# ======================================================================


class TestEventLog:
    def test_append_e_read(self, log):
        seq = log.append(_event("a"))
        assert seq == 1
        seq = log.append(_event("b"))
        assert seq == 2
        assert log.count() == 2

    def test_read_since(self, log):
        log.append(_event("a"))
        log.append(_event("b"))
        log.append(_event("c"))
        events = log.read_since(cursor=1, limit=2)
        assert len(events) == 2
        assert events[0][0] == 2  # sequence
        assert events[0][1].type == "b"
        assert events[1][0] == 3
        assert events[1][1].type == "c"

    def test_read_all(self, log):
        log.append(_event("x"))
        log.append(_event("y"))
        all_ = log.read_all()
        assert len(all_) == 2
        assert all_[0][0] == 1
        assert all_[1][0] == 2

    def test_read_since_alem_do_fim(self, log):
        log.append(_event("a"))
        events = log.read_since(cursor=99, limit=10)
        assert events == []

    def test_stats_vazio(self, log):
        stats = log.get_stats()
        assert stats.total_events == 0

    def test_stats_com_eventos(self, log):
        log.append(_event("a"))
        log.append(_event("b"))
        stats = log.get_stats()
        assert stats.total_events == 2
        assert stats.oldest_sequence == 1
        assert stats.newest_sequence == 2

    def test_clear(self, log):
        log.append(_event("a"))
        log.clear()
        assert log.count() == 0
        assert log.get_stats().total_events == 0


# ======================================================================
# Event Bus — assinatura
# ======================================================================


class TestBusSubscribe:
    def test_subscribe_e_recebe(self, bus):
        received = []
        bus.subscribe("test.event", lambda e: received.append(e))
        bus.publish(_event("test.event", msg="hello"))
        assert len(received) == 1
        assert received[0].payload["msg"] == "hello"

    def test_subscribe_wildcard(self, bus):
        received = []
        bus.subscribe("*", lambda e: received.append(e.type))
        bus.publish(_event("a"))
        bus.publish(_event("b"))
        assert received == ["a", "b"]

    def test_subscribe_multiplos_handlers(self, bus):
        r1, r2 = [], []
        bus.subscribe("t", r1.append)
        bus.subscribe("t", r2.append)
        bus.publish(_event("t"))
        assert len(r1) == 1
        assert len(r2) == 1

    def test_unsubscribe_retorna_callable(self, bus):
        received = []
        unsub = bus.subscribe("t", lambda e: received.append(e))
        bus.publish(_event("t"))
        assert len(received) == 1
        unsub()
        bus.publish(_event("t"))
        assert len(received) == 1  # nao incrementou

    def test_unsubscribe_inexistente_levanta(self, bus):
        with pytest.raises(SubscriptionNotFoundError):
            bus._unsubscribe("t", lambda e: None)

    def test_subscribers_count(self, bus):
        assert bus.subscribers_count() == 0
        bus.subscribe("a", lambda e: None)
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        assert bus.subscribers_count() == 3
        assert bus.subscribers_count("a") == 2
        assert bus.subscribers_count("b") == 1
        assert bus.subscribers_count("c") == 0

    def test_list_subscribed_types(self, bus):
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        types = bus.list_subscribed_types()
        assert "a" in types
        assert "b" in types


# ======================================================================
# Event Bus — publicacao
# ======================================================================


class TestBusPublish:
    def test_publish_persiste_no_log(self, bus, log):
        bus.publish(_event("t"))
        assert log.count() == 1

    def test_publish_notifica_tipo_especifico(self, bus):
        received = []
        bus.subscribe("t", lambda e: received.append(e))
        bus.subscribe("outro", lambda e: received.append("nao"))
        bus.publish(_event("t"))
        assert len(received) == 1

    def test_publish_notifica_wildcard_e_tipo(self, bus):
        r_specific = []
        r_wild = []
        bus.subscribe("t", lambda e: r_specific.append(e))
        bus.subscribe("*", lambda e: r_wild.append(e))
        bus.publish(_event("t"))
        assert len(r_specific) == 1
        assert len(r_wild) == 1

    def test_handler_ruim_nao_derruba_outros(self, bus):
        good = []
        bus.subscribe("t", lambda e: (_ for _ in ()).throw(Exception("fail")))
        bus.subscribe("t", lambda e: good.append(e))
        bus.publish(_event("t"))  # nao deve levantar
        assert len(good) == 1

    def test_evento_sem_assinantes_nao_quebra(self, bus):
        bus.publish(_event("orphan"))  # nao deve levantar

    def test_publica_com_correlation_id(self, bus):
        received = []
        bus.subscribe("t", lambda e: received.append(e))
        e = Event(type="t", correlation_id="abc-123")
        bus.publish(e)
        assert received[0].correlation_id == "abc-123"


# ======================================================================
# Event Bus — metricas
# ======================================================================


class TestBusMetrics:
    def test_stats_iniciais(self, bus):
        stats = bus.get_stats()
        assert stats.total_published == 0
        assert stats.total_delivered == 0
        assert stats.total_failures == 0

    def test_stats_apos_publicar(self, bus):
        bus.subscribe("t", lambda e: None)
        bus.publish(_event("t"))
        stats = bus.get_stats()
        assert stats.total_published == 1
        assert stats.total_delivered == 1

    def test_stats_com_falha(self, bus):
        bus.subscribe("t", lambda e: (_ for _ in ()).throw(Exception("fail")))
        bus.publish(_event("t"))
        stats = bus.get_stats()
        assert stats.total_published == 1
        assert stats.total_failures == 1

    def test_stats_subscribers_by_type(self, bus):
        bus.subscribe("a", lambda e: None)
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        stats = bus.get_stats()
        assert stats.subscribers_by_type["a"] == 2
        assert stats.subscribers_by_type["b"] == 1

    def test_reset_metrics(self, bus):
        bus.subscribe("t", lambda e: None)
        bus.publish(_event("t"))
        bus.reset_metrics()
        stats = bus.get_stats()
        assert stats.total_published == 0
        assert stats.total_delivered == 0

    def test_health_check(self, bus):
        assert bus.health_check() is True
        assert bus.healthy is True


# ======================================================================
# Event Bus — integracao
# ======================================================================


class TestBusIntegration:
    def test_ciclo_vida_completo(self):
        """Event Log + Event Bus: publicar, ler do log, verificar."""
        log = InMemoryEventLog()
        bus = InProcessEventBus(log)

        received = []
        bus.subscribe("test.complete", lambda e: received.append(e))

        bus.publish(Event(type="test.complete", payload={"step": 1}))
        bus.publish(Event(type="test.complete", payload={"step": 2}))

        assert len(received) == 2
        assert log.count() == 2

        # Ler do log
        events = log.read_since(0)
        assert len(events) == 2
        assert events[0][1].payload["step"] == 1
        assert events[1][1].payload["step"] == 2

    def test_assinantes_independentes(self):
        """Assinantes de tipos diferentes nao se interferem."""
        log = InMemoryEventLog()
        bus = InProcessEventBus(log)

        r1, r2 = [], []
        bus.subscribe("type.a", lambda e: r1.append(e))
        bus.subscribe("type.b", lambda e: r2.append(e))

        bus.publish(Event(type="type.a"))
        assert len(r1) == 1
        assert len(r2) == 0

        bus.publish(Event(type="type.b"))
        assert len(r1) == 1
        assert len(r2) == 1

    def test_mesmo_handler_para_multiplos_tipos(self):
        """Um handler pode assinar varios tipos."""
        log = InMemoryEventLog()
        bus = InProcessEventBus(log)

        received = []
        handler = lambda e: received.append(e.type)
        bus.subscribe("x", handler)
        bus.subscribe("y", handler)

        bus.publish(Event(type="x"))
        bus.publish(Event(type="y"))
        assert received == ["x", "y"]

    def test_subscribe_retorna_unsub_e_funciona(self):
        """Unsubscribe via callable retornado por subscribe."""
        log = InMemoryEventLog()
        bus = InProcessEventBus(log)

        received = []
        unsub = bus.subscribe("t", lambda e: received.append(e))
        bus.publish(Event(type="t"))
        assert len(received) == 1

        unsub()
        bus.publish(Event(type="t"))
        assert len(received) == 1  # nao incrementou

    def test_event_log_rejeita_evento_invalido(self):
        """Event Log ignora eventos invalidos sem quebrar."""
        log = InMemoryEventLog()
        # Nao deve levantar
        log.append(Event(type="valid"))
        assert log.count() == 1

    def test_fluxo_real_capability_registry_pov(self):
        """Simula o uso do Event Bus pelo Capability Registry."""
        log = InMemoryEventLog()
        bus = InProcessEventBus(log)

        events = []
        bus.subscribe(EventType.CAPABILITY_REGISTERED, lambda e: events.append(e))
        bus.subscribe(EventType.CAPABILITY_UNREGISTERED, lambda e: events.append(e))
        bus.subscribe(EventType.CAPABILITY_FALLBACK, lambda e: events.append(e))

        # Simula eventos que o Registry publicaria
        bus.publish(Event(
            type=EventType.CAPABILITY_REGISTERED,
            payload={"name": "email.send", "plugin_id": "cris-inbox"},
        ))
        bus.publish(Event(
            type=EventType.CAPABILITY_FALLBACK,
            payload={"name": "email.send", "from": "cris-inbox", "to": "cris-backup"},
        ))
        bus.publish(Event(
            type=EventType.CAPABILITY_UNREGISTERED,
            payload={"name": "email.send", "plugin_id": "cris-inbox"},
        ))

        assert len(events) == 3
        assert log.count() == 3

    def test_log_stats_apos_eventos(self):
        log = InMemoryEventLog()
        log.append(Event(type="a"))
        log.append(Event(type="b"))
        stats = log.get_stats()
        assert stats.total_events == 2