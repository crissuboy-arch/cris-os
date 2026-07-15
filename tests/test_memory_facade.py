"""
Caracterização (Onda 1 / B0) — MemoryFacade.build_context (escopo).
Fixa o escopo por projeto antes de qualquer mexida em memória/roteamento.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from memory import (  # noqa: E402
    ConversationMemory,
    KnowledgeBaseMemory,
    MemoryFacade,
    PermanentMemory,
    ProjectMemory,
    TemporaryMemory,
)
from memory.seed import seed_if_empty  # noqa: E402
from storage import SQLiteMemory  # noqa: E402


def _facade(tmp: Path):
    m = SQLiteMemory(tmp / "m.db")
    perm, proj = PermanentMemory(m), ProjectMemory(m)
    seed_if_empty(perm, proj)
    facade = MemoryFacade(
        ConversationMemory(m, 10), TemporaryMemory(m), proj, perm, KnowledgeBaseMemory(m)
    )
    return m, facade


def test_scope_single_project(tmp_path: Path):
    m, facade = _facade(tmp_path)
    ctx = facade.build_context(["Zavix.online"], "s", "q")
    assert {i.title for i in ctx.project_memory} == {"Zavix.online"}
    assert ctx.permanent
    m.close()


def test_scope_empty_and_all(tmp_path: Path):
    m, facade = _facade(tmp_path)
    assert facade.build_context([], "s", "q").project_memory == []
    assert len(facade.build_context(["*"], "s", "q").project_memory) >= 9
    m.close()


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        base = Path(d)
        for i, t in enumerate((test_scope_single_project, test_scope_empty_and_all)):
            sub = base / f"t{i}"
            sub.mkdir()
            t(sub)
    print("OK - test_memory_facade")
