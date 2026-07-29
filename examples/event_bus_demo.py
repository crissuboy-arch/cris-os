#!/usr/bin/env python3
"""Exemplo funcional — Event Bus do CRIS OS.

Fluxo:
  1. Criar EventLog e EventBus
  2. Assinar eventos de tipos especificos e wildcard
  3. Publicar eventos
  4. Verificar entregas e metricas
  5. Remover assinante (unsubscribe)
  6. Ler eventos do log
  7. Health check
"""

from core.domain.events import Event, EventType
from core.events import InMemoryEventLog, InProcessEventBus


def cabecalho(titulo: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {titulo}")
    print(f"{'='*60}")


def main() -> None:
    # ======================================================================
    # 1. Criar EventLog e EventBus
    # ======================================================================
    cabecalho("1. Criando EventLog e EventBus")
    log = InMemoryEventLog()
    bus = InProcessEventBus(log)
    print("  EventLog e EventBus criados com sucesso")
    print(f"  Health check: {bus.health_check()}")

    # ======================================================================
    # 2. Assinar eventos
    # ======================================================================
    cabecalho("2. Assinando eventos")

    email_events = []
    system_events = []
    all_events = []

    # Assinatura especifica
    bus.subscribe("email.sent", lambda e: email_events.append(e))
    print("  Assinante registrado para 'email.sent'")

    # Assinatura wildcard
    bus.subscribe("*", lambda e: all_events.append(e))
    print("  Assinante registrado para '*' (todos)")

    # Subscribe retornando unsubscribe
    unsub = bus.subscribe("system.shutdown", lambda e: system_events.append(e))
    print("  Assinante registrado para 'system.shutdown'")

    print(f"\n  Total de assinantes: {bus.subscribers_count()}")
    print(f"  Tipos com assinantes: {bus.list_subscribed_types()}")

    # ======================================================================
    # 3. Publicar eventos
    # ======================================================================
    cabecalho("3. Publicando eventos")

    bus.publish(Event(
        type="email.sent",
        payload={"to": "cris@example.com", "subject": "Relatorio mensal"},
        source="cris-inbox",
    ))
    print("  [OK] Evento 'email.sent' publicado")

    bus.publish(Event(
        type="email.sent",
        payload={"to": "cliente@example.com", "subject": "Proposta"},
        source="cris-inbox",
    ))
    print("  [OK] Evento 'email.sent' publicado")

    bus.publish(Event(
        type="system.shutdown",
        payload={"reason": "manutencao"},
        source="core",
    ))
    print("  [OK] Evento 'system.shutdown' publicado")

    bus.publish(Event(
        type="user.login",
        payload={"user": "cris"},
        source="auth",
    ))
    print("  [OK] Evento 'user.login' publicado")

    # ======================================================================
    # 4. Verificar entregas
    # ======================================================================
    cabecalho("4. Verificando entregas")

    print(f"  Eventos 'email.sent' recebidos: {len(email_events)}")
    assert len(email_events) == 2, f"Esperava 2, obteve {len(email_events)}"
    print(f"    Primeiro: para {email_events[0].payload['to']}")
    print(f"    Segundo: para {email_events[1].payload['to']}")

    print(f"  Eventos 'system.shutdown' recebidos: {len(system_events)}")
    assert len(system_events) == 1

    print(f"  Eventos '*' recebidos (todos): {len(all_events)}")
    assert len(all_events) == 4

    # ======================================================================
    # 5. Unsubscribe
    # ======================================================================
    cabecalho("5. Removendo assinante (unsubscribe)")
    unsub()
    print("  Assinante 'system.shutdown' removido")

    bus.publish(Event(type="system.shutdown", payload={"reason": "teste"}))
    print(f"  Eventos 'system.shutdown' apos unsubscribe: {len(system_events)}")
    assert len(system_events) == 1  # nao incrementou
    print("  [OK] Assinante nao recebeu o evento apos unsubscribe")

    # ======================================================================
    # 6. Ler eventos do log
    # ======================================================================
    cabecalho("6. Lendo eventos do log (auditoria/failover)")

    log_events = log.read_all()
    print(f"  Eventos no log: {len(log_events)}")
    assert len(log_events) == 5

    for seq, event in log_events:
        print(f"    #{seq}: {event.type} [source={event.source}] "
              f"correlation_id={event.correlation_id[:8]}...")

    stats = log.get_stats()
    print(f"\n  Log stats: {stats.total_events} eventos, "
          f"sequencia {stats.oldest_sequence}-{stats.newest_sequence}")

    # ======================================================================
    # 7. Metricas do bus
    # ======================================================================
    cabecalho("7. Metricas do Event Bus")

    bus_stats = bus.get_stats()
    print(f"  Total publicado: {bus_stats.total_published}")
    print(f"  Total entregue: {bus_stats.total_delivered}")
    print(f"  Total falhas: {bus_stats.total_failures}")
    print(f"  Assinantes por tipo: {bus_stats.subscribers_by_type}")
    print(f"  Saudavel: {bus_stats.is_healthy}")

    print(f"\n{'='*60}")
    print("  Event Bus funcionando corretamente")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()