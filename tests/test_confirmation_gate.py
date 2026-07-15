"""
Onda 2 / B6 — ConfirmationGate (proteção de ações externas/destrutivas).

  - read-only executa sem confirmação;
  - sensível SEM confirmação -> bloqueado (alvo NÃO roda), pede confirmação;
  - sensível COM confirmação (ctx.confirmed) -> executa.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.application import ConfirmationGate, ExecutionDispatcher, TargetRegistry  # noqa: E402
from core.contracts.execution import DispatchContext, ExecutionTarget  # noqa: E402
from core.domain.execution import Effect, ExecutionType  # noqa: E402
from core.models import ExecutionResult, ExecutionStep  # noqa: E402


class FakeTarget:
    def __init__(self, type):
        self.id = f"{type}.fake"
        self.type = type
        self.ran = False

    def run(self, step, ctx) -> ExecutionResult:
        self.ran = True
        return ExecutionResult(source=step.name, type=self.type, output="executado")


def test_target_cumpre_a_porta():
    assert isinstance(FakeTarget(ExecutionType.TOOL), ExecutionTarget)


def test_read_only_executa_sem_confirmacao():
    t = FakeTarget(ExecutionType.SKILL)
    disp = ExecutionDispatcher(TargetRegistry().register(t))
    res = disp.run([ExecutionStep("ler", ExecutionType.SKILL)], DispatchContext(session="s"))
    assert t.ran and res[0].success and res[0].output == "executado"


def test_sensitive_bloqueia_sem_confirmacao():
    t = FakeTarget(ExecutionType.TOOL)
    disp = ExecutionDispatcher(TargetRegistry().register(t))
    res = disp.run([ExecutionStep("comprar", ExecutionType.TOOL, effect=Effect.SENSITIVE)],
                   DispatchContext(session="s"))
    assert t.ran is False  # alvo NÃO executou
    assert res[0].success is False
    assert res[0].data.get("confirmation_required") is True
    assert "confirmação" in res[0].output


def test_sensitive_executa_com_confirmacao():
    t = FakeTarget(ExecutionType.TOOL)
    disp = ExecutionDispatcher(TargetRegistry().register(t))
    res = disp.run([ExecutionStep("comprar", ExecutionType.TOOL, effect=Effect.SENSITIVE)],
                   DispatchContext(session="s", confirmed=True))
    assert t.ran and res[0].success and res[0].output == "executado"


def test_gate_direto():
    gate = ConfirmationGate()
    sensivel = ExecutionStep("deletar", ExecutionType.TOOL, effect=Effect.SENSITIVE)
    assert gate.check(sensivel, DispatchContext(session="s")) is not None      # bloqueia
    assert gate.check(sensivel, DispatchContext(session="s", confirmed=True)) is None  # libera
    assert gate.check(ExecutionStep("ler", ExecutionType.SKILL), DispatchContext(session="s")) is None


if __name__ == "__main__":
    test_target_cumpre_a_porta()
    test_read_only_executa_sem_confirmacao()
    test_sensitive_bloqueia_sem_confirmacao()
    test_sensitive_executa_com_confirmacao()
    test_gate_direto()
    print("OK - test_confirmation_gate")
