"""
Testes da Fase 8: roteamento determinístico do Execution Engine -- frases
do kickoff da Fase 8, sem colidir com Fases 1-7.
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
        FakeAgent("execution_engine"),
    ]
    return AgentOrchestrator(llm=FakeLLMQueBoom(), agents=agentes)


@pytest.mark.parametrize("mensagem", [
    "Execute o plano aprovado deste projeto.",
    "Qual o andamento deste projeto?",
    "Pause a execução.",
    "Continue a execução.",
    "Cancele a execução.",
])
def test_frases_do_kickoff_da_fase_8_devem_rotear_pro_execution_engine(mensagem):
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", mensagem)
    assert agente is not None
    assert agente.name == "execution_engine"


# ---------------------------------------------------------------------------
# Nao colisao com Fases 1-7
# ---------------------------------------------------------------------------

def test_produto_continua_no_product_architect():
    orc = _orchestrator()
    assert orc._escolher_agente("user1", "Crie o produto.").name == "product_architect"


def test_business_builder_continua_funcionando():
    orc = _orchestrator()
    assert orc._escolher_agente("user1", "Prepare o BusinessPlan deste projeto.").name == "business_builder"


def test_paid_traffic_continua_funcionando():
    orc = _orchestrator()
    assert orc._escolher_agente("user1", "Cris, crie o plano de tráfego deste projeto.").name == "paid_traffic_architect"


def test_campaign_executor_continua_funcionando():
    orc = _orchestrator()
    assert orc._escolher_agente("user1", "Cris, prepare a campanha deste projeto.").name == "campaign_executor"


def test_performance_agent_continua_funcionando():
    orc = _orchestrator()
    assert orc._escolher_agente("user1", "Como está a performance desta campanha?").name == "performance_agent"


def test_manifesto_continua_no_product_factory():
    orc = _orchestrator()
    assert orc._escolher_agente("user1", "Cris, mostre o manifesto.").name == "product_factory"


def test_execute_o_plano_aprovado_deste_produto_nao_cai_no_product_architect():
    """'produto' esta em `_PRODUCT_ARCHITECT_KEYWORDS` -- Execution Engine
    precisa ser checado ANTES."""
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Cris, execute o plano aprovado deste produto.")
    assert agente is not None
    assert agente.name == "execution_engine"


def test_conversa_comum_nao_e_capturada():
    orc = _orchestrator()
    for mensagem in [
        "Qual é a previsão do tempo hoje?",
        "Me ajuda a organizar minha agenda de amanhã?",
        "Investigue essa oportunidade que salvei.",
    ]:
        agente = orc._escolher_agente("user1", mensagem)
        assert agente is None or agente.name != "execution_engine"
