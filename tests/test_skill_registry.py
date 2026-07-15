"""
Caracterização (Onda 1 / B0) — SkillRegistry.
Fixa descoberta/validação/versão/on-off/load_executor antes da unificação (N2/B3).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.skills import SkillRegistry  # noqa: E402


def _reg():
    return SkillRegistry().discover(RAIZ / "skills")


def test_discover_skips_template_and_counts():
    reg = _reg()
    assert "_template" not in reg.names()
    assert len(reg.all()) == 5
    for s in reg.all():
        assert s.valid, (s.name, s.issues)


def test_session_handoff_production():
    reg = _reg()
    sh = reg.get("session-handoff")
    assert sh.status == "production" and sh.enabled and sh.version == "1.0.0"
    assert [s.name for s in reg.enabled()] == ["session-handoff"]


def test_enable_disable_and_version():
    reg = _reg()
    assert reg.enable("roast") and reg.get("roast").enabled
    assert reg.disable("roast") and not reg.get("roast").enabled
    assert reg.version_of("session-handoff") == "1.0.0"


def test_load_executor():
    reg = _reg()
    ex = reg.load_executor("session-handoff")
    assert ex is not None and ex.name == "session-handoff"
    # scaffold sem executor declarado -> None
    assert reg.load_executor("roast") is None


def test_skills_load_domain():
    reg = _reg()
    assert reg.get("session-handoff").domain == "sistema"
    assert reg.get("browser-tool").domain == "pesquisa"
    assert reg.get("curriculum-builder").domain == "curriculo"


def test_load_executor_cache():
    reg = _reg()
    a = reg.load_executor("session-handoff")
    b = reg.load_executor("session-handoff")
    assert a is b  # mesma instância (cache por nome@versão)


def test_load_executor_invalid_raises(tmp_path):
    from core.skills.registry import SkillLoadError
    from core.skills.skill import Skill

    reg = SkillRegistry()
    reg.register(Skill(name="bad", title="Bad", description="", version="1.0.0",
                       status="production", enabled=True, category="", path=tmp_path,
                       executor="handler:Missing"))  # handler.py não existe
    try:
        reg.load_executor("bad")
        raise AssertionError("deveria levantar SkillLoadError")
    except SkillLoadError:
        pass


if __name__ == "__main__":
    import tempfile

    test_discover_skips_template_and_counts()
    test_session_handoff_production()
    test_enable_disable_and_version()
    test_load_executor()
    test_skills_load_domain()
    test_load_executor_cache()
    with tempfile.TemporaryDirectory() as d:
        test_load_executor_invalid_raises(Path(d))
    print("OK - test_skill_registry")
