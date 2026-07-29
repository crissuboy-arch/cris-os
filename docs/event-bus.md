# Modulo 2: Event Bus

## Visao Geral

O Event Bus e o backbone event-driven do CRIS OS. Toda acontecimento
relevante vira um `Event` que e:
1. **Persistido** no `Event Log` (append-only, sequencial)
2. **Notificado** a todos os assinantes interessados

Isso resolve 4 requisitos ao mesmo tempo:
- **Event-Driven**: assinantes reagem a eventos (pub/sub)
- **Auditoria**: todo evento gravado, amarrado por `correlation_id`
- **Replicacao**: o log pode ser enviado a 2a maquina
- **Failover**: a replica reprocessa eventos e reconstroi o estado

## Arquivos

```
core/events/
  __init__.py   - exports publicos
  bus.py        - InProcessEventBus (pub/sub sincrono)
  log.py        - InMemoryEventLog (append-only, thread-safe)
  errors.py     - EventBusError, SubscriptionNotFoundError, EventLogError

core/domain/events.py - Event, EventType (modelos compartilhados)
core/contracts/events.py - EventBus (Protocol), EventLog (Protocol)

tests/
  test_event_bus.py              - 33 testes unitarios
  integration/
    test_event_bus_integration.py - 5 testes de integracao com CapabilityRegistry

examples/
  event_bus_demo.py - exemplo funcional completo
```

## API Publica

### InProcessEventBus

```python
bus = InProcessEventBus(event_log)
```

#### Assinatura
| Metodo | Descricao |
|--------|-----------|
| `subscribe(event_type, handler)` | Assina um tipo (ou '*' para todos). Retorna callable de unsubscribe. |
| `subscribers_count(event_type=None)` | Numero de assinantes. |
| `list_subscribed_types()` | Lista tipos com assinantes. |

#### Publicacao
| Metodo | Descricao |
|--------|-----------|
| `publish(event)` | Publica: persiste no log + notifica assinantes. Falhas isoladas. |

#### Saude e Metricas
| Metodo | Descricao |
|--------|-----------|
| `health_check()` | Verifica se o bus esta saudavel. |
| `get_stats()` | Estatisticas: total_published, total_delivered, total_failures, subscribers_by_type, is_healthy. |
| `reset_metrics()` | Zera contadores de metricas. |

### InMemoryEventLog

```python
log = InMemoryEventLog()
```

| Metodo | Descricao |
|--------|-----------|
| `append(event)` | Persiste evento, retorna numero de sequencia. |
| `read_since(cursor, limit)` | Le eventos desde uma posicao. |
| `read_all()` | Todos os eventos. |
| `count()` | Total de eventos. |
| `get_stats()` | Estatisticas do log. |
| `clear()` | Limpa o log. |

### Erros

| Erro | Quando |
|------|--------|
| `EventBusError` | Erro base. |
| `SubscriptionNotFoundError` | Unsubscribe de handler inexistente. |
| `EventLogError` | Erro no Event Log. |

## Como Executar

```bash
# Testes unitarios
python -m pytest tests/test_event_bus.py -v

# Testes de integracao
python -m pytest tests/integration/test_event_bus_integration.py -v

# Exemplo funcional
PYTHONPATH=. python examples/event_bus_demo.py
```

## Arquitetura

### Fluxo de um Evento

```
Publisher (ex.: CapabilityRegistry)
  |
  v
InProcessEventBus.publish(event)
  |
  +--> EventLog.append(event)     # persistencia (fonte da verdade)
  |
  +--> handlers[event.type]       # assinantes especificos
  |
  +--> handlers["*"]              # assinantes globais
```

### Isolamento de Falhas

Se um assinante levanta excecao:
- O erro e logado (`logger.exception`)
- Os demais assinantes continuam sendo notificados
- O `total_failures` nas metricas e incrementado

### Thread Safety

Todas as operacoes do Event Bus e Event Log sao protegidas por `Lock`.

### Event Log para Failover

```python
# Maquina primaria
log.append(event)  # sequencia 1, 2, 3...

# Maquina replica (failover)
for seq, event in log.read_since(last_cursor):
    reprocess(event)
```

## Checklist de Conclusao

- [x] Totalmente desacoplado (usa protocolos, nao classes concretas)
- [x] Orientado a eventos (pub/sub)
- [x] Tipado (Event, EventType, protocolos)
- [x] Sincrono primeiro, assincrono opcional (contrato permite)
- [x] Testes unitarios (33)
- [x] Testes de integracao com CapabilityRegistry (5)
- [x] Documentacao (este arquivo)
- [x] Exemplo executavel
- [x] Metricas (total_published, delivered, failures, subscribers_by_type)
- [x] Health check (health_check())
- [x] Compativel com plugins (EventBus protocol)
- [x] Unsubscribe funcional
- [x] Event Log para auditoria e failover
- [x] Zero regressoes (196 + 38 = 234 testes no total)