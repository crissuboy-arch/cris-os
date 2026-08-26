"""
Testes das rotas FastAPI do modulo Prospector (/api/prospector/*).
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from web.backend.app import app  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def teardown_module():
    from database.connection import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM prospector_leads")
    conn.commit()


def test_status_route(client):
    r = client.get("/api/prospector/status")
    assert r.status_code == 200
    data = r.json()
    assert "provedor" in data and "modo" in data and "ml_dir" in data


def test_leads_route(client):
    r = client.get("/api/prospector/leads")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_financeiro_route(client):
    r = client.get("/api/prospector/financeiro")
    assert r.status_code == 200
    assert "fechados" in r.json()


def test_contratos_route(client):
    r = client.get("/api/prospector/contratos")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_fechar_lead_inexistente(client):
    r = client.post("/api/prospector/fechar", json={"slug": "nao-existe-xyz", "valor": 100})
    assert r.status_code == 200
    assert r.json()["ok"] is False
