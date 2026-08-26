"""
Testes do ProspectorService (fachada) — camada de servico.

Se a pasta da Maquina de Leads nao existir, os testes de servico sao pulados
(so migracao/estado estatico sao testados, que nao dependem do motor).
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from services.prospector.config import ml_dir  # noqa: E402
from services.prospector.service import ProspectorService, get_prospector_service  # noqa: E402

TEM_ML = ml_dir().exists()
ML_DIR = str(ml_dir())


def teardown_module():
    from database.connection import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM prospector_leads")
    conn.commit()


@pytest.mark.skipif(not TEM_ML, reason="Maquina de Leads nao presente")
def test_status_com_ml():
    svc = ProspectorService(simular=True)
    st = svc.status()
    assert st["ml_dir"] == ML_DIR
    assert st["ml_dir_existe"] is True
    assert st["modo"] == "simulacao"


def test_status_sem_dependencia_da_ml():
    svc = ProspectorService(simular=True)
    st = svc.status()
    assert "provedor" in st
    assert "modo" in st
    assert "leads" in st


def test_singleton():
    a = get_prospector_service()
    b = get_prospector_service()
    assert a is b


@pytest.mark.skipif(not TEM_ML, reason="Maquina de Leads nao presente")
def test_executar_comando_ajuda_sem_efeito():
    svc = ProspectorService(simular=True)
    out = svc.executar_comando("ajuda", simular=True)
    assert isinstance(out, str) and out.strip()


@pytest.mark.skipif(not TEM_ML, reason="Maquina de Leads nao presente")
def test_leads_e_financeiro():
    svc = ProspectorService(simular=True)
    leads = svc.leads()
    assert isinstance(leads, list)
    fin = svc.financeiro()
    assert set(("fechados", "total", "mrr", "recebido")).issubset(fin)
