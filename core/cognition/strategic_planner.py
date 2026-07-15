"""
StrategicPlanner — PENSA antes de agir.

Responsabilidade única: receber um Objective, analisar o contexto, consultar a
memória (4 camadas, via MemoryFacade), escolher a melhor Strategy e criar um Plan
(passo a passo). NUNCA executa tarefas — só decide o caminho.

Eventos que publicará (via Event Bus):
  CONTEXT_ANALYZED · STRATEGY_SELECTED · PLAN_CREATED

⚠️ ESQUELETO: a lógica de planejamento será implementada após a revisão de
arquitetura. Hoje `plan()` levanta NotImplementedError de propósito.
"""

from __future__ import annotations

from core.domain.planning import Objective, Plan


class StrategicPlanner:
    def __init__(self, llm, memory_facade, intent_router, event_bus) -> None:
        # Dependências injetadas (DIP). Reaproveita o IntentRouter v3 para a
        # seleção de agente por passo, mas num nível mais alto (estratégia + plano).
        self.llm = llm
        self.memory = memory_facade
        self.intent_router = intent_router
        self.event_bus = event_bus

    def plan(self, objective: Objective) -> Plan:
        """
        TODO (pós-revisão):
          1. analisar contexto (memória permanente + projeto + base de conhecimento)
             -> publicar CONTEXT_ANALYZED;
          2. escolher a melhor estratégia (uma ou várias etapas, paralelo/sequencial)
             -> publicar STRATEGY_SELECTED;
          3. montar o Plan com PlanStep(s), dependências, timeout e max_retries
             -> publicar PLAN_CREATED;
          4. devolver o Plan (sem executar nada).
        """
        raise NotImplementedError(
            "StrategicPlanner.plan ainda não implementado (camada de cognição em "
            "evolução arquitetural)."
        )
