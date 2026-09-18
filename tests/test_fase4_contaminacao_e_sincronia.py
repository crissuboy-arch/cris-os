"""
Reproducao dos dois bugs reais do terceiro round de teste da Fase 4 (Telegram),
projeto real `proj_cb094b4ef6a4` (oportunidade de velas artesanais):

  BUG 1 -- COPY/EVIDENCIA DO CONCORRENTE TRATADA COMO COPY DO PRODUTO NOVO:
  o manifesto/artefato da Product Factory reproduziu alegacoes do ANUNCIO
  ORIGINAL ("já ajudou mais de 13.000 pessoas", "Acesso Vitalício", "Lista
  de Fornecedor Incluso") como se fossem fatos do produto NOVO (que ainda
  nem foi produzido).

  BUG 2 -- BUSINESS PLAN NAO SINCRONIZADO NO MANIFESTO: o Business Builder
  gerou `status_business_plan: READY_FOR_APPROVAL`, mas o MASTER-PROJECT.json
  exibido logo depois mostrou `status_business_plan: None` -- o manifesto
  tinha sido gerado (e persistido como cache) ANTES do Business Plan existir,
  e nunca foi regenerado.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

import pytest

import tools.business_builder_tools as bbt
import tools.product_architect_tools as pat
import tools.product_factory_tools as pft
from core.evidence_guard import contem_claim_herdada, sanitizar_claims_herdadas
from core.product_architect import _validar_candidato
from core.tool_registry import MINI_APP_BUILDER
from memory.layers import ProjectMemory
from memory.project_brain import ProjectBrainStore
from storage import SQLiteMemory

_HEADLINE_CONCORRENTE = "VELAS ARTESANAIS COMO NEGÓCIO — já ajudou mais de 13.000 pessoas"
_COPY_CONCORRENTE = (
    "Acesso Vitalício ao curso completo. Lista de Fornecedor Incluso. "
    "Garantia de satisfação de 7 dias."
)


def _oportunidade_velas(store):
    brain = store.create(name="Curso de Velas Artesanais", tipo="opportunity")
    brain.origem.source_headline = _HEADLINE_CONCORRENTE
    brain.origem.source_copy = _COPY_CONCORRENTE
    brain.mercado.niche = "velas artesanais"
    brain.mercado.target_country = "BR"
    brain.oportunidade.score = 88
    brain.oportunidade.evidence = ["4 resultados para 'velas artesanais' no TikTok"]
    brain.decisao.recommended_path = "AFFILIATE"
    brain.decisao.reasoning_summary = "2+ fontes externas confirmam sinal"
    brain.decisao.evidence_level = "medio"
    store.save(brain)
    return brain


class FakeLLMJSON:
    _provider_name = "fake:inteligente"

    def __init__(self, payload):
        self.payload = payload

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False))

    def is_alive(self):
        return True


class FakeLLMTexto:
    """LLM fake que devolve texto puro (nao JSON) -- usado pra
    gerar_copy_simples/gerar_especificacao_tecnica."""

    _provider_name = "fake:economico"

    def __init__(self, texto):
        self.texto = texto

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        return LLMResponse(content=self.texto)

    def is_alive(self):
        return True


# Candidato CONTAMINADO (simula o LLM do Product Architect ecoando o anuncio).
_CANDIDATO_MINI_APP_CONTAMINADO = {
    "product_type": "mini_app",
    "audience_hypothesis": "Pessoas que já ajudou mais de 13.000 pessoas a fazer velas",
    "problem": "Não sabem por onde começar a fazer velas artesanais",
    "why_it_fits": "Assim como o concorrente, oferecemos Acesso Vitalício e Lista de Fornecedor Incluso",
    "functional_proposal": "App com receitas -- já ajudou mais de 13.000 pessoas a aprender",
    "production_difficulty": "media",
    "estimated_speed_to_mvp": "3-5 dias",
    "monetization": ["pagamento unico"],
    "supporting_evidence": ["Anuncio do concorrente menciona metodo estruturado"],
    "missing_evidence": ["Nenhum teste real do mini-app"],
    "confidence": "MEDIO",
}

_PAYLOAD_HIPOTESES_CONTAMINADO = {
    "candidates": [_CANDIDATO_MINI_APP_CONTAMINADO],
    "recommendation": {"product_type": None, "reasoning_summary": "x", "ready_for_approval": False},
    "assumptions": [], "risks": [],
}

_PAYLOAD_NEGOCIO_VELAS = {
    "business_model": "Pagamento único", "value_proposition": "Aprenda a fazer velas artesanais em casa",
    "target_audience": "Iniciantes em velas artesanais", "problem": "Não sabem por onde começar",
    "solution": "Mini-app guiado", "positioning": None, "mechanism": None,
    "main_offer": "Mini-app com receitas de velas", "monetization_format": "Pagamento único",
    "price": None, "price_is_hypothesis": True, "bonuses": [], "order_bump": None,
    "upsell": [], "downsell": [], "acquisition_channels": ["TikTok"], "sales_channels": ["Página própria"],
    "sales_page_structure": None, "headline": None, "promise": None, "key_arguments": [],
    "objections": [], "cta": None, "funnel_structure": None, "email_sequence": [],
    "content_strategy": None, "content_channels": [], "launch_strategy": None,
    "plan_30_days": [], "assumptions": [], "missing_evidence": [], "risks": [],
    "dependencies": [], "next_steps": [],
}


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_fase4_contaminacao.db"


@pytest.fixture()
def brain_store(db_path):
    backend = SQLiteMemory(db_path)
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


# ---------------------------------------------------------------------------
# BUG 1 -- separacao evidencia do concorrente / copy do produto novo
# ---------------------------------------------------------------------------

def test_evidence_guard_remove_claims_conhecidas():
    assert contem_claim_herdada("já ajudou mais de 13.000 pessoas")
    assert contem_claim_herdada("Acesso Vitalício ao curso")
    assert contem_claim_herdada("Lista de Fornecedor Incluso")
    assert contem_claim_herdada("Garantia de satisfação de 7 dias")
    assert not contem_claim_herdada("Público-alvo: iniciantes em velas artesanais")

    limpo = sanitizar_claims_herdadas("já ajudou mais de 13.000 pessoas a começar")
    assert "13.000" not in limpo
    assert "CLAIM REMOVIDA" in limpo


def test_validar_candidato_remove_claim_herdada_do_concorrente():
    candidato = _validar_candidato(_CANDIDATO_MINI_APP_CONTAMINADO)
    assert candidato is not None
    assert "13.000" not in candidato["audience_hypothesis"]
    assert "13.000" not in candidato["functional_proposal"]
    assert "Acesso Vitalício" not in candidato["why_it_fits"]
    assert "Fornecedor Incluso" not in candidato["why_it_fits"]
    assert "REMOVIDA" in candidato["why_it_fits"]


def test_evidencia_original_do_concorrente_e_preservada_intacta(brain_store):
    """A evidencia em si (headline/copy do anuncio original) NUNCA e
    alterada -- so o que seria COPY DO PRODUTO NOVO e sanitizado."""
    brain = _oportunidade_velas(brain_store)
    assert brain.origem.source_headline == _HEADLINE_CONCORRENTE
    assert "13.000" in brain.origem.source_headline
    assert "Acesso Vitalício" in brain.origem.source_copy


def test_product_factory_artefato_final_nunca_contem_claim_herdada(monkeypatch):
    """Defesa de ultima linha: mesmo se um LLM (por erro) devolver uma claim
    herdada diretamente no artefato final, o resultado retornado nunca a
    contem."""
    from core.product_factory import gerar_copy_simples
    from memory.project_brain import ProductBlueprint

    bp = ProductBlueprint(
        project_id="p1", recommended_product_type="mini_app",
        product_concept="App de velas artesanais",
    )
    fake = FakeLLMTexto("Nosso mini-app já ajudou mais de 13.000 pessoas a fazer velas artesanais.")
    resultado = gerar_copy_simples(bp, llm=fake)
    assert "13.000" not in resultado
    assert "CLAIM REMOVIDA" in resultado


def test_business_plan_nao_herda_claim_do_concorrente(brain_store):
    """Mesmo se o LLM do Business Builder (por erro) ecoar a alegacao do
    anuncio original, o BusinessPlan final nao a carrega."""
    from core.business_builder import construir_plano_negocio
    from memory.project_brain import ProductBlueprint

    brain = _oportunidade_velas(brain_store)
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id, recommended_product_type="mini_app",
        decision_status="APPROVED", target_audience="Iniciantes em velas artesanais",
    )
    payload = {
        "business_model": "Assinatura",
        "value_proposition": "Já ajudou mais de 13.000 pessoas a fazer velas em casa",
        "target_audience": None, "problem": None, "solution": None,
        "positioning": None, "mechanism": None,
        "main_offer": "Curso com Acesso Vitalício e Lista de Fornecedor Incluso",
        "monetization_format": "Assinatura", "price": None, "price_is_hypothesis": True,
        "bonuses": [], "order_bump": None, "upsell": [], "downsell": [],
        "acquisition_channels": [], "sales_channels": [],
        "sales_page_structure": None, "headline": None, "promise": None,
        "key_arguments": [], "objections": [], "cta": None, "funnel_structure": None,
        "email_sequence": [], "content_strategy": None, "content_channels": [],
        "launch_strategy": None, "plan_30_days": [], "assumptions": [],
        "missing_evidence": [], "risks": [], "dependencies": [], "next_steps": [],
    }
    plano = construir_plano_negocio(brain, llm=FakeLLMJSON(payload))
    assert "13.000" not in (plano.value_proposition or "")
    assert "Acesso Vitalício" not in (plano.main_offer or "")
    assert "REMOVIDA" in plano.value_proposition
    assert "REMOVIDA" in plano.main_offer


# ---------------------------------------------------------------------------
# BUG 2 -- Business Plan sincronizado no Project Brain / manifesto
# ---------------------------------------------------------------------------

def test_manifest_reflete_business_plan_gerado_depois_da_producao(db_path, brain_store, monkeypatch):
    session = "telegram:6460872429"
    brain = _oportunidade_velas(brain_store)

    for mod in (pat, pft, bbt):
        monkeypatch.setattr(mod, "get_project_brain_store", lambda: brain_store)
        monkeypatch.setattr(mod, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(pat, "set_foco_atual", lambda s, pid: None)
    monkeypatch.setattr(pat, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_HIPOTESES_CONTAMINADO))
    monkeypatch.setattr(pft, "_get_llm_economico", lambda: None)
    monkeypatch.setattr(bbt, "_get_llm_economico", lambda: FakeLLMJSON(_PAYLOAD_NEGOCIO_VELAS))

    pat.gerenciar_produto("mostre as hipóteses de produto, sem aprovar nenhuma", session)
    pat.gerenciar_produto("Aprovo o formato mini_app para este projeto.", session)

    # Logo apos aprovar (ANTES do Business Builder rodar), o manifesto ainda
    # nao tem business plan -- isso e esperado (honesto, nao inventado).
    resposta_manifest_antes = pft.gerenciar_producao("quais artefatos esse projeto precisa?", session)
    assert "status_business_plan: None" in resposta_manifest_antes

    # Business Builder roda DEPOIS.
    resposta_negocio = bbt.gerenciar_negocio("transforme este produto aprovado em um negócio", session)
    assert "READY_FOR_APPROVAL" in resposta_negocio

    # BUG REAL: pedir o manifesto de novo DEVE refletir o business plan que
    # acabou de ser persistido -- nunca servir o snapshot congelado de antes.
    resposta_manifest_depois = pft.gerenciar_producao("quais artefatos esse projeto precisa?", session)
    assert "status_business_plan: READY_FOR_APPROVAL" in resposta_manifest_depois
    assert "status_business_plan: None" not in resposta_manifest_depois


def test_manifest_nao_inventa_aprovacao_do_business_plan(db_path, brain_store, monkeypatch):
    """READY_FOR_APPROVAL nunca vira APPROVED sozinho -- nem no BusinessPlan
    nem no manifesto."""
    session = "telegram:6460872429"
    brain = _oportunidade_velas(brain_store)

    monkeypatch.setattr(pat, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pat, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(pat, "set_foco_atual", lambda s, pid: None)
    monkeypatch.setattr(pat, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_HIPOTESES_CONTAMINADO))
    monkeypatch.setattr(pft, "_get_llm_economico", lambda: None)
    monkeypatch.setattr(bbt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(bbt, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(bbt, "_get_llm_economico", lambda: FakeLLMJSON(_PAYLOAD_NEGOCIO_VELAS))

    pat.gerenciar_produto("mostre as hipóteses de produto, sem aprovar nenhuma", session)
    pat.gerenciar_produto("Aprovo o formato mini_app para este projeto.", session)
    bbt.gerenciar_negocio("transforme este produto aprovado em um negócio", session)

    persistido = brain_store.load(brain.project_id)
    assert persistido.business_plan.approval_status == "READY_FOR_APPROVAL"
    assert persistido.business_plan.approval_status != "APPROVED"


def test_business_plan_e_aprovacao_sobrevivem_a_restart(db_path, brain_store, monkeypatch):
    session = "telegram:6460872429"
    brain = _oportunidade_velas(brain_store)

    monkeypatch.setattr(pat, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pat, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(pat, "set_foco_atual", lambda s, pid: None)
    monkeypatch.setattr(pat, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_HIPOTESES_CONTAMINADO))
    monkeypatch.setattr(pft, "_get_llm_economico", lambda: None)
    monkeypatch.setattr(bbt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(bbt, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(bbt, "_get_llm_economico", lambda: FakeLLMJSON(_PAYLOAD_NEGOCIO_VELAS))

    pat.gerenciar_produto("mostre as hipóteses de produto, sem aprovar nenhuma", session)
    pat.gerenciar_produto("Aprovo o formato mini_app para este projeto.", session)
    bbt.gerenciar_negocio("transforme este produto aprovado em um negócio", session)

    novo_backend = SQLiteMemory(db_path)
    novo_store = ProjectBrainStore(ProjectMemory(novo_backend))
    try:
        recarregado = novo_store.load(brain.project_id)
        assert recarregado.blueprint.esta_aprovado() is True
        assert recarregado.business_plan is not None
        assert recarregado.business_plan.approval_status == "READY_FOR_APPROVAL"

        monkeypatch.setattr(pft, "get_project_brain_store", lambda: novo_store)
        monkeypatch.setattr(pft, "get_foco_atual", lambda s: brain.project_id)
        resposta = pft.gerenciar_producao("quais artefatos esse projeto precisa?", session)
        assert "status_business_plan: READY_FOR_APPROVAL" in resposta
    finally:
        novo_backend.close()


def test_projeto_sem_business_plan_continua_retornando_none(brain_store):
    """Regressao: um projeto que NUNCA passou pelo Business Builder deve
    continuar mostrando `status_business_plan: None` -- nunca inventar um
    plano que nao existe."""
    from core.artifact_manifest import gerar_manifest
    from memory.project_brain import Identidade, ProductBlueprint, ProjectBrain

    brain = ProjectBrain(identidade=Identidade(project_id="proj_semplano", name="x"))
    brain.blueprint = ProductBlueprint(project_id="proj_semplano", recommended_product_type="ebook", decision_status="APPROVED")
    manifest = gerar_manifest(brain)
    assert manifest["master_project"]["status_business_plan"] is None
