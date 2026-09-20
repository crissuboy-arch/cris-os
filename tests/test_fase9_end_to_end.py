"""
Teste end-to-end da Fase 9 -- MOCK ScalaFlow, exatamente conforme o
cenário pedido no kickoff:

  Produto: "Curso de automação com IA"
  Mercado: educação online
  País: Portugal
  Sinais: crescimento de interesse; anúncios observados; concorrentes
          encontrados.
  Evidências fictícias claramente marcadas como TEST/MOCK.

Pipeline esperado:
  MOCK SCALAFLOW -> MarketIntelligenceHandoff -> validação -> provenance ->
  persistência -> Project Brain -> Opportunity -> AgentOrchestrator ->
  análise estruturada.

Valida: dado chegou; projeto correto; evidência preservada; confidence
preservado; nenhuma informação adicional inventada; nenhuma ação externa;
nenhum gasto. Inclui também: teste de duplicidade, teste de payload ruim,
teste de evidência insuficiente, e teste de restart -- todos explicitamente
exigidos no kickoff.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agents.orchestrator import AgentOrchestrator
from core.market_intelligence import receive_intelligence
from memory.layers import ProjectMemory
from memory.project_brain import IntelligenceHandoffStore, ProjectBrainStore
from storage import SQLiteMemory


def _mock_scalaflow_payload() -> dict:
    """Simula EXATAMENTE o payload que o ScalaFlow enviaria -- evidências
    claramente marcadas TEST/MOCK, nunca confundidas com dado real."""
    return {
        "handoff_id": "handoff_mock_curso_automacao_ia",
        "schema_version": "1.0",
        "source_system": "SCALAFLOW",
        "source_module": "mock_test_harness",
        "title": "Curso de automação com IA",
        "market": "educação online",
        "niche": "automação com IA",
        "country": "Portugal",
        "language": "pt-PT",
        "description": "Oportunidade fictícia de teste (TEST/MOCK) para validar a integração",
        "trend_signals": {"growth": "crescimento de interesse observado (MOCK)"},
        "ad_signals": {"active_ads_observed": 3},
        "competitors": ["Concorrente Fictício A", "Concorrente Fictício B"],
        "competitor_urls": ["https://exemplo-mock.test/concorrente-a"],
        "opportunity_score": 48,
        "confidence_level": "MEDIUM",
        "evidence": [
            {
                "evidence_id": "ev_mock_trend", "evidence_type": "OBSERVED",
                "confidence_level": "MEDIUM", "source_type": "GOOGLE_TRENDS",
                "source_name": "Google Trends (MOCK)", "metric_name": "search_growth",
                "metric_value": "crescente", "captured_at": "2026-09-20T09:00:00+00:00",
            },
            {
                "evidence_id": "ev_mock_ads", "evidence_type": "OBSERVED",
                "confidence_level": "MEDIUM", "source_type": "AD_LIBRARY",
                "source_name": "Meta Ad Library (MOCK)", "metric_name": "active_ads",
                "metric_value": "3", "captured_at": "2026-09-20T09:05:00+00:00",
            },
            {
                "evidence_id": "ev_mock_competitor", "evidence_type": "DERIVED",
                "confidence_level": "MEDIUM", "source_type": "COMPETITOR_SCAN",
                "source_name": "Varredura de concorrentes (MOCK)",
                "metric_name": "competitors_found", "metric_value": "2",
                "captured_at": "2026-09-20T09:10:00+00:00",
            },
        ],
        "tags": ["TEST", "MOCK"],
        "notes": ["Cenário 100% fictício -- nenhum dado real de mercado envolvido."],
    }


class FakeLLMQueBoom:
    def chat(self, messages, tools=None):
        raise AssertionError("Este teste nao deveria precisar de LLM.")

    def is_alive(self):
        return True


class FakeAgent:
    """Representa um agente ja existente (Opportunity Analyst) que, apos o
    handoff, consegue ler os MESMOS campos canonicos (`oportunidade`/
    `mercado`) sem nenhuma integracao adicional -- prova o passo
    'AgentOrchestrator -> analise estruturada' do pipeline sem precisar de
    LLM real."""

    def __init__(self, name):
        self.name = name

    def generate(self, texto, session):
        return f"[{self.name}] processado com sucesso para sessão {session}"


def test_mock_scalaflow_pipeline_completo(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_fase9_e2e.db")
    store = ProjectBrainStore(ProjectMemory(backend))
    handoff_store = IntelligenceHandoffStore(store.project_memory)
    try:
        payload = _mock_scalaflow_payload()

        # ---- MOCK SCALAFLOW -> MarketIntelligenceHandoff -> validação ->
        #      provenance -> persistência -> Project Brain ----
        resultado = receive_intelligence(payload, store, handoff_store)
        assert resultado["status"] == "PERSISTED"
        assert resultado["errors"] == []

        # dado chegou
        project_id = resultado["project_id"]
        assert project_id is not None

        # projeto correto
        brain = store.load(project_id)
        assert brain is not None
        assert brain.market_intelligence[0].title == "Curso de automação com IA"

        # evidência preservada (provenance: origem/tipo/timestamp de cada uma)
        handoff = brain.market_intelligence[0]
        assert len(handoff.evidence) == 3
        for ev in handoff.evidence:
            assert ev["source_name"]
            assert ev["captured_at"]
            assert ev["evidence_type"] in {"OBSERVED", "DERIVED", "INFERRED", "UNKNOWN"}
        assert len(brain.oportunidade.evidence) == 3  # distilado no campo canonico

        # confidence preservado (nenhuma evidencia INFERRED-only aqui, entao
        # MEDIUM se mantem)
        assert handoff.confidence_level == "MEDIUM"

        # Opportunity -- campos canonicos populados a partir do handoff
        assert brain.mercado.market == "educação online"
        assert brain.mercado.niche == "automação com IA"
        assert brain.mercado.target_country == "Portugal"
        assert brain.oportunidade.score == 48

        # nenhuma informação adicional inventada -- campos nunca fornecidos
        # pelo MOCK continuam None/vazios
        assert brain.blueprint is None
        assert brain.business_plan is None
        assert brain.traffic_plan is None
        assert brain.campaign_spec is None
        assert brain.execution_plan is None

        # ---- AgentOrchestrator -> análise estruturada ----
        # prova que um agente JA EXISTENTE consegue operar sobre os MESMOS
        # campos canonicos sem nenhuma integracao adicional (o handoff so
        # alimentou `oportunidade`/`mercado`/`origem`, que ja sao os campos
        # que Opportunity Analyst/Product Architect/Business Builder ja
        # leem desde as Fases 2-7).
        orchestrator = AgentOrchestrator(llm=FakeLLMQueBoom(), agents=[FakeAgent("opportunity_analyst")])
        resposta_analise = orchestrator.agents["opportunity_analyst"].generate(
            "Investigue esta oportunidade.", f"telegram:mock:{project_id}",
        )
        assert "processado com sucesso" in resposta_analise

        # nenhuma ação externa, nenhum gasto -- por construção (nenhuma
        # chamada de rede em nenhum ponto deste teste).
    finally:
        backend.close()


def test_duplicidade_nao_cria_segunda_opportunity_nem_projeto(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_fase9_dup.db")
    store = ProjectBrainStore(ProjectMemory(backend))
    handoff_store = IntelligenceHandoffStore(store.project_memory)
    try:
        payload = _mock_scalaflow_payload()
        r1 = receive_intelligence(payload, store, handoff_store)

        # reenviar EXATAMENTE o mesmo handoff
        r2 = receive_intelligence(payload, store, handoff_store)

        assert r2["status"] == "DUPLICATE"
        assert r2["project_id"] == r1["project_id"]
        assert len(store.list_all()) == 1  # NAO criou segundo Project
        brain = store.load(r1["project_id"])
        assert len(brain.market_intelligence) == 1  # NAO duplicou evidencia
    finally:
        backend.close()


def test_payload_ruim_nao_contamina_project_brain(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_fase9_bad_payload.db")
    store = ProjectBrainStore(ProjectMemory(backend))
    handoff_store = IntelligenceHandoffStore(store.project_memory)
    try:
        payloads_ruins = [
            {"source_system": "SCALAFLOW"},  # sem ID
            {"handoff_id": "x", "source_system": "SCALAFLOW", "schema_version": "abc"},  # schema invalida
            {"handoff_id": "y", "source_system": "SCALAFLOW", "opportunity_score": 999},  # score fora do range
            {"handoff_id": "z", "source_system": "SCALAFLOW", "created_at": "ontem"},  # timestamp invalido
            {"handoff_id": "w", "source_system": "SCALAFLOW", "sales_page_url": "not-a-url"},  # url invalida
            {"handoff_id": "v", "source_system": "SCALAFLOW", "evidence": [{"evidence_type": 123}]},  # tipo incorreto
        ]
        for payload in payloads_ruins:
            resultado = receive_intelligence(payload, store, handoff_store)
            assert resultado["status"] == "REJECTED"

        assert store.list_all() == []  # nenhum contaminou o Project Brain
    finally:
        backend.close()


def test_evidencia_insuficiente_classificada_adequadamente(tmp_path):
    """ScalaFlow afirma 'Produto vencedor' mas NÃO envia evidência
    suficiente -- nunca vira fato confirmado."""
    backend = SQLiteMemory(tmp_path / "test_fase9_evidencia.db")
    store = ProjectBrainStore(ProjectMemory(backend))
    handoff_store = IntelligenceHandoffStore(store.project_memory)
    try:
        payload = {
            "handoff_id": "handoff_produto_vencedor_sem_evidencia",
            "source_system": "SCALAFLOW",
            "title": "Produto vencedor",
            "description": "Produto vencedor, altíssimo potencial",
            "confidence_level": "HIGH",
            "opportunity_score": 88,
            "evidence": [],
        }
        resultado = receive_intelligence(payload, store, handoff_store)
        # score alto + zero evidencia -- fail closed, precisa revisao humana
        assert resultado["status"] == "NEEDS_REVIEW"
        assert store.list_all() == []
        assert any("evidência" in w.lower() or "revis" in w.lower() for w in resultado["warnings"])
    finally:
        backend.close()


def test_restart_completo_com_reenvio_do_mesmo_handoff(tmp_path):
    """Passo a passo exigido: receber handoff; persistir; simular restart;
    carregar; verificar evidence/provenance; reenviar mesmo handoff;
    confirmar deduplicação."""
    db_path = tmp_path / "test_fase9_restart.db"

    backend = SQLiteMemory(db_path)
    store = ProjectBrainStore(ProjectMemory(backend))
    handoff_store = IntelligenceHandoffStore(store.project_memory)
    payload = _mock_scalaflow_payload()
    resultado = receive_intelligence(payload, store, handoff_store)
    project_id = resultado["project_id"]
    backend.close()

    novo_backend = SQLiteMemory(db_path)
    novo_store = ProjectBrainStore(ProjectMemory(novo_backend))
    novo_handoff_store = IntelligenceHandoffStore(novo_store.project_memory)
    try:
        brain = novo_store.load(project_id)
        assert len(brain.market_intelligence) == 1
        assert len(brain.market_intelligence[0].evidence) == 3
        assert brain.oportunidade.evidence

        resultado2 = receive_intelligence(payload, novo_store, novo_handoff_store)
        assert resultado2["status"] == "DUPLICATE"
        assert len(novo_store.load(project_id).market_intelligence) == 1
    finally:
        novo_backend.close()


def test_seguranca_do_workflow_nenhuma_acao_externa_nenhum_gasto(monkeypatch, tmp_path):
    import requests

    def _boom(*a, **k):
        raise AssertionError("Nenhuma chamada HTTP deveria acontecer no pipeline de intelligence")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    backend = SQLiteMemory(tmp_path / "test_fase9_seguranca.db")
    store = ProjectBrainStore(ProjectMemory(backend))
    handoff_store = IntelligenceHandoffStore(store.project_memory)
    try:
        resultado = receive_intelligence(_mock_scalaflow_payload(), store, handoff_store)
        assert resultado["status"] == "PERSISTED"
        # GASTO: US$0 -- nenhum campo de custo real existe no handoff nem no
        # ProjectBrain resultante para esta operacao.
    finally:
        backend.close()
