# Baseline v1 — Capability Registry (Core Module 1)

> **Checkpoint:** 2026-07-28
> **Status:** CONCLUIDO E CONGELADO
> **Testes:** 196/196 passando (0 falhas, 0 regressoes)
> **Exemplo:** `examples/capability_registry_demo.py` — executa sem erros

## O que foi entregue

### Modulo 1: Capability Registry (`core/capability/`)

Catalogo central de capacidades do CRIS OS. Qualquer plugin que queira
expor ou consumir uma capacidade passa por aqui.

| Componente | Arquivo | Responsabilidade |
|------------|---------|-----------------|
| `CapabilityRegistry` | `registry.py` | Nucleo: registro, resolucao, cache, indices |
| `Capability` | `models.py` | Dado de uma capacidade (nome, versao, plugin, prioridade, saude...) |
| `HealthTracker` | `health.py` | Saude passiva: 5 falhas consecutivas → DOWN, 1 sucesso apos DOWN → DEGRADED |
| `MetricsCollector` | `metrics.py` | Metricas de chamada com percentis (p50, p95, p99) |
| `Version` + `match()` | `semver.py` | Matching semantico: ^, ~, >=, range, wildcard, major-only |
| Erros | `errors.py` | `CapabilityNotFoundError`, `CapabilityUnavailableError`, etc. |
| Contratos | `contracts/capability.py` | `CapabilityProvider`, `CapabilityRegistryProtocol`, `CapabilityEngineProtocol` |

### Testes

- **50 testes unitarios** (`tests/test_capability_registry.py`)
- **12 testes de integracao** (`tests/integration/test_capability_integration.py`)
  - Ciclo de vida completo (register → resolve → fallback → metrics → unregister)
  - Eventos publicados no barramento (SpyEventBus)
  - Cache com invalidacao correta
  - Fallback com publicacao de evento
  - Conflito entre plugins
  - Cenarios paralelos
- **Zero regressoes** em todo o projeto (196 testes)

### Exemplo funcional

```bash
PYTHONPATH=. python examples/capability_registry_demo.py
```

Fluxo: registra 2 providers → resolve (maior prioridade) → 5 falhas → DOWN →
fallback automatico → metricas → remove provider → verifica consistencia.

### Eventos publicados (quando um `event_bus` e injetado)

| Evento | Disparado por |
|--------|--------------|
| `capability.registered` | `register()` quando nova capability |
| `capability.unregistered` | `unregister()` / `unregister_plugin()` |
| `capability.health.changed` | `_update_health()` quando health muda |
| `capability.conflict.detected` | `register()` quando mesma (nome,versao) de plugins diferentes |
| `capability.call.started` | `record_call()` antes da execucao |
| `capability.call.completed` | `record_call()` em caso de sucesso |
| `capability.call.failed` | `record_call()` em caso de erro / `resolve()` todos DOWN |
| `capability.fallback` | `resolve()` quando melhor provider esta DOWN |
| `capability.not_found` | `resolve()` sem providers |

---

## Interfaces Publicas Congeladas (Breaking Changes = Major Version)

Nenhuma das interfaces abaixo pode ser alterada sem bump de versao major.
Quem consome o Capability Registry (Plugin Loader, Capability Engine, Event Bus,
plugins) depende EXCLUSIVAMENTE destes contratos.

### 1. `CapabilityRegistry` (metodos publicos)

```python
register(capability: Capability) -> None
unregister(name: str, plugin_id: str, version: str | None = None) -> None
unregister_plugin(plugin_id: str) -> None

resolve(name: str, constraint: str | None = None, context: ResolveContext | None = None) -> ResolvedCapability
resolve_all(name: str, constraint: str | None = None, context: ResolveContext | None = None) -> list[ResolvedCapability]

find_by_name(name: str) -> list[Capability]
find_by_plugin(plugin_id: str) -> list[Capability]
find_by_domain(domain_prefix: str) -> list[Capability]
get(name: str, plugin_id: str, version: str | None = None) -> Capability | None
list_all() -> list[Capability]
list_plugins() -> list[str]

record_success(name: str, plugin_id: str) -> None
record_failure(name: str, plugin_id: str) -> None
update_health(name: str, plugin_id: str, health: HealthStatus) -> None
get_health(name: str, plugin_id: str) -> HealthStatus

record_call(name: str, plugin_id: str, duration_ms: int, success: bool) -> None
get_metrics(name: str, plugin_id: str) -> CapabilityMetrics

get_stats() -> CapabilityRegistryStats
```

### 2. Modelos de dados (`models.py`)

| Modelo | Campos publicos |
|--------|----------------|
| `Capability` | name, version, plugin_id, priority, input_schema, output_schema, config_schema, timeout_ms, idempotent, status, health, routing_rules, description, id, registered_at, updated_at |
| `CapabilityResult` | success, output, error, provider_plugin_id, provider_version, duration_ms, correlation_id |
| `CapabilityContext` | caller_plugin_id, session_id, user_id, correlation_id, execution_id, metadata |
| `CapabilityRegistration` | capability, call_count, error_count, total_duration_ms, last_called_at, last_error_at |
| `ResolvedCapability` | capability, score |
| `ResolveContext` | caller_plugin_id, prefer_plugin_id, min_version, tags |
| `CapabilityRegistryStats` | total_capabilities, total_plugins, by_status, by_health, total_calls, total_errors, cache_hit_ratio |

### 3. Enums

| Enum | Valores |
|------|---------|
| `CapabilityStatus` | ACTIVE, DEGRADED, DEPRECATED, REMOVED |
| `HealthStatus` | OK, DEGRADED, DOWN, UNKNOWN |
| `FallbackStrategy` | FAILOVER, CIRCUIT_BREAKER, DEGRADED, FALLBACK_VALUE |
| `ConflictStrategy` | HIGHEST_PRIORITY, HIGHEST_VERSION, BEST_HEALTH, COMPOSITE_SCORE |

### 4. Erros

`CapabilityError`, `CapabilityNotFoundError`, `CapabilityUnavailableError`,
`CapabilityConflictError`, `CapabilityTimeoutError`, `CapabilityPermissionError`,
`InvalidVersionError`

### 5. Contratos (`contracts/capability.py`)

`CapabilityProvider` (protocol), `CapabilityRegistryProtocol` (protocol),
`CapabilityEngineProtocol` (protocol), `CapabilityDef`, `CapabilityRequire`,
`CapabilityProvide`

### 6. Utilitarios

`semver_match(version, constraint) -> bool`, `Version.parse(text) -> Version`

---

## Dependencias do Proximo Modulo (Event Bus)

O Event Bus (Modulo 2) depende EXCLUSIVAMENTE das interfaces abaixo.
Nenhum detalhe interno do Capability Registry sera acessado.

### O que o Event Bus precisa do Capability Registry

| Dependencia | Tipo | Uso |
|------------|------|-----|
| `Event` | Classe do `core/domain/events.py` | Estrutura do evento (type, payload, correlation_id, id, source, ts) |
| `EventType` | Classe do `core/domain/events.py` | Constantes de tipos de evento |
| `EventBus` protocol | Contrato do `core/contracts/events.py` | Interface que o Event Bus implementara |
| `EventLog` protocol | Contrato do `core/contracts/events.py` | Interface que o Event Log implementara |

### O que o Event Bus NAO precisa (e NAO acessara)

- `CapabilityRegistry` — o Event Bus nao sabe que CapabilityRegistry existe
- `core/capability/*` — o Event Bus nao importa nada do modulo de capabilities
- `HealthTracker`, `MetricsCollector` — internos do Registry
- Nenhum metodo privado (`_` prefixado) de qualquer classe

### Contrato de integracao

O CapabilityRegistry injeta um `event_bus` (qualquer objeto com `.publish(Event)`)
no construtor. O Event Bus implementara exatamente este protocolo:

```python
class EventBus(Protocol):
    def publish(self, event: Event) -> None: ...
    def subscribe(self, event_type: str, handler: Subscriber) -> None: ...
    # Subscriber = Callable[[Event], None]
```

Nenhum acoplamento adicional. O Event Bus pode ser construido, testado e
evoluido independentemente do Capability Registry.