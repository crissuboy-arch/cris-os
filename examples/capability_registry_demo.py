#!/usr/bin/env python3
"""
Exemplo funcional minimo — Capability Registry do CRIS OS.

Fluxo:
  1. Registrar provider cris-inbox com email.send
  2. Registrar provider alternativo cris-backup
  3. Resolver e usar o provider principal
  4. Simular falha do provider principal (5 falhas consecutivas)
  5. Confirmar fallback automatico para cris-backup
  6. Exibir metricas e health status
  7. Remover provider principal
  8. Confirmar que o registry atualizou corretamente
"""

from core.capability import (
    Capability,
    CapabilityNotFoundError,
    CapabilityRegistry,
    CapabilityUnavailableError,
    ConflictStrategy,
    HealthStatus,
)


def cabecalho(titulo: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {titulo}")
    print(f"{'='*60}")


def main() -> None:
    reg = CapabilityRegistry(conflict_strategy=ConflictStrategy.HIGHEST_PRIORITY)

    # ======================================================================
    # 1. Registrar provider principal
    # ======================================================================
    cabecalho("1. Registrando provider principal: cris-inbox")
    p1 = Capability(
        name="email.send",
        version="1.0.0",
        plugin_id="cris-inbox",
        priority=80,
        health=HealthStatus.OK,
        description="Envio de e-mail via SMTP (provider principal)",
    )
    reg.register(p1)
    print(f"  Registrado: {p1.name} v{p1.version} por {p1.plugin_id} (priority={p1.priority})")
    print(f"  Total no registry: {len(reg.list_all())} capabilities")

    # ======================================================================
    # 2. Registrar provider alternativo
    # ======================================================================
    cabecalho("2. Registrando provider alternativo: cris-backup")
    p2 = Capability(
        name="email.send",
        version="1.0.0",
        plugin_id="cris-backup",
        priority=30,
        health=HealthStatus.OK,
        description="Envio de e-mail via API alternativa (fallback)",
    )
    reg.register(p2)
    print(f"  Registrado: {p2.name} v{p2.version} por {p2.plugin_id} (priority={p2.priority})")
    print(f"  Total no registry: {len(reg.list_all())} capabilities")

    # ======================================================================
    # 3. Resolver e usar provider principal
    # ======================================================================
    cabecalho("3. Resolvendo email.send (deve escolher cris-inbox)")
    resolved = reg.resolve("email.send")
    print(f"  Provider escolhido: {resolved.capability.plugin_id}")
    print(f"  Score: {resolved.score:.4f}")
    assert resolved.capability.plugin_id == "cris-inbox", (
        f"Esperava cris-inbox, obteve {resolved.capability.plugin_id}"
    )
    print("  [OK] Resolucao correta: cris-inbox tem maior prioridade (80 > 30)")

    # ======================================================================
    # 4. Simular falha do provider principal
    # ======================================================================
    cabecalho("4. Simulando falhas em cris-inbox (5 chamadas com erro)")
    for i in range(5):
        reg.record_call("email.send", "cris-inbox", duration_ms=500, success=False)
        reg.record_failure("email.send", "cris-inbox")
        print(f"  Falha {i+1}/5 registrada")

    health = reg.get_health("email.send", "cris-inbox")
    print(f"\n  Health do cris-inbox: {health.value}")
    assert health == HealthStatus.DOWN, f"Esperava DOWN, obteve {health.value}"
    print("  [OK] Provider principal marcado como DOWN")

    # ======================================================================
    # 5. Fallback automatico
    # ======================================================================
    cabecalho("5. Fallback automatico para cris-backup")
    resolved = reg.resolve("email.send")
    print(f"  Provider escolhido: {resolved.capability.plugin_id}")
    print(f"  Score: {resolved.score:.4f}")
    assert resolved.capability.plugin_id == "cris-backup", (
        f"Esperava cris-backup, obteve {resolved.capability.plugin_id}"
    )
    print("  [OK] Fallback funcionou: cris-inbox esta DOWN, migrou para cris-backup")

    # ======================================================================
    # 6. Metricas e health status
    # ======================================================================
    cabecalho("6. Metricas e health status")
    reg.record_call("email.send", "cris-backup", duration_ms=120, success=True)
    reg.record_call("email.send", "cris-backup", duration_ms=200, success=True)
    reg.record_call("email.send", "cris-backup", duration_ms=80, success=True)

    metrics_p1 = reg.get_metrics("email.send", "cris-inbox")
    metrics_p2 = reg.get_metrics("email.send", "cris-backup")
    stats = reg.get_stats()

    print(f"  cris-inbox: {metrics_p1.call_count} chamadas, {metrics_p1.error_count} erros, "
          f"avg {metrics_p1.avg_duration_ms:.0f}ms")
    print(f"  cris-backup: {metrics_p2.call_count} chamadas, {metrics_p2.error_count} erros, "
          f"avg {metrics_p2.avg_duration_ms:.0f}ms")
    print(f"  Stats globais: {stats.total_capabilities} capabilities, "
          f"{stats.total_plugins} plugins, {stats.total_calls} chamadas, "
          f"{stats.total_errors} erros")
    print(f"  Status por health: {dict(stats.by_health)}")

    # ======================================================================
    # 7. Remover provider principal
    # ======================================================================
    cabecalho("7. Removendo provider cris-inbox")
    reg.unregister("email.send", "cris-inbox")
    removed = reg.get("email.send", "cris-inbox")
    print(f"  get('email.send', 'cris-inbox') = {removed}")
    assert removed is None, "Provider nao foi removido corretamente"
    print("  [OK] Provider principal removido com sucesso")

    # ======================================================================
    # 8. Confirmar consistencia
    # ======================================================================
    cabecalho("8. Verificando consistencia do registry")
    caps = reg.find_by_name("email.send")
    print(f"  Providers restantes para email.send: {len(caps)}")
    assert len(caps) == 1, f"Esperava 1, obteve {len(caps)}"
    assert caps[0].plugin_id == "cris-backup"
    print(f"  Provider: {caps[0].plugin_id} (v{caps[0].version})")

    plugins = reg.list_plugins()
    print(f"  Plugins ativos: {plugins}")
    assert "cris-inbox" not in plugins, "cris-inbox ainda esta na lista de plugins"
    assert "cris-backup" in plugins, "cris-backup deveria estar na lista"

    print(f"\n  Lista completa ({len(reg.list_all())} capabilities):")
    for cap in reg.list_all():
        print(f"    - {cap.name} v{cap.version} [{cap.plugin_id}] "
              f"priority={cap.priority} health={cap.health.value}")

    print(f"\n{'='*60}")
    print("  Exemplo executado com sucesso - Capability Registry OK")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()