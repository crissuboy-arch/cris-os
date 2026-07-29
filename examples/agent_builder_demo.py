"""
Demonstracao do CRIS Agent Builder.

Cria um agente, publica, executa via AgentRuntime com plugins reais,
desativa, duplica e remove — tudo sem alterar codigo do Core.

Uso:
    python examples/agent_builder_demo.py
"""

from __future__ import annotations

import sys, tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.agent import AgentRuntime
from core.capability import CapabilityRegistry
from core.events import InProcessEventBus, InMemoryEventLog
from core.plugins.loader import PluginLoader
from core.registry import AgentRegistry
from agent_builder import AgentBuilder, AgentStore, AgentStatus, CapabilityBinding


def setup():
    """Cria infraestrutura completa: registry, event bus, loader, runtime."""
    registry = CapabilityRegistry()
    event_log = InMemoryEventLog()
    event_bus = InProcessEventBus(event_log=event_log)

    loader = PluginLoader(registry=registry, event_bus=event_bus, plugins_dir=str(RAIZ / "plugins"))
    loaded = loader.load_all()
    loader.start_all()

    agent_reg = AgentRegistry()
    runtime = AgentRuntime(agent_registry=agent_reg, plugin_loader=loader, event_bus=event_bus)

    store = AgentStore(RAIZ / "agent_builder" / "agents")
    builder = AgentBuilder(store=store, agent_registry=agent_reg, runtime=runtime, plugin_loader=loader)

    print(f"Plugins disponiveis: {list(loaded.keys())}")
    caps = [c.name for c in registry.list_all()]
    print(f"Capabilities disponiveis: {caps}")
    return builder, agent_reg, runtime, store


def main():
    print("=" * 70)
    print("CRIS Agent Builder — Demonstracao")
    print("=" * 70)

    builder, agent_reg, runtime, store = setup()

    # =================================================================
    # 1. CRIAR agente
    # =================================================================
    print("\n[1] Criando agente...")
    agente = builder.create(
        "assistente-de-notas",
        "Agente que cria notas e responde a ecos",
        bindings=[
            CapabilityBinding(
                keyword="criar nota",
                capability="notes.create",
                input_template={"title": "Nota do Assistente", "content": "{instruction}"},
            ),
            CapabilityBinding(
                keyword="echo",
                capability="demo.echo",
                input_template={"message": "{instruction}"},
                priority=100,
            ),
        ],
    )
    print(f"    Criado: {agente.name} (id={agente.agent_id}, status={agente.status})")
    print(f"    Bindings: {[(b.keyword, b.capability) for b in agente.bindings]}")

    # =================================================================
    # 2. TESTAR antes de publicar
    # =================================================================
    print("\n[2] Testando agente antes de publicar...")
    r1 = builder.test(agente.agent_id, "echo testando 1 2 3")
    print(f"    Resultado: {r1.output}")

    # =================================================================
    # 3. PUBLICAR
    # =================================================================
    print("\n[3] Publicando agente...")
    publicado = builder.publish(agente.agent_id)
    print(f"    Status: {publicado.status}")
    print(f"    Versao: {publicado.version}")
    print(f"    Publicado em: {publicado.published_at}")
    registrado = agent_reg.get("assistente-de-notas")
    print(f"    Registrado no AgentRegistry: {registrado is not None}")

    # =================================================================
    # 4. EXECUTAR via AgentRuntime (agora registrado)
    # =================================================================
    print("\n[4] Executando via AgentRuntime...")
    r2 = runtime.execute("assistente-de-notas", "echo ola cris os")
    print(f"    echo: {r2.output}")

    r3 = runtime.execute("assistente-de-notas", "criar nota sobre reuniao de segunda")
    print(f"    criar nota: {r3.output}")

    # =================================================================
    # 5. LISTAR agentes
    # =================================================================
    print("\n[5] Listando agentes...")
    for a in builder.list():
        print(f"    - {a.name} (id={a.agent_id}, status={a.status})")

    # =================================================================
    # 6. DUPLICAR
    # =================================================================
    print("\n[6] Duplicando agente...")
    copia = builder.duplicate(agente.agent_id, "assistente-copia")
    print(f"    Copia: {copia.name} (id={copia.agent_id})")

    # =================================================================
    # 7. VERSIONAR (editar apos publicacao cria nova versao)
    # =================================================================
    print("\n[7] Editando agente publicado (cria nova versao)...")
    editado = builder.update(agente.agent_id, description="Nova versao com descricao atualizada")
    print(f"    Versao: {editado.version} (bumped de 1.0.0 para {editado.version})")
    print(f"    Status: {editado.status} (voltou para draft)")
    versoes = builder.list_versions(agente.agent_id)
    print(f"    Versoes no historico: {versoes}")

    # =================================================================
    # 8. DESATIVAR
    # =================================================================
    print("\n[8] Desativando agente...")
    desativado = builder.deactivate(agente.agent_id)
    print(f"    Status: {desativado.status}")
    print(f"    Ainda no AgentRegistry: {agent_reg.get('assistente-de-notas') is not None}")

    # =================================================================
    # 9. EXPORTAR / IMPORTAR
    # =================================================================
    print("\n[9] Exportando e importando agente...")
    with tempfile.TemporaryDirectory() as export_dir:
        exported = builder.export(agente.agent_id, export_dir)
        print(f"    Exportado para: {exported}")

        store2 = AgentStore(tempfile.mkdtemp())
        builder2 = AgentBuilder(store=store2, agent_registry=AgentRegistry())
        importado = builder2.import_agent(exported)
        print(f"    Importado: {importado.name} (id={importado.agent_id})")

    # =================================================================
    # 10. REMOVER
    # =================================================================
    print("\n[10] Removendo agente...")
    removido = builder.delete(agente.agent_id)
    print(f"    Removido: {removido}")
    print(f"    Existe no store: {store.exists(agente.agent_id)}")

    # Copia de teste
    builder.delete(copia.agent_id)

    print("\n" + "=" * 70)
    print("Demonstracao concluida!")
    print("Nenhuma alteracao no Core foi necessaria.")
    print("=" * 70)


if __name__ == "__main__":
    main()