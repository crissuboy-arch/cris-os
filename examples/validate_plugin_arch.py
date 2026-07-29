#!/usr/bin/env python3
"""
Script de VALIDACAO END-TO-END da arquitetura de plugins do CRIS OS.

Valida:
  - PluginLoader (descoberta, carregamento, capacidades, eventos)
  - CapabilityRegistry (registro, resolucao, metricas, health)
  - EventBus (publicacao, assinatura, eventos)
  - ConfigurationStore (configuracao por plugin)
  - PermissionChecker (permissoes para capabilities sensiveis)
  - CRIS Demo Plugin (isolation, fallback, ciclo de vida)
  - CRIS Inbox Plugin (6 capabilities, email.send, email.search)

Uso:
  python examples/validate_plugin_arch.py [--verbose]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.capability import CapabilityRegistry, CapabilityStatus, HealthStatus
from core.capability.errors import CapabilityPermissionError
from core.configuration import PluginConfigStore
from core.domain.events import Event
from core.events import InMemoryEventLog, InProcessEventBus
from core.permission import SimplePermissionChecker
from core.plugins import PluginLoader

# ---------------------------------------------------------------------------

VERBOSE = "--verbose" in sys.argv
PASS = 0
FAIL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        if VERBOSE:
            print(f"  [PASS] {label}")
    else:
        FAIL += 1
        msg = f"  [FAIL] {label}"
        if detail:
            msg += f" — {detail}"
        print(msg)


# =========================================================================
# Setup
# =========================================================================

print("=" * 60)
print("CRIS OS — Validacao Final da Arquitetura de Plugins")
print("=" * 60)

registry = CapabilityRegistry()
event_log = InMemoryEventLog()
event_bus = InProcessEventBus(event_log=event_log)
config_store = PluginConfigStore()
perm_checker = SimplePermissionChecker()

# Permite permissoes para plugins
perm_checker.allow("email.send", "cris-inbox")
perm_checker.allow("email.archive", "cris-inbox")
perm_checker.allow("notes.delete", "cris-notes")
perm_checker.allow_all("orchestrator")

loader = PluginLoader(
    registry=registry,
    event_bus=event_bus,
    plugins_dir=Path("plugins"),
    config_store=config_store,
    permission_checker=perm_checker,
)

# =========================================================================
# 1. Descoberta e Carregamento
# =========================================================================

print("\n[1/12] Descoberta e Carregamento")

plugins = loader.load_all()

# Demo plugin
check("Plugin 'cris-demo' foi encontrado", "cris-demo" in plugins)
check("DemoPlugin classe correta", plugins["cris-demo"].__class__.__name__ == "DemoPlugin")
check("DemoPlugin estado INSTALLED", plugins["cris-demo"].state.value == "installed")

# CRIS Inbox plugin
check("Plugin 'cris-inbox' foi encontrado", "cris-inbox" in plugins)
inbox = plugins["cris-inbox"]
check("CrisInboxPlugin classe correta", inbox.__class__.__name__ == "CrisInboxPlugin")
check("CrisInboxPlugin estado INSTALLED", inbox.state.value == "installed")

# CRIS Notes plugin
check("Plugin 'cris-notes' foi encontrado", "cris-notes" in plugins)
notes = plugins["cris-notes"]
check("CrisNotesPlugin classe correta", notes.__class__.__name__ == "CrisNotesPlugin")
check("CrisNotesPlugin estado INSTALLED", notes.state.value == "installed")

# =========================================================================
# 2. Capabilities Registradas (3 plugins = 17)
# =========================================================================

print("\n[2/12] Registro de Capabilities")

demo_caps = {"demo.hello", "demo.health", "demo.echo", "demo.fallback", "demo.isolation"}
inbox_caps = {"email.read", "email.search", "email.send", "email.archive", "email.health", "email.metrics"}
notes_caps = {"notes.create", "notes.read", "notes.search", "notes.delete", "notes.health", "notes.metrics"}
all_expected = demo_caps | inbox_caps | notes_caps
registered = {c.name for c in registry.list_all()}
check("Todas as 17 capabilities registradas", registered == all_expected)

for cap_name in inbox_caps | notes_caps:
    resolved = registry.resolve(cap_name)
    check(f"{cap_name} resolvida no registry", resolved is not None)
    check(f"{cap_name} esta ACTIVE", resolved.capability.status == CapabilityStatus.ACTIVE)

# =========================================================================
# 3. ConfigurationStore
# =========================================================================

print("\n[3/12] ConfigurationStore")

config_store.set("cris-inbox", "email_provider", "simulado")
config_store.set("cris-inbox", "polling_interval_sec", "30")

check("get_config email_provider = simulado", inbox.api.get_config("email_provider", "") == "simulado")
check("get_config polling = 30", inbox.api.get_config("polling_interval_sec") == "30")

all_config = inbox.api.get_all_config()
check("get_all_config retorna 2 keys", len(all_config) >= 2)
check("get_all_config contem email_provider", all_config.get("email_provider") == "simulado")

inbox.api.set_config("max_results", "50")
check("set_config + get_config max_results = 50", inbox.api.get_config("max_results") == "50")

inbox.api.delete_config("max_results")
check("delete_config removeu max_results", inbox.api.get_config("max_results") == "")

# Nao interfere com outro plugin
check("demo plugin nao ve config do inbox", plugins["cris-demo"].api.get_config("email_provider") == "")

# =========================================================================
# 4. PermissionChecker
# =========================================================================

print("\n[4/12] PermissionChecker")

# email.read e READ_ONLY (nao contem padrao sensivel)
check("email.read permitido para qualquer um", perm_checker.check("unknown-plugin", "email.read"))

# email.send e SENSITIVE (contem "send")
check("cris-inbox autorizado para email.send", perm_checker.check("cris-inbox", "email.send"))
check("unknown-plugin BLOQUEADO para email.send", not perm_checker.check("unknown-plugin", "email.send"))

# email.archive e SENSITIVE (contem "archive")
check("cris-inbox autorizado para email.archive", perm_checker.check("cris-inbox", "email.archive"))

# orchestrator tem permissao curinga
check("orchestrator permitido para email.send (allow_all)", perm_checker.check("orchestrator", "email.send"))

# require levanta excecao
try:
    perm_checker.require("unknown-plugin", "email.send")
    check("require nao levantou excecao", False, "Deveria ter levantado CapabilityPermissionError")
except CapabilityPermissionError:
    check("require levantou CapabilityPermissionError", True)

# notes.delete e SENSITIVE (contem "delete")
check("notes.delete BLOQUEADO sem permissao", not perm_checker.check("unknown", "notes.delete"))
check("cris-notes autorizado para notes.delete", perm_checker.check("cris-notes", "notes.delete"))
check("notes.create contem 'create' (SENSITIVE)", not perm_checker.check("anyone", "notes.create"))

# =========================================================================
# 5. CRIS Inbox — email.search e email.send
# =========================================================================

print("\n[5/12] CRIS Inbox — email.search() e email.send()")

# --- email.search ---
r_search = inbox.execute("email.search", {"query": "orcamento"})
check("email.search executou com sucesso", r_search["success"])
check("email.search encontrou 1 resultado", r_search["total"] == 1)
check("email.search retornou resultado", len(r_search["results"]) == 1)
check("Resultado e o orcamento", r_search["results"][0]["id"] == "msg-001")

# search sem resultados
r_empty = inbox.execute("email.search", {"query": "inexistente"})
check("email.search query sem resultados retorna 0", r_empty["total"] == 0)

# --- email.send (com permissao) ---
r_send = inbox.execute("email.send", {"to": "cris@crisos.com", "subject": "Teste", "body": "Mensagem de teste"})
check("email.send executou com sucesso", r_send["success"])
check("email.send retornou message_id", r_send.get("message_id", "").startswith("msg-out-"))
check("email.send retornou status sent", r_send["status"] == "sent")

# --- email.read ---
r_read = inbox.execute("email.read", {"message_id": "msg-001"})
check("email.read encontrou msg-001", r_read["success"])
check("email.read retornou subject correto", r_read.get("subject") == "Orcamento")

r_read_miss = inbox.execute("email.read", {"message_id": "nao-existe"})
check("email.read msg inexistente retorna erro", not r_read_miss["success"])

# --- email.archive (com permissao) ---
r_arch = inbox.execute("email.archive", {"message_id": "msg-001"})
check("email.archive executou com sucesso", r_arch["success"])
check("email.archive retornou status archived", r_arch["status"] == "archived")

# =========================================================================
# 6. Permission no plugin (email.send negado)
# =========================================================================

print("\n[6/12] Isolamento de Permissao no Plugin")

# Simula um plugin SEM permissao chamando email.send
# O CrisInboxPlugin vai chamar api.require_permission("email.send") internamente
# Como estamos chamando via inbox.execute(), vai checar o caller correto

# Teste: se um plugin sem permissao tentar chamar email.send, o checker nega
check("perm_checker nega unknown-plugin para email.send",
      not perm_checker.check("unknown-plugin", "email.send"))

# =========================================================================
# 7. Eventos (demo ping/pong + inbox email events)
# =========================================================================

print("\n[7/12] Eventos")

# --- Ping/Pong ---
received_pong: list[Event] = []
def on_pong(event):
    received_pong.append(event)

event_bus.subscribe("demo.pong", on_pong)
event_bus.publish(Event(type="demo.ping", payload={"from": "validator"}, source="validator"))
time.sleep(0.02)
check("Ping gerou Pong (evento)", len(received_pong) == 1)
check("Pong contem ping_count == 1", received_pong[0].payload.get("ping_count") == 1)

# --- Inbox: email.send publicado evento email.sent ---
received_sent: list[Event] = []
def on_sent(event):
    received_sent.append(event)

event_bus.subscribe("email.sent", on_sent)
inbox.execute("email.send", {"to": "cris@crisos.com", "subject": "Evento", "body": "Teste de evento"})
time.sleep(0.02)
check("email.send publicou evento email.sent", len(received_sent) >= 1)
check("Evento email.sent contem subject", received_sent[0].payload.get("subject") == "Evento")

# --- Inbox: evento email.send.requested → resposta ---
received_completed: list[Event] = []
def on_completed(event):
    received_completed.append(event)

event_bus.subscribe("email.send.completed", on_completed)
event_bus.publish(Event(type="email.send.requested", payload={
    "to": "destino@teste.com", "subject": "Via evento", "body": "Enviado por evento"
}, source="validator"))
time.sleep(0.02)
check("Evento email.send.requested gerou email.send.completed", len(received_completed) >= 1)

# --- Inbox: evento email.sync.triggered nao quebra ---
event_bus.publish(Event(type="email.sync.triggered", payload={}, source="validator"))

# =========================================================================
# 8. CRIS Notes — dominio totalmente diferente
# =========================================================================

print("\n[8/12] CRIS Notes — notes.create, notes.search, notes.delete")

# --- notes.create ---
r_nc = notes.execute("notes.create", {"title": "Ideia", "content": "Conteudo da nota", "tags": ["pessoal", "ideias"]})
check("notes.create executou com sucesso", r_nc["success"])
check("notes.create retornou id", len(r_nc.get("id", "")) > 0)
note_id_1 = r_nc["id"]
check("notes.create retornou titulo", r_nc["title"] == "Ideia")

r_nc2 = notes.execute("notes.create", {"title": "Compras", "content": "Leite, pao, ovos"})
check("Segunda nota criada", r_nc2["success"])
note_id_2 = r_nc2["id"]

# --- notes.read ---
r_nr = notes.execute("notes.read", {"note_id": note_id_1})
check("notes.read encontrou nota", r_nr["success"])
check("notes.read retornou conteudo", r_nr["content"] == "Conteudo da nota")
check("notes.read retornou tags", r_nr["tags"] == ["pessoal", "ideias"])

r_nr_miss = notes.execute("notes.read", {"note_id": "fake-id"})
check("notes.read id inexistente retorna erro", not r_nr_miss["success"])

# --- notes.search ---
r_ns = notes.execute("notes.search", {"query": "Ideia"})
check("notes.search encontrou 1", r_ns["success"] and r_ns["total"] == 1)

r_ns2 = notes.execute("notes.search", {"query": "Leite"})
check("notes.search encontrou 'Compras' por conteudo", r_ns2["success"] and r_ns2["total"] == 1)

r_ns3 = notes.execute("notes.search", {"query": "pessoal"})
check("notes.search encontrou por tag", r_ns3["success"] and r_ns3["total"] == 1)

r_ns4 = notes.execute("notes.search", {"query": "inexistente"})
check("notes.search sem resultados", r_ns4["success"] and r_ns4["total"] == 0)

# --- notes.delete ---
r_nd = notes.execute("notes.delete", {"note_id": note_id_2})
check("notes.delete executou", r_nd["success"] and r_nd["status"] == "deleted")

r_nd2 = notes.execute("notes.delete", {"note_id": note_id_2})
check("notes.delete nota ja removida", not r_nd2["success"])

# --- notes.delete sem permissao ---
# O checker nega (mas o plugin usa require_permission internamente)
check("notes.delete requer permissao (SimplePermissionChecker)",
      not perm_checker.check("no-permission", "notes.delete"))

# --- Eventos do Notes (notes.created / notes.deleted) ---
received_note_created: list[Event] = []
received_note_deleted: list[Event] = []
def on_note_created(e): received_note_created.append(e)
def on_note_deleted(e): received_note_deleted.append(e)

event_bus.subscribe("notes.created", on_note_created)
event_bus.subscribe("notes.deleted", on_note_deleted)

notes.execute("notes.create", {"title": "Nota-Evento", "content": "Teste"})
notes.execute("notes.delete", {"note_id": note_id_1})
time.sleep(0.02)
check("notes.create publicou evento notes.created", len(received_note_created) >= 1)
check("notes.delete publicou evento notes.deleted", len(received_note_deleted) >= 1)
check("Evento notes.created com titulo", received_note_created[-1].payload.get("title") == "Nota-Evento")

# --- Evento notes.sync.requested ---
received_sync: list[Event] = []
def on_sync(e): received_sync.append(e)
event_bus.subscribe("notes.sync.completed", on_sync)
event_bus.publish(Event(type="notes.sync.requested", payload={}, source="validator"))
time.sleep(0.02)
check("Evento notes.sync.requested gerou notes.sync.completed", len(received_sync) >= 1)
check("Sync completado com total_notes", received_sync[0].payload.get("total_notes") is not None)

# --- Configuracao do Notes ---
check("notes usa config (max_notes default)", notes.api.get_config("max_notes", "1000") == "1000")
notes.api.set_config("max_notes", "500")
check("notes config alterada", notes.api.get_config("max_notes") == "500")
notes.api.delete_config("max_notes")

# =========================================================================
# 9. Ciclo de Vida (start → stop)
# =========================================================================

print("\n[9/12] Ciclo de Vida")

loader.start_all()
check("cris-demo mudou para ACTIVE", plugins["cris-demo"].state.value == "active")
check("cris-inbox mudou para ACTIVE", inbox.state.value == "active")
check("cris-notes mudou para ACTIVE", notes.state.value == "active")

loader.stop_all()
check("cris-demo mudou para STOPPED", plugins["cris-demo"].state.value == "stopped")
check("cris-inbox mudou para STOPPED", inbox.state.value == "stopped")
check("cris-notes mudou para STOPPED", notes.state.value == "stopped")

# =========================================================================
# 10. Health e Metricas
# =========================================================================

print("\n[10/12] Health e Metricas")

r_health = inbox.execute("email.health", {})
check("email.health executou", r_health["success"])
check("email.health provider simulado", r_health["provider"] == "simulado")
check("email.health uptime >= 0", r_health["uptime_ms"] >= 0)

r_metrics = inbox.execute("email.metrics", {})
check("email.metrics executou", r_metrics["success"])
check("email.metrics total_sent >= 2", r_metrics["total_sent"] >= 2)
check("email.metrics total_searched >= 1", r_metrics["total_searched"] >= 1)
check("email.metrics total_read >= 1", r_metrics["total_read"] >= 1)
check("email.metrics total_archived >= 1", r_metrics["total_archived"] >= 1)

# Metricas via CoreAPI
metrics = inbox.api.get_metrics("email.send")
check("Metricas de email.send existem", metrics is not None)
check("email.send chamado pelo menos 2x", metrics.call_count >= 2)

health = inbox.api.get_health("email.send")
check("Health de email.send e OK", health == HealthStatus.OK)

# Health e Metricas do Notes
r_nh = notes.execute("notes.health", {})
check("notes.health executou", r_nh["success"])
check("notes.health tem status", r_nh.get("status") is not None)
check("notes.health retorna total_notes", r_nh.get("total_notes", -1) >= 0)

r_nm = notes.execute("notes.metrics", {})
check("notes.metrics executou", r_nm["success"])
check("notes.metrics total_created >= 3", r_nm["total_created"] >= 3)
check("notes.metrics total_deleted >= 1", r_nm["total_deleted"] >= 1)
check("notes.metrics active_notes >= 1", r_nm["active_notes"] >= 1)

# Metricas via CoreAPI para notas
notes_metrics = notes.api.get_metrics("notes.create")
check("Metricas de notes.create existem", notes_metrics is not None)
check("notes.create chamado pelo menos 3x", notes_metrics.call_count >= 3)

# =========================================================================
# 11. Demo plugin ainda funciona (nada quebrou)
# =========================================================================

print("\n[11/12] Demo Plugin — Regressao")

demo = plugins["cris-demo"]

r = demo.execute("demo.hello", {"name": "Final"})
check("demo.hello ainda funciona", r["success"] and "Final" in r["greeting"])

try:
    demo.execute("demo.isolation", {"trigger": "final-test"})
    check("demo.isolation ainda lanca excecao", False, "Excecao nao foi lancada")
except RuntimeError:
    check("demo.isolation ainda isola excecao", True)

# =========================================================================
# Relatorio final
# =========================================================================

print("\n" + "=" * 60)
print(f"RESULTADO: {PASS} passaram, {FAIL} falharam de {PASS + FAIL} testes")
print("=" * 60)

if FAIL > 0:
    print("\nALGUMAS VALIDACOES FALHARAM.")
    sys.exit(1)
else:
    print("Arquitetura de plugins VALIDADA com sucesso.")
    print("Plugin CRIS Inbox operacional sobre ConfigurationStore + PermissionChecker + EventBus + CapabilityRegistry.")
    sys.exit(0)