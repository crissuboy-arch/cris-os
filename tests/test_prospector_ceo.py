"""
Testes da integracao do CEO Mode com o agente Prospector.

Objetivo do enunciado: "Quero encontrar 50 clientes para impressao 3d em
Portugal" deve ser reconhecido como prospeccao e delegar ao agente prospector.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from services.ceo_mode import CATALOGO_AGENTES, CeoMode  # noqa: E402


def test_catalogo_inclui_prospector():
    assert "prospector" in CATALOGO_AGENTES


def test_entender_detecta_prospecao():
    e = CeoMode().entender("Quero encontrar 50 clientes para impressao 3d em Portugal")
    assert e["tipo"] == "prospecao"
    assert e["numero"] == 50.0
    assert e["unidade"] == "clientes"
    assert e["mercado"] == "portugal"


def test_entender_detecta_prospectar():
    e = CeoMode().entender("Quero prospectar 20 leads de marmorarias em Sao Paulo")
    assert e["tipo"] == "prospecao"
    assert e["unidade"] == "leads"


def test_planejar_prospecao_delega_ao_prospector():
    p = CeoMode().planejar("Quero encontrar 50 clientes para impressao 3d em Portugal")
    assert p["tipo"] == "prospecao"
    assert {t["agente"] for t in p["tarefas"]} == {"prospector"}
    # A tarefa sensivel (contratos/fechamentos) exige confirmacao
    assert len(p["confirmacoes_necessarias"]) == 1
    assert p["proxima_acao"].startswith("Prospectar 50 clientes em portugal")


def test_planejar_prospecao_fases():
    p = CeoMode().planejar("Quero prospectar clientes em Lisboa")
    nomes = [f["nome"] for f in p["fases"]]
    assert nomes == [
        "1. Prospeccao",
        "2. Redesign e Propostas",
        "3. Follow-up e Contratos",
    ]
