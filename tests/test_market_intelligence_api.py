"""
Testes do receptor HTTP de Market Intelligence (Fase 9 -- conexão real com
o ScalaFlow) -- primeiro teste `TestClient` deste repositório.

CRÍTICO: monkeypatcha `tools.opportunity_tools.get_project_brain_store`
(a fonte real usada por `web/backend/routes/market_intelligence.py:_obter_stores`,
via import preguiçoso dentro da função -- lido em cada chamada) para NUNCA
tocar no banco de produção real (`data/cris_os.db`) durante os testes --
mesma lição aprendida e aplicada desde a Fase 6.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

# web/backend (CRIS OS Studio) tem dependencias PROPRIAS (web/backend/requirements.txt),
# deliberadamente separadas do requirements.txt do bot core -- instalar
# `pip install -r requirements.txt` (raiz) sozinho nao inclui FastAPI. Este
# arquivo so roda quando o ambiente TAMBEM tem `web/backend/requirements.txt`
# instalado (ex.: `pip install -r web/backend/requirements.txt`); caso
# contrario, e pulado (nunca falha o resto da suite).
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import tools.opportunity_tools as ot  # noqa: E402
from config.settings import settings
from memory.layers import ProjectMemory
from memory.project_brain import ProjectBrainStore
from storage import SQLiteMemory
from web.backend.app import app


@pytest.fixture()
def brain_store(tmp_path, monkeypatch):
    backend = SQLiteMemory(tmp_path / "test_market_intelligence_api.db")
    store = ProjectBrainStore(ProjectMemory(backend))
    # Patch na fonte REAL (`tools.opportunity_tools`), nao no route module --
    # a rota importa `get_project_brain_store` de dentro da funcao a cada
    # chamada, entao o patch aqui e sempre observado, sem risco de bater no
    # banco de producao real.
    monkeypatch.setattr(ot, "get_project_brain_store", lambda: store)
    yield store
    backend.close()


@pytest.fixture()
def token(monkeypatch):
    valor = "test-token-para-scalaflow"
    monkeypatch.setattr(settings, "CRIS_OS_INTEGRATION_TOKEN", valor)
    return valor


@pytest.fixture()
def client():
    return TestClient(app)


def _payload(**overrides):
    payload = {
        "handoff_id": "handoff_api_test_1",
        "source_system": "SCALAFLOW",
        "source_module": "mock_test_harness",
        "title": "Curso de automação com IA",
        "market": "educação online",
        "niche": "automação com IA",
        "country": "PT",
        "opportunity_score": 40,
        "confidence_level": "MEDIUM",
        "evidence": [{
            "evidence_type": "OBSERVED", "confidence_level": "HIGH",
            "source_type": "AD_LIBRARY", "metric_name": "active_ads",
            "metric_value": "3",
        }],
    }
    payload.update(overrides)
    return payload


URL = "/api/integrations/scalaflow/intelligence"


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def test_sem_token_configurado_devolve_503(client, brain_store, monkeypatch):
    monkeypatch.setattr(settings, "CRIS_OS_INTEGRATION_TOKEN", "")
    r = client.post(URL, json=_payload())
    assert r.status_code == 503


def test_sem_header_authorization_devolve_401(client, brain_store, token):
    r = client.post(URL, json=_payload())
    assert r.status_code == 401
    assert r.json()["detail"]


def test_token_errado_devolve_401(client, brain_store, token):
    r = client.post(URL, json=_payload(), headers={"Authorization": "Bearer token-errado"})
    assert r.status_code == 401


def test_token_correto_sem_prefixo_bearer_tambem_funciona(client, brain_store, token):
    r = client.post(URL, json=_payload(), headers={"Authorization": token})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Fluxo feliz -- persiste, projeto correto, idempotente
# ---------------------------------------------------------------------------

def test_handoff_valido_persiste_e_devolve_200(client, brain_store, token):
    r = client.post(URL, json=_payload(), headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["status"] == "PERSISTED"
    assert corpo["project_id"] is not None

    brain = brain_store.load(corpo["project_id"])
    assert brain is not None
    assert brain.market_intelligence[0].handoff_id == "handoff_api_test_1"


def test_handoff_duplicado_devolve_200_duplicate(client, brain_store, token):
    r1 = client.post(URL, json=_payload(), headers={"Authorization": f"Bearer {token}"})
    r2 = client.post(URL, json=_payload(), headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["status"] == "DUPLICATE"
    assert len(brain_store.list_all()) == 1


# ---------------------------------------------------------------------------
# Payload invalido / fail closed
# ---------------------------------------------------------------------------

def test_payload_invalido_devolve_400(client, brain_store, token):
    r = client.post(URL, json={"handoff_id": "x"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
    assert r.json()["status"] == "REJECTED"
    assert brain_store.list_all() == []


def test_score_alto_sem_evidencia_devolve_202_needs_review(client, brain_store, token):
    payload = _payload(opportunity_score=95, confidence_level="HIGH", evidence=[])
    r = client.post(URL, json=payload, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 202
    assert r.json()["status"] == "NEEDS_REVIEW"
    assert brain_store.list_all() == []


def test_json_malformado_devolve_400(client, brain_store, token):
    r = client.post(
        URL, content=b"{isso nao e json valido",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    assert r.status_code == 400


def test_corpo_excedendo_tamanho_maximo_devolve_413(client, brain_store, token):
    payload = _payload(description="x" * (300 * 1024))
    r = client.post(URL, json=payload, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 413


# ---------------------------------------------------------------------------
# Nunca expõe segredo/stack trace
# ---------------------------------------------------------------------------

def test_resposta_nunca_contem_segredo(client, brain_store, token):
    r = client.post(URL, json=_payload(), headers={"Authorization": f"Bearer {token}"})
    corpo = r.text.lower()
    assert token.lower() not in corpo
    assert "traceback" not in corpo
    assert "secret" not in corpo


def test_token_invalido_nunca_aparece_na_resposta(client, brain_store, token):
    r = client.post(URL, json=_payload(), headers={"Authorization": "Bearer meu-token-secreto-errado"})
    assert "meu-token-secreto-errado" not in r.text


# ---------------------------------------------------------------------------
# Nunca chama nada externo real (Ads, Apify, etc.)
# ---------------------------------------------------------------------------

def test_endpoint_nunca_faz_chamada_http_externa(client, brain_store, token, monkeypatch):
    import requests

    def _boom(*a, **k):
        raise AssertionError("O receptor de intelligence nunca deveria fazer chamada HTTP externa")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    r = client.post(URL, json=_payload(), headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
