"""
Caracterização (Onda 2 / B0) — execução ATUAL de Skills (session-handoff).

Fixa o contrato de execução antes de estender na Onda 2:
  - B1 (SkillResult): o shape do retorno de execute();
  - B2 (load_executor cache/validação): o contrato do load_executor;
  - B3 (SkillMemory): o efeito na memória e nos eventos.

Não muda produção — só protege o comportamento observável durante a Onda 2.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.events import InProcessEventBus  # noqa: E402
from core.skills import SkillContext, SkillRegistry  # noqa: E402
from memory import (  # noqa: E402
    ConversationMemory,
    FacadeSkillMemory,
    KnowledgeBaseMemory,
    MemoryFacade,
    PermanentMemory,
    ProjectMemory,
    TemporaryMemory,
)
from storage import SQLiteMemory, SQLiteOpsStore  # noqa: E402


def _stack(tmp: Path):
    mem = SQLiteMemory(tmp / "mem.db")
    ops = SQLiteOpsStore(tmp / "ops.db")
    bus = InProcessEventBus(ops)
    facade = MemoryFacade(
        ConversationMemory(mem, 10), TemporaryMemory(mem),
        ProjectMemory(mem), PermanentMemory(mem), KnowledgeBaseMemory(mem),
    )
    return ops, bus, facade


def _skill():
    return SkillRegistry().discover(RAIZ / "skills").load_executor("session-handoff")


def test_load_executor_contract():
    reg = SkillRegistry().discover(RAIZ / "skills")
    ex = reg.load_executor("session-handoff")
    assert ex is not None
    assert ex.name == "session-handoff" and ex.version == "1.0.0"
    assert callable(getattr(ex, "execute", None))
    # skill scaffold (sem executor declarado) -> None
    assert reg.load_executor("roast") is None


def test_execute_save_return_shape(tmp_path: Path):
    _, bus, facade = _stack(tmp_path)
    ctx = SkillContext(session="telegram:1", memory=FacadeSkillMemory(facade), publish=bus.publish, caller="secretary")
    r = _skill().execute({"action": "save", "notes": "n", "next_steps": ["passo"]}, ctx)
    assert isinstance(r, dict)
    assert {"ok", "skill", "action", "handoff_id", "summary", "data"} <= set(r)
    assert r["ok"] is True and r["skill"] == "session-handoff" and r["action"] == "save"
    assert r["handoff_id"]


def test_save_persists_and_emits(tmp_path: Path):
    ops, bus, facade = _stack(tmp_path)
    ctx = SkillContext(session="telegram:1", memory=FacadeSkillMemory(facade), publish=bus.publish, caller="secretary")
    _skill().execute({"action": "save", "next_steps": ["passo"]}, ctx)
    assert any(i.type == "handoff" for i in facade.permanent.recall())  # Memory L3
    tipos = [e.type for _, e in ops.read_since(0)]  # Event Log
    assert "skill.session_handoff.created" in tipos


def test_resume_returns_and_emits(tmp_path: Path):
    ops, bus, facade = _stack(tmp_path)
    ctx = SkillContext(session="telegram:1", memory=FacadeSkillMemory(facade), publish=bus.publish, caller="secretary")
    skill = _skill()
    skill.execute({"action": "save", "next_steps": ["continuar Y"]}, ctx)
    r = skill.execute({"action": "resume"}, ctx)
    assert r["found"] is True and "continuar Y" in r["summary"]
    tipos = [e.type for _, e in ops.read_since(0)]
    assert "skill.session_handoff.resumed" in tipos


if __name__ == "__main__":
    import tempfile

    test_load_executor_contract()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        base = Path(d)
        for i, t in enumerate((test_execute_save_return_shape, test_save_persists_and_emits,
                               test_resume_returns_and_emits)):
            sub = base / f"t{i}"
            sub.mkdir()
            t(sub)
    print("OK - test_skill_execution")
