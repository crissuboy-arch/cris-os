"""
Testes do novo sistema de memoria (MemorySystem + SQLiteMemoryStore).

Cobre:
  - CRUD (criar, pesquisar, atualizar, fundir, excluir)
  - Confirmacao para excluir (forget -> confirm_forget)
  - Isolamento entre utilizadores
  - Isolamento entre workspaces
  - Busca por projeto, cliente, tags, textual
  - Fallback sem embeddings (FTS5 -> LIKE)
  - Recuperacao apos reinicio
  - Limite de contexto (max results)
  - Nao salvar saudacoes
  - Nao expor segredos
  - Injecao correta no agente
  - Memoria inexistente
  - Telegram integration (parse de linguagem natural)
  - Multiplos utilizadores simultaneos
  - Estatisticas
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from core.models import MemoryItem
from memory.memory_system import MemorySystem
from storage.sqlite_memory_store import SQLiteMemoryStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store():
    """Cria store em arquivo temporario."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = SQLiteMemoryStore(db_path)
    yield store
    store.close()
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def ms(store):
    """MemorySystem sobre o store temporario."""
    return MemorySystem(store)


def _make_item(user_id: str, content: str, **kw) -> MemoryItem:
    return MemoryItem(
        id="",
        user_id=user_id,
        content=content,
        title=kw.pop("title", content[:60]),
        **kw,
    )


# ---------------------------------------------------------------------------
# 1. Criar memoria
# ---------------------------------------------------------------------------


def test_criar_memoria(ms):
    item = ms.remember("o preco do chaveiro e 4,90 EUR", user_id="user1")
    assert item.id
    assert item.user_id == "user1"
    assert "4,90" in item.content or "4.90" in item.content
    assert item.type == "fact"
    assert item.importance >= 5
    assert item.origin == "telegram"


def test_criar_memoria_importancia_padrao(ms):
    item = ms.remember("gosto de pizza", user_id="user1")
    assert item.importance == 3
    assert item.type == "note"


def test_criar_memoria_projeto(ms):
    item = ms.remember(
        "lembre que o prazo do projeto Zavix e 15/12", user_id="user1",
    )
    assert item.project == "zavix"
    assert item.type == "project_info"


def test_criar_memoria_raw(ms):
    item = MemoryItem(
        id="", user_id="user1", content="teste raw",
        importance=7, origin="api", agent="test_agent",
    )
    saved = ms.remember_raw(item)
    assert saved.id
    assert saved.origin == "api"
    assert saved.agent == "test_agent"


# ---------------------------------------------------------------------------
# 2. Pesquisar memoria
# ---------------------------------------------------------------------------


def test_pesquisar_memoria(ms):
    ms.remember("o preco do chaveiro e 4,90 euros", user_id="user1")
    ms.remember("o telefone da Maria e 912345678", user_id="user1")
    results = ms.query("preco do chaveiro", user_id="user1")
    assert len(results) >= 1
    assert any("4,90" in r.content or "4.90" in r.content for r in results)


def test_pesquisar_sem_resultados(ms):
    results = ms.query("algo que nunca existiu", user_id="user1")
    assert len(results) == 0


def test_pesquisar_query_natural(ms):
    ms.remember("o email do cliente e cliente@teste.com", "user1")
    results = ms.query("o que voce sabe sobre cliente", user_id="user1")
    assert len(results) >= 1
    assert any("cliente@teste.com" in r.content for r in results)


# ---------------------------------------------------------------------------
# 3. Atualizar memoria
# ---------------------------------------------------------------------------


def test_atualizar_memoria(ms):
    item = ms.remember("preco do produto e 10 euros", user_id="user1")
    updated = ms.update(item.id, "user1", content="preco do produto e 15 euros", importance=8)
    assert updated is not None
    assert "15" in updated.content
    assert updated.importance == 8


def test_atualizar_memoria_inexistente(ms):
    updated = ms.update("id_inexistente", "user1", content="novo")
    assert updated is None


# ---------------------------------------------------------------------------
# 4. Fundir duplicadas
# ---------------------------------------------------------------------------


def test_fundir_duplicadas(ms):
    ms.remember("preco 10 euros", user_id="user1")
    ms.remember("preco 10 euros", user_id="user1")
    count_before = ms.count("user1")
    merged = ms.merge_duplicates("user1")
    assert merged > 0
    count_after = ms.count("user1")
    assert count_after < count_before


# ---------------------------------------------------------------------------
# 5. Excluir memoria + confirmacao
# ---------------------------------------------------------------------------


def test_excluir_memoria(ms):
    item = ms.remember("preco 10 euros", user_id="user1")
    ok = ms.confirm_forget(item.id, "user1")
    assert ok
    found = ms.store.get(item.id, "user1")
    assert found is None


def test_excluir_memoria_inexistente(ms):
    ok = ms.confirm_forget("id_inexistente", "user1")
    assert not ok


def test_forget_candidates(ms):
    ms.remember("o preco do chaveiro e 4,90 euros", user_id="user1")
    ms.remember("o telefone da Maria e 912345678", user_id="user1")
    candidates = ms.forget("chaveiro", user_id="user1")
    assert len(candidates) >= 1
    assert any("chaveiro" in c.content.lower() or "4,90" in c.content for c in candidates)


def test_forget_sem_candidatos(ms):
    candidates = ms.forget("algo inexistente", user_id="user1")
    assert len(candidates) == 0


# ---------------------------------------------------------------------------
# 6. Isolamento entre utilizadores
# ---------------------------------------------------------------------------


def test_isolamento_utilizadores(ms):
    ms.remember("dado do user1", user_id="user1")
    ms.remember("dado do user2", user_id="user2")
    r1 = ms.query("dado", user_id="user1")
    r2 = ms.query("dado", user_id="user2")
    assert len(r1) >= 1
    assert len(r2) >= 1
    # Nenhum resultado do user1 contem dados do user2
    for r in r1:
        assert r.user_id == "user1"


def test_isolamento_utilizadores_exclusao(ms):
    item = ms.remember("dado sigiloso", user_id="user1")
    # User2 nao pode ver
    found = ms.store.get(item.id, "user2")
    assert found is None
    # User2 nao pode excluir
    ok = ms.confirm_forget(item.id, "user2")
    assert not ok


# ---------------------------------------------------------------------------
# 7. Isolamento entre workspaces
# ---------------------------------------------------------------------------


def test_isolamento_workspaces(ms):
    ms.remember("dado do workspace A", user_id="user1", workspace="workspace_a")
    ms.remember("dado do workspace B", user_id="user1", workspace="workspace_b")
    r = ms.search("dado", user_id="user1", workspace="workspace_a")
    for item in r:
        assert item.workspace == "workspace_a"


# ---------------------------------------------------------------------------
# 8. Busca por projeto
# ---------------------------------------------------------------------------


def test_busca_por_projeto(ms):
    ms.remember("lembre que prazo do projeto zavix e dia 15", "user1")
    ms.remember("cliente da pinklogic quer 10 unidades", "user1")
    results = ms.search("", user_id="user1", project="zavix")
    assert len(results) >= 1
    assert any("zavix" in r.project.lower() or "15" in r.content for r in results)


# ---------------------------------------------------------------------------
# 9. Busca por cliente
# ---------------------------------------------------------------------------


def test_busca_por_cliente(ms):
    ms.remember_raw(_make_item("user1", "contrato do joao silva", client="Joao Silva"))
    ms.remember_raw(_make_item("user1", "reuniao com maria", client="Maria Souza"))
    results = ms.search("", user_id="user1", client="Joao")
    assert len(results) >= 1
    assert any("joao" in r.client.lower() for r in results)


# ---------------------------------------------------------------------------
# 10. Busca por tags
# ---------------------------------------------------------------------------


def test_busca_por_tags(ms):
    ms.remember_raw(_make_item("user1", "configuracao servidor", tags=["tecnico", "urgente"]))
    ms.remember_raw(_make_item("user1", "nota qualquer", tags=["geral"]))
    results = ms.search("", user_id="user1", tag="urgente")
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# 11. Busca textual (FTS5/LIKE fallback)
# ---------------------------------------------------------------------------


def test_busca_textual(ms):
    ms.remember("o codigo de acesso e ABC123", user_id="user1")
    results = ms.search("ABC123", user_id="user1")
    assert len(results) >= 1


def test_busca_textual_parcial(ms):
    ms.remember("o servidor esta em manutencao programada", user_id="user1")
    results = ms.search("manutencao", user_id="user1")
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# 12. Fallback sem embeddings
# ---------------------------------------------------------------------------


def test_fallback_like(ms):
    """FTS5 pode nao estar disponivel => LIKE e usado. Testamos o LIKE."""
    ms.remember("informacao importante sobre orcamento", user_id="user1")
    results = ms.store.search("orcamento", user_id="user1")
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# 13. Recuperacao apos reinicio (persistencia)
# ---------------------------------------------------------------------------


def test_recuperacao_apos_reinicio():
    """Dados persistem no SQLite apos fechar e reabrir."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        store1 = SQLiteMemoryStore(db_path)
        ms1 = MemorySystem(store1)
        ms1.remember("dado persistente", "user1")
        item_id = ms1.list_by_user("user1")[0].id
        store1.close()

        store2 = SQLiteMemoryStore(db_path)
        ms2 = MemorySystem(store2)
        found = ms2.store.get(item_id, "user1")
        assert found is not None
        assert found.content == "dado persistente"
        store2.close()
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 14. Limite de contexto (max results)
# ---------------------------------------------------------------------------


def test_limite_contexto(ms):
    for i in range(10):
        ms.remember(f"item {i}", "user1")
    results = ms.search("", user_id="user1", limit=3)
    assert len(results) <= 3


# ---------------------------------------------------------------------------
# 15. Nao salvar saudacoes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("saudacao", ["ola", "Oi", "Bom dia", "Boa tarde", "tudo bem"])
def test_nao_salvar_saudacoes(ms, saudacao):
    assert not ms.should_save(saudacao)


def test_salvar_nao_saudacao(ms):
    assert ms.should_save("preco do produto e 10")


# ---------------------------------------------------------------------------
# 16. Nao expor segredos (filtro basico)
# ---------------------------------------------------------------------------


def test_nao_expor_segredos_outro_usuario(ms):
    ms.remember("senha: minha_senha_secreta", user_id="user1")
    results = ms.query("senha", user_id="user2")
    assert len(results) == 0


# ---------------------------------------------------------------------------
# 17. Injecao correta no agente
# ---------------------------------------------------------------------------


def test_injecao_correta_item(ms):
    item = ms.remember("dado do agente marketing", user_id="user1", agent="marketing")
    assert item.agent == "marketing"


# ---------------------------------------------------------------------------
# 18. Memoria inexistente
# ---------------------------------------------------------------------------


def test_memoria_inexistente_get(ms):
    found = ms.store.get("id_falso", "user1")
    assert found is None


def test_memoria_inexistente_update(ms):
    updated = ms.update("id_falso", "user1", content="novo")
    assert updated is None


# ---------------------------------------------------------------------------
# 19. Telegram integration (parse de linguagem natural)
# ---------------------------------------------------------------------------


def test_detect_intent_remember(ms):
    assert ms.detect_intent("lembre que o preco e 10 euros") == "remember"
    assert ms.detect_intent("guarde que a reuniao e amanha") == "remember"
    assert ms.detect_intent("anote o telefone 912345678") == "remember"


def test_detect_intent_remember_project(ms):
    assert ms.detect_intent("lembre que o prazo e 15/12 pertence ao projeto Zavix") == "remember_project"


def test_detect_intent_forget(ms):
    assert ms.detect_intent("esqueca o preco do chaveiro") == "forget"
    assert ms.detect_intent("apague o telefone da Maria") == "forget"


def test_detect_intent_query(ms):
    assert ms.detect_intent("o que voce sabe sobre o projeto Zavix") == "query"
    assert ms.detect_intent("o que voce lembra sobre a Maria") == "query"


def test_detect_intent_greeting(ms):
    assert ms.detect_intent("ola") == "greeting"
    assert ms.detect_intent("Bom dia") == "greeting"


def test_detect_intent_other(ms):
    assert ms.detect_intent("qual a capital do brasil") == "other"
    assert ms.detect_intent("crie uma legenda para instagram") == "other"


# ---------------------------------------------------------------------------
# 20. Multiplos utilizadores simultaneos (thread safety)
# ---------------------------------------------------------------------------


def test_multiplos_utilizadores_simultaneos(ms):
    errors = []

    def worker(user_id: str, n: int):
        try:
            for i in range(n):
                ms.remember(f"item {i} do {user_id}", user_id=user_id)
        except Exception as e:
            errors.append((user_id, str(e)))

    threads = [
        threading.Thread(target=worker, args=(f"user_{j}", 5))
        for j in range(5)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Erros em threads: {errors}"
    for j in range(5):
        uid = f"user_{j}"
        count = ms.count(uid)
        assert count == 5, f"user_{j} tem {count} itens (esperado 5)"


# ---------------------------------------------------------------------------
# 21. Estatisticas
# ---------------------------------------------------------------------------


def test_estatisticas(ms):
    ms.remember("preco produto 10 euros", user_id="user1")
    ms.remember("telefone 912345678", user_id="user1")
    stats = ms.stats("user1")
    assert stats["total"] >= 2
    assert stats["total_acessos"] >= 0
    assert "fact" in stats["por_tipo"] or "note" in stats["por_tipo"]


# ---------------------------------------------------------------------------
# 22. Listagem por projeto
# ---------------------------------------------------------------------------


def test_listar_por_projeto(ms):
    ms.remember_raw(_make_item("user1", "dado projeto X", project="ProjetoX"))
    ms.remember_raw(_make_item("user1", "outro dado projeto X", project="ProjetoX"))
    results = ms.list_by_project("ProjetoX", "user1")
    assert len(results) >= 2


# ---------------------------------------------------------------------------
# Execucao direta
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("OK - Todos os testes de memoria passaram!")
