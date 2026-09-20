"""
Testes da Fase 7: Business Builder ampliado (estrategia de negocio) --
novos campos do BusinessPlan, handoff estruturado, honestidade (nunca
fabrica economia/confianca sem base), e o teste funcional pedido
explicitamente (oportunidade fictícia de educação online).

Nada aqui bate em nenhuma API externa nem gasta OpenRouter de verdade --
LLM é sempre um Fake controlado neste arquivo.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

import pytest

from core.business_builder import construir_plano_negocio, gerar_handoff
from memory.layers import ProjectMemory
from memory.project_brain import BusinessPlan, ProductBlueprint, ProjectBrainStore
from storage import SQLiteMemory


@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_fase7_business_builder.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def _produto_aprovado(store, **overrides):
    brain = store.create(name="Automação com IA para Profissionais", tipo="opportunity")
    brain.oportunidade.evidence = ["12 anúncios ativos sobre automação com IA no Meta"]
    brain.oportunidade.risks = ["Mercado de cursos de IA está saturado"]
    defaults = dict(
        project_id=brain.project_id,
        recommended_product_type="curso",
        target_audience="Profissionais que querem aprender automação com IA",
        problem="Não sabem por onde começar a automatizar tarefas com IA",
        product_concept="Curso de automação com IA para profissionais",
        niche="educação online",
        market="educação online para profissionais",
        country="BR",
        differentiation="Método prático com casos reais de automação",
        monetization_options=["assinatura", "pagamento único"],
        evidence=list(brain.oportunidade.evidence),
        risks=list(brain.oportunidade.risks),
        decision_status="APPROVED",
    )
    defaults.update(overrides)
    brain.blueprint = ProductBlueprint(**defaults)
    store.save(brain)
    return brain


class FakeLLMJSON:
    def __init__(self, payload: dict):
        self.payload = payload
        self._provider_name = "fake:economico"
        self.chamadas = 0

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        self.chamadas += 1
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False))

    def is_alive(self):
        return True


_PAYLOAD_EDUCACAO_ONLINE = {
    "business_model": "Curso online com comunidade",
    "value_proposition": "Aprenda a automatizar seu trabalho com IA em 4 semanas",
    "target_audience": "Profissionais que querem aprender automação com IA",
    "problem": "Não sabem por onde começar a automatizar tarefas com IA",
    "solution": "Curso estruturado com projetos práticos",
    "positioning": "O curso mais prático de automação com IA para quem já trabalha",
    "mechanism": "Método de automação em 4 etapas",
    "main_offer": "Curso + comunidade de prática",
    "monetization_format": "Pagamento único com upsell de mentoria",
    "price": "R$ 697",
    "price_is_hypothesis": True,
    "bonuses": ["Templates de automação prontos"],
    "order_bump": "Checklist de ferramentas",
    "upsell": ["Mentoria em grupo"],
    "downsell": ["Versão self-paced com desconto"],
    "acquisition_channels": ["LinkedIn", "YouTube", "Instagram"],
    "sales_channels": ["Página de vendas própria"],
    "sales_page_structure": "Headline -> dor -> solução -> prova -> oferta -> CTA",
    "headline": "Automatize seu trabalho com IA em 4 semanas",
    "promise": "Você vai sair sabendo automatizar pelo menos 3 tarefas do seu dia a dia",
    "key_arguments": ["Método testado em projetos reais", "Comunidade de prática"],
    "objections": [{"objecao": "Não sei programar", "resposta": "O curso não exige programação"}],
    "cta": "Quero automatizar meu trabalho",
    "funnel_structure": "Anúncio -> Lead magnet -> Sequência de e-mail -> Oferta",
    "email_sequence": [
        {"numero": 1, "objetivo": "Boas-vindas", "assunto": "Bem-vindo(a)!", "resumo": "Apresenta o método"},
        {"numero": 2, "objetivo": "Autoridade", "assunto": "Como cheguei aqui", "resumo": "História de origem"},
        {"numero": 3, "objetivo": "Prova social", "assunto": "Resultados de quem já começou", "resumo": "Depoimentos"},
        {"numero": 4, "objetivo": "Quebra de objeção", "assunto": "Não sabe programar? Leia isso", "resumo": "Trata objeções"},
        {"numero": 5, "objetivo": "Oferta", "assunto": "Últimas vagas", "resumo": "CTA final"},
    ],
    "content_strategy": "Conteúdo educativo sobre automação 3x por semana",
    "content_channels": ["LinkedIn", "YouTube"],
    "launch_strategy": "Lançamento por lista de espera",
    "plan_30_days": [
        {"periodo": "dias 1-7", "acoes": ["Gravar aulas piloto", "Criar lista de espera"]},
        {"periodo": "dias 8-30", "acoes": ["Publicar conteúdo", "Abrir vendas"]},
    ],
    "assumptions": ["Público tem interesse real em automação, não só curiosidade"],
    "missing_evidence": ["Nenhum teste de preço real feito ainda"],
    "risks": ["Mercado de cursos de IA está saturado"],
    "dependencies": ["Gravação das aulas"],
    "next_steps": ["Validar preço com uma lista pequena"],
    "desired_outcome": "Profissional automatiza pelo menos 3 tarefas repetitivas",
    "subniche": "automação com IA para não-programadores",
    "offer_type": "curso online + comunidade",
    "pricing_strategy": "Preço único de entrada, upsell de mentoria",
    "estimated_price_range": "R$ 497 a R$ 997",
    "bonuses_strategy": "Empilhar templates prontos para reduzir fricção",
    "guarantee_strategy": "Garantia de 7 dias incondicional",
    "urgency_strategy": "Turma com vagas limitadas por coorte",
    "primary_channel": "LinkedIn",
    "secondary_channels": ["YouTube", "Instagram"],
    "sales_model": "Checkout self-service com página de vendas",
    "estimated_ticket": "R$ 697 (estimativa de planejamento)",
    "estimated_margin": "70% (estimativa, sem custo real validado)",
    "estimated_cac_target": "Até R$ 150 por venda (meta de planejamento)",
    "estimated_break_even": "30 vendas para cobrir produção do curso (estimativa)",
    "revenue_scenarios": [
        {"nome": "LOW", "descricao": "10 vendas no primeiro lançamento", "type": "PLANNING_ASSUMPTION"},
        {"nome": "STANDARD", "descricao": "30 vendas no primeiro lançamento", "type": "PLANNING_ASSUMPTION"},
        {"nome": "EXPANDED", "descricao": "80 vendas no primeiro lançamento", "type": "PLANNING_ASSUMPTION"},
    ],
    "competitors": ["Cursos genéricos de IA sem foco em automação prática"],
    "differentiation": "Foco em automação prática para quem já trabalha, não em teoria de IA",
    "market_gaps": ["Poucos cursos focam em automação para não-programadores"],
    "barriers": ["Ceticismo sobre IA substituir o próprio trabalho"],
    "validation_requirements": ["Testar conversão da página de vendas com tráfego real"],
    "confidence_score": "medio",
    "required_assets": ["Landing page com prova social e CTA claro", "5 vídeos de aula piloto"],
    "kpis": ["Taxa de conversão da lista de espera", "CAC por canal"],
}


# ---------------------------------------------------------------------------
# Novos campos (Fase 7) -- populados via LLM, nunca inventados sem base
# ---------------------------------------------------------------------------

def test_construir_plano_negocio_popula_campos_ampliados_da_fase_7(brain_store):
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=FakeLLMJSON(_PAYLOAD_EDUCACAO_ONLINE))

    assert plano.positioning
    assert plano.monetization_format
    assert plano.primary_channel == "LinkedIn"
    assert plano.secondary_channels == ["YouTube", "Instagram"]
    assert plano.competitors
    assert plano.risks
    assert plano.assumptions
    assert plano.kpis
    assert plano.next_steps
    assert plano.required_assets
    assert plano.confidence_score == "medio"


def test_market_niche_herdados_do_blueprint_sem_duplicar_fonte(brain_store):
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=FakeLLMJSON(_PAYLOAD_EDUCACAO_ONLINE))
    assert plano.market == brain.blueprint.market
    assert plano.niche == brain.blueprint.niche


def test_product_blueprint_id_e_deterministico_e_rastreavel(brain_store):
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=FakeLLMJSON(_PAYLOAD_EDUCACAO_ONLINE))
    assert plano.product_blueprint_id == f"blueprint:{brain.project_id}"


def test_revenue_scenarios_sempre_marcados_planning_assumption(brain_store):
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=FakeLLMJSON(_PAYLOAD_EDUCACAO_ONLINE))
    assert len(plano.revenue_scenarios) == 3
    for cenario in plano.revenue_scenarios:
        assert cenario["type"] == "PLANNING_ASSUMPTION"


def test_revenue_scenario_com_nome_invalido_e_descartado(brain_store):
    payload = json.loads(json.dumps(_PAYLOAD_EDUCACAO_ONLINE))
    payload["revenue_scenarios"] = [{"nome": "GIGANTE", "descricao": "1000 vendas", "type": "PLANNING_ASSUMPTION"}]
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=FakeLLMJSON(payload))
    assert plano.revenue_scenarios == []


def test_confidence_score_invalido_vira_none_nunca_inventado(brain_store):
    payload = json.loads(json.dumps(_PAYLOAD_EDUCACAO_ONLINE))
    payload["confidence_score"] = "super garantido"
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=FakeLLMJSON(payload))
    assert plano.confidence_score is None


def test_claim_de_concorrente_removida_de_campos_novos(brain_store):
    payload = json.loads(json.dumps(_PAYLOAD_EDUCACAO_ONLINE))
    payload["pricing_strategy"] = "O concorrente já ajudou mais de 5.000 pessoas com esse anúncio"
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=FakeLLMJSON(payload))
    assert "5.000" not in plano.pricing_strategy
    assert "REMOVIDA" in plano.pricing_strategy


# ---------------------------------------------------------------------------
# Handoff estruturado (Fase 7) -- contrato de dados, nenhuma acao executada
# ---------------------------------------------------------------------------

def test_handoff_none_quando_plano_nao_aprovado(brain_store):
    brain = _produto_aprovado(brain_store)
    brain.business_plan = construir_plano_negocio(brain, llm=FakeLLMJSON(_PAYLOAD_EDUCACAO_ONLINE))
    assert brain.business_plan.approval_status == "READY_FOR_APPROVAL"
    assert gerar_handoff(brain) is None


def test_handoff_sem_business_plan_nenhum_e_none():
    from memory.project_brain import Identidade, ProjectBrain
    brain = ProjectBrain(identidade=Identidade(project_id="p1", name="x"))
    assert gerar_handoff(brain) is None


def test_handoff_completo_quando_plano_aprovado(brain_store):
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=FakeLLMJSON(_PAYLOAD_EDUCACAO_ONLINE))
    plano.approval_status = "APPROVED"
    brain.business_plan = plano

    handoff = gerar_handoff(brain)
    assert handoff is not None
    assert handoff["project_id"] == brain.project_id
    assert handoff["business_plan_id"] == f"bizplan:{brain.project_id}:v{plano.version}"
    assert handoff["status"] == "APPROVED"
    assert handoff["positioning"] == plano.positioning
    assert handoff["target_audience"] == plano.target_audience
    assert handoff["core_offer"] == plano.main_offer
    assert handoff["acquisition_channels"] == plano.acquisition_channels
    assert handoff["required_assets"] == plano.required_assets
    assert handoff["kpis"] == plano.kpis
    assert handoff["risks"] == plano.risks
    assert handoff["assumptions"] == plano.assumptions


def test_handoff_nunca_executa_nenhuma_acao_e_e_dado_puro(brain_store):
    """O handoff e um dict simples -- nao chama nenhuma funcao externa, nao
    faz I/O, nao publica nada. Prova estrutural: e reconstruivel varias
    vezes sem efeito colateral."""
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=FakeLLMJSON(_PAYLOAD_EDUCACAO_ONLINE))
    plano.approval_status = "APPROVED"
    brain.business_plan = plano

    h1 = gerar_handoff(brain)
    h2 = gerar_handoff(brain)
    assert h1 == h2  # idempotente, sem efeito colateral


# ---------------------------------------------------------------------------
# Persistencia / restart (novos campos sobrevivem ao reload completo)
# ---------------------------------------------------------------------------

def test_campos_ampliados_sobrevivem_a_save_e_load(brain_store):
    brain = _produto_aprovado(brain_store)
    brain.business_plan = construir_plano_negocio(brain, llm=FakeLLMJSON(_PAYLOAD_EDUCACAO_ONLINE))
    brain_store.save(brain)

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.business_plan.primary_channel == "LinkedIn"
    assert recarregado.business_plan.competitors == brain.business_plan.competitors
    assert recarregado.business_plan.confidence_score == "medio"
    assert len(recarregado.business_plan.revenue_scenarios) == 3


def test_plano_sobrevive_a_restart_real(tmp_path):
    db_path = tmp_path / "test_fase7_restart.db"
    backend = SQLiteMemory(db_path)
    store = ProjectBrainStore(ProjectMemory(backend))
    brain = _produto_aprovado(store)
    brain.business_plan = construir_plano_negocio(brain, llm=FakeLLMJSON(_PAYLOAD_EDUCACAO_ONLINE))
    store.save(brain)
    backend.close()

    novo_backend = SQLiteMemory(db_path)
    novo_store = ProjectBrainStore(ProjectMemory(novo_backend))
    try:
        recarregado = novo_store.load(brain.project_id)
        assert recarregado.business_plan is not None
        assert recarregado.business_plan.approval_status == "READY_FOR_APPROVAL"
        assert recarregado.business_plan.project_id == brain.project_id
        assert recarregado.blueprint.decision_status == "APPROVED"  # relacao com outro artefato intacta
    finally:
        novo_backend.close()


# ---------------------------------------------------------------------------
# Teste funcional pedido explicitamente: oportunidade fictícia de educação
# online (automação com IA para profissionais)
# ---------------------------------------------------------------------------

def test_teste_funcional_oportunidade_educacao_online_automacao_ia(brain_store):
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=FakeLLMJSON(_PAYLOAD_EDUCACAO_ONLINE))

    # existe estrategia
    assert plano.business_model
    # existe posicionamento
    assert plano.positioning
    # existe modelo de monetizacao
    assert plano.monetization_format
    # existem canais recomendados
    assert plano.acquisition_channels or plano.primary_channel
    # existem riscos
    assert plano.risks
    # existem premissas
    assert plano.assumptions
    # existem KPIs
    assert plano.kpis
    # existem proximos passos
    assert plano.next_steps

    # NAO existe ebook/post/landing page/campanha produzidos -- estrutural:
    # nenhum campo do BusinessPlan guarda um ativo PRONTO, so
    # especificacoes/textos estrategicos (sales_page_structure descreve a
    # ESTRUTURA, nunca o HTML/conteudo publicavel da pagina).
    from dataclasses import fields
    nomes = {f.name for f in fields(BusinessPlan)}
    proibidos = {
        "ebook_content", "ebook_pdf", "post_content", "carousel_images",
        "landing_page_html", "landing_page_url", "published_campaign_id",
        "campaign_id",
    }
    assert not (nomes & proibidos)
