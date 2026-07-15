"""
Onda 2 / B4 — SkillRunner (execução de skill no fluxo).

Roda a session-handoff via runner (SQLite + Event Log reais, sem Telegram/Ollama):
  - sucesso -> devolve SkillResult(ok=True) e emite skill.started + skill.completed;
  - ação desconhecida (ok=False) -> emite skill.failed;
  - skill sem executor declarado -> emite skill.failed.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.application import SkillRunner  # noqa: E402
from core.events import InProcessEventBus  # noqa: E402
from core.models import SkillResult  # noqa: E402
from core.skills import SkillRegistry  # noqa: E402
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


def _runner(tmp: Path):
    mem = SQLiteMemory(tmp / "mem.db")
    ops = SQLiteOpsStore(tmp / "ops.db")
    bus = InProcessEventBus(ops)
    facade = MemoryFacade(
        ConversationMemory(mem, 10), TemporaryMemory(mem),
        ProjectMemory(mem), PermanentMemory(mem), KnowledgeBaseMemory(mem),
    )
    skills = SkillRegistry().discover(RAIZ / "skills")
    return ops, SkillRunner(skills, ops, bus, FacadeSkillMemory(facade))


def test_run_success_emits_completed(tmp_path: Path):
    ops, runner = _runner(tmp_path)
    r = runner.run("session-handoff", {"action": "save", "next_steps": ["x"]},
                   session="telegram:1", correlation_id="c1")
    assert isinstance(r, SkillResult) and r.ok and r.skill == "session-handoff" and r.output
    tipos = [e.type for _, e in ops.read_since(0)]
    assert "skill.started" in tipos and "skill.completed" in tipos


def test_run_unknown_action_emits_failed(tmp_path: Path):
    ops, runner = _runner(tmp_path)
    r = runner.run("session-handoff", {"action": "xpto"}, session="telegram:1")
    assert r.ok is False and r.error
    tipos = [e.type for _, e in ops.read_since(0)]
    assert "skill.failed" in tipos


def test_run_without_executor_emits_failed(tmp_path: Path):
    ops, runner = _runner(tmp_path)
    r = runner.run("roast", {}, session="telegram:1")  # scaffold sem executor
    assert r.ok is False
    tipos = [e.type for _, e in ops.read_since(0)]
    assert "skill.failed" in tipos


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        base = Path(d)
        for i, t in enumerate((test_run_success_emits_completed,
                               test_run_unknown_action_emits_failed,
                               test_run_without_executor_emits_failed)):
            sub = base / f"t{i}"
            sub.mkdir()
            t(sub)
    print("OK - test_skill_runner")
