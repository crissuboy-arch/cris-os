# Modulo 1: Capability Registry

## Visao Geral

O Capability Registry e o catalogo central de capacidades do CRIS OS.
Cada plugin declara no seu manifesto quais capacidades ele **fornece**
(`provides`) e quais ele **requer** (`requires`). O Registry e a autoridade
que responde "quem atende esta capacidade?" em tempo de execucao.

Principios:
- **Capability-first**: plugins nao conhecem outros plugins por nome;
  eles conhecem apenas capacidades. O Core resolve qual plugin atende
  cada requisicao.
- **Multi-versao**: um mesmo plugin pode registrar varias versoes da
  mesma capacidade simultaneamente.
- **Multi-provider**: varios plugins podem oferecer a mesma capacidade;
  o Registry escolhe o melhor com base em score composto (prioridade,
  saude, versao).
- **Thread-safe**: todas as operacoes sao protegidas por RLock.

## Arquivos

```
core/capability/
  __init__.py     - exports publicos
  models.py       - Capability, ResolvedCapability, ResolveContext, etc.
  registry.py     - CapabilityRegistry (nucleo do modulo)
  semver.py       - matching semantico (^, ~, >=, range, wildcard)
  health.py       - HealthTracker (monitoramento passivo de saude)
  metrics.py      - MetricsCollector (metricas de chamada com percentis)
  errors.py       - CapabilityError hierarquia

core/contracts/capability.py  - protocolos CapabilityProvider, CapabilityRegistryProtocol, CapabilityEngineProtocol

tests/
  test_capability_registry.py   - 50 testes unitarios
  integration/
    test_capability_integration.py  - 12 testes de integracao

examples/
  capability_registry_demo.py   - exemplo funcional completo
```

## API Publica

### CapabilityRegistry

```python
reg = CapabilityRegistry(
    conflict_strategy=ConflictStrategy.COMPOSITE_SCORE,
    event_bus=None,   # EventBus opcional (protocolo)
)
```

#### Registro e Remocao
| Metodo | Descricao |
|--------|-----------|
| `register(capability)` | Registra uma capacidade. Substitui se mesma (name,plugin,version). |
| `unregister(name, plugin_id, version=None)` | Remove versao especifica ou todas. |
| `unregister_plugin(plugin_id)` | Remove TODAS as capacidades de um plugin. |

#### Resolucao
| Metodo | Descricao |
|--------|-----------|
| `resolve(name, constraint=None, context=None)` | Melhor provider para a capacidade. |
| `resolve_all(name, constraint=None, context=None)` | Todos os providers ordenados por score. |

#### Consultas
| Metodo | Descricao |
|--------|-----------|
| `find_by_name(name)` | Todas as versoes de todos os plugins. |
| `find_by_plugin(plugin_id)` | Todas as capacidades de um plugin. |
| `find_by_domain(prefix)` | Capacidades com nome comecando com prefixo. |
| `get(name, plugin_id, version=None)` | Capacidade especifica. |
| `list_all()` | Todas as capacidades. |
| `list_plugins()` | Todos os plugins com capacidades. |

#### Saude e Metricas
| Metodo | Descricao |
|--------|-----------|
| `record_success(name, plugin_id)` | Registra sucesso (tracker passivo). |
| `record_failure(name, plugin_id)` | Registra falha (5 consecutivas -> DOWN). |
| `update_health(name, plugin_id, health)` | Define saude manualmente (reseta tracker). |
| `get_health(name, plugin_id)` | Saude atual (tracker ou field). |
| `record_call(name, plugin_id, duration_ms, success)` | Registra chamada + metricas. |
| `get_metrics(name, plugin_id)` | Metricas agregadas. |
| `get_stats()` | Estatisticas do registry. |

### Health State Machine
```
0 falhas consecutivas + 0 sucessos consecutivos -> UNKNOWN
3 falhas consecutivas -> DEGRADED
5 falhas consecutivas -> DOWN
1 sucesso apos DOWN -> DEGRADED
5 sucessos consecutivos -> OK
```

### Score Composto (default)
```
score = priority * 0.4 + health * 0.35 + version * 0.25
```

Estrategias alternativas: `HIGHEST_PRIORITY`, `HIGHEST_VERSION`, `BEST_HEALTH`.

### Eventos Publicados
Quando um `event_bus` e fornecido, o registry publica:

| Evento | Quando |
|--------|--------|
| `capability.registered` | Nova capacidade registrada |
| `capability.unregistered` | Capacidade removida |
| `capability.health.changed` | Saude de uma capacidade mudou |
| `capability.conflict.detected` | Mesma (nome,versao) registrada por plugins diferentes |
| `capability.call.started` | Chamada iniciada |
| `capability.call.completed` | Chamada bem-sucedida |
| `capability.call.failed` | Chamada falhou |
| `capability.fallback` | Resolve fez fallback para provider alternativo |
| `capability.not_found` | Nenhum provider encontrado |

## Como Executar

```bash
# Testes unitarios
python -m pytest tests/test_capability_registry.py -v

# Testes de integracao
python -m pytest tests/integration/test_capability_integration.py -v

# Exemplo funcional
PYTHONPATH=. python examples/capability_registry_demo.py
```

## Checklist de Conclusao

- [x] Interfaces publicas estaveis (`__init__.py`)
- [x] Contratos tipados (`contracts/capability.py`)
- [x] Registro de capability
- [x] Remocao de capability
- [x] Busca por nome e dominio
- [x] Suporte a multiplos providers
- [x] Versionamento (semver)
- [x] Prioridade entre providers
- [x] Fallback automatico
- [x] Health check (passivo e manual)
- [x] Metricas de chamada
- [x] Cache com invalidacao correta
- [x] Eventos publicados no Event Bus
- [x] Testes unitarios (50)
- [x] Testes de integracao (12)
- [x] Documentacao (este arquivo)
- [x] Exemplo executavel
- [x] Garantia de compatibilidade (184 testes no total, 0 falhas)