"""
Testes da Fase 4: roteamento deterministico do Business Builder e da Product
Factory no AgentOrchestrator -- incluindo as colisoes de palavra-chave com
agentes ja existentes (Fase 3: product_architect; Fase 2/Marco 1:
scalaflow_intel/opportunity_analyst) que o proprio pedido da Fase 4 cita como
exemplo ("transforme esse produto aprovado em um negocio" contem "produto").
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
        FakeAgent("product_factory"), FakeAgent("produtividade"),
        FakeAgent("vendas"),
    ]
    return AgentOrchestrator(llm=FakeLLMQueBoom(), agents=agentes)


@pytest.mark.parametrize("mensagem", [
    "Cris, transforme esse produto aprovado em um negócio.",
    "Cris, transforme o produto aprovado em um negócio.",
    "Cris, monte o modelo de negócio desse produto.",
    "Cris, monte a oferta desse produto.",
    "Cris, como vamos monetizar esse produto?",
])
def test_business_builder_intercepta_antes_do_product_architect(mensagem):
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", mensagem)
    assert agente is not None
    assert agente.name == "business_builder"


@pytest.mark.parametrize("mensagem", [
    "Cris, prepare o plano de produção.",
    "Cris, o que precisa ser produzido para lançar esse produto?",
    "Cris, mostre o plano de produção.",
    "Cris, quais artefatos esse projeto precisa?",
])
def test_product_factory_intercepta_antes_do_product_architect(mensagem):
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", mensagem)
    assert agente is not None
    assert agente.name == "product_factory"


@pytest.mark.parametrize("mensagem", [
    "Cris, mostre somente o manifesto atual deste projeto. Não gere nem altere nada.",
    "Cris, mostre o manifesto.",
    "Qual o status deste projeto?",
    "Mostre a estrutura atual do projeto.",
])
def test_manifesto_intercepta_deterministicamente_regressao_bug_real(mensagem):
    """Bug real do teste no Telegram: a frase exata acima caiu no assistente
    generico ("Não tenho acesso ao manifesto...") porque o orchestrator nao
    reconhecia 'manifesto'/'status do projeto' -- so a Tool reconhecia."""
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", mensagem)
    assert agente is not None
    assert agente.name == "product_factory"


def test_conversa_comum_nao_e_capturada_pela_rota_de_manifesto():
    """A nova deteccao de 'status do projeto'/'estrutura atual' nao pode
    sequestrar conversas comuns que nao tem nada a ver com manifesto."""
    orc = _orchestrator()
    for mensagem in [
        "Qual é a previsão do tempo hoje?",
        "Como está o status da minha entrega dos Correios?",
        "Me ajuda a organizar minha agenda de amanhã?",
    ]:
        agente = orc._escolher_agente("user1", mensagem)
        assert agente is None or agente.name != "product_factory"


def test_mostre_o_plano_de_negocio_e_pendencias_vai_pro_business_builder():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Cris, mostre o plano de negócio e as principais pendências.")
    assert agente is not None
    assert agente.name == "business_builder"


def test_oferta_sozinha_continua_indo_pro_scalaflow_regressao():
    """'oferta'/'ofertas' sozinha (sem frase de Business Builder) continua
    sendo o scalaflow_intel -- regressao da Fase 2/Marco 1, nao pode quebrar."""
    orc = _orchestrator()
    for mensagem in ["Quais são as ofertas de hoje?", "Mostre minhas ofertas salvas"]:
        agente = orc._escolher_agente("user1", mensagem)
        assert agente is not None
        assert agente.name == "scalaflow_intel"


def test_investigar_oportunidade_continua_indo_pro_opportunity_analyst_regressao():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Investigue minha melhor oferta")
    assert agente is not None
    assert agente.name == "opportunity_analyst"


def test_proposta_comercial_continua_indo_pro_vendas_regressao():
    from agents.orchestrator import AgentOrchestrator as AO
    assert AO._rotear_por_keyword("preciso de uma proposta comercial") == "vendas"
