"""
Testes unitários da Skill Session Handoff.

Usam SQLite real (memória) + Event Bus real sobre o SQLiteOpsStore (Event Log),
sem Telegram nem Ollama. Provam a integração com Memory, Event Log e Registry, e
que qualquer agente pode acionar a skill.

Rodar:  pytest -q tests/test_session_handoff.py   (ou)   python tests/test_session_handoff.py
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
    reg = SkillRegistry().discover(RAIZ / "skills")
    return reg, reg.load_executor("session-handoff")


# ----------------------------------------------------------------------
def test_registry_integration():
    reg, skill = _skill()
    s = reg.get("session-handoff")
    assert s is not None and s.valid and s.enabled
    assert s.status == "production" and s.version == "1.0.0"
    assert skill is not None and skill.name == "session-handoff"
    # qualquer agente: o manifesto declara "*"
    assert s.agents == ["*"]


def test_save_and_resume(tmp_path: Path):
    ops, bus, facade = _stack(tmp_path)
    facade.conversation.add("telegram:1", "user", "oi")
    facade.conversation.add("telegram:1", "assistant", "olá")
    facade.temporary.add("telegram:1", "beber água")

    _, skill = _skill()
    ctx = SkillContext(session="telegram:1", memory=FacadeSkillMemory(facade), publish=bus.publish,
                       correlation_id="c1", caller="secretary")

    r = skill.execute({"action": "save", "notes": "parei na fase X",
                       "next_steps": ["continuar Y"]}, ctx)
    assert r["ok"] and r["action"] == "save" and r["handoff_id"]
    # Memory: handoff persistido na permanente (L3)
    assert any(i.type == "handoff" for i in facade.permanent.recall())
    # Event Log: evento de criação gravado
    tipos = [e.type for _, e in ops.read_since(0)]
    assert "skill.session_handoff.created" in tipos

    r2 = skill.execute({"action": "resume"}, ctx)
    assert r2["ok"] and r2["found"] and "continuar Y" in r2["summary"]
    tipos2 = [e.type for _, e in ops.read_since(0)]
    assert "skill.session_handoff.resumed" in tipos2


def test_resume_sem_historico(tmp_path: Path):
    ops, bus, facade = _stack(tmp_path)
    _, skill = _skill()
    ctx = SkillContext(session="telegram:vazio", memory=FacadeSkillMemory(facade), publish=bus.publish)
    r = skill.execute({"action": "resume"}, ctx)
    assert r["ok"] and r["found"] is False


def test_any_agent_can_call(tmp_path: Path):
    ops, bus, facade = _stack(tmp_path)
    _, skill = _skill()
    for caller in ("secretary", "zavix", "orchestrator"):
        ctx = SkillContext(session=f"telegram:{caller}", memory=FacadeSkillMemory(facade),
                           publish=bus.publish, caller=caller)
        r = skill.execute({"action": "save"}, ctx)
        assert r["ok"] and r["handoff_id"]


if __name__ == "__main__":
    import tempfile

    test_registry_integration()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        base = Path(d)
        for i, t in enumerate((test_save_and_resume, test_resume_sem_historico,
                               test_any_agent_can_call)):
            sub = base / f"t{i}"
            sub.mkdir()
            t(sub)
    print("OK - Testes da Session Handoff passaram!")
