"""
Testes da Fase 9: Market Intelligence -- fronteira de integração ScalaFlow
-> CRIS OS (lógica pura, sem Telegram/HTTP real).

Nada aqui bate em nenhuma API externa nem gasta OpenRouter/Apify de
verdade -- todos os payloads são construídos localmente neste arquivo.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from core.market_intelligence import (
    get_intelligence,
    get_project_intelligence,
    receive_intelligence,
    resolver_projeto,
    validar_payload,
)
from memory.layers import ProjectMemory
from memory.project_brain import (
    BusinessPlan,
    CampaignSpec,
    ExecutionPlan,
    IntelligenceHandoffStore,
    MarketIntelligenceHandoff,
    PendingApprovalStore,
    ProductBlueprint,
    ProjectBrainStore,
    TrafficPlan,
)
from storage import SQLiteMemory


@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_market_intelligence.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


@pytest.fixture()
def handoff_store(brain_store):
    return IntelligenceHandoffStore(brain_store.project_memory)


def _payload_valido(handoff_id="handoff_001", **overrides):
    payload = {
        "handoff_id": handoff_id,
        "schema_version": "1.0",
        "source_system": "SCALAFLOW",
        "source_module": "tiktok_miner",
        "title": "Curso de automação com IA",
        "market": "educação online",
        "niche": "automação com IA",
        "country": "PT",
        "language": "pt-PT",
        "description": "Anúncios crescentes sobre automação com IA em Portugal",
        "trend_signals": {"growth": "crescente"},
        "ad_signals": {"active_ads": 5},
        "competitors": ["Concorrente X"],
        "competitor_urls": ["https://exemplo.com/concorrente-x"],
        "opportunity_score": 55,
        "confidence_level": "MEDIUM",
        "evidence": [{
            "evidence_type": "OBSERVED", "confidence_level": "HIGH",
            "source_type": "AD_LIBRARY", "source_name": "Meta Ad Library",
            "source_url": "https://facebook.com/ads/library/x",
            "metric_name": "active_ads", "metric_value": "5",
            "captured_at": "2026-09-20T10:00:00+00:00",
        }],
        "tags": ["TEST", "MOCK"],
        "notes": ["Cenário fictício de teste (TEST/MOCK)"],
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Validacao de payload -- FAIL CLOSED
# ---------------------------------------------------------------------------

def test_payload_valido_passa():
    valido, erros = validar_payload(_payload_valido())
    assert valido is True
    assert erros == []


@pytest.mark.parametrize("payload,motivo", [
    ({}, "sem handoff_id/source_system"),
    ({"handoff_id": "x"}, "sem source_system"),
    ({"handoff_id": "x", "source_system": "SCALAFLOW", "schema_version": "99.9"}, "schema invalida"),
    ({"handoff_id": "x", "source_system": "SCALAFLOW", "opportunity_score": 150}, "score fora do range"),
    ({"handoff_id": "x", "source_system": "SCALAFLOW", "opportunity_score": -1}, "score negativo"),
    ({"handoff_id": "x", "source_system": "SCALAFLOW", "confidence_level": "SUPER_ALTO"}, "confidence invalido"),
    ({"handoff_id": "x", "source_system": "SCALAFLOW", "created_at": "nao-e-data"}, "timestamp invalido"),
    ({"handoff_id": "x", "source_system": "SCALAFLOW", "sales_page_url": "nao-e-url"}, "url invalida"),
    ({"handoff_id": "x", "source_system": "SCALAFLOW", "competitor_urls": ["ftp://nao-http"]}, "competitor url invalida"),
    ({"handoff_id": "x", "source_system": "SCALAFLOW", "evidence": [{"evidence_type": "FACT"}]}, "evidence_type invalido"),
    ("nao-e-dict", "payload nao e dict"),
    (None, "payload none"),
])
def test_payload_invalido_e_rejeitado(payload, motivo):
    valido, erros = validar_payload(payload)
    assert valido is False, motivo
    assert erros


def test_payload_excede_tamanho_maximo_e_rejeitado():
    payload = _payload_valido()
    payload["description"] = "x" * (300 * 1024)
    valido, erros = validar_payload(payload)
    assert valido is False
    assert any("tamanho máximo" in e for e in erros)


def test_payload_invalido_nao_entra_no_project_brain(brain_store, handoff_store):
    resultado = receive_intelligence({"handoff_id": "bad"}, brain_store, handoff_store)
    assert resultado["status"] == "REJECTED"
    assert resultado["project_id"] is None
    assert brain_store.list_all() == []


# ---------------------------------------------------------------------------
# Verification before trust
# ---------------------------------------------------------------------------

def test_score_alto_sem_evidencia_vira_needs_review(brain_store, handoff_store):
    payload = _payload_valido(handoff_id="handoff_sem_evidencia", opportunity_score=95, confidence_level="HIGH", evidence=[])
    resultado = receive_intelligence(payload, brain_store, handoff_store)
    assert resultado["status"] == "NEEDS_REVIEW"
    assert resultado["project_id"] is None
    assert brain_store.list_all() == []  # nunca contamina o Project Brain


def test_produto_vencedor_sem_evidencia_nunca_vira_fato(brain_store, handoff_store):
    """Cenario explicito: ScalaFlow afirma 'Produto vencedor' sem evidencia
    suficiente -- nunca pode virar fato confirmado."""
    payload = _payload_valido(
        handoff_id="handoff_produto_vencedor", title="Produto vencedor",
        description="Produto vencedor comprovado", confidence_level="HIGH",
        opportunity_score=30, evidence=[],
    )
    resultado = receive_intelligence(payload, brain_store, handoff_store)
    assert resultado["status"] == "PERSISTED"  # score baixo -- nao exige revisao, mas...
    brain = brain_store.load(resultado["project_id"])
    handoff = brain.market_intelligence[0]
    assert handoff.confidence_level == "UNKNOWN"  # ...a confianca foi rebaixada, nunca aceita como HIGH


def test_apenas_inferred_rebaixa_confidence_para_low(brain_store, handoff_store):
    payload = _payload_valido(
        handoff_id="handoff_inferred", confidence_level="HIGH", opportunity_score=20,
        evidence=[{"evidence_type": "INFERRED", "confidence_level": "HIGH", "metric_name": "chute"}],
    )
    resultado = receive_intelligence(payload, brain_store, handoff_store)
    brain = brain_store.load(resultado["project_id"])
    assert brain.market_intelligence[0].confidence_level == "LOW"


def test_evidencia_observed_preserva_confidence(brain_store, handoff_store):
    resultado = receive_intelligence(_payload_valido(), brain_store, handoff_store)
    brain = brain_store.load(resultado["project_id"])
    assert brain.market_intelligence[0].confidence_level == "MEDIUM"


# ---------------------------------------------------------------------------
# Deduplicacao / idempotencia
# ---------------------------------------------------------------------------

def test_handoff_duplicado_nao_cria_segunda_opportunity(brain_store, handoff_store):
    payload = _payload_valido()
    r1 = receive_intelligence(payload, brain_store, handoff_store)
    r2 = receive_intelligence(payload, brain_store, handoff_store)
    assert r1["status"] == "PERSISTED"
    assert r2["status"] == "DUPLICATE"
    assert r2["project_id"] == r1["project_id"]
    assert len(brain_store.list_all()) == 1
    brain = brain_store.load(r1["project_id"])
    assert len(brain.market_intelligence) == 1  # nao duplicou a evidencia


def test_handoff_com_id_diferente_nao_e_duplicado(brain_store, handoff_store):
    r1 = receive_intelligence(_payload_valido(handoff_id="a"), brain_store, handoff_store)
    r2 = receive_intelligence(_payload_valido(handoff_id="b"), brain_store, handoff_store)
    assert r1["status"] == "PERSISTED"
    assert r2["status"] == "PERSISTED"


# ---------------------------------------------------------------------------
# Project resolution -- nunca adivinha
# ---------------------------------------------------------------------------

def test_sem_project_id_cria_projeto_novo_controladamente(brain_store, handoff_store):
    resultado = receive_intelligence(_payload_valido(), brain_store, handoff_store)
    assert resultado["status"] == "PERSISTED"
    assert resultado["project_id"] is not None
    assert brain_store.load(resultado["project_id"]) is not None


def test_com_project_id_valido_associa_ao_projeto_correto(brain_store, handoff_store):
    brain = brain_store.create(name="Projeto já existente", tipo="opportunity")
    payload = _payload_valido(handoff_id="handoff_com_projeto", project_id=brain.project_id)
    resultado = receive_intelligence(payload, brain_store, handoff_store)
    assert resultado["project_id"] == brain.project_id
    assert len(brain_store.list_all()) == 1  # nao criou um segundo projeto


def test_project_id_inexistente_nunca_adivinha(brain_store, handoff_store):
    payload = _payload_valido(project_id="proj_nao_existe")
    resultado = receive_intelligence(payload, brain_store, handoff_store)
    assert resultado["status"] == "NEEDS_REVIEW"
    assert brain_store.list_all() == []


def test_external_project_ref_ambiguo_nunca_adivinha(brain_store, handoff_store):
    b1 = brain_store.create(name="P1", tipo="opportunity")
    b1.origem.source_offer_id = "ref_compartilhada"
    brain_store.save(b1)
    b2 = brain_store.create(name="P2", tipo="opportunity")
    b2.origem.source_offer_id = "ref_compartilhada"
    brain_store.save(b2)

    payload = _payload_valido(external_project_ref="ref_compartilhada")
    resultado = receive_intelligence(payload, brain_store, handoff_store)
    assert resultado["status"] == "NEEDS_REVIEW"


def test_external_project_ref_unico_resolve_corretamente(brain_store, handoff_store):
    b1 = brain_store.create(name="P1", tipo="opportunity")
    b1.origem.source_offer_id = "ref_unica"
    brain_store.save(b1)

    payload = _payload_valido(external_project_ref="ref_unica")
    resultado = receive_intelligence(payload, brain_store, handoff_store)
    assert resultado["project_id"] == b1.project_id
    assert len(brain_store.list_all()) == 1


# ---------------------------------------------------------------------------
# Persistencia -- aplica aos campos canonicos existentes, nunca inventa
# ---------------------------------------------------------------------------

def test_dados_aplicados_aos_campos_canonicos_sem_duplicar_modelo(brain_store, handoff_store):
    resultado = receive_intelligence(_payload_valido(), brain_store, handoff_store)
    brain = brain_store.load(resultado["project_id"])
    assert brain.mercado.market == "educação online"
    assert brain.mercado.niche == "automação com IA"
    assert brain.mercado.target_country == "PT"
    assert brain.oportunidade.score == 55
    assert any("active_ads" in e for e in brain.oportunidade.evidence)
    assert "trend" in brain.oportunidade.signals


def test_campos_ausentes_no_payload_nunca_sao_inventados(brain_store, handoff_store):
    payload = {"handoff_id": "handoff_minimo", "source_system": "SCALAFLOW"}
    resultado = receive_intelligence(payload, brain_store, handoff_store)
    assert resultado["status"] == "PERSISTED"
    brain = brain_store.load(resultado["project_id"])
    assert brain.mercado.market is None
    assert brain.mercado.niche is None
    assert brain.oportunidade.score is None
    assert brain.oportunidade.evidence == []


# ---------------------------------------------------------------------------
# get_intelligence / get_project_intelligence
# ---------------------------------------------------------------------------

def test_get_intelligence_recupera_pelo_handoff_id(brain_store, handoff_store):
    resultado = receive_intelligence(_payload_valido(), brain_store, handoff_store)
    handoff = get_intelligence("handoff_001", brain_store, handoff_store)
    assert handoff is not None
    assert handoff.handoff_id == "handoff_001"
    assert handoff.project_id == resultado["project_id"]


def test_get_intelligence_inexistente_devolve_none(brain_store, handoff_store):
    assert get_intelligence("nao_existe", brain_store, handoff_store) is None


def test_get_project_intelligence_lista_todos_os_handoffs_do_projeto(brain_store, handoff_store):
    brain = brain_store.create(name="P", tipo="opportunity")
    receive_intelligence(_payload_valido(handoff_id="h1", project_id=brain.project_id), brain_store, handoff_store)
    receive_intelligence(_payload_valido(handoff_id="h2", project_id=brain.project_id), brain_store, handoff_store)
    lista = get_project_intelligence(brain.project_id, brain_store)
    assert len(lista) == 2


# ---------------------------------------------------------------------------
# Persistencia apos restart
# ---------------------------------------------------------------------------

def test_restart_preserva_handoff_evidence_provenance(tmp_path):
    db_path = tmp_path / "test_mi_restart.db"
    backend = SQLiteMemory(db_path)
    store = ProjectBrainStore(ProjectMemory(backend))
    handoff_store = IntelligenceHandoffStore(store.project_memory)

    resultado = receive_intelligence(_payload_valido(), store, handoff_store)
    backend.close()

    novo_backend = SQLiteMemory(db_path)
    novo_store = ProjectBrainStore(ProjectMemory(novo_backend))
    novo_handoff_store = IntelligenceHandoffStore(novo_store.project_memory)
    try:
        brain = novo_store.load(resultado["project_id"])
        assert len(brain.market_intelligence) == 1
        assert brain.market_intelligence[0].handoff_id == "handoff_001"
        assert brain.oportunidade.evidence  # provenance preservada

        # reenviar o MESMO handoff apos restart -- dedup continua funcionando
        resultado2 = receive_intelligence(_payload_valido(), novo_store, novo_handoff_store)
        assert resultado2["status"] == "DUPLICATE"
        assert len(novo_store.load(resultado["project_id"]).market_intelligence) == 1
    finally:
        novo_backend.close()


# ---------------------------------------------------------------------------
# ScalaFlow NAO manda no CRIS OS -- testes de seguranca do workflow
# ---------------------------------------------------------------------------

def _brain_com_todos_os_artefatos_pendentes(store):
    brain = store.create(name="Projeto com tudo pendente", tipo="opportunity")
    brain.blueprint = ProductBlueprint(project_id=brain.project_id, decision_status="PENDING_APPROVAL")
    brain.business_plan = BusinessPlan(project_id=brain.project_id, approval_status="READY_FOR_APPROVAL")
    brain.traffic_plan = TrafficPlan(project_id=brain.project_id, version=1, status="READY_FOR_APPROVAL")
    brain.campaign_spec = CampaignSpec(project_id=brain.project_id, status="READY_FOR_APPROVAL", channel="TIKTOK_ADS")
    brain.execution_plan = ExecutionPlan(project_id=brain.project_id, status="READY_FOR_APPROVAL")
    store.save(brain)
    return brain


def test_handoff_nunca_aprova_business_plan(brain_store, handoff_store):
    brain = _brain_com_todos_os_artefatos_pendentes(brain_store)
    receive_intelligence(_payload_valido(project_id=brain.project_id), brain_store, handoff_store)
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.business_plan.approval_status == "READY_FOR_APPROVAL"


def test_handoff_nunca_aprova_traffic_plan(brain_store, handoff_store):
    brain = _brain_com_todos_os_artefatos_pendentes(brain_store)
    receive_intelligence(_payload_valido(project_id=brain.project_id), brain_store, handoff_store)
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.traffic_plan.status == "READY_FOR_APPROVAL"


def test_handoff_nunca_executa_campaign_spec(brain_store, handoff_store):
    brain = _brain_com_todos_os_artefatos_pendentes(brain_store)
    receive_intelligence(_payload_valido(project_id=brain.project_id), brain_store, handoff_store)
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.campaign_spec.status == "READY_FOR_APPROVAL"


def test_handoff_nunca_burla_approval_router(brain_store, handoff_store):
    """Mesmo se o payload tentar 'contrabandear' um status de aprovacao via
    campos extras, `_construir_handoff` so aceita campos que EXISTEM no
    dataclass `MarketIntelligenceHandoff` -- nunca grava em outro artefato."""
    brain = _brain_com_todos_os_artefatos_pendentes(brain_store)
    payload = _payload_valido(project_id=brain.project_id)
    payload["business_plan"] = {"approval_status": "APPROVED"}  # tentativa de injecao
    payload["approval_status"] = "APPROVED"
    resultado = receive_intelligence(payload, brain_store, handoff_store)
    assert resultado["status"] == "PERSISTED"
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.business_plan.approval_status == "READY_FOR_APPROVAL"  # inalterado


def test_handoff_nunca_cria_pending_approval(brain_store, handoff_store):
    brain = _brain_com_todos_os_artefatos_pendentes(brain_store)
    pending = PendingApprovalStore(brain_store.project_memory)
    receive_intelligence(_payload_valido(project_id=brain.project_id), brain_store, handoff_store)
    assert pending.get_pending("telegram:qualquer") is None


def test_handoff_nunca_executa_task_externa(brain_store, handoff_store):
    brain = _brain_com_todos_os_artefatos_pendentes(brain_store)
    receive_intelligence(_payload_valido(project_id=brain.project_id), brain_store, handoff_store)
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.execution_plan.status == "READY_FOR_APPROVAL"
    for t in recarregado.execution_plan.tasks:
        assert t.status != "COMPLETED"


def test_handoff_nunca_provoca_gasto_ou_chamada_http(monkeypatch, brain_store, handoff_store):
    import requests

    def _boom(*a, **k):
        raise AssertionError("receive_intelligence nunca deveria fazer chamada HTTP")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    receive_intelligence(_payload_valido(), brain_store, handoff_store)


def test_handoff_nao_altera_credenciais_nem_expoe_segredo(brain_store, handoff_store):
    resultado = receive_intelligence(_payload_valido(), brain_store, handoff_store)
    assert "api_key" not in str(resultado).lower()
    assert "secret" not in str(resultado).lower()
    assert "token" not in str(resultado).lower()


def test_market_intelligence_handoff_nao_tem_campo_para_dado_inventado():
    from dataclasses import fields
    nomes = {f.name for f in fields(MarketIntelligenceHandoff)}
    proibidos = {"actual_sales", "confirmed_revenue", "verified_fact"}
    assert not (nomes & proibidos)
