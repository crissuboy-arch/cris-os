"""
Testes da Fase 4: camada de Tools do Business Builder e da Product Factory
(sob demanda pelo Telegram) -- gate de seguranca (item 12: nunca avanca sem
produto aprovado), reaproveitamento de foco por sessao (sem repetir
project_id), cache (nao gasta LLM de novo em cima do que ja foi calculado) e
ausencia de chamadas externas/publicacao/gasto.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

import pytest

import tools.business_builder_tools as bbt
import tools.product_factory_tools as pft
from memory.layers import ProjectMemory
from memory.project_brain import ProductBlueprint, ProjectBrainStore
from storage import SQLiteMemory


# ---------------------------------------------------------------------------
# Regressao de padrao ja visto 3x na Fase 3: a Tool precisa reconhecer a
# MESMA mensagem que o orchestrator ja roteou pro agente certo -- senao o
# SpecialistAgent cai no LLM generico mesmo com o agente certo escolhido.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mensagem", [
    "Cris, transforme esse produto aprovado em um negócio.",
    "Cris, monte a oferta desse produto.",
    "Cris, como vamos monetizar esse produto?",
    "Cris, mostre o plano de negócio e as principais pendências.",
])
def test_tool_business_builder_reconhece_frases_do_orchestrator(mensagem):
    tool = bbt.get_tools()[0]
    assert tool.matches(mensagem)


@pytest.mark.parametrize("mensagem", [
    "Cris, prepare o plano de produção.",
    "Cris, o que precisa ser produzido para lançar esse produto?",
    "Cris, mostre o plano de produção.",
    "Cris, quais artefatos esse projeto precisa?",
])
def test_tool_product_factory_reconhece_frases_do_orchestrator(mensagem):
    tool = pft.get_tools()[0]
    assert tool.matches(mensagem)


@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_fase4_tools.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def _brain_com_blueprint(store, tipo="curso", status="PENDING_APPROVAL"):
    brain = store.create(name="Oferta Teste", tipo="opportunity")
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id,
        recommended_product_type=tipo,
        target_audience="Iniciantes",
        decision_status=status,
    )
    store.save(brain)
    return brain


class FakeLLMEconomico:
    _provider_name = "fake:economico"

    def __init__(self, payload):
        self.payload = payload
        self.chamadas = 0

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        self.chamadas += 1
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False))

    def is_alive(self):
        return True


_PAYLOAD_NEGOCIO_MINIMO = {
    "business_model": "Assinatura", "value_proposition": "Aprenda rapido",
    "target_audience": "Iniciantes", "problem": "Nao sabem por onde comecar",
    "solution": "Curso guiado", "positioning": None, "mechanism": None,
    "main_offer": "Curso", "monetization_format": "Assinatura",
    "price": None, "price_is_hypothesis": True, "bonuses": [], "order_bump": None,
    "upsell": [], "downsell": [], "acquisition_channels": [], "sales_channels": [],
    "sales_page_structure": None, "headline": None, "promise": None,
    "key_arguments": [], "objections": [], "cta": None, "funnel_structure": None,
    "email_sequence": [], "content_strategy": None, "content_channels": [],
    "launch_strategy": None, "plan_30_days": [], "assumptions": [],
    "missing_evidence": [], "risks": [], "dependencies": [], "next_steps": [],
}


# ---------------------------------------------------------------------------
# Gate de seguranca (Fase 4, item 12) -- nunca avanca sem produto aprovado
# ---------------------------------------------------------------------------

def test_business_builder_bloqueia_sem_foco(monkeypatch, brain_store):
    monkeypatch.setattr(bbt, "get_foco_atual", lambda session: None)
    resposta = bbt.gerenciar_negocio("transforme esse produto em um negócio", "telegram:1")
    assert "não sei a qual projeto" in resposta.lower()


def test_business_builder_bloqueia_produto_nao_aprovado(monkeypatch, brain_store):
    brain = _brain_com_blueprint(brain_store, status="PENDING_APPROVAL")
    monkeypatch.setattr(bbt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(bbt, "get_project_brain_store", lambda: brain_store)

    resposta = bbt.gerenciar_negocio("transforme esse produto em um negócio", "telegram:1")
    assert "ainda não foi aprovado" in resposta.lower()


def test_product_factory_bloqueia_produto_nao_aprovado(monkeypatch, brain_store):
    brain = _brain_com_blueprint(brain_store, status="PENDING_APPROVAL")
    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)

    resposta = pft.gerenciar_producao("prepare o plano de produção", "telegram:1")
    assert "ainda não foi aprovado" in resposta.lower()


# ---------------------------------------------------------------------------
# Fluxo feliz + persistencia + cache (nao gasta LLM de novo)
# ---------------------------------------------------------------------------

def test_business_builder_gera_e_persiste_e_reaproveita_foco(monkeypatch, brain_store):
    brain = _brain_com_blueprint(brain_store, status="APPROVED")
    monkeypatch.setattr(bbt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(bbt, "get_project_brain_store", lambda: brain_store)
    fake = FakeLLMEconomico(_PAYLOAD_NEGOCIO_MINIMO)
    monkeypatch.setattr(bbt, "_get_llm_economico", lambda: fake)

    resposta = bbt.gerenciar_negocio("transforme esse produto em um negócio", "telegram:1")
    assert "PLANO DE NEGÓCIO" in resposta
    assert fake.chamadas == 1

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.business_plan is not None
    assert recarregado.business_plan.business_model == "Assinatura"


def test_business_builder_nao_gasta_llm_de_novo_ao_mostrar_plano_ja_calculado(monkeypatch, brain_store):
    brain = _brain_com_blueprint(brain_store, status="APPROVED")
    monkeypatch.setattr(bbt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(bbt, "get_project_brain_store", lambda: brain_store)
    fake = FakeLLMEconomico(_PAYLOAD_NEGOCIO_MINIMO)
    monkeypatch.setattr(bbt, "_get_llm_economico", lambda: fake)

    bbt.gerenciar_negocio("transforme esse produto em um negócio", "telegram:1")
    assert fake.chamadas == 1

    def _boom():
        raise AssertionError("Nao deveria chamar o LLM de novo -- plano ja calculado")
    monkeypatch.setattr(bbt, "_get_llm_economico", _boom)

    resposta = bbt.gerenciar_negocio("mostre o plano de negócio e as pendências", "telegram:1")
    assert "PLANO DE NEGÓCIO" in resposta


def test_product_factory_prepara_e_persiste_plano_e_manifest(monkeypatch, brain_store):
    brain = _brain_com_blueprint(brain_store, tipo="ebook", status="APPROVED")
    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pft, "_get_llm_economico", lambda: None)  # fallback deterministico, sem custo

    resposta = pft.gerenciar_producao("prepare o plano de produção", "telegram:1")
    assert "PLANO DE PRODUÇÃO" in resposta

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.production_plan is not None
    assert recarregado.artifact_manifest is not None


def test_product_factory_reaproveita_plano_ja_preparado(monkeypatch, brain_store):
    brain = _brain_com_blueprint(brain_store, tipo="ebook", status="APPROVED")
    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pft, "_get_llm_economico", lambda: None)

    pft.gerenciar_producao("prepare o plano de produção", "telegram:1")

    def _boom(*args, **kwargs):
        raise AssertionError("Nao deveria recalcular a Product Factory de novo")
    monkeypatch.setattr(pft, "preparar_plano_producao", _boom)

    resposta = pft.gerenciar_producao("mostre o plano de produção", "telegram:1")
    assert "PLANO DE PRODUÇÃO" in resposta


def test_quais_artefatos_mostra_manifest(monkeypatch, brain_store):
    brain = _brain_com_blueprint(brain_store, tipo="ebook", status="APPROVED")
    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pft, "_get_llm_economico", lambda: None)

    pft.gerenciar_producao("prepare o plano de produção", "telegram:1")
    resposta = pft.gerenciar_producao("quais artefatos esse projeto precisa?", "telegram:1")
    assert "MANIFESTO DO PROJETO" in resposta
    assert "status_producao: IN_PRODUCTION" in resposta


def test_quais_artefatos_sem_plano_preparado_mostra_manifesto_honesto(monkeypatch, brain_store):
    """GET_CURRENT_PROJECT_MANIFEST (Fase 4 -- correcao pos-teste real) e uma
    leitura PURA -- nunca bloqueia so porque o plano de producao ainda nao
    foi preparado, so mostra "vazio" pra essa secao (nunca inventa)."""
    brain = _brain_com_blueprint(brain_store, tipo="ebook", status="APPROVED")
    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)

    resposta = pft.gerenciar_producao("quais artefatos esse projeto precisa?", "telegram:1")
    assert "MANIFESTO DO PROJETO" in resposta
    assert "status_producao: None" in resposta


# ---------------------------------------------------------------------------
# Ausencia de acoes externas / publicacao / gasto (estrutural)
# ---------------------------------------------------------------------------

def test_nenhuma_chamada_http_e_feita_quando_llm_e_fake_ou_none(monkeypatch, brain_store):
    """Nem Business Builder nem Product Factory devem tocar em `requests`
    diretamente -- toda comunicacao externa passa exclusivamente pelo
    provider de LLM (aqui, Fake/None), nunca por uma chamada de rede solta."""
    import requests

    def _boom(*args, **kwargs):
        raise AssertionError("Nenhuma chamada HTTP deveria acontecer aqui")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    brain = _brain_com_blueprint(brain_store, status="APPROVED")
    monkeypatch.setattr(bbt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(bbt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(bbt, "_get_llm_economico", lambda: FakeLLMEconomico(_PAYLOAD_NEGOCIO_MINIMO))
    bbt.gerenciar_negocio("transforme esse produto em um negócio", "telegram:1")

    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pft, "_get_llm_economico", lambda: None)
    pft.gerenciar_producao("prepare o plano de produção", "telegram:1")
