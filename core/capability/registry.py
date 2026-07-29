"""
CapabilityRegistry — catálogo central de capacidades do CRIS OS.

Responsabilidades:
  1. Registrar capabilities fornecidas por plugins
  2. Resolver qual provider atende uma requisição de capacidade
  3. Manter índices: por nome, plugin, domínio
  4. Rastrear health e métricas de cada capability
  5. Detectar conflitos entre providers

Cada (capability_name, plugin_id, version) é uma entrada única.
Um mesmo plugin pode registrar múltiplas versões da mesma capability.
"""

from __future__ import annotations

import fnmatch
import logging
from threading import RLock
from typing import Any

from core.capability.errors import (
    CapabilityNotFoundError,
    CapabilityUnavailableError,
)
from core.capability.health import HealthTracker
from core.capability.metrics import MetricsCollector, CapabilityMetrics
from core.capability.models import (
    Capability,
    CapabilityRegistration,
    CapabilityRegistryStats,
    CapabilityStatus,
    ConflictStrategy,
    HealthStatus,
    ResolveContext,
    ResolvedCapability,
)
from core.capability.semver import match as semver_match
from core.domain.events import Event, EventType

logger = logging.getLogger(__name__)

_RESOLVE_CACHE_TTL = 30


class CapabilityRegistry:
    """Catálogo central de capacidades.

    Thread-safe. Opera em memória (as capacidades são registradas
    pelo PluginLoader a partir dos manifests dos plugins).

    Cada entrada é única por (name, plugin_id, version) — um mesmo plugin
    pode ter várias versões da mesma capability coexistindo.
    """

    def __init__(
        self,
        conflict_strategy: ConflictStrategy = ConflictStrategy.COMPOSITE_SCORE,
        event_bus: Any | None = None,
    ) -> None:
        self._lock = RLock()
        self._conflict_strategy = conflict_strategy
        self._event_bus = event_bus

        # Chave primária: (name, plugin_id, version) -> CapabilityRegistration
        self._entries: dict[tuple[str, str, str], CapabilityRegistration] = {}

        # Índice: name -> set de (plugin_id, version)
        self._by_name: dict[str, set[tuple[str, str]]] = {}

        # Índice reverso: plugin_id -> set de (name, version)
        self._by_plugin: dict[str, set[tuple[str, str]]] = {}

        self._health_tracker = HealthTracker()
        self._metrics = MetricsCollector()

        # Cache de resolução: (name, constraint, caller) -> ResolvedCapability
        self._resolve_cache: dict[tuple, tuple[ResolvedCapability | None, float]] = {}

    # ======================================================================
    # Registro
    # ======================================================================

    def register(self, capability: Capability) -> None:
        """Registra uma capability.

        Se a mesma (name, plugin_id, version) já existir, substitui.
        Cada (name, plugin_id, version) é uma entrada independente.
        """
        if capability.status == CapabilityStatus.REMOVED:
            return

        key = (capability.name, capability.plugin_id, capability.version)

        with self._lock:
            # Conflito: mesma capacidade, mesma versão, plugin diferente
            for (n, pid, ver) in list(self._entries.keys()):
                if n == capability.name and ver == capability.version and pid != capability.plugin_id:
                    logger.warning(
                        "Conflito: '%s' v%s registrada por '%s' e '%s'",
                        capability.name, capability.version, pid, capability.plugin_id,
                    )
                    self._publish(
                        EventType.CAPABILITY_CONFLICT_DETECTED,
                        name=capability.name,
                        version=capability.version,
                        existing_plugin=pid,
                        new_plugin=capability.plugin_id,
                    )

            is_new = key not in self._entries
            self._entries[key] = CapabilityRegistration(capability=capability)

            # Índice por nome
            if capability.name not in self._by_name:
                self._by_name[capability.name] = set()
            self._by_name[capability.name].add((capability.plugin_id, capability.version))

            # Índice por plugin
            if capability.plugin_id not in self._by_plugin:
                self._by_plugin[capability.plugin_id] = set()
            self._by_plugin[capability.plugin_id].add((capability.name, capability.version))

            self._invalidate_cache(capability.name)

            if is_new:
                logger.info(
                    "Capability registrada: '%s' v%s por '%s' (priority=%d)",
                    capability.name, capability.version, capability.plugin_id, capability.priority,
                )
                self._publish(
                    EventType.CAPABILITY_REGISTERED,
                    name=capability.name,
                    version=capability.version,
                    plugin_id=capability.plugin_id,
                    priority=capability.priority,
                    status=capability.status.value,
                )

    def unregister(self, name: str, plugin_id: str, version: str | None = None) -> None:
        """Remove uma ou todas as versões de uma capability de um plugin.

        Args:
            name: Nome da capability.
            plugin_id: Plugin a remover.
            version: Se informada, remove só esta versão. Se None, remove todas.
        """
        with self._lock:
            keys_to_remove: list[tuple[str, str, str]] = []
            for (n, pid, ver) in list(self._entries.keys()):
                if n == name and pid == plugin_id:
                    if version is None or ver == version:
                        keys_to_remove.append((n, pid, ver))

            for key in keys_to_remove:
                del self._entries[key]
                n, pid, ver = key

                # Limpa índice por nome
                if n in self._by_name:
                    self._by_name[n].discard((pid, ver))
                    if not self._by_name[n]:
                        del self._by_name[n]

                # Limpa índice por plugin
                if pid in self._by_plugin:
                    self._by_plugin[pid].discard((n, ver))
                    if not self._by_plugin[pid]:
                        del self._by_plugin[pid]

                logger.info("Capability '%s' v%s removida do plugin '%s'", n, ver, pid)
                self._publish(
                    EventType.CAPABILITY_UNREGISTERED,
                    name=n,
                    version=ver,
                    plugin_id=pid,
                )

            self._invalidate_cache(name)

    def unregister_plugin(self, plugin_id: str) -> None:
        """Remove TODAS as capabilities de um plugin."""
        with self._lock:
            pairs = list(self._by_plugin.get(plugin_id, set()))
            for name, ver in pairs:
                key = (name, plugin_id, ver)
                self._entries.pop(key, None)
                if name in self._by_name:
                    self._by_name[name].discard((plugin_id, ver))
                    if not self._by_name[name]:
                        del self._by_name[name]
            if plugin_id in self._by_plugin:
                del self._by_plugin[plugin_id]

            self._invalidate_cache(None)
            logger.info("Plugin '%s' removido com %d capabilities", plugin_id, len(pairs))
            for name, ver in pairs:
                self._publish(
                    EventType.CAPABILITY_UNREGISTERED,
                    name=name,
                    version=ver,
                    plugin_id=plugin_id,
                )

    # ======================================================================
    # Resolução
    # ======================================================================

    def resolve(
        self,
        name: str,
        constraint: str | None = None,
        context: ResolveContext | None = None,
    ) -> ResolvedCapability:
        """Resolve a melhor capability para o nome + constraint.

        Returns:
            ResolvedCapability com o melhor provider.

        Raises:
            CapabilityNotFoundError: nenhum provider registrado.
            CapabilityUnavailableError: providers existem mas todos DOWN.
        """
        caller = context.caller_plugin_id if context else None
        cache_key = (name, constraint, caller)
        now = __import__("time").time()

        with self._lock:
            cached = self._resolve_cache.get(cache_key)
            if cached and (now - cached[1]) < _RESOLVE_CACHE_TTL:
                if cached[0] is None:
                    raise CapabilityNotFoundError(name, constraint)
                return cached[0]

        providers = self.resolve_all(name, constraint, context)

        if not providers:
            self._publish(EventType.CAPABILITY_NOT_FOUND, name=name, constraint=constraint)
            with self._lock:
                self._resolve_cache[cache_key] = (None, now)
            raise CapabilityNotFoundError(name, constraint)

        best = providers[0]
        if best.capability.health == HealthStatus.DOWN:
            healthy = [p for p in providers if p.capability.health != HealthStatus.DOWN]
            if not healthy:
                self._publish(EventType.CAPABILITY_CALL_FAILED, name=name, constraint=constraint, reason="all_down")
                raise CapabilityUnavailableError(name)
            fallback = healthy[0]
            logger.info(
                "Fallback: '%s' de '%s' para '%s'",
                name, best.capability.plugin_id, fallback.capability.plugin_id,
            )
            self._publish(
                EventType.CAPABILITY_FALLBACK,
                name=name,
                original_plugin=best.capability.plugin_id,
                fallback_plugin=fallback.capability.plugin_id,
            )
            best = fallback

        with self._lock:
            self._resolve_cache[cache_key] = (best, now)

        return best

    def resolve_all(
        self,
        name: str,
        constraint: str | None = None,
        context: ResolveContext | None = None,
    ) -> list[ResolvedCapability]:
        """Retorna todos os providers ordenados por score."""
        with self._lock:
            pairs = list(self._by_name.get(name, set()))

        if not pairs:
            return []

        results: list[ResolvedCapability] = []
        for plugin_id, version in pairs:
            key = (name, plugin_id, version)
            with self._lock:
                reg = self._entries.get(key)
            if reg is None:
                continue
            cap = reg.capability
            if cap.status not in (CapabilityStatus.ACTIVE, CapabilityStatus.DEGRADED):
                continue
            if constraint and not semver_match(cap.version, constraint):
                continue
            if context and context.min_version:
                if not semver_match(cap.version, f">={context.min_version}"):
                    continue
            if context and cap.routing_rules:
                if not self._match_routing_rules(cap.routing_rules, context):
                    continue

            score = self._calculate_score(cap, context)
            results.append(ResolvedCapability(capability=cap, score=score))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    # ======================================================================
    # Consultas
    # ======================================================================

    def find_by_name(self, name: str) -> list[Capability]:
        """Retorna todas as versões de uma capability de todos os plugins."""
        with self._lock:
            pairs = self._by_name.get(name, set())
            result = []
            for pid, ver in pairs:
                reg = self._entries.get((name, pid, ver))
                if reg:
                    result.append(reg.capability)
            return result

    def find_by_plugin(self, plugin_id: str) -> list[Capability]:
        """Retorna todas as capabilities de um plugin."""
        with self._lock:
            pairs = self._by_plugin.get(plugin_id, set())
            result = []
            for name, ver in pairs:
                reg = self._entries.get((name, plugin_id, ver))
                if reg:
                    result.append(reg.capability)
            return result

    def find_by_domain(self, domain_prefix: str) -> list[Capability]:
        """Retorna capabilities cujo nome começa com o prefixo."""
        with self._lock:
            pattern = f"{domain_prefix}.*"
            result = []
            for name, pairs in self._by_name.items():
                if name == domain_prefix or fnmatch.fnmatch(name, pattern):
                    for pid, ver in pairs:
                        reg = self._entries.get((name, pid, ver))
                        if reg:
                            result.append(reg.capability)
            return result

    def get(self, name: str, plugin_id: str, version: str | None = None) -> Capability | None:
        """Retorna uma capability específica.

        Args:
            name: Nome da capability.
            plugin_id: Plugin.
            version: Se informada, retorna a versão exata.
                     Se None, retorna a de maior versão.
        """
        with self._lock:
            if version:
                reg = self._entries.get((name, plugin_id, version))
                return reg.capability if reg else None

            pairs = self._by_name.get(name, set())
            candidates = [(pid, v) for pid, v in pairs if pid == plugin_id]
            if not candidates:
                return None
            # Retorna a de maior versão
            from core.capability.semver import Version
            best = max(candidates, key=lambda x: Version.parse(x[1]))
            reg = self._entries.get((name, best[0], best[1]))
            return reg.capability if reg else None

    def list_all(self) -> list[Capability]:
        """Lista todas as capabilities registradas."""
        with self._lock:
            return [reg.capability for reg in self._entries.values()]

    def list_plugins(self) -> list[str]:
        """Lista todos os plugin_ids com capabilities registradas."""
        with self._lock:
            return list(self._by_plugin.keys())

    # ======================================================================
    # Health
    # ======================================================================

    def record_success(self, name: str, plugin_id: str) -> None:
        health = self._health_tracker.record_success(name, plugin_id)
        if health is not None:
            self._update_health(name, plugin_id, health)

    def record_failure(self, name: str, plugin_id: str) -> None:
        health = self._health_tracker.record_failure(name, plugin_id)
        if health is not None:
            self._update_health(name, plugin_id, health)

    def update_health(self, name: str, plugin_id: str, health: HealthStatus) -> None:
        self._update_health(name, plugin_id, health)
        self._health_tracker.reset(name, plugin_id)

    def _update_health(self, name: str, plugin_id: str, health: HealthStatus) -> None:
        with self._lock:
            for (n, pid, ver), reg in self._entries.items():
                if n == name and pid == plugin_id:
                    old = reg.capability.health
                    reg.capability.health = health
                    reg.capability.updated_at = _agora()
                    if old != health:
                        self._publish(
                            EventType.CAPABILITY_HEALTH_CHANGED,
                            name=n,
                            version=ver,
                            plugin_id=pid,
                            old_health=old.value,
                            new_health=health.value,
                        )
            self._invalidate_cache(name)

    def get_health(self, name: str, plugin_id: str) -> HealthStatus:
        health = self._health_tracker.get_health(name, plugin_id)
        if health is not None:
            return health
        cap = self.get(name, plugin_id)
        return cap.health if cap else HealthStatus.UNKNOWN

    # ======================================================================
    # Métricas
    # ======================================================================

    def record_call(self, name: str, plugin_id: str, duration_ms: int, success: bool) -> None:
        self._publish(
            EventType.CAPABILITY_CALL_STARTED,
            name=name,
            plugin_id=plugin_id,
        )
        self._metrics.record_call(name, plugin_id, duration_ms, success)
        event_type = EventType.CAPABILITY_CALL_COMPLETED if success else EventType.CAPABILITY_CALL_FAILED
        with self._lock:
            for (n, pid, ver), reg in self._entries.items():
                if n == name and pid == plugin_id:
                    reg.call_count += 1
                    reg.total_duration_ms += duration_ms
                    reg.last_called_at = _agora()
                    if not success:
                        reg.error_count += 1
                        reg.last_error_at = _agora()
        self._publish(
            event_type,
            name=name,
            plugin_id=plugin_id,
            duration_ms=duration_ms,
        )

    def get_metrics(self, name: str, plugin_id: str) -> CapabilityMetrics:
        return self._metrics.get_metrics(name, plugin_id)

    # ======================================================================
    # Estatísticas
    # ======================================================================

    def get_stats(self) -> CapabilityRegistryStats:
        with self._lock:
            all_caps = self.list_all()
            stats = CapabilityRegistryStats(
                total_capabilities=len(all_caps),
                total_plugins=len(self._by_plugin),
            )
            for cap in all_caps:
                stats.by_status[cap.status.value] = stats.by_status.get(cap.status.value, 0) + 1
                stats.by_health[cap.health.value] = stats.by_health.get(cap.health.value, 0) + 1

            all_metrics = self._metrics.get_all_metrics()
            for name, plugins in all_metrics.items():
                for plugin_id, m in plugins.items():
                    stats.total_calls += m.call_count
                    stats.total_errors += m.error_count
            return stats

    # ======================================================================
    # Internos
    # ======================================================================

    def _calculate_score(self, capability: Capability, context: ResolveContext | None = None) -> float:
        priority_w = capability.priority / 100.0
        health_map = {
            HealthStatus.OK: 1.0, HealthStatus.DEGRADED: 0.4,
            HealthStatus.DOWN: 0.0, HealthStatus.UNKNOWN: 0.6,
        }
        health_w = health_map.get(capability.health, 0.5)

        from core.capability.semver import Version
        ver = Version.parse(capability.version)
        version_w = min(1.0, (ver.major * 100 + ver.minor * 10 + ver.patch) / 1000)

        if self._conflict_strategy == ConflictStrategy.HIGHEST_PRIORITY:
            return priority_w
        if self._conflict_strategy == ConflictStrategy.HIGHEST_VERSION:
            return version_w
        if self._conflict_strategy == ConflictStrategy.BEST_HEALTH:
            return health_w
        return priority_w * 0.4 + health_w * 0.35 + version_w * 0.25

    def _match_routing_rules(self, rules: dict, context: ResolveContext) -> bool:
        tags = context.tags or {}
        for key, allowed_values in rules.items():
            if not isinstance(allowed_values, list):
                allowed_values = [allowed_values]
            actual = tags.get(key)
            if actual and actual not in allowed_values:
                return False
        return True

    def _invalidate_cache(self, name: str | None = None) -> None:
        if name is None:
            self._resolve_cache.clear()
            return
        keys_to_remove = [k for k in self._resolve_cache if k[0] == name]
        for k in keys_to_remove:
            del self._resolve_cache[k]

    def _publish(self, event_type: str, **payload: Any) -> None:
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(Event(type=event_type, payload=payload, source="capability.registry"))
        except Exception:
            logger.exception("Falha ao publicar evento %s", event_type)


def _agora() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()