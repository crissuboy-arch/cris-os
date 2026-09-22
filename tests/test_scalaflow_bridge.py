"""
Testes da ponte ScalaFlow (`core/scalaflow_bridge.py`) -- fecha o caminho
MarketIntelligenceHandoff -> BusinessPlan -> PendingApproval -> Telegram ->
aprovação/rejeição -> ExecutionPlan -> Tasks, reaproveitando os componentes
JÁ existentes das Fases 6-9 (Approval Router, Business Builder, Product
Architect, Execution Engine, MarketIntelligenceHandoff).

Sem IA paga: todo LLM usado aqui é um FAKE em memória (mesmo padrão já
usado em `tests/test_fase7_aprovacao.py:FakeLLMJSON`) -- zero chamada de
rede/custo real. `llm=None` também é testado explicitamente (caminho 100%
determinístico, sem evidência suficiente).
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

import channels.telegram.bot as telegram_bot
import core.scalaflow_bridge as bridge
from core.approval_router import resolver_aprovacao_contextual
from core.market_intelligence import receive_intelligence
from memory.layers import ProjectMemory
from memory.project_brain import IntelligenceHandoffStore, PendingApprovalStore, ProjectBrainStore
from storage import SQLiteMemory

SESSION = "telegram:1"


# ---------------------------------------------------------------------------
# Fixtures -- mesmo padrão de tmp_path + SQLiteMemory usado em todo o resto
# da suíte (NUNCA toca no banco de produção real).
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_scalaflow_bridge.db"


@pytest.fixture()
def brain_store(db_path):
    backend = SQLiteMemory(db_path)
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


@pytest.fixture()
def pending_store(brain_store):
    return PendingApprovalStore(brain_store.project_memory)


@pytest.fixture()
def handoff_store(brain_store):
    return IntelligenceHandoffStore(brain_store.project_memory)


@pytest.fixture(autouse=True)
def _sessao_fixa(monkeypatch):
    """Fixa a sessão Telegram canônica usada por `sessao_cris()` para um
    valor previsível em teste (independe de `TELEGRAM_ALLOWED_USER_ID` real)."""
    monkeypatch.setattr(bridge, "sessao_cris", lambda: SESSION)


@pytest.fixture(autouse=True)
def _sem_notificacao_de_verdade(monkeypatch):
    """Por padrão, testes NÃO devem bater na API real do Telegram --
    substitui por um fake que só registra chamadas. Testes que querem
    verificar o conteúdo da notificação sobrescrevem isso."""
    monkeypatch.setattr(telegram_bot, "enviar_mensagem_proativa", lambda texto: True)


def _payload_carla_like(handoff_id: str, **overrides) -> dict:
    payload = {
        "handoff_id": handoff_id,
        "source_system": "scalaflow",
        "source_module": "collected_ad_transform",
        "title": "Carla Figurinhas",
        "market": "UNKNOWN",
        "niche": "UNKNOWN",
        "platform": "FACEBOOK",
        "opportunity_score": 88,
        "confidence_level": "UNKNOWN",
        "evidence": [{
            "platform": "FACEBOOK", "module": "collected_ad_transform",
            "original_url": "https://www.facebook.com/ads/library/?id=123",
            "collected_at": "2026-09-21T21:56:24+00:00",
        }],
    }
    payload.update(overrides)
    return payload


def _payload_vazio(handoff_id: str) -> dict:
    """Handoff estruturalmente válido mas SEM evidência nenhuma aproveitável
    (nem headline/copy/nicho/score) -- caminho fail-closed."""
    return {
        "handoff_id": handoff_id,
        "source_system": "scalaflow",
        "source_module": "collected_ad_transform",
    }


class FakeLLMProductArchitect:
    """Fake do Product Architect -- devolve candidatos SEM recomendação
    confiante (`ready_for_approval: false`), justamente para exercitar a
    ponte de consolidação de `core/scalaflow_bridge.py` (promove o melhor
    candidato mesmo sem o próprio Product Architect ter "decidido")."""

    def __init__(self):
        self._provider_name = "fake:inteligente"
        self.chamadas = 0

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        self.chamadas += 1
        corpo = {
            "candidates": [
                {
                    "product_type": "kit_digital", "audience_hypothesis": "Pessoas que gostam de papelaria personalizada",
                    "problem": "Falta de opções de figurinhas personalizadas", "why_it_fits": "Nicho com demanda visível no anúncio",
                    "production_difficulty": "baixa", "estimated_speed_to_mvp": "3-5 dias",
                    "monetization": ["venda direta"], "supporting_evidence": ["score_scalaflow: 88"],
                    "missing_evidence": ["validação de preço"], "confidence": "MEDIO",
                },
                {
                    "product_type": "template", "audience_hypothesis": "Criadores de conteúdo",
                    "problem": "Falta de templates prontos", "why_it_fits": "Alternativa mais simples de produzir",
                    "production_difficulty": "baixa", "estimated_speed_to_mvp": "1-2 dias",
                    "monetization": ["venda direta"], "supporting_evidence": [], "missing_evidence": ["nicho ainda genérico"],
                    "confidence": "BAIXO",
                },
            ],
            "recommendation": {"product_type": None, "reasoning_summary": "Evidência ainda fraca (niche=UNKNOWN)", "ready_for_approval": False},
            "assumptions": ["Mercado de papelaria digital existe"],
            "risks": ["Nicho pouco específico"],
        }
        return LLMResponse(content=json.dumps(corpo, ensure_ascii=False))

    def is_alive(self):
        return True


_BUSINESS_PLAN_PAYLOAD_MINIMO = {
    "business_model": "Venda direta de kit digital", "value_proposition": "Figurinhas prontas para imprimir",
    "target_audience": "Pessoas que gostam de papelaria personalizada", "problem": "Falta de opções prontas",
    "solution": "Kit digital pronto para uso", "positioning": "Mais prático do mercado",
    "mechanism": "Download imediato", "main_offer": "Kit de figurinhas Carla",
    "monetization_format": "Pagamento único", "price": "R$ 19,90", "price_is_hypothesis": True,
    "bonuses": [], "order_bump": None, "upsell": [], "downsell": [],
    "acquisition_channels": ["Instagram"], "sales_channels": ["Página própria"],
    "sales_page_structure": "Headline -> galeria -> CTA", "headline": "Figurinhas prontas",
    "promise": "Você recebe o arquivo pronto para imprimir", "key_arguments": [],
    "objections": [], "cta": "Quero o kit", "funnel_structure": "Anúncio -> página -> checkout",
    "email_sequence": [{"numero": i, "objetivo": "x", "assunto": "x", "resumo": "x"} for i in range(1, 6)],
    "content_strategy": "Conteúdo visual", "content_channels": ["Instagram"],
    "launch_strategy": "Lançamento direto", "plan_30_days": [],
    "assumptions": ["Público tem interesse real"], "missing_evidence": ["validação de preço"],
    "risks": ["Nicho genérico"], "dependencies": [], "next_steps": ["Validar preço"],
    "desired_outcome": None, "subniche": None, "offer_type": "kit_digital",
    "pricing_strategy": "Preço único baixo", "estimated_price_range": None,
    "bonuses_strategy": None, "guarantee_strategy": None, "urgency_strategy": None,
    "primary_channel": "Instagram", "secondary_channels": [], "sales_model": "Checkout self-service",
    "estimated_ticket": None, "estimated_margin": None, "estimated_cac_target": None,
    "estimated_break_even": None, "revenue_scenarios": [],
    "competitors": [], "differentiation": "Nicho específico", "market_gaps": [], "barriers": [],
    "validation_requirements": [], "confidence_score": "baixo",
    "required_assets": ["Landing page"], "kpis": ["conversão"],
}


class FakeLLMBusinessBuilder:
    def __init__(self, payload=None):
        self.payload = payload or _BUSINESS_PLAN_PAYLOAD_MINIMO
        self._provider_name = "fake:economico"
        self.chamadas = 0

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        self.chamadas += 1
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False))

    def is_alive(self):
        return True


def _receber_handoff_carla(brain_store, handoff_store, handoff_id="ho_carla_teste_1", **overrides):
    resultado = receive_intelligence(_payload_carla_like(handoff_id, **overrides), brain_store, handoff_store)
    assert resultado["status"] == "PERSISTED"
    return resultado["project_id"]


# ---------------------------------------------------------------------------
# 1) Handoff completo Carla-like: receive -> project
# ---------------------------------------------------------------------------

def test_handoff_completo_cria_projeto(brain_store, handoff_store):
    project_id = _receber_handoff_carla(brain_store, handoff_store)
    brain = brain_store.load(project_id)
    assert brain is not None
    assert brain.market_intelligence[0].handoff_id == "ho_carla_teste_1"
    assert brain.business_plan is None
    assert brain.blueprint is None


# ---------------------------------------------------------------------------
# 2) project -> BusinessPlan (via blueprint consolidado) -> PendingApproval
# ---------------------------------------------------------------------------

def test_project_para_business_plan_e_pending_approval(brain_store, handoff_store, pending_store):
    project_id = _receber_handoff_carla(brain_store, handoff_store)
    brain = brain_store.load(project_id)

    resultado = bridge.avancar_projeto(
        brain, brain_store, pending_store, session=SESSION,
        llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder(),
    )

    assert resultado["status"] == "PENDING_APPROVAL_CREATED"
    assert resultado["project_id"] == project_id
    assert resultado["handoff_id"] == "ho_carla_teste_1"

    recarregado = brain_store.load(project_id)
    assert recarregado.blueprint is not None
    # Ponte consolida a aprovação de formato mesmo sem "ready_for_approval"
    # do próprio Product Architect -- documentado em core/scalaflow_bridge.py.
    assert recarregado.blueprint.decision_status == "APPROVED"
    assert recarregado.blueprint.recommended_product_type == "kit_digital"
    assert recarregado.business_plan is not None
    assert recarregado.business_plan.approval_status == "READY_FOR_APPROVAL"

    pendente = pending_store.get_pending(SESSION)
    assert pendente is not None
    assert pendente["artifact_type"] == "BUSINESS_PLAN"
    assert pendente["project_id"] == project_id
    # vínculo inequívoco project_id + handoff_id (Seção 4 da missão)
    assert pendente["handoff_id"] == "ho_carla_teste_1"


# ---------------------------------------------------------------------------
# 3) Sem evidência nenhuma -> fail closed, nada criado
# ---------------------------------------------------------------------------

def test_sem_evidencia_nao_cria_nada(brain_store, handoff_store, pending_store):
    resultado_recv = receive_intelligence(_payload_vazio("ho_vazio_1"), brain_store, handoff_store)
    assert resultado_recv["status"] == "PERSISTED"
    project_id = resultado_recv["project_id"]
    brain = brain_store.load(project_id)

    resultado = bridge.avancar_projeto(
        brain, brain_store, pending_store, session=SESSION,
        llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder(),
    )
    assert resultado["status"] == "NEEDS_MORE_EVIDENCE"

    recarregado = brain_store.load(project_id)
    assert recarregado.blueprint is None
    assert recarregado.business_plan is None
    assert pending_store.get_pending(SESSION) is None


# ---------------------------------------------------------------------------
# 4) Aprovação -> ExecutionPlan -> Tasks (encadeado pelo Approval Router)
# ---------------------------------------------------------------------------

def test_aprovacao_gera_execution_plan_com_tasks_dependentes(brain_store, handoff_store, pending_store):
    project_id = _receber_handoff_carla(brain_store, handoff_store)
    brain = brain_store.load(project_id)
    bridge.avancar_projeto(
        brain, brain_store, pending_store, session=SESSION,
        llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder(),
    )

    resposta = resolver_aprovacao_contextual("Aprovado", SESSION, pending_store, brain_store)
    assert "Plano de negócio aprovado" in resposta
    assert "plano de execução" in resposta.lower()

    recarregado = brain_store.load(project_id)
    assert recarregado.business_plan.approval_status == "APPROVED"
    assert recarregado.execution_plan is not None
    assert recarregado.execution_plan.status == "READY_FOR_APPROVAL"
    assert len(recarregado.execution_plan.tasks) == 4
    # dependências reais entre tasks (Fase 8) -- nunca uma lista solta
    ids = {t.task_id for t in recarregado.execution_plan.tasks}
    for t in recarregado.execution_plan.tasks[1:]:
        assert set(t.dependencies) <= ids

    pendente = pending_store.get_pending(SESSION)
    assert pendente["artifact_type"] == "EXECUTION_PLAN"
    assert pendente["project_id"] == project_id


# ---------------------------------------------------------------------------
# 5) Rejeição -> SEM ExecutionPlan, sem Tasks, nenhuma ação externa
# ---------------------------------------------------------------------------

def test_rejeicao_nao_cria_execution_plan(brain_store, handoff_store, pending_store):
    project_id = _receber_handoff_carla(brain_store, handoff_store)
    brain = brain_store.load(project_id)
    bridge.avancar_projeto(
        brain, brain_store, pending_store, session=SESSION,
        llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder(),
    )

    resposta = resolver_aprovacao_contextual("Não gostei, quero outro.", SESSION, pending_store, brain_store)
    assert "rejeitado" in resposta.lower()

    recarregado = brain_store.load(project_id)
    assert recarregado.business_plan.approval_status == "REJECTED"
    assert recarregado.execution_plan is None
    assert pending_store.get_pending(SESSION) is None


# ---------------------------------------------------------------------------
# 6) Duplicate handoff -> zero duplicação de projeto
# ---------------------------------------------------------------------------

def test_handoff_duplicado_nao_duplica_projeto(brain_store, handoff_store):
    project_id_1 = _receber_handoff_carla(brain_store, handoff_store)
    resultado2 = receive_intelligence(_payload_carla_like("ho_carla_teste_1"), brain_store, handoff_store)
    assert resultado2["status"] == "DUPLICATE"
    assert resultado2["project_id"] == project_id_1
    assert len(brain_store.list_all()) == 1


# ---------------------------------------------------------------------------
# 7) Restart/retry -> zero duplicação (chamar avancar_projeto 2x seguidas)
# ---------------------------------------------------------------------------

def test_chamar_avancar_projeto_duas_vezes_nao_duplica_nada(brain_store, handoff_store, pending_store):
    project_id = _receber_handoff_carla(brain_store, handoff_store)
    brain = brain_store.load(project_id)
    llm_bp, llm_biz = FakeLLMProductArchitect(), FakeLLMBusinessBuilder()

    r1 = bridge.avancar_projeto(brain, brain_store, pending_store, session=SESSION, llm_blueprint=llm_bp, llm_business=llm_biz)
    assert r1["status"] == "PENDING_APPROVAL_CREATED"
    assert llm_biz.chamadas == 1

    brain2 = brain_store.load(project_id)  # simula um restart -- releitura do disco
    r2 = bridge.avancar_projeto(brain2, brain_store, pending_store, session=SESSION, llm_blueprint=llm_bp, llm_business=llm_biz)
    assert r2["status"] == "PENDING_APPROVAL_ALREADY_SET"
    assert llm_biz.chamadas == 1  # NAO gerou um segundo plano

    assert len(brain_store.list_all()) == 1


# ---------------------------------------------------------------------------
# 8) Resume de projeto existente SEM novo handoff (mecanismo da Seção 5)
# ---------------------------------------------------------------------------

def test_resume_via_handoff_id_sem_novo_handoff(brain_store, handoff_store, pending_store):
    project_id = _receber_handoff_carla(brain_store, handoff_store)

    resultado = bridge.avancar_a_partir_do_handoff(
        "ho_carla_teste_1", brain_store, handoff_store, pending_store, session=SESSION,
        llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder(),
    )
    assert resultado["status"] == "PENDING_APPROVAL_CREATED"
    assert resultado["project_id"] == project_id

    # Chamar de novo pelo MESMO handoff_id (ex.: botão do ScalaFlow já
    # SENT/desabilitado -- única forma de continuar é por aqui) -- idempotente.
    resultado2 = bridge.avancar_a_partir_do_handoff(
        "ho_carla_teste_1", brain_store, handoff_store, pending_store, session=SESSION,
        llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder(),
    )
    assert resultado2["status"] == "PENDING_APPROVAL_ALREADY_SET"
    assert len(brain_store.list_all()) == 1


def test_resume_handoff_inexistente_devolve_not_found(brain_store, handoff_store, pending_store):
    resultado = bridge.avancar_a_partir_do_handoff("ho_nao_existe", brain_store, handoff_store, pending_store, session=SESSION)
    assert resultado["status"] == "HANDOFF_NOT_FOUND"


def test_resume_detecta_etapa_faltante_blueprint_existe_business_plan_falta(brain_store, handoff_store, pending_store):
    """Exemplo literal da missão: se o blueprint já existe (aprovado) mas o
    BusinessPlan falta, o resume NÃO deve recriar o blueprint -- só cria o
    BusinessPlan."""
    project_id = _receber_handoff_carla(brain_store, handoff_store)
    brain = brain_store.load(project_id)
    from memory.project_brain import ProductBlueprint

    brain.blueprint = ProductBlueprint(
        project_id=project_id, recommended_product_type="kit_digital",
        decision_status="APPROVED", generated_by="teste_manual",
    )
    brain_store.save(brain)

    llm_bp_que_nao_deveria_ser_chamado = FakeLLMProductArchitect()
    resultado = bridge.avancar_a_partir_do_handoff(
        "ho_carla_teste_1", brain_store, handoff_store, pending_store, session=SESSION,
        llm_blueprint=llm_bp_que_nao_deveria_ser_chamado, llm_business=FakeLLMBusinessBuilder(),
    )
    assert resultado["status"] == "PENDING_APPROVAL_CREATED"
    assert llm_bp_que_nao_deveria_ser_chamado.chamadas == 0  # blueprint reaproveitado, nao regenerado

    recarregado = brain_store.load(project_id)
    assert recarregado.blueprint.generated_by == "teste_manual"  # inalterado
    assert recarregado.business_plan is not None


def test_resume_quando_approval_ja_existe_nao_duplica(brain_store, handoff_store, pending_store):
    project_id = _receber_handoff_carla(brain_store, handoff_store)
    brain = brain_store.load(project_id)
    bridge.avancar_projeto(
        brain, brain_store, pending_store, session=SESSION,
        llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder(),
    )
    pendente_antes = pending_store.get_pending(SESSION)

    resultado = bridge.avancar_a_partir_do_handoff("ho_carla_teste_1", brain_store, handoff_store, pending_store, session=SESSION)
    assert resultado["status"] == "PENDING_APPROVAL_ALREADY_SET"
    assert pending_store.get_pending(SESSION) == pendente_antes


def test_resume_nao_sobrescreve_pendencia_de_outro_projeto(brain_store, handoff_store, pending_store):
    project_a = _receber_handoff_carla(brain_store, handoff_store, handoff_id="ho_projeto_a")
    _receber_handoff_carla(brain_store, handoff_store, handoff_id="ho_projeto_b")

    pending_store.set_pending(SESSION, project_a, "BUSINESS_PLAN", "APPROVE", handoff_id="ho_projeto_a")

    resultado = bridge.avancar_a_partir_do_handoff(
        "ho_projeto_b", brain_store, handoff_store, pending_store, session=SESSION,
        llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder(),
    )
    assert resultado["status"] == "PENDING_APPROVAL_BLOCKED_BY_OTHER"
    pendente = pending_store.get_pending(SESSION)
    assert pendente["project_id"] == project_a  # inalterado


# ---------------------------------------------------------------------------
# 9) Notificação Telegram idempotente + aprovação continua o projeto correto
# ---------------------------------------------------------------------------

def test_notificacao_telegram_idempotente(monkeypatch, brain_store, handoff_store, pending_store):
    chamadas = []
    monkeypatch.setattr(telegram_bot, "enviar_mensagem_proativa", lambda texto: chamadas.append(texto) or True)

    project_id = _receber_handoff_carla(brain_store, handoff_store)
    brain = brain_store.load(project_id)
    bridge.avancar_projeto(brain, brain_store, pending_store, session=SESSION, llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder())
    assert len(chamadas) == 1

    brain2 = brain_store.load(project_id)
    bridge.avancar_projeto(brain2, brain_store, pending_store, session=SESSION, llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder())
    assert len(chamadas) == 1  # nao notificou de novo


def test_aprovacao_telegram_continua_projeto_correto(brain_store, handoff_store, pending_store):
    project_a = _receber_handoff_carla(brain_store, handoff_store, handoff_id="ho_projeto_a")
    project_b = _receber_handoff_carla(brain_store, handoff_store, handoff_id="ho_projeto_b")

    bridge.avancar_a_partir_do_handoff("ho_projeto_a", brain_store, handoff_store, pending_store, session=SESSION, llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder())
    resolver_aprovacao_contextual("Aprovado", SESSION, pending_store, brain_store)

    brain_a = brain_store.load(project_a)
    brain_b = brain_store.load(project_b)
    assert brain_a.business_plan.approval_status == "APPROVED"
    assert brain_b.business_plan is None  # projeto B nunca foi tocado


# ---------------------------------------------------------------------------
# 10) Nenhuma ação externa antes da aprovação
# ---------------------------------------------------------------------------

def test_nenhuma_chamada_http_externa_antes_da_aprovacao(monkeypatch, brain_store, handoff_store, pending_store):
    import requests

    def _boom(*a, **k):
        raise AssertionError("avancar_projeto nao deveria fazer chamada HTTP externa real")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    project_id = _receber_handoff_carla(brain_store, handoff_store)
    brain = brain_store.load(project_id)
    resultado = bridge.avancar_projeto(
        brain, brain_store, pending_store, session=SESSION,
        llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder(),
    )
    assert resultado["status"] == "PENDING_APPROVAL_CREATED"


def test_notificacao_falha_de_rede_nao_quebra_a_orquestracao(monkeypatch, brain_store, handoff_store, pending_store):
    def _falha(texto):
        raise OSError("rede indisponível (simulado)")
    monkeypatch.setattr(telegram_bot, "enviar_mensagem_proativa", _falha)

    project_id = _receber_handoff_carla(brain_store, handoff_store)
    brain = brain_store.load(project_id)
    resultado = bridge.avancar_projeto(
        brain, brain_store, pending_store, session=SESSION,
        llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder(),
    )
    assert resultado["status"] == "PENDING_APPROVAL_CREATED"
    assert resultado["notificado"] is False


# ---------------------------------------------------------------------------
# 11) Status (montar_status) -- nunca inclui segredo
# ---------------------------------------------------------------------------

def test_montar_status_reflete_estado_real(brain_store, handoff_store, pending_store):
    project_id = _receber_handoff_carla(brain_store, handoff_store)
    brain = brain_store.load(project_id)
    bridge.avancar_projeto(brain, brain_store, pending_store, session=SESSION, llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder())

    status = bridge.montar_status("ho_carla_teste_1", brain_store, handoff_store, pending_store, session=SESSION)
    assert status["project_id"] == project_id
    assert status["project_name"] == "Carla Figurinhas"
    assert status["business_plan"]["status"] == "READY_FOR_APPROVAL"
    assert status["approval"] == {"artifact_type": "BUSINESS_PLAN", "status": "PENDING"}
    assert status["execution_plan"] == {"id": None, "status": None}
    assert status["tasks"] == {"total": 0, "pending": 0, "running": 0, "completed": 0, "failed": 0}

    resolver_aprovacao_contextual("Aprovado", SESSION, pending_store, brain_store)
    status2 = bridge.montar_status("ho_carla_teste_1", brain_store, handoff_store, pending_store, session=SESSION)
    assert status2["business_plan"]["status"] == "APPROVED"
    assert status2["approval"] == {"artifact_type": "EXECUTION_PLAN", "status": "PENDING"}
    assert status2["execution_plan"]["status"] == "READY_FOR_APPROVAL"
    assert status2["tasks"]["total"] == 4


def test_montar_status_handoff_inexistente_devolve_none(brain_store, handoff_store, pending_store):
    assert bridge.montar_status("ho_nao_existe", brain_store, handoff_store, pending_store) is None


def test_montar_status_nunca_contem_segredo(monkeypatch, brain_store, handoff_store, pending_store):
    from config.settings import settings as cfg_settings
    monkeypatch.setattr(cfg_settings, "CRIS_OS_INTEGRATION_TOKEN", "segredo-super-secreto")
    project_id = _receber_handoff_carla(brain_store, handoff_store)
    brain = brain_store.load(project_id)
    bridge.avancar_projeto(brain, brain_store, pending_store, session=SESSION, llm_blueprint=FakeLLMProductArchitect(), llm_business=FakeLLMBusinessBuilder())

    status = bridge.montar_status("ho_carla_teste_1", brain_store, handoff_store, pending_store, session=SESSION)
    bruto = json.dumps(status)
    assert "segredo-super-secreto" not in bruto
    assert "token" not in bruto.lower()
