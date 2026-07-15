"""
Entidades de domínio da camada de cognição (planejamento → execução → supervisão).

São apenas DADOS (dataclasses puras), sem lógica nem dependências externas —
fazem parte do domínio, o centro da Clean Architecture. Descrevem o vocabulário
do "sistema operacional autônomo":

  Objective       -> o que a Cris quer alcançar
  Strategy        -> a abordagem escolhida para alcançar o objetivo
  PlanStep / Plan -> o passo a passo decidido pelo Strategic Planner
  StepResult / ExecutionReport -> o que o Execution Manager produziu
  QualityVerdict  -> o parecer do Quality Supervisor (aprova ou pede refação)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _novo_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Objective:
    """O objetivo do usuário, ponto de partida da camada de cognição."""

    text: str
    session: str
    correlation_id: str
    context: dict = field(default_factory=dict)  # análise de contexto/memória
    id: str = field(default_factory=_novo_id)
    created_at: str = field(default_factory=_agora)


@dataclass
class Strategy:
    """A melhor abordagem escolhida para atingir o objetivo."""

    name: str
    rationale: str = ""  # por que esta estratégia foi escolhida
    params: dict = field(default_factory=dict)


@dataclass
class PlanStep:
    """Um passo do plano: qual agente faz o quê (com política de execução)."""

    agent: str
    instruction: str
    id: str = field(default_factory=_novo_id)
    depends_on: list[str] = field(default_factory=list)  # ids de passos anteriores
    timeout_seconds: int | None = None
    max_retries: int = 0


@dataclass
class Plan:
    """O plano completo criado pelo Strategic Planner (que nunca executa)."""

    objective: Objective
    strategy: Strategy
    steps: list[PlanStep] = field(default_factory=list)
    id: str = field(default_factory=_novo_id)
    created_at: str = field(default_factory=_agora)


@dataclass
class StepResult:
    """Resultado de um passo, com metadados de execução (tentativas/timeout)."""

    step_id: str
    agent: str
    output: str
    success: bool = True
    attempts: int = 1
    timed_out: bool = False


@dataclass
class ExecutionReport:
    """O que o Execution Manager produziu ao rodar o plano."""

    plan_id: str
    results: list[StepResult] = field(default_factory=list)
    completed: bool = False
    failures: list[str] = field(default_factory=list)  # ids de passos que falharam


@dataclass
class QualityVerdict:
    """Parecer do Quality Supervisor. Só 'approved' chega à Cris."""

    approved: bool
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    revision_request: str | None = None  # instrução para nova execução, se reprovado
