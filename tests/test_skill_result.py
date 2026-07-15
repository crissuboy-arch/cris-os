"""
Onda 2 / B1 — SkillResult (padronização) + eventos skill.*.
Verifica: construção, normalização de dict (estilo session-handoff) e de
SkillResult, e a existência das constantes de evento.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.domain.events import EventType  # noqa: E402
from core.models import SkillResult  # noqa: E402


def test_construct():
    r = SkillResult(skill="x", ok=True, output="oi", data={"a": 1})
    assert r.skill == "x" and r.ok and r.output == "oi" and r.data == {"a": 1} and r.error == ""


def test_of_idempotent_on_skillresult():
    r = SkillResult(skill="x", output="oi")
    assert SkillResult.of(r) is r


def test_of_normalizes_dict_session_handoff_like():
    d = {"ok": True, "skill": "session-handoff", "action": "save",
         "handoff_id": "abc", "summary": "Sessão empacotada", "data": {"session": "s"}}
    r = SkillResult.of(d)
    assert r.skill == "session-handoff" and r.ok is True
    assert r.output == "Sessão empacotada"                     # summary -> output
    assert r.data["session"] == "s"                            # data preservado
    assert r.data["action"] == "save" and r.data["handoff_id"] == "abc"  # extras preservados


def test_of_error_dict():
    r = SkillResult.of({"ok": False, "error": "falhou"}, skill="y")
    assert r.skill == "y" and r.ok is False and r.error == "falhou"


def test_skill_events_exist():
    for ev in ("SKILL_STARTED", "SKILL_COMPLETED", "SKILL_FAILED"):
        assert hasattr(EventType, ev)
    assert EventType.SKILL_FAILED == "skill.failed"


if __name__ == "__main__":
    test_construct()
    test_of_idempotent_on_skillresult()
    test_of_normalizes_dict_session_handoff_like()
    test_of_error_dict()
    test_skill_events_exist()
    print("OK - test_skill_result")
