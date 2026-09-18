"""
Reproducao do quarto round de correcao da Fase 4 (teste real via Telegram):

  BUG 1/2 -- HIPOTESES ESCRITAS COMO FATOS / CLAIMS DE URGENCIA-PROVA-SOCIAL:
  "fornecedores confiaveis", "comunidade de usuarios", "aumentando sua
  chance de sucesso", "depoimentos", "ultima chance", "desconto", "bonus
  exclusivos", "webinario exclusivo", "consultoria one-on-one" apareceram
  como caracteristicas REAIS do produto novo, sem terem sido aprovadas ou
  construidas.

  BUG 3 -- READY_FOR_APPROVAL != APPROVED (gate do Business Plan).

  BUG 4 -- GET_CURRENT_PROJECT_MANIFEST precisa ser uma leitura PURA: ZERO
  LLM, ZERO OpenRouter, ZERO regeneracao de plano, ZERO alteracao no
  projeto -- e nao pode despejar o Business Plan inteiro.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

import tools.product_factory_tools as pft
from core.evidence_guard import sanitizar_claims_herdadas
from memory.layers import ProjectMemory
from memory.project_brain import BusinessPlan, Identidade, ProductBlueprint, ProjectBrain, ProjectBrainStore
from storage import SQLiteMemory


# ---------------------------------------------------------------------------
# BUG 1/2 -- classificacao semantica de hipotese/funcionalidade nao construida
# vs. claim de urgencia/prova social/promessa de resultado
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("frase, esperado_no_resultado", [
    ("Nosso mini-app tem fornecedores confiáveis.", "HIPÓTESE DE FUNCIONALIDADE"),
    ("Diretório de fornecedores de alta qualidade.", "HIPÓTESE DE FUNCIONALIDADE"),
    ("Uma comunidade de usuários pra trocar experiências.", "HIPÓTESE DE FUNCIONALIDADE"),
    ("Oferecemos consultoria one-on-one.", "HIPÓTESE DE FUNCIONALIDADE"),
])
def test_funcionalidade_nao_construida_vira_hipotese_nao_e_apagada(frase, esperado_no_resultado):
    """Pedido explicito: essas sao IDEIAS legitimas -- nao devem ser
    apagadas, devem ser REESCRITAS como hipotese explicita."""
    resultado = sanitizar_claims_herdadas(frase)
    assert esperado_no_resultado in resultado
    # a ideia original continua legivel dentro do marcador (nao "some")
    assert "fornecedores" in resultado.lower() or "comunidade" in resultado.lower() or "consultoria" in resultado.lower()


@pytest.mark.parametrize("frase", [
    "Isso vai aumentar sua chance de sucesso.",
    "Garante o sucesso do seu negócio.",
    "Depoimentos de quem já comprou.",
    "Última chance de garantir sua vaga!",
    "Desconto exclusivo por tempo limitado.",
    "Bônus exclusivos inclusos.",
    "Webinário exclusivo incluso.",
    "Garantia de satisfação de 7 dias.",
])
def test_claims_de_urgencia_prova_social_e_promessa_sao_removidas(frase):
    resultado = sanitizar_claims_herdadas(frase)
    assert "REMOVIDA" in resultado


def test_business_builder_nao_promete_resultado_financeiro_implicito():
    from core.business_builder import construir_plano_negocio

    brain = ProjectBrain(identidade=Identidade(project_id="p1", name="x"))
    brain.blueprint = ProductBlueprint(
        project_id="p1", recommended_product_type="mini_app",
        decision_status="APPROVED", target_audience="Iniciantes",
    )

    class FakeLLM:
        _provider_name = "fake"

        def chat(self, messages, tools=None):
            import json
            from core.contracts.llm import LLMResponse
            payload = {
                "business_model": "Assinatura",
                "value_proposition": "Aumenta sua chance de sucesso no negócio de velas",
                "target_audience": None, "problem": None, "solution": None,
                "positioning": None, "mechanism": None,
                "main_offer": "Comunidade de usuários e fornecedores confiáveis",
                "monetization_format": "Assinatura", "price": None, "price_is_hypothesis": True,
                "bonuses": [], "order_bump": None, "upsell": [], "downsell": [],
                "acquisition_channels": [], "sales_channels": [],
                "sales_page_structure": None, "headline": None, "promise": None,
                "key_arguments": [], "objections": [], "cta": None, "funnel_structure": None,
                "email_sequence": [], "content_strategy": None, "content_channels": [],
                "launch_strategy": None, "plan_30_days": [], "assumptions": [],
                "missing_evidence": [], "risks": [], "dependencies": [], "next_steps": [],
            }
            return LLMResponse(content=json.dumps(payload, ensure_ascii=False))

        def is_alive(self):
            return True

    plano = construir_plano_negocio(brain, llm=FakeLLM())
    assert "chance de sucesso" not in plano.value_proposition.lower() or "REMOVIDA" in plano.value_proposition
    assert "HIPÓTESE DE FUNCIONALIDADE" in plano.main_offer


# ---------------------------------------------------------------------------
# BUG 3 -- READY_FOR_APPROVAL nunca vira APPROVED sozinho
# ---------------------------------------------------------------------------

def test_business_plan_esta_aprovado_so_true_com_approved_explicito():
    bp = BusinessPlan(project_id="p1", approval_status="READY_FOR_APPROVAL")
    assert bp.esta_aprovado() is False
    bp.approval_status = "APPROVED"
    assert bp.esta_aprovado() is True
    bp.approval_status = "DRAFT"
    assert bp.esta_aprovado() is False


# ---------------------------------------------------------------------------
# BUG 4 -- GET_CURRENT_PROJECT_MANIFEST: leitura pura
# ---------------------------------------------------------------------------

@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_fase4_manifesto_puro.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def _brain_aprovado(store, tipo="mini_app"):
    brain = store.create(name="Curso de Velas", tipo="opportunity")
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id, recommended_product_type=tipo,
        decision_status="APPROVED",
    )
    store.save(brain)
    return brain


def test_manifesto_faz_zero_chamadas_llm(monkeypatch, brain_store):
    brain = _brain_aprovado(brain_store)
    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)

    def _boom():
        raise AssertionError("Manifesto NUNCA deveria chamar um LLM")
    monkeypatch.setattr(pft, "_get_llm_economico", _boom)

    def _boom_preparar(*args, **kwargs):
        raise AssertionError("Manifesto NUNCA deveria (re)preparar o plano de producao")
    monkeypatch.setattr(pft, "preparar_plano_producao", _boom_preparar)

    resposta = pft.gerenciar_producao("mostre o manifesto atual", "telegram:1")
    assert "MANIFESTO DO PROJETO" in resposta


def test_manifesto_nao_altera_o_project_brain(monkeypatch, brain_store):
    """ZERO alteracao no projeto: `store.save` nunca e chamado so por
    pedir o manifesto."""
    brain = _brain_aprovado(brain_store)
    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)

    original_save = brain_store.save
    def _save_boom(*args, **kwargs):
        raise AssertionError("Manifesto NUNCA deveria salvar/alterar o Project Brain")
    monkeypatch.setattr(brain_store, "save", _save_boom)

    try:
        resposta = pft.gerenciar_producao("quais artefatos esse projeto precisa?", "telegram:1")
        assert "MANIFESTO DO PROJETO" in resposta
    finally:
        monkeypatch.setattr(brain_store, "save", original_save)


def test_manifesto_nunca_despeja_business_plan_completo(monkeypatch, brain_store):
    brain = _brain_aprovado(brain_store)
    brain.business_plan = BusinessPlan(
        project_id=brain.project_id,
        value_proposition="Um texto de proposta de valor bem longo e detalhado " * 5,
        funnel_structure="Estrutura de funil detalhada com varias etapas " * 5,
        approval_status="READY_FOR_APPROVAL",
    )
    brain_store.save(brain)

    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)

    resposta = pft.gerenciar_producao("mostre somente o manifesto atual", "telegram:1")
    assert "proposta de valor bem longo" not in resposta
    assert "Estrutura de funil detalhada" not in resposta
    assert "status_business_plan: READY_FOR_APPROVAL" in resposta


def test_manifesto_nao_chama_business_builder(monkeypatch, brain_store):
    """'mostre somente o manifesto atual' nunca deve disparar o Business
    Builder (que teria custo de LLM e alteraria o projeto)."""
    import tools.business_builder_tools as bbt

    brain = _brain_aprovado(brain_store)
    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)

    def _boom(*args, **kwargs):
        raise AssertionError("Manifesto nunca deveria chamar o Business Builder")
    monkeypatch.setattr(bbt, "gerenciar_negocio", _boom)

    resposta = pft.gerenciar_producao("mostre somente o manifesto atual", "telegram:1")
    assert "MANIFESTO DO PROJETO" in resposta


def test_manifesto_funciona_sem_production_plan_ainda_preparado(monkeypatch, brain_store):
    brain = _brain_aprovado(brain_store)
    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)

    resposta = pft.gerenciar_producao("quais artefatos esse projeto precisa?", "telegram:1")
    assert "MANIFESTO DO PROJETO" in resposta
    assert "status_producao: None" in resposta


def test_manifesto_bloqueia_sem_aprovacao_do_blueprint(monkeypatch, brain_store):
    """Regressao: o manifesto continua atras do gate de aprovacao do
    Product Blueprint (nao virou uma porta aberta sem controle)."""
    brain = brain_store.create(name="x", tipo="opportunity")
    brain.blueprint = ProductBlueprint(project_id=brain.project_id, decision_status="PENDING_APPROVAL")
    brain_store.save(brain)

    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)

    resposta = pft.gerenciar_producao("mostre o manifesto atual", "telegram:1")
    assert "ainda não foi aprovado" in resposta.lower()


# ---------------------------------------------------------------------------
# BUG DE ROTEAMENTO (5º round) -- Orchestrator -> agente product_factory ->
# Tool -> GET_CURRENT_PROJECT_MANIFEST, ponta a ponta, ZERO LLM.
# ---------------------------------------------------------------------------

class _FakeLLMQueBoom:
    """Prova que NENHUM LLM e chamado em nenhum ponto do pipeline (roteamento
    do orchestrator, nem fallback dentro do SpecialistAgent)."""

    def chat(self, messages, tools=None):
        raise AssertionError("Nenhum LLM deveria ser chamado pra ler o manifesto!")

    def is_alive(self):
        return True


@pytest.mark.parametrize("mensagem", [
    "Cris, mostre somente o manifesto atual deste projeto. Não gere nem altere nada.",
    "Cris, mostre o manifesto.",
    "Qual o status deste projeto?",
    "Mostre a estrutura atual do projeto.",
])
def test_pipeline_completo_orchestrator_ate_manifesto_zero_llm(monkeypatch, brain_store, mensagem):
    """Reproducao EXATA do bug real: Telegram -> Orchestrator -> agente
    `product_factory` -> Tool -> `get_current_project_manifest` -> Project
    Brain -> resposta, sem passar pelo assistente generico em nenhum ponto."""
    import agents.product_factory as pf_agent
    from agents.orchestrator import AgentOrchestrator

    brain = _brain_aprovado(brain_store)
    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)

    fake_llm = _FakeLLMQueBoom()
    agente_product_factory = pf_agent.create(fake_llm)
    orc = AgentOrchestrator(llm=fake_llm, agents=[agente_product_factory])

    from core.models import IncomingMessage
    incoming = IncomingMessage(channel="telegram", sender_id="123", text=mensagem)
    resposta = orc.handle(incoming)

    assert "não tenho acesso" not in resposta.lower()
    assert "/use" not in resposta.lower()
    assert "MANIFESTO DO PROJETO" in resposta


def test_pipeline_sem_projeto_em_foco_nao_inventa_e_nao_chama_llm(monkeypatch):
    """Sem projeto em foco (UserFocusStore vazio): responde honestamente,
    nunca inventa um manifesto, nunca chama LLM."""
    import agents.product_factory as pf_agent
    from agents.orchestrator import AgentOrchestrator
    from core.models import IncomingMessage

    monkeypatch.setattr(pft, "get_foco_atual", lambda session: None)

    fake_llm = _FakeLLMQueBoom()
    agente_product_factory = pf_agent.create(fake_llm)
    orc = AgentOrchestrator(llm=fake_llm, agents=[agente_product_factory])

    incoming = IncomingMessage(channel="telegram", sender_id="123", text="Cris, mostre o manifesto atual.")
    resposta = orc.handle(incoming)

    assert "MANIFESTO DO PROJETO" not in resposta
    assert "não sei a qual projeto" in resposta.lower() or "não sei" in resposta.lower()
