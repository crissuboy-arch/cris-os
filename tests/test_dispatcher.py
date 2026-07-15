"""
Onda 2 / B5 — ExecutionDispatcher + TargetRegistry (kernel de execução genérico).

Prova: despacho por ExecutionType, indexação por id, falha clara quando não há
target para o tipo, e o caminho REAL de skill (SkillTarget -> SkillRunner) via
dispatcher emitindo skill.completed.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.application import (  # noqa: E402
    ExecutionDispatcher,
    SkillRunner,
    SkillTarget,
    TargetRegistry,
)
from core.contracts.execution import DispatchContext, ExecutionTarget  # noqa: E402
from core.domain.execution import ExecutionType  # noqa: E402
from core.events import InProcessEventBus  # noqa: E402
from core.models import ExecutionResult, ExecutionStep  # noqa: E402
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


class FakeTarget:
    def __init__(self, id, type, out):
        self.id = id
        self.type = type
        self.out = out
        self.calls: list[str] = []

    def run(self, step, ctx) -> ExecutionResult:
        self.calls.append(step.name)
        return ExecutionResult(source=step.name, type=self.type, output=self.out)


def test_target_cumpre_a_porta():
    assert isinstance(FakeTarget("t", ExecutionType.AGENT, "x"), ExecutionTarget)


def test_dispatch_por_tipo_e_ordem():
    ag = FakeTarget("agent.fake", ExecutionType.AGENT, "A")
    sk = FakeTarget("skill.fake", ExecutionType.SKILL, "S")
    disp = ExecutionDispatcher(TargetRegistry().register(ag).register(sk))
    plano = [ExecutionStep("secretary", ExecutionType.AGENT, instruction="x"),
             ExecutionStep("session-handoff", ExecutionType.SKILL, payload={"action": "save"})]
    res = disp.run(plano, DispatchContext(session="s"))
    assert [r.source for r in res] == ["secretary", "session-handoff"]
    assert res[0].type == ExecutionType.AGENT and res[1].type == ExecutionType.SKILL
    assert ag.calls == ["secretary"] and sk.calls == ["session-handoff"]


def test_indexacao_por_id_e_tipo():
    ag = FakeTarget("agent.fake", ExecutionType.AGENT, "A")
    targets = TargetRegistry().register(ag)
    assert targets.by_id("agent.fake") is ag
    assert targets.get(ExecutionType.AGENT) is ag


def test_tipo_sem_target_falha_claro():
    disp = ExecutionDispatcher(TargetRegistry())  # nada registrado
    res = disp.run([ExecutionStep("x", ExecutionType.TOOL)], DispatchContext(session="s"))
    assert len(res) == 1 and res[0].success is False and "Sem executor" in res[0].error


def _skill_target(tmp: Path):
    mem = SQLiteMemory(tmp / "mem.db")
    ops = SQLiteOpsStore(tmp / "ops.db")
    bus = InProcessEventBus(ops)
    facade = MemoryFacade(
        ConversationMemory(mem, 10), TemporaryMemory(mem),
        ProjectMemory(mem), PermanentMemory(mem), KnowledgeBaseMemory(mem),
    )
    skills = SkillRegistry().discover(RAIZ / "skills")
    runner = SkillRunner(skills, ops, bus, FacadeSkillMemory(facade))
    return ops, SkillTarget(runner)


def test_caminho_real_de_skill(tmp_path: Path):
    ops, sk = _skill_target(tmp_path)
    disp = ExecutionDispatcher(TargetRegistry().register(sk))
    res = disp.run(
        [ExecutionStep("session-handoff", ExecutionType.SKILL,
                       payload={"action": "save", "next_steps": ["y"]})],
        DispatchContext(session="telegram:1", correlation_id="c1"),
    )
    assert len(res) == 1 and res[0].type == ExecutionType.SKILL
    assert res[0].success and res[0].output
    tipos = [e.type for _, e in ops.read_since(0)]
    assert "skill.completed" in tipos


if __name__ == "__main__":
    import tempfile

    test_target_cumpre_a_porta()
    test_dispatch_por_tipo_e_ordem()
    test_indexacao_por_id_e_tipo()
    test_tipo_sem_target_falha_claro()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        test_caminho_real_de_skill(Path(d))
    print("OK - test_dispatcher")
