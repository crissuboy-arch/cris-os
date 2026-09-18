"""
Testes da Fase 5: roteamento deterministico do Paid Traffic Architect no
AgentOrchestrator -- incluindo as colisoes de palavra-chave explicitamente
citadas no pedido (product_architect via "produto", scalaflow_intel via
"anuncios") e as frases reais que devem/nao devem rotear pra ca.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from agents.orchestrator import AgentOrchestrator


class FakeLLMQueBoom:
    """Prova que o roteamento deterministico NUNCA passa pelo LLM/Ollama."""

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
        FakeAgent("produtividade"), FakeAgent("vendas"),
    ]
    return AgentOrchestrator(llm=FakeLLMQueBoom(), agents=agentes)


@pytest.mark.parametrize("mensagem", [
    "Cris, crie o plano de tráfego deste projeto.",
    "Monte uma estratégia de anúncios para este produto.",
    "Como vamos anunciar esse mini app?",
    "Quero o plano de Meta, Google e TikTok desse projeto.",
    "Mostre o plano de tráfego atual.",
    "Qual o status do plano de tráfego?",
])
def test_frases_reais_devem_rotear_pro_paid_traffic_architect(mensagem):
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", mensagem)
    assert agente is not None
    assert agente.name == "paid_traffic_architect"


@pytest.mark.parametrize("mensagem, agente_esperado", [
    ("Mostre os melhores anúncios dos EUA.", "scalaflow_intel"),
    ("Mostre minhas ofertas salvas.", "scalaflow_intel"),
    ("Mostre o manifesto.", "product_factory"),
    ("Crie o produto.", "product_architect"),
    ("Qual produto devemos criar?", "product_architect"),
])
def test_frases_reais_nao_devem_cair_no_paid_traffic_architect(mensagem, agente_esperado):
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", mensagem)
    assert agente is not None
    assert agente.name == agente_esperado
    assert agente.name != "paid_traffic_architect"


def test_meta_sozinha_no_sentido_de_objetivo_nao_dispara_paid_traffic():
    """'meta' de proposito NAO entra na co-ocorrencia com 'plano' (colide com
    'meta' no sentido de objetivo/goal) -- so a frase completa 'meta ads'
    conta."""
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Preciso de um plano para bater minha meta de vendas este mês.")
    assert agente is None or agente.name != "paid_traffic_architect"


def test_meta_ads_frase_completa_dispara_paid_traffic():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Quero anunciar no Meta Ads para este produto.")
    assert agente is not None
    assert agente.name == "paid_traffic_architect"


def test_conversa_comum_nao_e_capturada_pelo_paid_traffic():
    orc = _orchestrator()
    for mensagem in [
        "Qual é a previsão do tempo hoje?",
        "Me ajuda a organizar minha agenda de amanhã?",
        "Preciso de uma proposta comercial pro meu cliente.",
    ]:
        agente = orc._escolher_agente("user1", mensagem)
        assert agente is None or agente.name != "paid_traffic_architect"


def test_regressao_fase4_manifesto_e_producao_continuam_funcionando():
    orc = _orchestrator()
    assert orc._escolher_agente("user1", "Cris, prepare o plano de produção.").name == "product_factory"
    assert orc._escolher_agente("user1", "Cris, transforme esse produto aprovado em um negócio.").name == "business_builder"
