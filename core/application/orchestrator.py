"""
Orchestrator — o gerente "Cris OS" (caso de uso de orquestração).

Amarra IntentRouter + WorkflowEngine + ResponseComposer e publica eventos a cada
etapa (todos amarrados por um `correlation_id`). Ele NUNCA executa tarefas de
domínio — só identifica a intenção, coordena os especialistas e entrega UMA
resposta. É o único componente com quem a Cris "conversa".
"""

from __future__ import annotations

import logging
import time

from core.application.timer import StageTimer
from core.contracts.execution import DispatchContext
from core.domain.events import Event, EventType
from core.models import IncomingMessage

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, intent_router, dispatcher, composer, conversation, event_bus,
                 planner_prompt: str) -> None:
        self.intent_router = intent_router
        self.dispatcher = dispatcher  # ExecutionDispatcher (agente/skill/tool/...)
        self.composer = composer
        self.conversation = conversation
        self.event_bus = event_bus
        self.planner_prompt = planner_prompt

    def handle(self, incoming: IncomingMessage) -> str:
        session = incoming.session
        corr = None
        t = StageTimer()

        # Evento de entrada (gera o correlation_id que amarra o pedido inteiro).
        evento = Event(
            type=EventType.MESSAGE_RECEIVED,
            source="orchestrator",
            payload={"session": session, "text": incoming.text},
        )
        self.event_bus.publish(evento)
        corr = evento.correlation_id

        # 1) Carregar memória da conversa.
        t.begin("1.memoria")
        conversa = self.conversation.recent(session)
        t.end("1.memoria")

        # 2) Decidir quem trabalha.
        t.begin("2.intent_router")
        plano = self.intent_router.plan(incoming.text, conversa, self.planner_prompt)
        t.end("2.intent_router")
        logger.info("=== [ORCHESTRATOR] Plano gerado: %s ===",
                    [{"target": s.name, "type": s.type.value, "instruction": s.instruction[:80]}
                     for s in plano])
        self.event_bus.publish(Event(
            type=EventType.INTENT_IDENTIFIED, correlation_id=corr, source="orchestrator",
            payload={"plan": [{"target": s.name, "type": s.type, "instruction": s.instruction}
                              for s in plano]},
        ))

        # 3) Coordenar a execução (despacha cada passo ao seu ExecutionTarget).
        t.begin("3.execucao")
        ctx = DispatchContext(session=session, query=incoming.text, correlation_id=corr)
        resultados = self.dispatcher.run(plano, ctx)
        t.end("3.execucao")
        logger.info("=== [ORCHESTRATOR] Resultados da execucao: %s ===",
                    [{"source": r.source, "success": r.success, "output": (r.output or "")[:100]}
                     for r in resultados])

        # 4) Entregar UMA resposta.
        t.begin("4.composer")
        resposta = self.composer.compose(incoming.text, resultados)
        t.end("4.composer")

        logger.info("=== [ORCHESTRATOR] Resposta final (%d chars): '%s' ===",
                    len(resposta), resposta[:200])
        self.event_bus.publish(Event(
            type=EventType.RESPONSE_COMPOSED, correlation_id=corr, source="orchestrator",
            payload={"sources": [r.source for r in resultados]},
        ))

        # Registrar o diálogo.
        self.conversation.add(session, "user", incoming.text)
        self.conversation.add(session, "assistant", resposta)

        logger.info("=== [TIMING] Orchestrator:\n%s", t.report())
        return resposta
