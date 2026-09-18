"""
Reproducao EXATA dos dois bugs reais reportados no teste da Fase 4 (Telegram),
projeto real `proj_cb094b4ef6a4` (oportunidade de velas artesanais):

  1. "Aprovo o formato mini_app para este projeto." -> APROVADO, IN_PRODUCTION.
  2. "Cris, transforme este produto aprovado em um negócio: [...]" ->
     RESULTADO INCORRETO: "Esse produto ainda não foi aprovado [...]"
     (Business Builder nao reconhecia a MESMA aprovacao que o Product
     Architect/Product Factory acabaram de persistir).
  3. O primeiro artefato do Product Factory saiu generico ("Apresentamos um
     mini app inovador...") ignorando o contexto real do projeto (nicho de
     velas artesanais).

Correcoes:
  - `ProductBlueprint.esta_aprovado()` (Fase 4) reconhece "APPROVED" E
    "IN_PRODUCTION"/"COMPLETED" -- Business Builder e Product Factory usam
    essa MESMA fonte de verdade (nao um campo/estado paralelo).
  - `promover_candidato_para_blueprint` copia os campos ricos do candidato
    vencedor (nicho/publico/problema/conceito/MVP) pros campos de topo do
    blueprint -- sem isso, `gerar_copy_simples`/`_resumir_contexto` do
    Business Builder so enxergavam campos vazios.
  - `gerar_especificacao_tecnica` + `plannable` no Tool Registry: mesmo com
    `MINI_APP_BUILDER` NOT_CONNECTED (sem executor automatico), a Product
    Factory agora PLANEJA uma especificacao tecnica real via LLM (ou
    template deterministico honesto, sem LLM).
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
from core.product_architect import propor_produto
from core.tool_registry import MINI_APP_BUILDER, criar_registry_padrao
from memory.layers import ProjectMemory
from memory.project_brain import ProjectBrainStore
from storage import SQLiteMemory


def _oportunidade_velas(store):
    """Fixture tematica identica ao cenario real reportado: oportunidade de
    velas artesanais."""
    brain = store.create(name="Curso de Velas Artesanais", tipo="opportunity")
    brain.origem.source_headline = "Aprenda a fazer velas artesanais em casa e venda no seu tempo livre"
    brain.origem.source_copy = "Metodo passo a passo pra fazer velas aromaticas artesanais, sem experiencia previa."
    brain.mercado.niche = "velas artesanais"
    brain.mercado.target_country = "BR"
    brain.oportunidade.score = 88
    brain.oportunidade.evidence = ["4 resultados para 'velas artesanais' no TikTok", "2 resultados no Instagram"]
    brain.decisao.recommended_path = "AFFILIATE"
    brain.decisao.reasoning_summary = "2+ fontes externas confirmam sinal"
    brain.decisao.evidence_level = "medio"
    store.save(brain)
    return brain


def _candidato_mini_app_velas():
    return {
        "product_type": "mini_app",
        "audience_hypothesis": "Pessoas iniciantes que querem aprender a fazer velas artesanais em casa",
        "problem": "Não sabem por onde começar nem quais insumos/proporções usar para fazer velas artesanais",
        "why_it_fits": "Um mini-app guiado (receitas + calculadora de insumos) reduz a fricção de começar",
        "functional_proposal": "App com receitas passo a passo e calculadora de proporção de cera/essência/pavio",
        "production_difficulty": "media",
        "estimated_speed_to_mvp": "3-5 dias",
        "monetization": ["pagamento unico", "assinatura"],
        "supporting_evidence": ["4 resultados para 'velas artesanais' no TikTok"],
        "missing_evidence": ["Nenhum teste real de conversao para o mini-app"],
        "confidence": "MEDIO",
    }


_PAYLOAD_HIPOTESES_VELAS = {
    "candidates": [
        _candidato_mini_app_velas(),
        {
            "product_type": "ebook", "audience_hypothesis": "Iniciantes em velas artesanais",
            "problem": "Não sabem receitas de velas artesanais", "why_it_fits": "Ebook e mais barato de produzir",
            "production_difficulty": "baixa", "estimated_speed_to_mvp": "1-2 dias",
            "monetization": ["pagamento unico"], "supporting_evidence": ["Copy do anuncio menciona metodo"],
            "missing_evidence": [], "confidence": "MEDIO",
        },
    ],
    "recommendation": {"product_type": None, "reasoning_summary": "Ainda sem sinal forte o bastante.", "ready_for_approval": False},
    "assumptions": [], "risks": [],
}


class FakeLLMJSON:
    _provider_name = "fake:inteligente"

    def __init__(self, payload):
        self.payload = payload

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False))

    def is_alive(self):
        return True


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_fase4_aprovacao_contexto.db"


@pytest.fixture()
def brain_store(db_path):
    backend = SQLiteMemory(db_path)
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def test_sequencia_real_aprovacao_compartilhada_e_contexto_especifico(db_path, brain_store, monkeypatch):
    session = "telegram:6460872429"
    brain = _oportunidade_velas(brain_store)

    # Todos os modulos precisam apontar pro MESMO store/foco (nunca um
    # segundo estado paralelo).
    for mod in (pat, pft, bbt):
        monkeypatch.setattr(mod, "get_project_brain_store", lambda: brain_store)
        monkeypatch.setattr(mod, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(pat, "set_foco_atual", lambda s, pid: None)
    monkeypatch.setattr(pat, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_HIPOTESES_VELAS))
    # Sem LLM economico (fallback deterministico) -- prova que ate SEM IA
    # nova o contexto ja deixa de ser generico (a correcao e sobre
    # PROMOCAO de campos ja coletados, nao sobre gastar mais IA).
    monkeypatch.setattr(pft, "_get_llm_economico", lambda: None)
    monkeypatch.setattr(bbt, "_get_llm_economico", lambda: None)

    # --- 1. Mensagem real: mostrar hipoteses ---
    pat.gerenciar_produto("mostre as hipóteses de produto, sem aprovar nenhuma", session)

    # --- 2. Mensagem real: "Aprovo o formato mini_app para este projeto." ---
    resposta_aprovacao = pat.gerenciar_produto("Aprovo o formato mini_app para este projeto.", session)
    assert "APROVADO" in resposta_aprovacao
    assert "IN_PRODUCTION" in resposta_aprovacao or "IN_PRODUCTION" in resposta_aprovacao.upper()

    persistido = brain_store.load(brain.project_id)
    assert persistido.blueprint.recommended_product_type == "mini_app"
    assert persistido.blueprint.decision_status == "IN_PRODUCTION"
    assert persistido.blueprint.esta_aprovado() is True

    # BUG 2 (artefato generico): os passos PLANNABLE (ex.: MINI_APP_BUILDER)
    # devem ter sido "planejados" com uma especificacao que reflete o
    # CONTEXTO REAL (velas), nunca um texto generico tipo "mini app inovador".
    passo_mini_app = next(p for p in persistido.production_plan.steps if p["capability"] == MINI_APP_BUILDER)
    assert passo_mini_app["status"] == "planejado"
    passos_planejados = [p for p in persistido.production_plan.steps if p["status"] == "planejado"]
    assert any("vela" in (p["resultado"] or "").lower() for p in passos_planejados)

    # --- 3. BUG 1 (o bug real): mensagem imediatamente depois, pedindo pra
    #     transformar em negocio -- NAO pode dizer "ainda nao foi aprovado". ---
    pedido_negocio = (
        "Cris, transforme este produto aprovado em um negócio: defina modelo "
        "de negócio, público, posicionamento, oferta, monetização, hipótese "
        "de preço, funil, 5 e-mails, canais orgânicos, plano de lançamento, "
        "plano de 30 dias, riscos e evidências ainda ausentes. Use todo o "
        "contexto deste projeto e não publique nem gaste nada."
    )
    resposta_negocio = bbt.gerenciar_negocio(pedido_negocio, session)

    assert "ainda não foi aprovado" not in resposta_negocio.lower()
    assert "PLANO DE NEGÓCIO" in resposta_negocio

    persistido2 = brain_store.load(brain.project_id)
    assert persistido2.business_plan is not None
    # Contexto ESPECIFICO (velas), nao generico -- vem do target_audience/
    # problem promovidos do candidato vencedor pro blueprint.
    assert "vela" in (persistido2.business_plan.target_audience or "").lower()


def test_aprovacao_sobrevive_a_restart_business_builder_e_product_factory(db_path, brain_store, monkeypatch):
    """Simula reinicio real: fecha a conexao, abre outra a partir do MESMO
    arquivo SQLite, e confirma que Business Builder e Product Factory
    continuam reconhecendo a aprovacao (nao dependem de cache/processo)."""
    session = "telegram:6460872429"
    brain = _oportunidade_velas(brain_store)

    monkeypatch.setattr(pat, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pat, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(pat, "set_foco_atual", lambda s, pid: None)
    monkeypatch.setattr(pat, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_HIPOTESES_VELAS))
    monkeypatch.setattr(pft, "_get_llm_economico", lambda: None)

    pat.gerenciar_produto("mostre as hipóteses de produto, sem aprovar nenhuma", session)
    pat.gerenciar_produto("Aprovo o formato mini_app para este projeto.", session)

    # --- "restart": fecha a store atual e a substitui por uma NOVA conexao
    #     sobre o MESMO arquivo (simula processo reiniciado). ---
    novo_backend = SQLiteMemory(db_path)
    novo_store = ProjectBrainStore(ProjectMemory(novo_backend))
    try:
        monkeypatch.setattr(pft, "get_project_brain_store", lambda: novo_store)
        monkeypatch.setattr(pft, "get_foco_atual", lambda s: brain.project_id)
        monkeypatch.setattr(bbt, "get_project_brain_store", lambda: novo_store)
        monkeypatch.setattr(bbt, "get_foco_atual", lambda s: brain.project_id)
        monkeypatch.setattr(bbt, "_get_llm_economico", lambda: None)

        resposta_producao = pft.gerenciar_producao("mostre o plano de produção", session)
        assert "ainda não foi aprovado" not in resposta_producao.lower()

        resposta_negocio = bbt.gerenciar_negocio(
            "transforme este produto aprovado em um negócio", session,
        )
        assert "ainda não foi aprovado" not in resposta_negocio.lower()
    finally:
        novo_backend.close()


def test_projeto_nao_aprovado_continua_bloqueado_regressao(brain_store, monkeypatch):
    """Regressao explicita: a correcao do gate (aceitar IN_PRODUCTION/
    COMPLETED) NUNCA pode fazer um projeto PENDING_APPROVAL passar."""
    session = "telegram:6460872429"
    brain = _oportunidade_velas(brain_store)

    monkeypatch.setattr(pat, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pat, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(pat, "set_foco_atual", lambda s, pid: None)
    monkeypatch.setattr(pat, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_HIPOTESES_VELAS))

    pat.gerenciar_produto("mostre as hipóteses de produto, sem aprovar nenhuma", session)
    persistido = brain_store.load(brain.project_id)
    assert persistido.blueprint.decision_status == "NEEDS_RESEARCH"
    assert persistido.blueprint.esta_aprovado() is False

    monkeypatch.setattr(bbt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(bbt, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pft, "get_foco_atual", lambda s: brain.project_id)

    assert "ainda não foi aprovado" in bbt.gerenciar_negocio("transforme em negócio", session).lower()
    assert "ainda não foi aprovado" in pft.gerenciar_producao("prepare o plano de produção", session).lower()


def test_not_connected_bloqueia_execucao_mas_nao_planejamento():
    """PLANNABLE vs NOT_CONNECTED (pedido explicito da Fase 4): uma
    capability NOT_CONNECTED (sem executor) ainda pode ser PLANEJADA."""
    registry = criar_registry_padrao()
    assert registry.disponivel(MINI_APP_BUILDER) is False  # nao executa sozinha
    assert registry.plannable(MINI_APP_BUILDER) is True  # mas pode planejar
    entry = registry.obter(MINI_APP_BUILDER)
    assert entry.status == "AVAILABLE_MANUAL"


def test_nenhuma_chamada_http_na_sequencia_completa(brain_store, monkeypatch):
    """Ausencia de acoes externas/gasto novo: a sequencia inteira (aprovar +
    montar negocio) nao pode tocar em `requests` -- so o LLM (fake/None)."""
    import requests

    def _boom(*args, **kwargs):
        raise AssertionError("Nenhuma chamada HTTP deveria acontecer aqui")
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)

    session = "telegram:6460872429"
    brain = _oportunidade_velas(brain_store)

    monkeypatch.setattr(pat, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pat, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(pat, "set_foco_atual", lambda s, pid: None)
    monkeypatch.setattr(pat, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_HIPOTESES_VELAS))
    monkeypatch.setattr(pft, "_get_llm_economico", lambda: None)
    monkeypatch.setattr(bbt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(bbt, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(bbt, "_get_llm_economico", lambda: None)

    pat.gerenciar_produto("mostre as hipóteses de produto, sem aprovar nenhuma", session)
    pat.gerenciar_produto("Aprovo o formato mini_app para este projeto.", session)
    bbt.gerenciar_negocio("transforme este produto aprovado em um negócio", session)
