"""
Testes da correcao da Fase 3: reconhecimento deterministico de link da Meta
Ads Library, contexto persistente entre mensagens, e selecao de "melhor
oportunidade" por completude de evidencia (nao so score bruto).

Sem rede real -- Supabase e sempre monkeypatchado.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from agents.orchestrator import AgentOrchestrator
from core.decision_engine import decidir
from memory.layers import ProjectMemory
from memory.project_brain import ProjectBrainStore
from storage import SQLiteMemory
from tools.opportunity_tools import (
    _extrair_ad_library_id,
    _pontuar_viabilidade,
    _selecionar_melhor_oportunidade,
    detectar_ad_library_id,
)

URL_REAL = "https://www.facebook.com/ads/library/?id=859300870484371"
ID_REAL = "859300870484371"
SESSAO_TESTE = "telegram:6460872429"


# ---------------------------------------------------------------------------
# Reconhecimento/extracao do link
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto,esperado", [
    (URL_REAL, ID_REAL),
    (f"olha esse anuncio: {URL_REAL} o que acha?", ID_REAL),
    ("859300870484371", ID_REAL),
    ("Investigue minha melhor oferta", None),
    ("Aprovado.", None),
    ("", None),
])
def test_extrair_ad_library_id(texto, esperado):
    assert _extrair_ad_library_id(texto) == esperado


def test_detectar_ad_library_id_e_alias_publico():
    assert detectar_ad_library_id(URL_REAL) == ID_REAL


# ---------------------------------------------------------------------------
# Roteamento: link nunca cai no LLM generico
# ---------------------------------------------------------------------------

class FakeLLMQueBoom:
    def chat(self, messages, tools=None):
        raise AssertionError("LLM NAO deveria ser chamado para um link reconhecido!")

    def is_alive(self):
        return True


class FakeAgent:
    def __init__(self, name):
        self.name = name


def _orchestrator():
    agentes = [FakeAgent("scalaflow_intel"), FakeAgent("opportunity_analyst"), FakeAgent("product_architect")]
    return AgentOrchestrator(llm=FakeLLMQueBoom(), agents=agentes)


def test_link_bare_roteia_para_opportunity_analyst_sem_llm():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", URL_REAL)
    assert agente is not None
    assert agente.name == "opportunity_analyst"


def test_id_numerico_cru_roteia_para_opportunity_analyst_sem_llm():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "o anuncio e esse aqui: 859300870484371")
    assert agente is not None
    assert agente.name == "opportunity_analyst"


def test_link_com_palavra_produto_ainda_assim_roteia_deterministicamente():
    """Link + palavra do product_architect -- continua sem LLM (so muda QUAL
    agente determinístico ganha, product_architect por ja ter prioridade)."""
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", f"{URL_REAL} que produto criamos com isso?")
    assert agente is not None
    assert agente.name in ("opportunity_analyst", "product_architect")


def test_mensagem_sem_link_e_sem_keyword_nao_forca_opportunity():
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Oi, tudo bem?")
    assert agente is None or agente.name not in ("opportunity_analyst", "scalaflow_intel", "product_architect")


# ---------------------------------------------------------------------------
# Resolucao do anuncio por ID (existente / inexistente) -- Supabase mockado
# ---------------------------------------------------------------------------

def test_resolver_oferta_por_id_existente(monkeypatch):
    import tools.opportunity_tools as ot

    monkeypatch.setattr(ot.settings, "SUPABASE_URL", "https://exemplo.supabase.co")
    monkeypatch.setattr(ot.settings, "SUPABASE_SERVICE_KEY", "chave-fake")

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return [{"id": "x", "ad_library_id": ID_REAL, "advertiser": "Anunciante X", "score": 91}]

    monkeypatch.setattr(ot.requests, "get", lambda *a, **kw: FakeResp())
    resultado = ot._resolver_oferta(URL_REAL)
    assert isinstance(resultado, dict)
    assert resultado["ad_library_id"] == ID_REAL


def test_resolver_oferta_por_id_inexistente_nao_inventa(monkeypatch):
    import tools.opportunity_tools as ot

    monkeypatch.setattr(ot.settings, "SUPABASE_URL", "https://exemplo.supabase.co")
    monkeypatch.setattr(ot.settings, "SUPABASE_SERVICE_KEY", "chave-fake")

    class FakeRespVazia:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return []

    monkeypatch.setattr(ot.requests, "get", lambda *a, **kw: FakeRespVazia())
    resultado = ot._resolver_oferta("https://www.facebook.com/ads/library/?id=999999999999999")
    assert isinstance(resultado, str)
    assert "Nao encontrei" in resultado or "não encontrei" in resultado.lower()
    assert "999999999999999" in resultado


# ---------------------------------------------------------------------------
# Foco/contexto persistente entre mensagens (Opportunity Analyst -> Decision
# Engine -> Product Architect usando o MESMO projeto)
# ---------------------------------------------------------------------------

@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_meta_link.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def test_investigar_estabelece_foco_e_persiste_no_project_brain(monkeypatch, brain_store):
    import tools.opportunity_tools as ot

    monkeypatch.setattr(ot, "_get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ot, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ot.settings, "SUPABASE_URL", "https://exemplo.supabase.co")
    monkeypatch.setattr(ot.settings, "SUPABASE_SERVICE_KEY", "chave-fake")

    oferta = {
        "id": "x", "ad_library_id": ID_REAL, "advertiser": "Velas Artesanais",
        "headline": "Aprenda a vender velas artesanais", "copy": "Curso completo " * 10,
        "keyword": "velas artesanais", "niche": "Geral", "score": 94, "country": "US",
        "platform": "FACEBOOK", "ad_url": URL_REAL,
    }

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return [oferta]

    monkeypatch.setattr(ot.requests, "get", lambda *a, **kw: FakeResp())

    resultado = ot.investigar_oportunidade(URL_REAL, SESSAO_TESTE)
    assert "Projeto:" in resultado

    foco = ot.get_foco_atual(SESSAO_TESTE)
    assert foco is not None
    brain = brain_store.load(foco)
    assert brain.origem.source_offer_id == ID_REAL
    assert brain.oportunidade.score == 94


def test_contexto_sobrevive_para_decision_engine_e_product_architect(monkeypatch, brain_store):
    """Depois que o Opportunity Analyst investiga por link, o Decision Engine
    e o Product Architect devem operar sobre o MESMO ProjectBrain (mesmo
    project_id) -- nao um novo, nao um generico."""
    import core.product_architect as pa
    import tools.opportunity_tools as ot
    import tools.product_architect_tools as pat

    monkeypatch.setattr(ot, "_get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ot, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pat, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ot.settings, "SUPABASE_URL", "https://exemplo.supabase.co")
    monkeypatch.setattr(ot.settings, "SUPABASE_SERVICE_KEY", "chave-fake")

    oferta = {
        "id": "x", "ad_library_id": ID_REAL, "advertiser": "Velas Artesanais",
        "headline": "Aprenda a vender velas artesanais", "copy": "Curso completo " * 10,
        "keyword": "velas artesanais", "niche": "Geral", "score": 94, "country": "US",
        "platform": "FACEBOOK", "ad_url": URL_REAL,
    }

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return [oferta]

    monkeypatch.setattr(ot.requests, "get", lambda *a, **kw: FakeResp())

    ot.investigar_oportunidade(URL_REAL, SESSAO_TESTE)
    foco_apos_investigacao = ot.get_foco_atual(SESSAO_TESTE)

    # Decision Engine ja rodou DENTRO da investigacao (Fase 2) -- confirma
    # que o resultado ficou no MESMO projeto:
    brain = brain_store.load(foco_apos_investigacao)
    assert brain.decisao.recommended_path is not None

    # Product Architect agora, SEM passar nenhum ID de novo, deve continuar
    # no mesmo foco (MESMA sessao):
    monkeypatch.setattr(pat, "_get_llm_inteligente", lambda: None)  # fallback deterministico, sem custo
    resposta = pat.gerenciar_produto("Que produto deveriamos criar?", SESSAO_TESTE)
    assert brain.project_id in resposta
    assert ot.get_foco_atual(SESSAO_TESTE) == foco_apos_investigacao  # nao trocou de projeto


def test_novo_link_troca_o_foco_mesmo_com_foco_anterior(monkeypatch, brain_store):
    """Se ja existe foco e chega um link NOVO, o novo link ganha -- nao fica
    preso no projeto antigo (bug corrigido nesta revisao)."""
    import tools.opportunity_tools as ot

    monkeypatch.setattr(ot, "_get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ot, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ot.settings, "SUPABASE_URL", "https://exemplo.supabase.co")
    monkeypatch.setattr(ot.settings, "SUPABASE_SERVICE_KEY", "chave-fake")

    ofertas = {
        "111111111111111": {"id": "a", "ad_library_id": "111111111111111", "advertiser": "Produto A", "score": 90},
        "222222222222222": {"id": "b", "ad_library_id": "222222222222222", "advertiser": "Produto B", "score": 80},
    }

    def fake_get(url, headers, params, timeout):
        class R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                ad_id = params.get("ad_library_id", "").replace("eq.", "")
                achado = ofertas.get(ad_id)
                return [achado] if achado else []
        return R()

    monkeypatch.setattr(ot.requests, "get", fake_get)

    ot.investigar_oportunidade("https://www.facebook.com/ads/library/?id=111111111111111", SESSAO_TESTE)
    foco1 = ot.get_foco_atual(SESSAO_TESTE)

    ot.investigar_oportunidade("https://www.facebook.com/ads/library/?id=222222222222222", SESSAO_TESTE)
    foco2 = ot.get_foco_atual(SESSAO_TESTE)

    assert foco1 != foco2
    assert brain_store.load(foco2).origem.source_offer_id == "222222222222222"


# ---------------------------------------------------------------------------
# Selecao de "melhor oportunidade" por completude, nao so score bruto
# ---------------------------------------------------------------------------

def test_pontuar_viabilidade_favorece_completude_sobre_score_bruto():
    rico_mas_score_menor = {
        "score": 90, "headline": "Curso completo de emagrecimento saudavel",
        "advertiser": "Fulano", "copy": "Descubra o metodo " * 10,
        "keyword": "emagrecimento", "niche": "Saude",
    }
    vazio_mas_score_maior = {
        "score": 99, "headline": "Fulano", "advertiser": "Fulano",
        "copy": "", "keyword": None, "niche": "Geral",
    }
    assert _pontuar_viabilidade(rico_mas_score_menor) > _pontuar_viabilidade(vazio_mas_score_maior)


def test_selecionar_melhor_oportunidade_prefere_completude(monkeypatch):
    import tools.opportunity_tools as ot

    candidatos = [
        {"score": 99, "headline": "Aapgis", "advertiser": "Aapgis", "copy": "", "keyword": None, "niche": "Geral"},
        {"score": 95, "headline": "Curso de marketing digital do zero",
         "advertiser": "Fulano", "copy": "Aprenda a vender online " * 8,
         "keyword": "marketing digital", "niche": "Marketing"},
    ]
    monkeypatch.setattr(ot, "_buscar_anuncios", lambda limite=10, pais=None: candidatos)
    melhor = _selecionar_melhor_oportunidade()
    assert melhor["score"] == 95  # nao e o de maior score, e o mais completo


def test_selecionar_melhor_oportunidade_sem_candidatos(monkeypatch):
    import tools.opportunity_tools as ot

    monkeypatch.setattr(ot, "_buscar_anuncios", lambda limite=10, pais=None: [])
    resultado = _selecionar_melhor_oportunidade()
    assert isinstance(resultado, str)


def test_decision_engine_nao_e_afetado_pela_selecao_de_completude():
    """Decision Engine continua so olhando score+sinais -- a mudanca foi so
    em QUAL oferta vira foco, nao em como se decide o caminho."""
    d = decidir(95, [])
    assert d.path == "INVESTIGATE_MORE"
