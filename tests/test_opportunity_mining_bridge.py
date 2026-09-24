"""
Testes da ponte Etapa 23 entre a investigação de oportunidade
(`tools/opportunity_tools.py`) e o cliente de mineração server-to-server do
ScalaFlow (`core/scalaflow_mining_client.py`).

ZERO chamada de rede real: Supabase (`requests.get`) e o cliente de
mineração (`solicitar_mineracao`) são sempre monkeypatchados/fakes.
`solicitar_mineracao_complementar` NUNCA é chamado automaticamente por
`investigar_oportunidade` -- cada teste chama as duas funções
explicitamente, na ordem que um uso real teria.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from core.scalaflow_mining_client import ResultadoMineracao
from memory.layers import ProjectMemory
from memory.project_brain import ProjectBrainStore
from storage import SQLiteMemory

SESSAO_TESTE = "telegram:6460872429"
ID_REAL = "780659311220315"

_OFERTA = {
    "id": "x", "ad_library_id": ID_REAL, "advertiser": "Hashtag Treinamentos",
    "headline": "MasterClass gratuita - Automatize tudo com IA e N8N",
    "copy": "Curso completo " * 10, "keyword": "automação", "niche": "Geral",
    "score": 99, "country": "BR", "platform": "FACEBOOK",
    "ad_url": f"https://www.facebook.com/ads/library/?id={ID_REAL}",
}


class FakeResp:
    def __init__(self, corpo):
        self.status_code = 200
        self._corpo = corpo

    def raise_for_status(self):
        pass

    def json(self):
        return self._corpo


def _fake_get_sem_evidencia_cruzada(url, headers=None, params=None, timeout=None):
    """`collected_ads` sempre devolve a oferta real; qualquer tabela
    `*_minerados` devolve vazio -- forca a decisao INVESTIGATE_MORE."""
    if "collected_ads" in url:
        return FakeResp([_OFERTA])
    return FakeResp([])


@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_opportunity_mining_bridge.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


@pytest.fixture()
def ot(monkeypatch, brain_store):
    """Investiga a oferta real (fake de rede) uma vez, deixando a
    oportunidade em foco e em INVESTIGATE_MORE -- estado de partida real
    para os testes da ponte de mineracao."""
    import tools.opportunity_tools as ot

    monkeypatch.setattr(ot, "_get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ot, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ot.settings, "SUPABASE_URL", "https://exemplo.supabase.co")
    monkeypatch.setattr(ot.settings, "SUPABASE_SERVICE_KEY", "chave-fake")
    monkeypatch.setattr(ot.requests, "get", _fake_get_sem_evidencia_cruzada)

    ot.investigar_oportunidade(ID_REAL, SESSAO_TESTE)
    return ot


def test_investigacao_de_partida_fica_em_investigate_more(ot, brain_store):
    foco = ot.get_foco_atual(SESSAO_TESTE)
    brain = brain_store.load(foco)
    assert brain.decisao.recommended_path == "INVESTIGATE_MORE"
    assert set(brain.oportunidade.risks) == {"tiktok", "instagram", "youtube", "google_trends"}


def test_solicita_mineracao_para_todas_as_fontes_faltantes(monkeypatch, ot):
    chamadas = []

    def _fake_solicitar(source, term, limit=20):
        chamadas.append((source, term))
        return ResultadoMineracao(ok=True, status="SUCCESS", retryable=False, dados={"queued": True})

    monkeypatch.setattr("core.scalaflow_mining_client.solicitar_mineracao", _fake_solicitar)

    resposta = ot.solicitar_mineracao_complementar("minere evidencia", SESSAO_TESTE)

    fontes_chamadas = {c[0] for c in chamadas}
    assert fontes_chamadas == {"tiktok", "instagram", "youtube", "google_trends"}
    assert all(termo == "automação" for _, termo in chamadas)
    assert "solicitado com sucesso" in resposta


def test_nunca_chama_dispatch_real_apenas_o_fake(monkeypatch, ot):
    """Garante que o teste nunca faz rede real -- qualquer tentativa de
    `requests.post` (usado pelo cliente real) falha o teste."""
    def _boom(*a, **k):
        raise AssertionError("nao deveria fazer POST real -- solicitar_mineracao deveria estar mockado")
    monkeypatch.setattr("requests.post", _boom)
    monkeypatch.setattr(
        "core.scalaflow_mining_client.solicitar_mineracao",
        lambda source, term, limit=20: ResultadoMineracao(ok=True, status="SUCCESS", retryable=False, dados={}),
    )

    ot.solicitar_mineracao_complementar("minere evidencia", SESSAO_TESTE)


def test_reporta_falha_de_uma_fonte_sem_interromper_as_outras(monkeypatch, ot):
    def _fake_solicitar(source, term, limit=20):
        if source == "instagram":
            return ResultadoMineracao(ok=False, status="RATE_LIMITED", retryable=False, erro="Rate limit atingido.")
        return ResultadoMineracao(ok=True, status="SUCCESS", retryable=False, dados={})

    monkeypatch.setattr("core.scalaflow_mining_client.solicitar_mineracao", _fake_solicitar)

    resposta = ot.solicitar_mineracao_complementar("minere evidencia", SESSAO_TESTE)

    assert "instagram: RATE_LIMITED" in resposta
    assert "tiktok: solicitado com sucesso" in resposta
    assert "youtube: solicitado com sucesso" in resposta
    assert "google_trends: solicitado com sucesso" in resposta


def test_nao_reavalia_decisao_automaticamente(monkeypatch, ot, brain_store):
    """Depois de solicitar mineracao, a decisao da oportunidade continua
    INVESTIGATE_MORE ate uma NOVA investigacao explicita ser pedida --
    nunca reavaliada sozinha."""
    monkeypatch.setattr(
        "core.scalaflow_mining_client.solicitar_mineracao",
        lambda source, term, limit=20: ResultadoMineracao(ok=True, status="SUCCESS", retryable=False, dados={}),
    )

    ot.solicitar_mineracao_complementar("minere evidencia", SESSAO_TESTE)

    foco = ot.get_foco_atual(SESSAO_TESTE)
    brain = brain_store.load(foco)
    assert brain.decisao.recommended_path == "INVESTIGATE_MORE"
    assert brain.business_plan is None
    assert brain.execution_plan is None
    assert brain.production_work_orders == []


def test_sem_oportunidade_em_foco_nao_falha(monkeypatch, brain_store):
    import tools.opportunity_tools as ot

    monkeypatch.setattr(ot, "_get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ot, "get_project_brain_store", lambda: brain_store)

    resposta = ot.solicitar_mineracao_complementar("minere evidencia", "sessao:sem-foco-nenhum")
    assert "não sei" in resposta.lower() or "nao sei" in resposta.lower()


def test_oportunidade_ja_decidida_nao_solicita_mineracao(monkeypatch, ot, brain_store):
    """Se a decisao ja saiu de INVESTIGATE_MORE (ex.: CREATE_OWN_PRODUCT),
    mineracao complementar nao se aplica mais -- nunca solicita a toa."""
    foco = ot.get_foco_atual(SESSAO_TESTE)
    brain = brain_store.load(foco)
    brain.decisao.recommended_path = "CREATE_OWN_PRODUCT"
    brain_store.save(brain)

    def _boom(source, term, limit=20):
        raise AssertionError("nao deveria solicitar mineracao -- decisao ja nao e INVESTIGATE_MORE")
    monkeypatch.setattr("core.scalaflow_mining_client.solicitar_mineracao", _boom)

    resposta = ot.solicitar_mineracao_complementar("minere evidencia", SESSAO_TESTE)
    assert "INVESTIGATE_MORE" in resposta


def test_tool_registrada_e_reconhecida_pelas_palavras_chave():
    from tools.opportunity_tools import get_tools

    ferramentas = {t.name: t for t in get_tools()}
    assert "solicitar_mineracao_complementar" in ferramentas
    tool = ferramentas["solicitar_mineracao_complementar"]
    assert tool.matches("pode minere evidencia pra mim?")
    assert not tool.matches("qual o clima hoje?")
