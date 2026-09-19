"""
Testes da Fase 6: roteamento determinístico do Campaign Executor e do
Performance Agent no AgentOrchestrator -- incluindo as colisões explícitas
citadas no pedido (product_architect via "produto", opportunity_analyst via
"analise", paid_traffic_architect via "campanha paga"/"plano de campanha")
e paráfrases reais.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from agents.orchestrator import AgentOrchestrator


class FakeLLMQueBoom:
    """Prova que o roteamento determinístico NUNCA passa pelo LLM/Ollama."""

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
        FakeAgent("produtividade"), FakeAgent("vendas"),
    ]
    return AgentOrchestrator(llm=FakeLLMQueBoom(), agents=agentes)


# ---------------------------------------------------------------------------
# Paráfrases reais (requisito O) -- Campaign Executor
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mensagem", [
    "Cris, prepare a campanha deste projeto.",
    "Cris, monte a campanha para este projeto.",
    "Cris, crie a campanha deste projeto com orçamento de 20 euros por dia.",
    "Cris, crie o rascunho da campanha.",
    "Cris, estruture a campanha para este projeto.",
    "Cris, mostre como esta campanha ficaria antes de publicar.",
    "Preview da campanha, por favor.",
    "Qual o status da campanha?",
])
def test_frases_reais_devem_rotear_pro_campaign_executor(mensagem):
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", mensagem)
    assert agente is not None
    assert agente.name == "campaign_executor"


# ---------------------------------------------------------------------------
# Paráfrases reais -- Performance Agent (requisito O)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mensagem", [
    "Cris, como está a campanha?",
    "Cris, como está a performance desta campanha?",
    "Analise os resultados desta campanha.",
    "Veja a performance da campanha, por favor.",
    "Qual a performance deste projeto?",
])
def test_frases_reais_devem_rotear_pro_performance_agent(mensagem):
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", mensagem)
    assert agente is not None
    assert agente.name == "performance_agent"


# ---------------------------------------------------------------------------
# Nao colisao com intents das Fases 1-5 (requisito P)
# ---------------------------------------------------------------------------

def test_campanha_paga_e_plano_de_campanha_continuam_no_paid_traffic():
    """Frases ja mapeadas pro Paid Traffic Architect (Fase 5) desde antes da
    Fase 6 -- NUNCA devem migrar pro Campaign Executor."""
    orc = _orchestrator()
    for mensagem in ["Monte o plano de campanha para este produto.", "Quero anúncios pagos, campanha paga no Meta."]:
        agente = orc._escolher_agente("user1", mensagem)
        assert agente is not None
        assert agente.name == "paid_traffic_architect"


def test_analise_de_oportunidade_continua_no_opportunity_analyst():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Analise essa oportunidade que salvei.")
    assert agente is not None
    assert agente.name == "opportunity_analyst"


def test_prepare_a_campanha_desse_produto_nao_cai_no_product_architect():
    """'produto' esta em `_PRODUCT_ARCHITECT_KEYWORDS` -- Campaign Executor
    precisa ser checado ANTES."""
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Cris, prepare a campanha desse produto.")
    assert agente is not None
    assert agente.name == "campaign_executor"


def test_manifesto_producao_e_negocio_continuam_funcionando():
    orc = _orchestrator()
    assert orc._escolher_agente("user1", "Cris, mostre o manifesto.").name == "product_factory"
    assert orc._escolher_agente("user1", "Cris, transforme esse produto aprovado em um negócio.").name == "business_builder"
    assert orc._escolher_agente("user1", "Cris, crie o plano de tráfego deste projeto.").name == "paid_traffic_architect"


def test_status_do_plano_de_trafego_nao_colide_com_status_da_campanha():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Qual o status do plano de tráfego?")
    assert agente is not None
    assert agente.name == "paid_traffic_architect"


def test_conversa_comum_nao_e_capturada():
    orc = _orchestrator()
    for mensagem in [
        "Qual é a previsão do tempo hoje?",
        "Me ajuda a organizar minha agenda de amanhã?",
        "Preciso de uma proposta comercial pro meu cliente.",
    ]:
        agente = orc._escolher_agente("user1", mensagem)
        assert agente is None or agente.name not in {"campaign_executor", "performance_agent"}
