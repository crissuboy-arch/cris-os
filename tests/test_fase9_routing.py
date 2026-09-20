"""
Testes da Fase 9: roteamento determinístico do Market Intelligence -- sem
colidir com Fases 1-8.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from agents.orchestrator import AgentOrchestrator


class FakeLLMQueBoom:
    def chat(self, messages, tools=None):
        raise AssertionError("LLM nao deveria ser chamado para comando determinístico!")

    def is_alive(self):
        return True


class FakeAgent:
    def __init__(self, name):
        self.name = name


def _orchestrator():
    agentes = [
        FakeAgent("scalaflow_intel"), FakeAgent("opportunity_analyst"),
        FakeAgent("product_architect"), FakeAgent("business_builder"),
        FakeAgent("product_factory"), FakeAgent("paid_traffic_architect"),
        FakeAgent("campaign_executor"), FakeAgent("performance_agent"),
        FakeAgent("execution_engine"), FakeAgent("market_intelligence"),
    ]
    return AgentOrchestrator(llm=FakeLLMQueBoom(), agents=agentes)


@pytest.mark.parametrize("mensagem", [
    "Mostre a inteligência de mercado deste projeto.",
    "Quais handoffs de inteligência este projeto já recebeu?",
    "Market intelligence deste projeto.",
])
def test_frases_de_market_intelligence_roteiam_corretamente(mensagem):
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", mensagem)
    assert agente is not None
    assert agente.name == "market_intelligence"


def test_inteligencia_de_mercado_deste_produto_nao_cai_no_product_architect():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Mostre a inteligência de mercado deste produto.")
    assert agente is not None
    assert agente.name == "market_intelligence"


# ---------------------------------------------------------------------------
# Nao colisao com Fases 1-8
# ---------------------------------------------------------------------------

def test_execution_engine_continua_funcionando():
    orc = _orchestrator()
    assert orc._escolher_agente("user1", "Execute o plano aprovado deste projeto.").name == "execution_engine"


def test_performance_agent_continua_funcionando():
    orc = _orchestrator()
    assert orc._escolher_agente("user1", "Como está a performance desta campanha?").name == "performance_agent"


def test_business_builder_continua_funcionando():
    orc = _orchestrator()
    assert orc._escolher_agente("user1", "Prepare o BusinessPlan deste projeto.").name == "business_builder"


def test_investigar_oportunidade_continua_no_opportunity_analyst():
    orc = _orchestrator()
    assert orc._escolher_agente("user1", "Investigue essa oportunidade que salvei.").name == "opportunity_analyst"


def test_conversa_comum_nao_e_capturada():
    orc = _orchestrator()
    for mensagem in [
        "Qual é a previsão do tempo hoje?",
        "Me ajuda a organizar minha agenda de amanhã?",
    ]:
        agente = orc._escolher_agente("user1", mensagem)
        assert agente is None or agente.name != "market_intelligence"
