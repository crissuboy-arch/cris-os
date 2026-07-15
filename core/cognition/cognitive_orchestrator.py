"""
CognitiveOrchestrator — o pipeline autônomo (planejar → executar → supervisionar).

Coordena os três componentes da camada de cognição com um LOOP de refação:
o objetivo é planejado, executado e supervisionado; se a supervisão reprovar,
volta para nova execução (até `max_revisions`). Só a resposta APROVADA é composta
e entregue à Cris.

Este arquivo é a ARQUITETURA do pipeline (a "cola"). A coordenação está escrita,
mas a inteligência vive nos componentes — que ainda são esqueletos
(NotImplementedError). Por isso o CognitiveOrchestrator NÃO é ligado ao runtime
ainda: o pipeline v3 (core/application/Orchestrator) continua atendendo a Cris
até a próxima revisão de arquitetura.

Todos os marcos são publicados no Event Bus já existente, amarrados pelo
`correlation_id` do objetivo.
"""

from __future__ import annotations

import logging

from core.domain.events import Event, EventType
from core.domain.planning import Objective
from core.models import IncomingMessage

logger = logging.getLogger(__name__)


class CognitiveOrchestrator:
    def __init__(self, planner, executor, supervisor, composer, conversation,
                 event_bus, max_revisions: int = 2) -> None:
        self.planner = planner
        self.executor = executor
        self.supervisor = supervisor
        self.composer = composer
        self.conversation = conversation
        self.event_bus = event_bus
        self.max_revisions = max_revisions

    def handle(self, incoming: IncomingMessage) -> str:
        session = incoming.session

        # 1) Transformar a mensagem em um Objetivo (gera o correlation_id).
        evento = Event(
            type=EventType.OBJECTIVE_RECEIVED,
            source="cognition",
            payload={"session": session, "text": incoming.text},
        )
        self.event_bus.publish(evento)
        objetivo = Objective(
            text=incoming.text, session=session, correlation_id=evento.correlation_id
        )

        # 2) PENSAR: criar o plano (Strategic Planner — nunca executa).
        plano = self.planner.plan(objetivo)

        # 3) EXECUTAR + SUPERVISIONAR, com loop de refação.
        report = None
        for tentativa in range(1, self.max_revisions + 1):
            report = self.executor.execute(plano)
            verdict = self.supervisor.review(plano, report)
            if verdict.approved:
                break
            # Reprovado: pedir nova execução (instrução de refação no próximo ciclo).
            self.event_bus.publish(Event(
                type=EventType.REEXECUTION_REQUESTED,
                correlation_id=objetivo.correlation_id, source="cognition",
                payload={"attempt": tentativa, "reason": verdict.revision_request},
            ))

        # 4) Compor UMA resposta aprovada e entregar.
        resposta = self.composer.compose(objetivo.text, report.results if report else [])
        self.conversation.add(session, "user", incoming.text)
        self.conversation.add(session, "assistant", resposta)
        return resposta
