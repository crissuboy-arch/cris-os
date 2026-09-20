"""
Testes da Fase 9: camada de Tools do Market Intelligence -- consulta
somente leitura, zero LLM, zero escrita, do que já foi recebido/persistido.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

import tools.market_intelligence_tools as mit
from core.market_intelligence import receive_intelligence
from memory.layers import ProjectMemory
from memory.project_brain import IntelligenceHandoffStore, ProjectBrainStore
from storage import SQLiteMemory


@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_fase9_tools.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def test_sem_intelligence_recebida_e_deterministico(monkeypatch, brain_store):
    brain = brain_store.create(name="x", tipo="opportunity")
    monkeypatch.setattr(mit, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(mit, "get_project_brain_store", lambda: brain_store)

    resposta = mit.gerenciar_market_intelligence("Mostre a inteligência de mercado deste projeto.", "telegram:1")
    assert "ainda não há inteligência" in resposta.lower()


def test_mostra_intelligence_ja_recebida(monkeypatch, brain_store):
    handoff_store = IntelligenceHandoffStore(brain_store.project_memory)
    brain = brain_store.create(name="Curso de automação com IA", tipo="opportunity")
    payload = {
        "handoff_id": "handoff_teste_tool", "source_system": "SCALAFLOW",
        "project_id": brain.project_id, "confidence_level": "MEDIUM",
        "opportunity_score": 40,
        "evidence": [{"evidence_type": "OBSERVED", "confidence_level": "MEDIUM", "metric_name": "x"}],
    }
    receive_intelligence(payload, brain_store, handoff_store)

    monkeypatch.setattr(mit, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(mit, "get_project_brain_store", lambda: brain_store)

    resposta = mit.gerenciar_market_intelligence("Mostre a inteligência de mercado deste projeto.", "telegram:1")
    assert "handoff_teste_tool" in resposta
    assert "MEDIUM" in resposta
    assert "fato" in resposta.lower() or "não" in resposta.lower()


def test_ferramenta_nunca_escreve_no_project_brain(monkeypatch, brain_store):
    brain = brain_store.create(name="x", tipo="opportunity")
    monkeypatch.setattr(mit, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(mit, "get_project_brain_store", lambda: brain_store)

    original_save = brain_store.save
    def _boom_save(*a, **k):
        raise AssertionError("Consulta de intelligence nunca deveria escrever no Project Brain")
    monkeypatch.setattr(brain_store, "save", _boom_save)
    try:
        mit.gerenciar_market_intelligence("Mostre a inteligência de mercado deste projeto.", "telegram:1")
    finally:
        monkeypatch.setattr(brain_store, "save", original_save)
