"""
Testes da Fase 7: roteamento determinístico ampliado do Business Builder --
frases explicitamente pedidas no kickoff da Fase 7, sem depender
exclusivamente de "negócio"/"monetiz", e sem colidir com Fases 1-6.
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
    ]
    return AgentOrchestrator(llm=FakeLLMQueBoom(), agents=agentes)


@pytest.mark.parametrize("mensagem", [
    "Analise o modelo de negócio deste projeto.",
    "Monte a estratégia de monetização deste produto.",
    "Transforme esta oportunidade em um plano de negócio.",
    "Prepare o BusinessPlan deste projeto.",
    "Qual seria o posicionamento deste produto?",
    "Qual modelo de negócio faz mais sentido para esta oportunidade?",
])
def test_frases_do_kickoff_da_fase_7_devem_rotear_pro_business_builder(mensagem):
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", mensagem)
    assert agente is not None
    assert agente.name == "business_builder"


# ---------------------------------------------------------------------------
# Nao colisao com Fases 1-6 (roteamento existente preservado)
# ---------------------------------------------------------------------------

def test_produto_sozinho_continua_no_product_architect():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Crie o produto.")
    assert agente is not None
    assert agente.name == "product_architect"


def test_plano_de_trafego_continua_no_paid_traffic_architect():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Cris, crie o plano de tráfego deste projeto.")
    assert agente is not None
    assert agente.name == "paid_traffic_architect"


def test_prepare_a_campanha_continua_no_campaign_executor():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Cris, prepare a campanha deste projeto.")
    assert agente is not None
    assert agente.name == "campaign_executor"


def test_performance_continua_no_performance_agent():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Como está a performance desta campanha?")
    assert agente is not None
    assert agente.name == "performance_agent"


def test_mostre_o_manifesto_continua_no_product_factory():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Cris, mostre o manifesto.")
    assert agente is not None
    assert agente.name == "product_factory"


def test_conversa_comum_nao_e_capturada_pelo_business_builder():
    orc = _orchestrator()
    for mensagem in [
        "Qual é a previsão do tempo hoje?",
        "Me ajuda a organizar minha agenda de amanhã?",
        "Investigue essa oportunidade que salvei.",
    ]:
        agente = orc._escolher_agente("user1", mensagem)
        assert agente is None or agente.name != "business_builder"
