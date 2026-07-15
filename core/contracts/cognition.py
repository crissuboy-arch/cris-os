"""
Portas da camada de cognição (o "cérebro estratégico" do CRIS OS).

Três responsabilidades, três portas (SRP + ISP):

  StrategicPlanner -> PENSA antes de agir. Recebe um Objective, analisa contexto e
                      memória, escolhe uma Strategy e cria um Plan. NUNCA executa.
  ExecutionManager -> EXECUTA o Plan: distribui aos agentes, monitora progresso,
                      reexecuta quando falha, detecta falhas e controla timeout.
  QualitySupervisor-> SUPERVISIONA: avalia os resultados, confere se o objetivo
                      foi atingido e, se preciso, pede nova execução. Só o que ele
                      aprova chega à Cris.

Status: contratos definidos. As implementações concretas (em core/cognition/) são
esqueletos — a inteligência será implementada após a revisão de arquitetura.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.domain.planning import (
    ExecutionReport,
    Objective,
    Plan,
    QualityVerdict,
)


@runtime_checkable
class StrategicPlanner(Protocol):
    def plan(self, objective: Objective) -> Plan:
        """Analisa o objetivo e devolve um Plan. Não executa nada."""
        ...


@runtime_checkable
class ExecutionManager(Protocol):
    def execute(self, plan: Plan) -> ExecutionReport:
        """Executa o plano (distribui, monitora, reexecuta, controla timeout)."""
        ...


@runtime_checkable
class QualitySupervisor(Protocol):
    def review(self, plan: Plan, report: ExecutionReport) -> QualityVerdict:
        """Avalia a qualidade e diz se aprova ou pede nova execução."""
        ...
