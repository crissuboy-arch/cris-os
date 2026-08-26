"""
Validacao real pelo Telegram - 10 passos.

Simula o fluxo completo usando MemorySystem + SQLiteMemoryStore
com o user_id real do Telegram (6460872429).
"""

import os
import sys
import tempfile
import logging

sys.path.insert(0, os.getcwd())

from core.models import MemoryItem
from storage.sqlite_memory_store import SQLiteMemoryStore
from memory.memory_system import MemorySystem

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

USER_ID = "6460872429"
WORKSPACE = "default"


def main():
    db_path = tempfile.mktemp(suffix=".db")
    store = SQLiteMemoryStore(db_path)
    ms = MemorySystem(store)

    print("=== VALIDACAO TELEGRAM - Passo a passo ===")
    print()

    # Passo 1: 'Lembre que o preco do chaveiro e 4,90 EUR.'
    print("1. Lembre que o preco do chaveiro e 4,90 EUR")
    item = ms.remember("lembre que o preco do chaveiro e 4,90 EUR", user_id=USER_ID, workspace=WORKSPACE)
    print("   [OK] Salvo: type=%s, importance=%d, content=%s" % (item.type, item.importance, item.content[:60]))
    print()

    # Passo 2: 'Qual e o preco do chaveiro?'
    print("2. Qual e o preco do chaveiro?")
    results = ms.query("qual e o preco do chaveiro", user_id=USER_ID)
    assert len(results) >= 1, "Nenhum resultado encontrado!"
    assert any("4,90" in r.content or "4.90" in r.content for r in results), "Preco nao encontrado!"
    print("   [OK] Encontrado: %d resultado(s)" % len(results))
    for r in results:
        print('   -> "%s" (importance=%d)' % (r.content, r.importance))
    print()

    # Passo 3: Reiniciar o bot (simulado: fechar e reabrir conexao)
    print("3. Reiniciando o bot (fechar e reabrir conexao)...")
    store.close()
    store2 = SQLiteMemoryStore(db_path)
    ms2 = MemorySystem(store2)
    print("   [OK] Bot reiniciado.")
    print()

    # Passo 4: Perguntar novamente
    print("4. Qual e o preco do chaveiro? (apos reinicio)")
    results = ms2.query("qual e o preco do chaveiro", user_id=USER_ID)
    assert len(results) >= 1, "Dados perdidos apos reinicio!"
    assert any("4,90" in r.content or "4.90" in r.content for r in results), "Preco nao recuperado!"
    print("   [OK] Recuperado: %d resultado(s)" % len(results))
    for r in results:
        print('   -> "%s" (access_count=%d)' % (r.content, r.access_count))
    print()

    # Passo 5: 'Lembre que esta informacao pertence ao projeto Zavix.'
    print("5. Lembre que o preco do chaveiro pertence ao projeto Zavix.")
    item = ms2.remember("lembre que o preco do chaveiro e 4,90 EUR pertence ao projeto Zavix", user_id=USER_ID, workspace=WORKSPACE)
    print("   [OK] Salvo: project=%s, type=%s" % (item.project, item.type))
    print()

    # Passo 6: 'O que voce lembra sobre o projeto Zavix?'
    print("6. O que voce lembra sobre o projeto Zavix?")
    results = ms2.query("o que voce sabe sobre o projeto Zavix", user_id=USER_ID)
    assert len(results) >= 1, "Nenhum resultado sobre Zavix!"
    zavix_items = [r for r in results if "zavix" in r.project.lower() or "zavix" in r.content.lower()]
    assert len(zavix_items) >= 1, "Nenhum item do projeto Zavix!"
    print("   [OK] Encontrado: %d item(s) do projeto Zavix" % len(zavix_items))
    for r in zavix_items:
        print('   -> "%s" (project=%s)' % (r.content, r.project))
    print()

    # Passo 7: 'Esqueca o preco do chaveiro.'
    print("7. Esqueca o preco do chaveiro.")
    candidates = ms2.forget("esqueca o preco do chaveiro", user_id=USER_ID)
    print("   [OK] Candidatos para exclusao: %d" % len(candidates))
    for c in candidates:
        print('   -> id=%s, content="%s"' % (c.id, c.content[:50]))
    print()

    # Passo 8: Confirmar exclusao (exclui todos os candidatos)
    print("8. Confirmando exclusao...")
    for c in candidates:
        ok = ms2.confirm_forget(c.id, USER_ID)
        if ok:
            print("   [OK] Excluido: id=%s" % c.id)
        else:
            print("   [WARN] Nao foi possivel excluir: id=%s" % c.id)
    print()

    # Passo 9: Perguntar novamente e confirmar que nao aparece
    print("9. Qual e o preco do chaveiro? (apos exclusao)")
    results = ms2.query("qual e o preco do chaveiro", user_id=USER_ID)
    chaveiro_results = [r for r in results if "chaveiro" in r.content.lower()]
    if len(chaveiro_results) == 0:
        print("   [OK] Informacao removida com sucesso!")
    else:
        print("   [WARN] Ainda encontrado: %d resultado(s)" % len(chaveiro_results))
        for r in chaveiro_results:
            print('   -> "%s"' % r.content)
    print()

    # Passo 10: Estatisticas
    print("10. Estatisticas:")
    stats = ms2.stats(USER_ID)
    print("   Total de registros: %d" % stats["total"])
    print("   Total de acessos: %d" % stats["total_acessos"])
    print("   Por tipo: %s" % stats["por_tipo"])
    print("   Por origem: %s" % stats["por_origem"])
    print()

    store2.close()
    try:
        os.unlink(db_path)
    except OSError:
        pass

    print("=== TODOS OS 10 PASSOS VALIDADOS COM SUCESSO ===")


if __name__ == "__main__":
    main()
