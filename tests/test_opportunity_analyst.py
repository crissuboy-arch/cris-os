"""
Testes da Fase 2: Decision Engine, Project Brain e roteamento determinístico
do Opportunity Analyst.

Nada aqui bate no Supabase real nem no Ollama -- Decision Engine e Project
Brain sao logica pura/SQLite local; o roteamento usa um FakeLLM que falha
propositalmente (garante que a interceptacao NUNCA chama o LLM).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from agents.orchestrator import AgentOrchestrator
from core.decision_engine import (
    SinalPlataforma,
    decidir,
    preparar_analise_afiliacao,
    preparar_analise_comercio,
    sugerir_formatos_produto_proprio,
)
from memory.layers import ProjectMemory
from memory.project_brain import ProjectBrain, ProjectBrainStore
from storage import SQLiteMemory


# ---------------------------------------------------------------------------
# Decision Engine (logica pura, sem rede)
# ---------------------------------------------------------------------------

def test_decidir_score_baixo_descarta():
    d = decidir(30, [])
    assert d.path == "DISCARD"
    assert "abaixo do minimo" in d.motivo


def test_decidir_sem_score_pede_mais_investigacao():
    d = decidir(None, [])
    assert d.path == "INVESTIGATE_MORE"


def test_decidir_sem_evidencia_externa_pede_mais_investigacao():
    sinais = [SinalPlataforma("tiktok", False, "Sem evidencia disponivel nesta fonte.")]
    d = decidir(90, sinais)
    assert d.path == "INVESTIGATE_MORE"
    assert d.fontes_com_evidencia == []
    assert "tiktok" in d.dados_faltantes


def test_decidir_uma_fonte_pede_mais_investigacao():
    sinais = [
        SinalPlataforma("tiktok", True, "3 resultados"),
        SinalPlataforma("instagram", False, "Sem evidencia disponivel nesta fonte."),
    ]
    d = decidir(90, sinais)
    assert d.path == "INVESTIGATE_MORE"
    assert d.fontes_com_evidencia == ["tiktok"]


def test_decidir_duas_fontes_recomenda_afiliacao():
    sinais = [
        SinalPlataforma("tiktok", True, "3 resultados"),
        SinalPlataforma("instagram", True, "2 resultados"),
    ]
    d = decidir(90, sinais)
    assert d.path == "AFFILIATE"
    assert d.evidence_level in ("medio", "alto")


def test_decidir_nunca_recomenda_produto_proprio_ou_comercio_sozinho():
    """Regra de negocio explicita: sem dado de fornecedor/modelo de negocio,
    o motor nunca decide CREATE_OWN_PRODUCT nem COMMERCE_RESALE sozinho."""
    casos = [
        (None, []),
        (10, []),
        (95, [SinalPlataforma(f, True, "x") for f in ("tiktok", "instagram", "youtube", "google_trends")]),
    ]
    for score, sinais in casos:
        d = decidir(score, sinais)
        assert d.path not in ("CREATE_OWN_PRODUCT", "COMMERCE_RESALE")


def test_sugerir_formatos_vazio_fora_de_create_own_product():
    from core.decision_engine import Decisao
    d = Decisao(path="AFFILIATE", motivo="x", evidence_level="medio")
    assert sugerir_formatos_produto_proprio(d) == []


def test_preparar_analise_afiliacao_nao_inventa_programa():
    resultado = preparar_analise_afiliacao([])
    assert "Sem evidencia" in resultado["programa_afiliados"]


def test_preparar_analise_comercio_nao_inventa_demanda():
    resultado = preparar_analise_comercio([])
    assert "Sem evidencia" in resultado["demanda"]


# ---------------------------------------------------------------------------
# Project Brain (SQLite local, isolado por tmp_path -- nao toca no banco real)
# ---------------------------------------------------------------------------

@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_project_brain.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def test_project_brain_create_and_load(brain_store):
    brain = brain_store.create(name="Oferta de teste", tipo="opportunity")
    assert brain.project_id.startswith("proj_")
    assert brain.decisao.decision_status == "PENDING_APPROVAL"

    carregado = brain_store.load(brain.project_id)
    assert carregado is not None
    assert carregado.identidade.name == "Oferta de teste"


def test_project_brain_save_e_upsert_nao_duplica(brain_store):
    brain = brain_store.create(name="Oferta X")
    brain.oportunidade.score = 91
    brain_store.save(brain)
    brain.oportunidade.score = 95
    brain_store.save(brain)

    carregado = brain_store.load(brain.project_id)
    assert carregado.oportunidade.score == 95
    assert len(brain_store.list_all()) == 1


def test_project_brain_roundtrip_preserva_campos_aninhados(brain_store):
    brain = brain_store.create(name="Oferta Y")
    brain.origem.source_offer_id = "12345"
    brain.oportunidade.signals = {"tiktok": {"encontrado": True}}
    brain.decisao.recommended_path = "INVESTIGATE_MORE"
    brain.registrar_run("opportunity_analyst", "teste")
    brain_store.save(brain)

    carregado = brain_store.load(brain.project_id)
    assert carregado.origem.source_offer_id == "12345"
    assert carregado.oportunidade.signals["tiktok"]["encontrado"] is True
    assert carregado.decisao.recommended_path == "INVESTIGATE_MORE"
    assert len(carregado.historico.agent_runs) == 1


def test_project_brain_load_projeto_inexistente_retorna_none(brain_store):
    assert brain_store.load("proj_nao_existe") is None


# ---------------------------------------------------------------------------
# Roteamento deterministico (sem LLM) -- Marco 1 preservado + Fase 2 nova
# ---------------------------------------------------------------------------

class FakeLLMQueBoom:
    """Garante que a interceptacao deterministica nunca chega a chamar o LLM."""

    def chat(self, messages, tools=None):
        raise AssertionError("LLM nao deveria ser chamado para comando determinístico!")

    def is_alive(self):
        return True


class FakeAgent:
    def __init__(self, name):
        self.name = name


def _orchestrator():
    agentes = [FakeAgent("scalaflow_intel"), FakeAgent("opportunity_analyst"), FakeAgent("produtividade")]
    return AgentOrchestrator(llm=FakeLLMQueBoom(), agents=agentes)


@pytest.mark.parametrize("mensagem", [
    "Mostre 5 ofertas escaladas",
    "Mostre minhas ofertas salvas",
    "Mostre meus favoritos",
    "Me de os 5 melhores anuncios do Brasil",
    "Me de os 5 melhores anuncios dos Estados Unidos",
])
def test_regressao_marco1_continua_indo_para_scalaflow_intel(mensagem):
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", mensagem)
    assert agente is not None
    assert agente.name == "scalaflow_intel"


@pytest.mark.parametrize("mensagem", [
    "Cris, investigue uma das minhas melhores ofertas.",
    "Cris, analise esta oportunidade.",
    "Cris, quais sinais temos dessa oportunidade?",
    "Cris, qual caminho faz sentido para essa oportunidade?",
    "Cris, investigue aquela oferta que salvei.",
])
def test_opportunity_analyst_intercepta_antes_do_scalaflow_e_do_llm(mensagem):
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", mensagem)
    assert agente is not None
    assert agente.name == "opportunity_analyst"


def test_continuacao_sem_palavra_inicial_fixa_quando_ultimo_agente_foi_opportunity():
    """'Cris, isso aparece no TikTok?' nao tem nenhuma keyword primaria do
    opportunity_analyst nem do scalaflow -- so deve rotear pra la porque a
    ULTIMA mensagem da conversa ja foi respondida pelo opportunity_analyst."""
    orc = _orchestrator()
    orc.last_agents["user1"] = "opportunity_analyst"
    agente = orc._escolher_agente("user1", "Cris, isso aparece no TikTok?")
    assert agente is not None
    assert agente.name == "opportunity_analyst"


def test_continuacao_nao_dispara_sem_contexto_previo():
    """A mesma frase, SEM o ultimo agente ter sido opportunity_analyst, nao
    pode ser sequestrada -- preserva o roteamento de 'tiktok' para outros
    agentes (ex.: social_media) via LLM/keyword normal."""
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Cris, isso aparece no TikTok?")
    assert agente is None or agente.name != "opportunity_analyst"


def test_continuacao_nao_sequestra_comando_scalaflow_mesmo_apos_opportunity():
    """Depois de investigar uma oportunidade, um comando CLARO de listagem
    (scalaflow_intel) continua funcionando -- nao fica preso no
    opportunity_analyst so porque foi o ultimo agente usado."""
    orc = _orchestrator()
    orc.last_agents["user1"] = "opportunity_analyst"
    agente = orc._escolher_agente("user1", "Mostre 5 ofertas escaladas")
    assert agente is not None
    assert agente.name == "scalaflow_intel"


# ---------------------------------------------------------------------------
# Resolucao de oferta por contexto/foco (sem rede -- so o caminho "sem foco")
# ---------------------------------------------------------------------------

def test_resolver_por_foco_sem_investigacao_previa_pede_para_indicar(monkeypatch):
    import tools.opportunity_tools as ot

    monkeypatch.setattr(ot, "_foco_atual_project_id", None)
    resultado = ot._resolver_por_foco_atual()
    assert isinstance(resultado, str)
    assert "Nao sei a qual oportunidade" in resultado


def test_resolver_oferta_com_referencia_contextual_usa_foco(monkeypatch):
    """'Isso aparece no TikTok?' deve consultar o foco atual, nao reiniciar
    a busca por 'melhor oferta' do zero."""
    import tools.opportunity_tools as ot

    monkeypatch.setattr(ot.settings, "SUPABASE_URL", "https://exemplo.supabase.co")
    monkeypatch.setattr(ot.settings, "SUPABASE_SERVICE_KEY", "chave-fake-de-teste")

    chamado = {}

    def fake_foco():
        chamado["usado"] = True
        return {"id": "abc", "score": 90}

    monkeypatch.setattr(ot, "_resolver_por_foco_atual", fake_foco)
    resultado = ot._resolver_oferta("Cris, isso aparece no TikTok?")
    assert chamado.get("usado") is True
    assert resultado == {"id": "abc", "score": 90}
