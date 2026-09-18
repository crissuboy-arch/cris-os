"""
Testes da Fase 3: Product Architect, Product Blueprint, gate de aprovacao,
Project Brain integration, Product Factory foundation, Tool Registry.

Nada aqui bate no Supabase nem gasta OpenRouter de verdade -- LLM e sempre
um Fake controlado neste arquivo.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

import pytest

from agents.orchestrator import AgentOrchestrator
from core.product_architect import (
    PRODUCT_TYPES,
    _fallback_deterministico,
    promover_proxima_alternativa,
    propor_produto,
)
from core.product_factory import ProductFactoryError, criar_plano_inicial, gerar_copy_simples
from core.tool_registry import COPY_GENERATOR, MINI_APP_BUILDER, criar_registry_padrao
from memory.layers import ProjectMemory
from memory.project_brain import ProductBlueprint, ProjectBrainStore
from storage import SQLiteMemory


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_product_architect.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def _oportunidade_investigada(store, score=90, path="AFFILIATE", nome="Oferta Teste"):
    """Monta um ProjectBrain como se o Opportunity Analyst ja tivesse rodado."""
    brain = store.create(name=nome, tipo="opportunity")
    brain.oportunidade.score = score
    brain.oportunidade.signals = {
        "tiktok": {"encontrado": True, "resumo": "3 resultados", "termo_busca": "x", "metricas": {}},
    }
    brain.oportunidade.evidence = ["3 resultados para 'x' no TikTok"]
    brain.decisao.recommended_path = path
    brain.decisao.reasoning_summary = "2 fontes externas confirmam sinal"
    brain.decisao.evidence_level = "medio"
    store.save(brain)
    return brain


class FakeLLMJSON:
    """LLM fake que devolve um JSON valido (formato esperado do Product Architect)."""

    def __init__(self, payload: dict):
        self.payload = payload
        self._provider_name = "fake:inteligente"

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False))

    def is_alive(self):
        return True


class FakeLLMTextoQuebrado:
    """LLM fake que devolve texto que NAO e JSON (simula resposta ruim)."""

    _provider_name = "fake:inteligente"

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        return LLMResponse(content="Desculpe, nao consigo ajudar com isso.")

    def is_alive(self):
        return True


class FakeLLMBoom:
    """LLM fake que sempre falha (simula OpenRouter indisponivel)."""

    _provider_name = "fake:inteligente"

    def chat(self, messages, tools=None):
        raise RuntimeError("OpenRouter indisponivel (simulado)")

    def is_alive(self):
        return False


def _candidato(tipo, confianca="MEDIO", missing=None):
    return {
        "product_type": tipo,
        "audience_hypothesis": f"Publico hipotetico de {tipo}",
        "problem": "Problema real identificado na oportunidade",
        "why_it_fits": f"{tipo} resolve o problema com baixo esforco de producao",
        "production_difficulty": "baixa",
        "estimated_speed_to_mvp": "1-2 dias",
        "monetization": ["assinatura"],
        "supporting_evidence": ["3 resultados para 'x' no TikTok"],
        "missing_evidence": missing or [],
        "confidence": confianca,
    }


# Payload "confiante": recomendacao pronta pra aprovacao (evidencia forte).
_PAYLOAD_VALIDO = {
    "candidates": [
        _candidato("mini_app", "ALTO", missing=["Dado de conversao real"]),
        _candidato("template", "MEDIO"),
        _candidato("ferramenta_web", "MEDIO"),
    ],
    "recommendation": {
        "product_type": "mini_app",
        "reasoning_summary": "Mini-app resolve o problema com baixo esforco de producao",
        "ready_for_approval": True,
    },
    "assumptions": ["Publico ja usa ferramentas parecidas"],
    "risks": ["Concorrencia direta"],
}

# Payload "exploratorio": so hipoteses, sem confianca pra recomendar.
_PAYLOAD_EXPLORATORIO = {
    "candidates": [
        _candidato("curso", "BAIXO", missing=["Validacao de demanda real"]),
        _candidato("ebook", "BAIXO", missing=["Dado de conversao"]),
        _candidato("kit_digital", "BAIXO", missing=["Custo de fornecedor"]),
    ],
    "recommendation": {
        "product_type": None,
        "reasoning_summary": "Evidencia ainda fraca para recomendar um unico formato",
        "ready_for_approval": False,
    },
    "assumptions": [],
    "risks": [],
}


# ---------------------------------------------------------------------------
# Product Architect
# ---------------------------------------------------------------------------

def test_propor_produto_com_llm_valido(brain_store):
    brain = _oportunidade_investigada(brain_store)
    bp = propor_produto(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert bp.recommended_product_type == "mini_app"
    assert bp.recommended_product_type in PRODUCT_TYPES
    assert set(bp.alternative_product_types) <= PRODUCT_TYPES
    assert bp.decision_status == "PENDING_APPROVAL"
    assert bp.generated_by == "fake:inteligente"


def test_propor_produto_rejeita_recomendacao_fora_do_vocabulario(brain_store):
    """Um `recommendation.product_type` invalido nunca e aceito as cegas --
    cai para modo hipoteses (candidatos validos continuam aparecendo)."""
    brain = _oportunidade_investigada(brain_store)
    payload = json.loads(json.dumps(_PAYLOAD_VALIDO))  # deep copy
    payload["recommendation"]["product_type"] = "ebook_magico_inventado"
    bp = propor_produto(brain, llm=FakeLLMJSON(payload))
    assert bp.recommended_product_type is None
    assert bp.decision_status == "NEEDS_RESEARCH"
    assert len(bp.candidates) == 3


def test_propor_produto_candidato_invalido_e_descartado_mas_outros_ficam(brain_store):
    brain = _oportunidade_investigada(brain_store)
    payload = json.loads(json.dumps(_PAYLOAD_EXPLORATORIO))
    payload["candidates"][0]["product_type"] = "formato_que_nao_existe"
    bp = propor_produto(brain, llm=FakeLLMJSON(payload))
    assert len(bp.candidates) == 2  # 1 descartado, 2 validos
    assert all(c["product_type"] in PRODUCT_TYPES for c in bp.candidates)


def test_propor_produto_sem_llm_usa_fallback_deterministico(brain_store):
    brain = _oportunidade_investigada(brain_store, path="AFFILIATE")
    bp = propor_produto(brain, llm=None)
    assert bp.generated_by == "fallback_deterministico"
    assert bp.recommended_product_type == "afiliado"
    assert bp.decision_status == "PENDING_APPROVAL"


def test_propor_produto_llm_falha_cai_no_fallback_sem_crashar(brain_store):
    brain = _oportunidade_investigada(brain_store, path="COMMERCE_RESALE")
    bp = propor_produto(brain, llm=FakeLLMBoom())
    assert bp.generated_by == "fallback_deterministico"
    assert bp.recommended_product_type == "comercio_revenda"


def test_propor_produto_resposta_nao_json_cai_no_fallback(brain_store):
    brain = _oportunidade_investigada(brain_store, path="AFFILIATE")
    bp = propor_produto(brain, llm=FakeLLMTextoQuebrado())
    assert bp.generated_by == "fallback_deterministico"


def test_fallback_sem_caminho_decidido_vira_needs_research(brain_store):
    brain = _oportunidade_investigada(brain_store, path="INVESTIGATE_MORE")
    bp = _fallback_deterministico(brain)
    assert bp.recommended_product_type is None
    assert bp.decision_status == "NEEDS_RESEARCH"


def test_propor_produto_nunca_inventa_evidencia_ausente_vira_missing_evidence(brain_store):
    """Quando o LLM diz que faltam dados, isso vai para missing_evidence -- nunca vira metrica inventada."""
    brain = _oportunidade_investigada(brain_store)
    bp = propor_produto(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert "Dado de conversao real" in bp.missing_evidence


def test_promover_proxima_alternativa_troca_recomendado(brain_store):
    bp = ProductBlueprint(
        project_id="p1", recommended_product_type="mini_app",
        alternative_product_types=["template", "ferramenta_web"],
        decision_status="PENDING_APPROVAL",
    )
    nova = promover_proxima_alternativa(bp, "não gostei de mini-app")
    assert nova.recommended_product_type == "template"
    assert "mini_app" in nova.alternative_product_types
    assert nova.decision_status == "PENDING_APPROVAL"


def test_promover_proxima_alternativa_sem_mais_opcoes_vira_needs_research(brain_store):
    bp = ProductBlueprint(
        project_id="p1", recommended_product_type="mini_app",
        alternative_product_types=[], decision_status="PENDING_APPROVAL",
    )
    nova = promover_proxima_alternativa(bp)
    assert nova.decision_status == "NEEDS_RESEARCH"
    assert nova.missing_evidence


# ---------------------------------------------------------------------------
# Product Blueprint <-> Project Brain (sem memoria paralela)
# ---------------------------------------------------------------------------

def test_blueprint_persiste_e_recarrega_dentro_do_project_brain(brain_store):
    brain = _oportunidade_investigada(brain_store)
    brain.blueprint = propor_produto(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    brain_store.save(brain)

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.blueprint is not None
    assert recarregado.blueprint.recommended_product_type == "mini_app"
    assert recarregado.blueprint.alternative_product_types == ["template", "ferramenta_web"]
    # a oportunidade original continua intacta (nao substituida pelo blueprint)
    assert recarregado.decisao.recommended_path == "AFFILIATE"
    assert recarregado.oportunidade.score == 90


def test_project_brain_sem_blueprint_continua_carregando_normalmente(brain_store):
    """Compatibilidade: projetos da Fase 2 (sem blueprint) continuam validos."""
    brain = _oportunidade_investigada(brain_store)
    recarregado = brain_store.load(brain.project_id)
    assert recarregado.blueprint is None


def test_aprovacao_fica_registrada_no_historico(brain_store):
    brain = _oportunidade_investigada(brain_store)
    brain.blueprint = propor_produto(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    brain.registrar_aprovacao("APPROVED")
    brain_store.save(brain)

    recarregado = brain_store.load(brain.project_id)
    assert len(recarregado.historico.approvals) == 1
    assert recarregado.historico.approvals[0]["status"] == "APPROVED"


# ---------------------------------------------------------------------------
# Approval gate / Product Factory foundation (NUNCA produz sem aprovacao)
# ---------------------------------------------------------------------------

def test_factory_recusa_blueprint_pending_approval(brain_store):
    brain = _oportunidade_investigada(brain_store)
    brain.blueprint = propor_produto(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    assert brain.blueprint.decision_status == "PENDING_APPROVAL"

    registry = criar_registry_padrao()
    with pytest.raises(ProductFactoryError):
        criar_plano_inicial(brain, registry)


def test_factory_recusa_blueprint_rejeitado(brain_store):
    brain = _oportunidade_investigada(brain_store)
    brain.blueprint = propor_produto(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    brain.blueprint.decision_status = "REJECTED"

    registry = criar_registry_padrao()
    with pytest.raises(ProductFactoryError):
        criar_plano_inicial(brain, registry)


def test_factory_recusa_projeto_sem_blueprint(brain_store):
    brain = _oportunidade_investigada(brain_store)
    registry = criar_registry_padrao()
    with pytest.raises(ProductFactoryError):
        criar_plano_inicial(brain, registry)


def test_factory_aceita_blueprint_approved_e_gera_um_artefato(brain_store):
    brain = _oportunidade_investigada(brain_store)
    brain.blueprint = propor_produto(brain, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    brain.blueprint.decision_status = "APPROVED"

    registry = criar_registry_padrao()
    plano = criar_plano_inicial(brain, registry)

    assert plano.product_type == "mini_app"
    assert len(plano.artefatos_gerados) >= 1
    passos_copy = [p for p in plano.passos if p.capability == COPY_GENERATOR]
    assert passos_copy and passos_copy[0].status == "concluido"
    # capabilities sem fornecedor NUNCA ficam "concluido" as cegas -- mas
    # MINI_APP_BUILDER e PLANNABLE (Fase 4: NOT_CONNECTED bloqueia so a
    # EXECUCAO automatica, nao o planejamento/especificacao via LLM).
    passos_mini_app = [p for p in plano.passos if p.capability == MINI_APP_BUILDER]
    assert passos_mini_app and passos_mini_app[0].status == "planejado"
    assert passos_mini_app[0].resultado  # especificacao real foi escrita, nunca vazia


def test_gerar_copy_simples_sem_llm_usa_template_sem_inventar():
    bp = ProductBlueprint(project_id="p1", recommended_product_type="ebook")
    texto = gerar_copy_simples(bp, llm=None)
    assert "ebook" in texto
    assert "não definido" in texto  # honesto sobre o que falta, nao inventa


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

def test_tool_registry_copy_generator_disponivel_maioria_nao():
    registry = criar_registry_padrao()
    assert registry.disponivel(COPY_GENERATOR) is True
    assert registry.disponivel(MINI_APP_BUILDER) is False
    indisponiveis = [e for e in registry.listar() if not e.disponivel]
    assert len(indisponiveis) >= 7  # a maioria das 9 capabilities previstas


def test_tool_registry_capability_desconhecida_nao_crasha():
    registry = criar_registry_padrao()
    resultado = registry.executar("CAPABILITY_QUE_NAO_EXISTE")
    assert "nao esta registrada" in resultado


def test_tool_registry_capability_indisponivel_nao_crasha():
    registry = criar_registry_padrao()
    resultado = registry.executar(MINI_APP_BUILDER)
    assert "indisponivel" in resultado


# ---------------------------------------------------------------------------
# Multi-projeto (isolamento de contexto -- preparo multi-tenant futuro)
# ---------------------------------------------------------------------------

def test_dois_projetos_nao_vazam_blueprint_um_no_outro(brain_store):
    b1 = _oportunidade_investigada(brain_store, nome="Oferta A", path="AFFILIATE")
    b2 = _oportunidade_investigada(brain_store, nome="Oferta B", path="COMMERCE_RESALE")

    b1.blueprint = propor_produto(b1, llm=FakeLLMJSON(_PAYLOAD_VALIDO))
    brain_store.save(b1)
    b2.blueprint = _fallback_deterministico(b2)
    brain_store.save(b2)

    r1 = brain_store.load(b1.project_id)
    r2 = brain_store.load(b2.project_id)
    assert r1.blueprint.recommended_product_type == "mini_app"
    assert r2.blueprint.recommended_product_type == "comercio_revenda"
    assert r1.project_id != r2.project_id


# ---------------------------------------------------------------------------
# Roteamento deterministico (sem LLM) -- Fase 3
# ---------------------------------------------------------------------------

class FakeLLMQueBoom:
    def chat(self, messages, tools=None):
        raise AssertionError("LLM nao deveria ser chamado para comando determinístico!")

    def is_alive(self):
        return True


class FakeAgent:
    def __init__(self, name):
        self.name = name


def _orchestrator():
    agentes = [
        FakeAgent("scalaflow_intel"), FakeAgent("opportunity_analyst"),
        FakeAgent("product_architect"), FakeAgent("produtividade"),
    ]
    return AgentOrchestrator(llm=FakeLLMQueBoom(), agents=agentes)


@pytest.mark.parametrize("mensagem", [
    "Cris, pegue uma das minhas melhores oportunidades e me diga que produto deveríamos criar.",
    "Cris, transforme essa oportunidade em uma proposta de produto.",
    "Cris, por que esse formato é melhor para essa oportunidade?",
    "Cris, quais alternativas de produto temos?",
    "Cris, quais projetos estão aguardando minha aprovação?",
])
def test_product_architect_intercepta_antes_de_opportunity_e_scalaflow(mensagem):
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", mensagem)
    assert agente is not None
    assert agente.name == "product_architect"


def test_aprovacao_so_funciona_como_continuacao_do_product_architect():
    orc = _orchestrator()
    orc.last_agents["user1"] = "product_architect"
    agente = orc._escolher_agente("user1", "Aprovado.")
    assert agente is not None
    assert agente.name == "product_architect"


def test_aprovacao_nao_dispara_sem_contexto_previo():
    """'Aprovado.' sozinho, sem o ultimo agente ter sido product_architect,
    NUNCA deve ser interpretado como aprovacao de produto."""
    orc = _orchestrator()
    agente = orc._escolher_agente("user1", "Aprovado.")
    assert agente is None or agente.name != "product_architect"


def test_rejeicao_promove_alternativa_via_continuacao():
    orc = _orchestrator()
    orc.last_agents["user1"] = "product_architect"
    agente = orc._escolher_agente("user1", "Não gostei. Quero outra alternativa.")
    assert agente is not None
    assert agente.name == "product_architect"


def test_regressao_marco1_fase2_preservada_apos_fase3():
    orc = _orchestrator()
    for mensagem, esperado in [
        ("Mostre 5 ofertas escaladas", "scalaflow_intel"),
        ("Mostre minhas ofertas salvas", "scalaflow_intel"),
        ("Investigue minha melhor oferta", "opportunity_analyst"),
    ]:
        agente = orc._escolher_agente("user1", mensagem)
        assert agente is not None and agente.name == esperado

    # "proposta comercial" (vendas) nao deve ser sequestrada pelo product_architect
    from agents.orchestrator import AgentOrchestrator as AO
    assert AO._rotear_por_keyword("preciso de uma proposta comercial") == "vendas"


# ---------------------------------------------------------------------------
# Correcao pos-teste real: CANDIDATOS/HIPOTESES != DECISAO FINAL
# ---------------------------------------------------------------------------

def test_evidencia_parcial_gera_hipoteses_em_vez_de_bloquear(brain_store):
    """Evidencia insuficiente pra RECOMENDAR nao pode significar 'nada pra
    mostrar' -- com evidencia parcial (headline/copy/score), o Product
    Architect deve devolver candidatos, mesmo sem uma recomendacao unica."""
    brain = _oportunidade_investigada(brain_store)
    bp = propor_produto(brain, llm=FakeLLMJSON(_PAYLOAD_EXPLORATORIO))
    assert bp.recommended_product_type is None
    assert bp.decision_status == "NEEDS_RESEARCH"
    assert len(bp.candidates) == 3  # NAO esta vazio so por nao haver recomendacao
    assert all(c["confidence"] == "BAIXO" for c in bp.candidates)


def test_sem_evidencia_nenhuma_nao_chama_llm_e_fica_vazio(brain_store):
    """So aqui e que 'insuficiente' realmente significa 'nada pra mostrar':
    sem headline/copy/nicho/score, nem tenta chamar o LLM (custo zero)."""

    class LLMQueBoom:
        def chat(self, messages, tools=None):
            raise AssertionError("LLM nao deveria ser chamado sem evidencia minima!")

        def is_alive(self):
            return True

    brain = brain_store.create(name="Oportunidade vazia", tipo="opportunity")
    # sem score, sem headline, sem copy, sem nicho
    bp = propor_produto(brain, llm=LLMQueBoom())
    assert bp.candidates == []
    assert bp.decision_status == "NEEDS_RESEARCH"


def test_formatar_proposta_modo_hipoteses_nao_e_terse(brain_store):
    """A resposta formatada em modo exploracao mostra os candidatos de
    verdade -- nao so a frase generica de 'evidencia insuficiente'."""
    import tools.product_architect_tools as pat

    brain = _oportunidade_investigada(brain_store)
    brain.blueprint = propor_produto(brain, llm=FakeLLMJSON(_PAYLOAD_EXPLORATORIO))
    texto = pat._formatar_proposta(brain)
    assert "HIPÓTESES" in texto.upper()
    assert "curso" in texto.lower()
    assert "ebook" in texto.lower()
    assert "kit_digital" in texto.lower()
    assert "Nenhuma foi aprovada" in texto
    assert "EVIDÊNCIA INSUFICIENTE" not in texto.upper() or "nem para formular" not in texto


def test_pedido_de_candidatos_reusa_blueprint_sem_chamar_llm_de_novo(brain_store, monkeypatch):
    """'Quais formatos sao candidatos?' depois de ja ter explorado NAO deve
    custar uma segunda chamada ao LLM -- reusa o que ja foi calculado."""
    import tools.product_architect_tools as pat

    brain = _oportunidade_investigada(brain_store)
    brain.blueprint = propor_produto(brain, llm=FakeLLMJSON(_PAYLOAD_EXPLORATORIO))
    brain_store.save(brain)

    monkeypatch.setattr(pat, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pat, "get_foco_atual", lambda session: brain.project_id)

    class LLMQueBoom:
        def chat(self, messages, tools=None):
            raise AssertionError("Nao deveria chamar o LLM de novo -- candidatos ja existem!")

        def is_alive(self):
            return True

    monkeypatch.setattr(pat, "_get_llm_inteligente", lambda: LLMQueBoom())
    resposta = pat.gerenciar_produto("quais formatos de produto sao candidatos para essa oportunidade?", "telegram:teste")
    assert "curso" in resposta.lower()
    assert brain.project_id in resposta


def test_aprovar_sem_recomendacao_unica_exige_nomear_candidato(brain_store, monkeypatch):
    import tools.product_architect_tools as pat

    monkeypatch.setattr(pat, "get_project_brain_store", lambda: brain_store)

    brain = _oportunidade_investigada(brain_store)
    brain.blueprint = propor_produto(brain, llm=FakeLLMJSON(_PAYLOAD_EXPLORATORIO))
    brain_store.save(brain)

    resposta = pat._aprovar(brain, "aprovado")
    assert "só hipóteses" in resposta.lower() or "so hipoteses" in resposta.lower()
    assert brain.blueprint.decision_status != "APPROVED"


def test_aprovar_nomeando_candidato_funciona_mesmo_sem_recomendacao_unica(brain_store, monkeypatch):
    import tools.product_architect_tools as pat
    import tools.product_factory_tools as pft

    monkeypatch.setattr(pat, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pft, "_get_llm_economico", lambda: None)

    brain = _oportunidade_investigada(brain_store)
    brain.blueprint = propor_produto(brain, llm=FakeLLMJSON(_PAYLOAD_EXPLORATORIO))
    brain_store.save(brain)

    resposta = pat._aprovar(brain, "aprovo o formato curso")
    assert brain.blueprint.recommended_product_type == "curso"
    assert brain.blueprint.decision_status == "IN_PRODUCTION"


def test_pergunta_exploratoria_com_a_palavra_aprovar_nao_e_interpretada_como_aprovacao():
    """A frase EXATA do teste real: menciona 'aprovar' dentro de uma
    pergunta exploratoria -- nunca pode ser lida como comando de aprovacao."""
    import tools.product_architect_tools as pat

    frase = (
        "Cris, com as evidências que já temos, quais formatos de produto são "
        "candidatos para essa oportunidade, sem aprovar nenhum ainda?"
    )
    texto = frase.lower()
    assert not pat._contains_any(texto, pat._PALAVRAS_APROVACAO, pat._FRASES_APROVACAO)
    assert pat._contains_any(texto, pat._PALAVRAS_ALTERNATIVAS, pat._FRASES_ALTERNATIVAS)
