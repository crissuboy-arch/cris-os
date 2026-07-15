"""
Caracterização (Onda 1 / B0) — IntentRouter.plan (comportamento 1-etapa ATUAL).
Fixa: delegação por tool-calling e fallback por palavra-chave.
> Este teste será ATUALIZADO no B7 (roteamento hierárquico) — aqui ele registra
> o comportamento de hoje para proteger os blocos B1–B6 (refator neutro).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agents.loader import carregar_agentes  # noqa: E402
from core.application import IntentRouter  # noqa: E402
from core.contracts.llm import LLMResponse, ToolCall  # noqa: E402
from core.domain.execution import ExecutionType  # noqa: E402
from core.registry import AgentRegistry  # noqa: E402
from core.router import Router  # noqa: E402


def _step(plano):
    """Atalho: garante 1 passo e o devolve."""
    assert len(plano) == 1
    return plano[0]


class FakeLLM:
    def __init__(self, route_to=None):
        self.route_to = route_to

    def is_alive(self):
        return True

    def chat(self, messages, tools=None):
        if tools and self.route_to:
            return LLMResponse(tool_calls=[ToolCall(name=self.route_to,
                                                    arguments={"instruction": "instr"})])
        return LLMResponse(content="texto")


class FakeLLM2:
    """Ciente de domínio: na etapa 1 devolve o domínio; na etapa 2, o agente."""

    def __init__(self, domain, agent):
        self.domain = domain
        self.agent = agent

    def is_alive(self):
        return True

    def chat(self, messages, tools=None):
        nomes = {t["function"]["name"] for t in (tools or [])}
        if self.domain in nomes:
            return LLMResponse(tool_calls=[ToolCall(name=self.domain, arguments={})])
        if self.agent in nomes:
            return LLMResponse(tool_calls=[ToolCall(name=self.agent,
                                                    arguments={"instruction": "instr"})])
        return LLMResponse(content="texto")


def _router(llm):
    agentes = carregar_agentes(RAIZ / "agents", llm=llm)
    reg = AgentRegistry()
    for a in agentes:
        reg.register(a)
    return IntentRouter(llm, reg, Router("secretary", agentes), "secretary")


def _router_with_skills(llm):
    from core.skills import SkillRegistry
    agentes = carregar_agentes(RAIZ / "agents", llm=llm)
    reg = AgentRegistry()
    for a in agentes:
        reg.register(a)
    skills = SkillRegistry().discover(RAIZ / "skills")
    return IntentRouter(llm, reg, Router("secretary", agentes), "secretary", skills=skills)


def test_plan_delegates_via_toolcalling():
    # Texto sem keyword match para garantir roteamento via LLM.
    s = _step(_router(FakeLLM(route_to="financeiro")).plan("preciso consultar o saldo", [], "gerente"))
    assert s.name == "financeiro" and s.instruction == "instr" and s.type == ExecutionType.AGENT


def test_plan_fallback_keyword():
    s = _step(_router(FakeLLM(route_to=None)).plan("preciso de um vídeo novo", [], "gerente"))
    assert s.name == "mkvideos" and s.instruction == "preciso de um vídeo novo"
    assert s.type == ExecutionType.AGENT


def test_two_step_domain_then_agent():
    # domínio 'pessoal' -> agente 'secretary' (nome do domínio != nome do agente)
    s = _step(_router(FakeLLM2("pessoal", "secretary")).plan("organiza meu dia", [], "gerente"))
    assert s.name == "secretary" and s.instruction == "instr" and s.type == ExecutionType.AGENT


def test_fallback_keyword_de_skill():
    # LLM não delega (sem tool_call) -> keyword de SKILL 'handoff' -> session-handoff (não agente).
    s = _step(_router_with_skills(FakeLLM(route_to=None)).plan("faça o handoff desta sessão", [], "g"))
    assert s.name == "session-handoff" and s.type == ExecutionType.SKILL


def test_fallback_prioridade_skill_antes_de_agente():
    # sem keyword de skill -> cai no keyword de AGENTE (preserva o fallback atual).
    s = _step(_router_with_skills(FakeLLM(route_to=None)).plan("preciso de um vídeo novo", [], "g"))
    assert s.name == "mkvideos" and s.type == ExecutionType.AGENT


def test_baseline_prioridade_atual():
    """Caracterização (Onda 3 / B0): trava a ordem ATUAL antes do refator do B1.
    tool-calling -> keyword de skill -> keyword de agente. Valores idênticos ao de hoje."""
    # 1) tool-calling do LLM -> agente
    s = _step(_router(FakeLLM(route_to="financeiro")).plan("como vão as vendas?", [], "g"))
    assert s.name == "financeiro" and s.type == ExecutionType.AGENT
    # 2) sem tool-call + keyword de SKILL -> skill
    s = _step(_router_with_skills(FakeLLM(route_to=None)).plan("faça o handoff desta sessão", [], "g"))
    assert s.name == "session-handoff" and s.type == ExecutionType.SKILL
    # 3) sem tool-call + sem keyword de skill -> keyword de AGENTE
    s = _step(_router_with_skills(FakeLLM(route_to=None)).plan("preciso de um vídeo novo", [], "g"))
    assert s.name == "mkvideos" and s.type == ExecutionType.AGENT


if __name__ == "__main__":
    test_plan_delegates_via_toolcalling()
    test_plan_fallback_keyword()
    test_two_step_domain_then_agent()
    test_fallback_keyword_de_skill()
    test_fallback_prioridade_skill_antes_de_agente()
    test_baseline_prioridade_atual()
    print("OK - test_intent_router")
