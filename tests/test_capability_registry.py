"""
Testes do Capability Registry — módulo 1 do CRIS OS Core.

Cobre:
  - Registro e remoção de capabilities
  - Resolução por nome + constraint semver
  - Score composto (prioridade, health, versão)
  - Health tracking passivo (sucessos/falhas consecutivas)
  - Métricas de chamadas
  - Consultas: find_by_name, find_by_plugin, find_by_domain, get, list_all
  - Cache de resolução
  - Conflitos entre plugins
  - Routing rules contextuais
  - Edge cases: versão inválida, capability inexistente, etc.
"""

import time
import pytest

from core.capability import (
    Capability,
    CapabilityRegistry,
    CapabilityNotFoundError,
    CapabilityUnavailableError,
    CapabilityStatus,
    ConflictStrategy,
    HealthStatus,
    ResolveContext,
)


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def registry():
    return CapabilityRegistry()


def _cap(name: str, version: str, plugin: str, **kw) -> Capability:
    """Helper para criar capabilities de teste."""
    return Capability(
        name=name,
        version=version,
        plugin_id=plugin,
        **kw,
    )


# ======================================================================
# Registro
# ======================================================================

class TestRegistro:
    def test_registrar_capability_simples(self, registry):
        c = _cap("email.send", "1.0.0", "cris-inbox")
        registry.register(c)
        assert len(registry.list_all()) == 1
        assert registry.get("email.send", "cris-inbox") == c

    def test_registrar_multiplas_versoes_mesmo_plugin(self, registry):
        c1 = _cap("email.send", "1.0.0", "cris-inbox")
        c2 = _cap("email.send", "2.0.0", "cris-inbox")
        registry.register(c1)
        registry.register(c2)
        caps = registry.find_by_name("email.send")
        assert len(caps) == 2

    def test_registrar_mesma_capability_plugins_diferentes(self, registry):
        c1 = _cap("email.send", "1.0.0", "cris-inbox")
        c2 = _cap("email.send", "1.0.0", "cris-marketing")
        registry.register(c1)
        registry.register(c2)  # não deve levantar exceção
        assert len(registry.find_by_name("email.send")) == 2

    def test_nao_registrar_se_removed(self, registry):
        c = _cap("email.send", "1.0.0", "cris-inbox",
                 status=CapabilityStatus.REMOVED)
        registry.register(c)
        assert len(registry.list_all()) == 0

    def test_unregister_por_plugin(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        registry.register(_cap("image.generate", "1.0.0", "cris-studio"))
        registry.unregister("email.send", "cris-inbox")
        assert registry.get("email.send", "cris-inbox") is None
        assert registry.get("image.generate", "cris-studio") is not None

    def test_unregister_plugin_completo(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        registry.register(_cap("email.read", "1.0.0", "cris-inbox"))
        registry.unregister_plugin("cris-inbox")
        assert len(registry.find_by_plugin("cris-inbox")) == 0
        assert "cris-inbox" not in registry.list_plugins()


# ======================================================================
# Resolução
# ======================================================================

class TestResolucao:
    def test_resolve_simples(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox", priority=80,
                               health=HealthStatus.OK))
        resolved = registry.resolve("email.send")
        assert resolved.capability.plugin_id == "cris-inbox"
        assert resolved.score > 0

    def test_resolve_inexistente_levanta_not_found(self, registry):
        with pytest.raises(CapabilityNotFoundError):
            registry.resolve("nao.existe")

    def test_resolve_com_constraint_exata(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        registry.register(_cap("email.send", "2.0.0", "cris-marketing"))
        resolved = registry.resolve("email.send", constraint="1.0.0")
        assert resolved.capability.plugin_id == "cris-inbox"

    def test_resolve_com_constraint_compativel(self, registry):
        registry.register(_cap("email.send", "1.5.0", "cris-inbox"))
        registry.register(_cap("email.send", "2.0.0", "cris-marketing"))
        resolved = registry.resolve("email.send", constraint="^1.0.0")
        assert resolved.capability.plugin_id == "cris-inbox"

    def test_resolve_prefere_maior_priority(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox", priority=50,
                               health=HealthStatus.OK))
        registry.register(_cap("email.send", "1.0.0", "cris-marketing", priority=90,
                               health=HealthStatus.OK))
        resolved = registry.resolve("email.send")
        assert resolved.capability.plugin_id == "cris-marketing"

    def test_resolve_prefere_melhor_health(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox", priority=80,
                               health=HealthStatus.DEGRADED))
        registry.register(_cap("email.send", "1.0.0", "cris-marketing", priority=60,
                               health=HealthStatus.OK))
        resolved = registry.resolve("email.send")
        # Score composite: health tem peso 0.35, priority 0.4
        # marketing: OK=1.0*0.35 + 0.6*0.4 = 0.35+0.24 = 0.59
        # inbox: DEGRADED=0.4*0.35 + 0.8*0.4 = 0.14+0.32 = 0.46
        assert resolved.capability.plugin_id == "cris-marketing"

    def test_resolve_pula_plugin_down(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox",
                               health=HealthStatus.DOWN))
        registry.register(_cap("email.send", "1.0.0", "cris-marketing",
                               health=HealthStatus.OK))
        resolved = registry.resolve("email.send")
        assert resolved.capability.plugin_id == "cris-marketing"

    def test_resolve_todos_down_levanta_unavailable(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox",
                               health=HealthStatus.DOWN))
        with pytest.raises(CapabilityUnavailableError):
            registry.resolve("email.send")

    def test_resolve_com_preferencia_plugin(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox", priority=80,
                               health=HealthStatus.OK))
        registry.register(_cap("email.send", "1.0.0", "cris-marketing", priority=60,
                               health=HealthStatus.OK))
        ctx = ResolveContext(caller_plugin_id="cris-crm", prefer_plugin_id="cris-marketing")
        resolved = registry.resolve("email.send", context=ctx)
        # prefer_plugin_id só é usado pelo Engine, Registry usa score
        assert resolved.capability.plugin_id == "cris-inbox"  # maior priority

    def test_resolve_retorna_ordenados(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox", priority=30,
                               health=HealthStatus.OK))
        registry.register(_cap("email.send", "1.0.0", "cris-marketing", priority=80,
                               health=HealthStatus.OK))
        all_r = registry.resolve_all("email.send")
        assert len(all_r) == 2
        assert all_r[0].capability.plugin_id == "cris-marketing"
        assert all_r[1].capability.plugin_id == "cris-inbox"

    def test_resolve_com_min_version(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        registry.register(_cap("email.send", "2.0.0", "cris-marketing"))
        ctx = ResolveContext(caller_plugin_id="cris-crm", min_version="2.0.0")
        resolved = registry.resolve("email.send", context=ctx)
        assert resolved.capability.plugin_id == "cris-marketing"


# ======================================================================
# Routing Rules
# ======================================================================

class TestRoutingRules:
    def test_routing_rule_match(self, registry):
        c = _cap("email.send", "1.0.0", "cris-inbox",
                 routing_rules={"environment": ["production"]})
        registry.register(c)
        ctx = ResolveContext(caller_plugin_id="cris-crm",
                             tags={"environment": "production"})
        resolved = registry.resolve("email.send", context=ctx)
        assert resolved.capability.plugin_id == "cris-inbox"

    def test_routing_rule_exclude(self, registry):
        c = _cap("email.send", "1.0.0", "cris-inbox",
                 routing_rules={"environment": ["production"]})
        registry.register(c)
        ctx = ResolveContext(caller_plugin_id="cris-crm",
                             tags={"environment": "staging"})
        resolved = registry.resolve_all("email.send", context=ctx)
        assert len(resolved) == 0


# ======================================================================
# Health
# ======================================================================

class TestHealth:
    def test_health_apos_5_sucessos_consecutivos(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        for _ in range(5):
            registry.record_success("email.send", "cris-inbox")
        assert registry.get_health("email.send", "cris-inbox") == HealthStatus.OK

    def test_health_apos_3_falhas_consecutivas(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox",
                               health=HealthStatus.OK))
        for _ in range(3):
            registry.record_failure("email.send", "cris-inbox")
        assert registry.get_health("email.send", "cris-inbox") == HealthStatus.DEGRADED

    def test_health_apos_5_falhas_consecutivas(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox",
                               health=HealthStatus.OK))
        for _ in range(5):
            registry.record_failure("email.send", "cris-inbox")
        assert registry.get_health("email.send", "cris-inbox") == HealthStatus.DOWN

    def test_health_recupera_apos_sucesso(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        for _ in range(5):
            registry.record_failure("email.send", "cris-inbox")
        assert registry.get_health("email.send", "cris-inbox") == HealthStatus.DOWN
        registry.record_success("email.send", "cris-inbox")
        assert registry.get_health("email.send", "cris-inbox") == HealthStatus.DEGRADED

    def test_update_health_manual(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        registry.update_health("email.send", "cris-inbox", HealthStatus.DOWN)
        assert registry.get_health("email.send", "cris-inbox") == HealthStatus.DOWN
        # update manual reseta rastreador — 1 sucesso sobe para DEGRADED
        registry.record_success("email.send", "cris-inbox")
        health = registry.get_health("email.send", "cris-inbox")
        assert health == HealthStatus.DEGRADED


# ======================================================================
# Métricas
# ======================================================================

class TestMetrics:
    def test_registra_metricas_de_chamada(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        registry.record_call("email.send", "cris-inbox", duration_ms=150, success=True)
        registry.record_call("email.send", "cris-inbox", duration_ms=200, success=True)
        m = registry.get_metrics("email.send", "cris-inbox")
        assert m.call_count == 2
        assert m.avg_duration_ms == 175.0

    def test_registra_metricas_com_erro(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        registry.record_call("email.send", "cris-inbox", duration_ms=100, success=True)
        registry.record_call("email.send", "cris-inbox", duration_ms=50, success=False)
        m = registry.get_metrics("email.send", "cris-inbox")
        assert m.call_count == 2
        assert m.error_count == 1
        assert m.error_rate == 0.5


# ======================================================================
# Consultas
# ======================================================================

class TestConsultas:
    def test_find_by_name(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        registry.register(_cap("email.send", "2.0.0", "cris-marketing"))
        caps = registry.find_by_name("email.send")
        assert len(caps) == 2

    def test_find_by_plugin(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        registry.register(_cap("email.read", "1.0.0", "cris-inbox"))
        registry.register(_cap("image.generate", "1.0.0", "cris-studio"))
        caps = registry.find_by_plugin("cris-inbox")
        assert len(caps) == 2
        assert {c.name for c in caps} == {"email.send", "email.read"}

    def test_find_by_domain(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        registry.register(_cap("email.read", "1.0.0", "cris-inbox"))
        registry.register(_cap("image.generate", "1.0.0", "cris-studio"))
        caps = registry.find_by_domain("email")
        assert len(caps) == 2

    def test_find_by_domain_prefix_exato(self, registry):
        registry.register(_cap("email", "1.0.0", "cris-inbox"))
        caps = registry.find_by_domain("email")
        assert len(caps) == 1

    def test_get(self, registry):
        c = _cap("email.send", "1.0.0", "cris-inbox")
        registry.register(c)
        assert registry.get("email.send", "cris-inbox") == c
        assert registry.get("email.send", "outro-plugin") is None

    def test_list_all(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        registry.register(_cap("image.generate", "1.0.0", "cris-studio"))
        assert len(registry.list_all()) == 2

    def test_list_plugins(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox"))
        registry.register(_cap("image.generate", "1.0.0", "cris-studio"))
        plugins = registry.list_plugins()
        assert "cris-inbox" in plugins
        assert "cris-studio" in plugins


# ======================================================================
# Cache
# ======================================================================

class TestCache:
    def test_cache_resolve(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox", priority=80,
                               health=HealthStatus.OK))
        r1 = registry.resolve("email.send")
        # Registrar outro provider — invalida cache
        registry.register(_cap("email.send", "2.0.0", "cris-marketing", priority=90,
                               health=HealthStatus.OK))
        # Cache foi invalidado pelo register, resolve novo provider
        r2 = registry.resolve("email.send")
        assert r2.capability.plugin_id == "cris-marketing"

    def test_cache_invalida_apos_register(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox", priority=80,
                               health=HealthStatus.OK))
        registry.resolve("email.send")
        # Registrar NOVO provider invalida cache
        registry.register(_cap("email.send", "2.0.0", "cris-marketing", priority=90,
                               health=HealthStatus.OK))
        r2 = registry.resolve("email.send")
        assert r2.capability.plugin_id == "cris-marketing"


# ======================================================================
# Stats
# ======================================================================

class TestStats:
    def test_stats_basicas(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox",
                               health=HealthStatus.OK))
        registry.register(_cap("email.read", "1.0.0", "cris-inbox",
                               health=HealthStatus.DEGRADED))
        registry.record_call("email.send", "cris-inbox", 100, True)
        registry.record_call("email.send", "cris-inbox", 200, True)
        registry.record_call("email.read", "cris-inbox", 50, False)
        stats = registry.get_stats()
        assert stats.total_capabilities == 2
        assert stats.total_plugins == 1
        assert stats.total_calls == 3
        assert stats.total_errors == 1


# ======================================================================
# Edge Cases
# ======================================================================

class TestEdgeCases:
    def test_resolve_sem_nenhum_provider(self, registry):
        with pytest.raises(CapabilityNotFoundError):
            registry.resolve("inexistente")

    def test_resolve_com_constraint_que_ninguem_atende(self, registry):
        registry.register(_cap("email.send", "2.0.0", "cris-inbox"))
        with pytest.raises(CapabilityNotFoundError):
            registry.resolve("email.send", constraint="^1.0.0")

    def test_multiplos_plugins_mesma_prioridade(self, registry):
        registry.register(_cap("email.send", "1.0.0", "cris-inbox", priority=50,
                               health=HealthStatus.OK))
        registry.register(_cap("email.send", "1.0.0", "cris-marketing", priority=50,
                               health=HealthStatus.OK))
        resolved = registry.resolve("email.send")
        # Ambos têm o mesmo score → o primeiro registrado vence (ou qualquer um)
        assert resolved.capability.plugin_id in ("cris-inbox", "cris-marketing")

    def test_unregister_plugin_inexistente(self, registry):
        registry.unregister_plugin("nao-existe")  # não deve levantar

    def test_unregister_capability_inexistente(self, registry):
        registry.unregister("nao.existe", "plugin")  # não deve levantar

    def test_registro_com_caracteres_especiais(self, registry):
        c = _cap("custom.apisi!@#", "1.0.0", "plugin-x")
        registry.register(c)
        assert registry.get("custom.apisi!@#", "plugin-x") == c


# ======================================================================
# Semver (testes diretos)
# ======================================================================

class TestSemver:
    def test_exata(self):
        from core.capability import semver_match
        assert semver_match("1.2.3", "1.2.3")
        assert not semver_match("1.2.4", "1.2.3")

    def test_compativel(self):
        from core.capability import semver_match
        assert semver_match("1.5.0", "^1.0.0")
        assert semver_match("1.9.9", "^1.0.0")
        assert not semver_match("2.0.0", "^1.0.0")

    def test_aproximado(self):
        from core.capability import semver_match
        assert semver_match("1.2.5", "~1.2.0")
        assert not semver_match("1.3.0", "~1.2.0")

    def test_maior_igual(self):
        from core.capability import semver_match
        assert semver_match("2.0.0", ">=1.0.0")
        assert semver_match("1.0.0", ">=1.0.0")
        assert not semver_match("0.9.0", ">=1.0.0")

    def test_menor_que(self):
        from core.capability import semver_match
        assert semver_match("1.0.0", "<2.0.0")
        assert not semver_match("2.0.0", "<2.0.0")

    def test_range(self):
        from core.capability import semver_match
        assert semver_match("1.5.0", ">=1.0.0 <2.0.0")
        assert not semver_match("2.0.0", ">=1.0.0 <2.0.0")

    def test_wildcard_x(self):
        from core.capability import semver_match
        assert semver_match("1.2.3", "1.x")
        assert semver_match("1.2.3", "1.2.x")
        assert not semver_match("2.0.0", "1.x")

    def test_apenas_major(self):
        from core.capability import semver_match
        assert semver_match("1.2.3", "1")
        assert not semver_match("2.0.0", "1")