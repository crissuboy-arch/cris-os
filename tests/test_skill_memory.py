"""
Onda 2 / B3 — porta estreita SkillMemory + adaptador FacadeSkillMemory.

Prova que o adaptador cumpre a porta (runtime_checkable) e que delega
corretamente ao MemoryFacade concreto (mesmo efeito no SQLite).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.contracts import SkillMemory  # noqa: E402
from memory import (  # noqa: E402
    ConversationMemory,
    FacadeSkillMemory,
    KnowledgeBaseMemory,
    MemoryFacade,
    PermanentMemory,
    ProjectMemory,
    TemporaryMemory,
)
from storage import SQLiteMemory  # noqa: E402


def _mem(tmp: Path):
    m = SQLiteMemory(tmp / "m.db")
    facade = MemoryFacade(
        ConversationMemory(m, 10), TemporaryMemory(m),
        ProjectMemory(m), PermanentMemory(m), KnowledgeBaseMemory(m),
    )
    return m, facade, FacadeSkillMemory(facade)


def test_adapter_cumpre_a_porta(tmp_path: Path):
    _, _, sm = _mem(tmp_path)
    assert isinstance(sm, SkillMemory)  # estrutural (runtime_checkable)


def test_delegacao_conversa_e_itens(tmp_path: Path):
    m, facade, sm = _mem(tmp_path)
    facade.conversation.add("s", "user", "oi")
    facade.temporary.add("s", "beber água")
    assert sm.recent_conversation("s") == facade.conversation.recent("s")
    assert sm.today_items("s") == ["beber água"]
    m.close()


def test_delegacao_remember_recall(tmp_path: Path):
    m, facade, sm = _mem(tmp_path)
    item = sm.remember("handoff", "t", "conteudo", tags=["handoff", "s"])
    assert item.id
    recuperados = sm.recall("handoff")
    assert any(i.id == item.id for i in recuperados)
    assert recuperados == facade.permanent.recall("handoff")  # mesmo backend
    m.close()


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        base = Path(d)
        for i, t in enumerate((test_adapter_cumpre_a_porta,
                               test_delegacao_conversa_e_itens,
                               test_delegacao_remember_recall)):
            sub = base / f"t{i}"
            sub.mkdir()
            t(sub)
    print("OK - test_skill_memory")
