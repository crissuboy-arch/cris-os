"""
Testes da Fase 4: Business Builder.

Nada aqui bate no Supabase nem gasta OpenRouter de verdade -- LLM e sempre
um Fake controlado neste arquivo, e nenhuma chamada de rede (`requests`) e
esperada em nenhum caminho testado.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

import pytest

from core.business_builder import (
    _fallback_deterministico,
    blueprint_aprovado,
    construir_plano_negocio,
)
from memory.layers import ProjectMemory
from memory.project_brain import ProductBlueprint, ProjectBrainStore
from storage import SQLiteMemory


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_business_builder.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def _produto_aprovado(store, tipo="curso", status="APPROVED"):
    brain = store.create(name="Oferta Teste", tipo="opportunity")
    brain.oportunidade.evidence = ["3 resultados para 'x' no TikTok"]
    brain.oportunidade.risks = ["Concorrencia interna alta"]
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id,
        recommended_product_type=tipo,
        target_audience="Pessoas querendo aprender X",
        problem="Nao sabem por onde comecar com X",
        product_concept=f"Um {tipo} sobre X",
        monetization_options=["assinatura", "pagamento unico"],
        evidence=list(brain.oportunidade.evidence),
        risks=list(brain.oportunidade.risks),
        decision_status=status,
    )
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


class FakeLLMBoom:
    _provider_name = "fake:economico"

    def chat(self, messages, tools=None):
        raise RuntimeError("OpenRouter indisponivel (simulado)")

    def is_alive(self):
        return False


_PAYLOAD_VALIDO = {
    "business_model": "Assinatura mensal",
    "value_proposition": "Aprenda X do zero em 30 dias",
    "target_audience": "Iniciantes em X",
    "problem": "Nao sabem por onde comecar",
    "solution": "Curso estruturado passo a passo",
    "positioning": "O curso mais direto ao ponto sobre X",
    "mechanism": "Metodo proprio de progressao",
    "main_offer": "Curso completo + comunidade",
    "monetization_format": "Assinatura mensal",
    "price": "R$ 47/mes",
    "price_is_hypothesis": True,
    "bonuses": ["Checklist de inicio rapido"],
    "order_bump": "Ebook complementar",
    "upsell": ["Mentoria em grupo"],
    "downsell": ["Versao anual com desconto"],
    "acquisition_channels": ["TikTok", "Instagram"],
    "sales_channels": ["Pagina de vendas propria"],
    "sales_page_structure": "Headline -> dor -> solucao -> prova -> oferta -> CTA",
    "headline": "Aprenda X sem enrolação",
    "promise": "Voce vai entender os fundamentos de X em 30 dias de estudo consistente",
    "key_arguments": ["Metodo testado", "Suporte em comunidade"],
    "objections": [{"objecao": "Não tenho tempo", "resposta": "Aulas de 10 minutos por dia"}],
    "cta": "Quero começar agora",
    "funnel_structure": "Anuncio -> Lead magnet -> Sequencia de email -> Oferta",
    "email_sequence": [
        {"numero": 1, "objetivo": "Boas-vindas", "assunto": "Bem-vindo(a)!", "resumo": "Apresenta o metodo"},
        {"numero": 2, "objetivo": "Autoridade", "assunto": "Como cheguei aqui", "resumo": "Historia de origem"},
        {"numero": 3, "objetivo": "Prova social", "assunto": "Resultados de quem já começou", "resumo": "Depoimentos"},
        {"numero": 4, "objetivo": "Quebra de objeção", "assunto": "Sem tempo? Leia isso", "resumo": "Trata objeções"},
        {"numero": 5, "objetivo": "Oferta", "assunto": "Últimas vagas", "resumo": "CTA final"},
    ],
    "content_strategy": "Conteudo educativo curto 3x por semana",
    "content_channels": ["TikTok", "YouTube"],
    "launch_strategy": "Lancamento por lista de espera",
    "plan_30_days": [
        {"periodo": "dias 1-7", "acoes": ["Gravar aulas piloto", "Criar lista de espera"]},
        {"periodo": "dias 8-30", "acoes": ["Publicar conteudo", "Abrir vendas"]},
    ],
    "assumptions": ["Publico tem acesso a internet estavel"],
    "missing_evidence": ["Nenhum teste de preco real feito ainda"],
    "risks": ["Concorrencia interna alta"],
    "dependencies": ["Gravação das aulas"],
    "next_steps": ["Validar preco com uma lista pequena"],
}


# ---------------------------------------------------------------------------
# Gate (Fase 4, item 12): nunca avanca sem blueprint aprovado
# ---------------------------------------------------------------------------

def test_gate_bloqueia_sem_blueprint():
    from memory.project_brain import Identidade, ProjectBrain
    brain = ProjectBrain(identidade=Identidade(project_id="p1", name="x"))
    assert blueprint_aprovado(brain) is False


def test_gate_bloqueia_blueprint_pending_approval(brain_store):
    brain = _produto_aprovado(brain_store, status="PENDING_APPROVAL")
    assert blueprint_aprovado(brain) is False


def test_gate_bloqueia_blueprint_rejeitado(brain_store):
    brain = _produto_aprovado(brain_store, status="REJECTED")
    assert blueprint_aprovado(brain) is False


def test_gate_libera_blueprint_approved(brain_store):
    brain = _produto_aprovado(brain_store, status="APPROVED")
    assert blueprint_aprovado(brain) is True


# ---------------------------------------------------------------------------
# Fallback deterministico (sem LLM -- nunca inventa)
# ---------------------------------------------------------------------------

def test_fallback_sem_llm_usa_apenas_dados_do_blueprint(brain_store):
    brain = _produto_aprovado(brain_store)
    plano = _fallback_deterministico(brain)

    assert plano.price is None
    assert plano.price_is_hypothesis is True
    assert plano.target_audience == brain.blueprint.target_audience
    assert plano.generated_by == "fallback_deterministico"
    assert plano.missing_evidence  # honesto: declara que faltou IA


def test_construir_plano_negocio_sem_llm_cai_no_fallback(brain_store):
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=None)
    assert plano.generated_by == "fallback_deterministico"


def test_construir_plano_negocio_llm_falhando_cai_no_fallback(brain_store):
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=FakeLLMBoom())
    assert plano.generated_by == "fallback_deterministico"


# ---------------------------------------------------------------------------
# Construcao via LLM (Fake) -- parsing/honestidade
# ---------------------------------------------------------------------------

def test_construir_plano_negocio_com_llm_valido(brain_store):
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))

    assert plano.business_model == "Assinatura mensal"
    assert plano.price == "R$ 47/mes"
    assert plano.price_is_hypothesis is True
    assert len(plano.email_sequence) == 5
    assert plano.approval_status == "READY_FOR_APPROVAL"
    assert plano.generated_by == "fake:economico"


def test_preco_sem_valor_e_sempre_marcado_como_hipotese(brain_store):
    """Mesmo se o LLM (por erro) mandar price_is_hypothesis=False sem
    nenhum preco concreto, o parsing nunca aceita isso como fato."""
    payload = dict(_PAYLOAD_VALIDO)
    payload["price"] = None
    payload["price_is_hypothesis"] = False
    brain = _produto_aprovado(brain_store)
    plano = construir_plano_negocio(brain, llm=FakeLLMJSON(payload))
    assert plano.price is None
    assert plano.price_is_hypothesis is True


def test_nao_existe_campo_para_metricas_proibidas():
    """Estrutural: o BusinessPlan nao tem ONDE guardar vendas/receita/CPA/
    ROAS/conversao/demanda -- essas metricas nao podem ser inventadas porque
    nao ha campo pra elas (garante a regra mesmo se o prompt falhar)."""
    from dataclasses import fields
    from memory.project_brain import BusinessPlan

    nomes = {f.name for f in fields(BusinessPlan)}
    proibidos = {"vendas", "receita", "revenue", "cpa", "roas", "conversao",
                 "conversion", "demanda", "demand", "tamanho_mercado", "market_size"}
    assert not (nomes & proibidos)


def test_business_plan_sobrevive_a_save_e_load(brain_store):
    """Regressao do padrao de persistencia da Fase 3 (UserFocusStore/
    ProjectBrainStore): o Business Plan precisa sobreviver a um reload
    completo do brain a partir do banco, nao so ficar na instancia em
    memoria."""
    brain = _produto_aprovado(brain_store)
    brain.business_plan = construir_plano_negocio(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    brain_store.save(brain)

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.business_plan is not None
    assert recarregado.business_plan.business_model == "Assinatura mensal"
    assert len(recarregado.business_plan.email_sequence) == 5
    assert recarregado.business_plan.price_is_hypothesis is True


def test_business_plan_nao_gasta_llm_alem_de_uma_chamada(brain_store):
    """Uma unica chamada de LLM gera o plano inteiro (todas as secoes) --
    nao ha chamadas separadas por secao (cost-first)."""
    brain = _produto_aprovado(brain_store)
    fake = FakeLLMJSON(_PAYLOAD_VALIDO)
    construir_plano_negocio(brain, llm=fake)
    assert fake.chamadas == 1
