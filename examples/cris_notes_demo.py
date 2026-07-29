#!/usr/bin/env python3
"""
Exemplo executavel do CRIS Notes.

Uso:
  python examples/cris_notes_demo.py

Demonstra:
  1. Inicializacao do Core (CapabilityRegistry, EventBus, etc.)
  2. Carregamento do plugin CRIS Notes via PluginLoader
  3. Criacao, leitura, busca e remocao de notas
  4. Health e metricas
  5. Eventos (notes.created, notes.deleted)
  6. Permissoes (notes.delete)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.capability import CapabilityRegistry
from core.configuration import PluginConfigStore
from core.domain.events import Event
from core.events import InMemoryEventLog, InProcessEventBus
from core.permission import SimplePermissionChecker
from core.plugins import PluginLoader


def demo():
    # ------------------------------------------------------------------
    # 1. Setup do Core
    # ------------------------------------------------------------------
    print("=" * 60)
    print("CRIS Notes — Plugin de Notas Pessoais")
    print("=" * 60)

    registry = CapabilityRegistry()
    event_bus = InProcessEventBus(InMemoryEventLog())
    config = PluginConfigStore()
    perm = SimplePermissionChecker()
    perm.allow("notes.delete", "cris-notes")
    perm.allow("notes.create", "cris-notes")

    loader = PluginLoader(
        registry=registry,
        event_bus=event_bus,
        plugins_dir=Path("plugins"),
        config_store=config,
        permission_checker=perm,
    )

    plugins = loader.load_all()
    notes = plugins.get("cris-notes")
    if not notes:
        print("ERRO: Plugin cris-notes nao encontrado.")
        sys.exit(1)

    print(f"\nPlugin carregado: {notes.name} v{notes.version}")
    print(f"Capabilities registradas: {len(notes.manifest.capabilities)}")
    print()

    # ------------------------------------------------------------------
    # 2. Criar notas
    # ------------------------------------------------------------------
    print("--- Criando notas ---")

    r1 = notes.execute("notes.create", {
        "title": "Ideia de projeto",
        "content": "Criar um sistema de notas pessoais integrado ao CRIS OS",
        "tags": ["projeto", "ideias"],
    })
    print(f"  Criada: {r1['title']} (id: {r1['id']})")

    r2 = notes.execute("notes.create", {
        "title": "Lista de compras",
        "content": "Leite, pao, ovos, cafe, acucar",
        "tags": ["pessoal", "compras"],
    })
    print(f"  Criada: {r2['title']} (id: {r2['id']})")

    r3 = notes.execute("notes.create", {
        "title": "Reuniao equipe",
        "content": "Pauta: revisao do sprint, novos requisitos, prazos",
        "tags": ["trabalho", "reuniao"],
    })
    print(f"  Criada: {r3['title']} (id: {r3['id']})")

    print()

    # ------------------------------------------------------------------
    # 3. Ler nota
    # ------------------------------------------------------------------
    print("--- Lendo nota ---")
    read = notes.execute("notes.read", {"note_id": r1["id"]})
    if read["success"]:
        print(f"  ID: {read['id']}")
        print(f"  Titulo: {read['title']}")
        print(f"  Conteudo: {read['content']}")
        print(f"  Tags: {', '.join(read['tags'])}")
    print()

    # ------------------------------------------------------------------
    # 4. Buscar notas
    # ------------------------------------------------------------------
    print("--- Buscando notas ---")

    search = notes.execute("notes.search", {"query": "projeto"})
    print(f"  Busca 'projeto': {search['total']} resultado(s)")
    for s in search["results"]:
        print(f"    - {s['title']}")

    search2 = notes.execute("notes.search", {"query": "compras"})
    print(f"  Busca 'compras': {search2['total']} resultado(s)")
    for s in search2["results"]:
        print(f"    - {s['title']}")

    search3 = notes.execute("notes.search", {"query": "cafe"})
    print(f"  Busca 'cafe' (conteudo): {search3['total']} resultado(s)")

    print()

    # ------------------------------------------------------------------
    # 5. Deletar nota
    # ------------------------------------------------------------------
    print("--- Removendo nota ---")
    delete = notes.execute("notes.delete", {"note_id": r2["id"]})
    print(f"  Status: {delete['status']} (id: {delete['note_id']})")

    # Confirma que foi removida
    confirm = notes.execute("notes.read", {"note_id": r2["id"]})
    print(f"  Ainda existe? {'Sim' if confirm['success'] else 'Nao (removida)'}")
    print()

    # ------------------------------------------------------------------
    # 6. Eventos
    # ------------------------------------------------------------------
    print("--- Eventos ---")

    received = []
    def on_notes_created(e):
        received.append(("created", e.payload["title"]))
    def on_notes_deleted(e):
        received.append(("deleted", e.payload["title"]))

    event_bus.subscribe("notes.created", on_notes_created)
    event_bus.subscribe("notes.deleted", on_notes_deleted)

    notes.execute("notes.create", {"title": "Nota com evento", "content": "Teste"})
    print("  Evento notes.created disparado")

    # Evento externo: sync.requested -> sync.completed
    sync_received = []
    def on_sync(e):
        sync_received.append(e)
    event_bus.subscribe("notes.sync.completed", on_sync)
    event_bus.publish(Event(type="notes.sync.requested", payload={}, source="demo"))
    time.sleep(0.02)
    print(f"  Evento notes.sync.requested -> completed: total_notes={sync_received[0].payload.get('total_notes')}")

    print()

    # ------------------------------------------------------------------
    # 7. Health e Metricas
    # ------------------------------------------------------------------
    print("--- Health e Metricas ---")

    health = notes.execute("notes.health", {})
    print(f"  Status: {health['status']}")
    print(f"  Notas ativas: {health['total_notes']}")
    print(f"  Uptime: {health['uptime_ms']}ms")

    metrics = notes.execute("notes.metrics", {})
    print(f"  Criadas: {metrics['total_created']}")
    print(f"  Lidas: {metrics['total_read']}")
    print(f"  Buscas: {metrics['total_searched']}")
    print(f"  Removidas: {metrics['total_deleted']}")
    print(f"  Ativas: {metrics['active_notes']}")

    print()
    print("=" * 60)
    print("CRIS Notes operacional. Nenhuma alteracao no Core foi necessaria.")
    print("=" * 60)


if __name__ == "__main__":
    demo()