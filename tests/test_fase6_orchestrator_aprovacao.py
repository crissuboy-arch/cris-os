"""
Testes da Fase 6 (correção estrutural): integração do AgentOrchestrator com
o Approval Router -- a resolução contextual roda ANTES de qualquer seleção
de agente/LLM, mas NUNCA rouba a continuação já funcional do Product
Architect (Fase 3, baseada em `last_agents`).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import core.approval_router as approval_router
from agents.orchestrator import AgentOrchestrator
from core.models import IncomingMessage


class FakeLLMQueBoom:
    def chat(self, messages, tools=None):
        raise AssertionError("LLM nao deveria ser chamado para aprovacao contextual!")

    def is_alive(self):
        return True


class FakeAgent:
    def __init__(self, name):
        self.name = name

    def generate(self, texto, session):
        return f"[{self.name}] resposta generica para: {texto}"


def _orchestrator():
    agentes = [
        FakeAgent("product_architect"), FakeAgent("paid_traffic_architect"),
        FakeAgent("campaign_executor"),
    ]
    return AgentOrchestrator(llm=FakeLLMQueBoom(), agents=agentes)


def test_aprovacao_contextual_resolvida_bypassa_selecao_de_agente(monkeypatch):
    orc = _orchestrator()

    chamadas = []

    def _fake_resolver(texto, session, pending_store, brain_store):
        chamadas.append((texto, session))
        return "Plano de tráfego aprovado.\n\nStatus: APPROVED"

    monkeypatch.setattr(approval_router, "resolver_aprovacao_contextual", _fake_resolver)
    monkeypatch.setattr("core.approval_router.eh_mensagem_de_aprovacao_ou_rejeicao", lambda t: True)

    incoming = IncomingMessage(channel="telegram", sender_id="1", text="Aprovado")
    resposta = orc.handle(incoming)

    assert resposta == "Plano de tráfego aprovado.\n\nStatus: APPROVED"
    assert chamadas == [("Aprovado", "telegram:1")]


def test_sem_pendencia_e_sem_ultimo_agente_devolve_mensagem_do_router(monkeypatch):
    orc = _orchestrator()

    def _fake_resolver(texto, session, pending_store, brain_store):
        return "Não há uma aprovação pendente inequívoca neste momento."

    monkeypatch.setattr(approval_router, "resolver_aprovacao_contextual", _fake_resolver)

    incoming = IncomingMessage(channel="telegram", sender_id="1", text="Aprovado")
    resposta = orc.handle(incoming)
    assert "não há uma aprovação pendente" in resposta.lower()


def test_nao_intercepta_mensagem_que_nao_e_aprovacao():
    orc = _orchestrator()
    incoming = IncomingMessage(channel="telegram", sender_id="1", text="Cris, crie o plano de tráfego deste projeto.")
    resposta = orc.handle(incoming)
    assert "paid_traffic_architect" in resposta


def test_nao_rouba_continuacao_do_product_architect(monkeypatch):
    """Se o ULTIMO agente foi o product_architect e a mensagem bate no
    padrao de continuidade dele ('aprovado' esta em
    `_PRODUCT_ARCHITECT_CONTINUACAO_KEYWORDS`), o Approval Router NUNCA e
    chamado -- o fluxo antigo (ja funcional) deve prevalecer."""
    orc = _orchestrator()
    orc.last_agents["1"] = "product_architect"

    def _boom(*a, **k):
        raise AssertionError("Approval Router nao deveria ser chamado aqui -- "
                              "e continuacao do Product Architect")
    monkeypatch.setattr(approval_router, "resolver_aprovacao_contextual", _boom)

    incoming = IncomingMessage(channel="telegram", sender_id="1", text="Aprovado")
    resposta = orc.handle(incoming)
    assert "product_architect" in resposta


def test_campaign_executor_intercepta_aprovado_quando_nao_e_continuacao_de_product_architect(monkeypatch):
    """Mesmo com um ULTIMO agente diferente de product_architect (ex.:
    campaign_executor), o Approval Router e chamado normalmente -- ele que
    decide, via pendencia persistida, a qual artefato a aprovacao se
    refere."""
    orc = _orchestrator()
    orc.last_agents["1"] = "campaign_executor"

    def _fake_resolver(texto, session, pending_store, brain_store):
        return "Especificação de campanha aprovada.\n\nStatus: APPROVED"

    monkeypatch.setattr(approval_router, "resolver_aprovacao_contextual", _fake_resolver)

    incoming = IncomingMessage(channel="telegram", sender_id="1", text="Aprovado")
    resposta = orc.handle(incoming)
    assert "Especificação de campanha aprovada" in resposta
