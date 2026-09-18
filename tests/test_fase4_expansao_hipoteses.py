"""
Reproducao EXATA do bug real reportado no teste da Fase 4 (Telegram):

  1. "Cris, mostre as hipóteses de produto deste projeto com a justificativa
     de cada uma, sem aprovar nenhuma." -> retornou hipoteses (ebook, curso,
     kit_digital, produto_fisico, comunidade).
  2. "Cris, considerando esta mesma oportunidade, proponha também
     alternativas de produto mais interativas e diferenciadas, como
     mini-app, ferramenta ou sistema, se fizerem sentido. Não aprove nada.
     Compare com as hipóteses atuais usando as evidências que já temos."
     -> RESULTADO INCORRETO: repetiu a lista anterior comecando de novo por
     EBOOK, sem gerar nada novo (o cache de "so mostrar hipoteses" bloqueou
     um pedido diferente de "expandir hipoteses").

Correcao: `_eh_pedido_expansao` detecta esse segundo tipo de pedido e chama
`core/product_architect.py:expandir_candidatos`, que SEMPRE reconsulta o LLM
(nao usa cache), MERGEA (nunca apaga) as hipoteses anteriores com as novas, e
nunca aprova nada automaticamente.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

import pytest

import tools.product_architect_tools as pat
from memory.layers import ProjectMemory
from memory.project_brain import ProjectBrainStore
from storage import SQLiteMemory


@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_fase4_expansao.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def _oportunidade_investigada(store):
    brain = store.create(name="Concorrente Livro X", tipo="opportunity")
    brain.origem.source_headline = "Aprenda o metodo X em 30 dias"
    brain.origem.source_copy = "O livro definitivo sobre X, testado por milhares de alunos."
    brain.oportunidade.score = 92
    brain.oportunidade.evidence = ["3 resultados para 'x' no TikTok", "2 resultados para 'x' no YouTube"]
    brain.decisao.recommended_path = "AFFILIATE"
    brain.decisao.reasoning_summary = "2 fontes externas confirmam sinal"
    brain.decisao.evidence_level = "medio"
    store.save(brain)
    return brain


def _candidato(tipo, confianca="MEDIO"):
    return {
        "product_type": tipo,
        "audience_hypothesis": f"Publico hipotetico de {tipo}",
        "problem": "Quer aprender X rapido",
        "why_it_fits": f"{tipo} resolve isso com baixo esforco de producao",
        "production_difficulty": "baixa",
        "estimated_speed_to_mvp": "1-2 dias",
        "monetization": ["pagamento unico"],
        "supporting_evidence": ["Copy do concorrente menciona metodo em 30 dias"],
        "missing_evidence": ["Nenhum teste real de conversao"],
        "confidence": confianca,
    }


_PAYLOAD_INICIAL = {
    "candidates": [
        _candidato("ebook", "MEDIO"),
        _candidato("curso", "MEDIO"),
        _candidato("kit_digital", "BAIXO"),
        _candidato("produto_fisico", "BAIXO"),
        _candidato("comunidade", "BAIXO"),
    ],
    "recommendation": {"product_type": None, "reasoning_summary": "Evidencia ainda nao justifica recomendacao unica.", "ready_for_approval": False},
    "assumptions": [], "risks": [],
}

_PAYLOAD_EXPANSAO = {
    "candidates": [
        {
            "product_type": "mini_app",
            "audience_hypothesis": "Pessoas que preferem praticar a ler",
            "problem": "Quer aprender X rapido de forma pratica",
            "why_it_fits": "Formato interativo pode aumentar engajamento vs. formato estatico",
            "functional_proposal": "Mini-app com exercicios guiados passo a passo",
            "production_difficulty": "media",
            "estimated_speed_to_mvp": "3-5 dias (estimativa)",
            "monetization": ["assinatura"],
            "supporting_evidence": ["Nicho tem sinal em TikTok/YouTube (evidencia ja coletada)"],
            "missing_evidence": ["Nenhuma validacao externa de que o publico prefere mini-app a ebook"],
            "risks": ["Maior complexidade de producao que um ebook"],
            "is_inference": True,
            "confidence": "BAIXO",
        },
        {
            "product_type": "ferramenta_web",
            "audience_hypothesis": "Pessoas que querem uma calculadora/guia interativo de X",
            "problem": "Quer aplicar o metodo X no proprio caso, nao so ler sobre ele",
            "why_it_fits": "Ferramenta pratica pode ser um diferencial frente ao concorrente (que so vende livro)",
            "functional_proposal": "Ferramenta web que gera um plano personalizado de X",
            "production_difficulty": "media",
            "estimated_speed_to_mvp": "3-5 dias (estimativa)",
            "monetization": ["pagamento unico", "assinatura"],
            "supporting_evidence": ["Copy do concorrente foca em metodo estruturado, compativel com uma ferramenta guiada"],
            "missing_evidence": ["Nenhum teste real de demanda por uma ferramenta (apenas inferencia)"],
            "risks": ["Exige mais desenvolvimento tecnico que conteudo"],
            "is_inference": True,
            "confidence": "BAIXO",
        },
    ],
    "comparison": (
        "Os formatos interativos (mini-app, ferramenta) tem potencial de "
        "diferenciacao frente ao concorrente (que vende so um livro), mas "
        "isso e INFERENCIA -- nao ha validacao externa de demanda por esse "
        "formato especifico. As hipoteses de conteudo (ebook/curso/kit) tem "
        "evidencia mais direta (o concorrente ja vende conteudo sobre o "
        "mesmo tema). Nenhum formato foi eliminado."
    ),
    "recommendation": {"product_type": None, "reasoning_summary": "Pedido explicito de comparar sem aprovar.", "ready_for_approval": False},
    "assumptions": ["Publico do nicho tem acesso a internet/smartphone"],
    "risks": [],
}


class FakeLLMSequencial:
    """
    Devolve o payload INICIAL na primeira chamada, e o payload de EXPANSAO
    quando reconhece o marcador que so aparece no prompt de expansao
    (`_prompt_expansao` inclui "Hipoteses ja existentes" no user message).
    Conta quantas vezes cada tipo de prompt foi chamado -- prova que a
    expansao SEMPRE dispara uma nova chamada real ao LLM (nao usa cache).
    """

    _provider_name = "fake:inteligente"

    def __init__(self):
        self.chamadas_iniciais = 0
        self.chamadas_expansao = 0

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        conteudo_usuario = messages[1]["content"] if len(messages) > 1 else ""
        if "Hipoteses ja existentes" in conteudo_usuario:
            self.chamadas_expansao += 1
            return LLMResponse(content=json.dumps(_PAYLOAD_EXPANSAO, ensure_ascii=False))
        self.chamadas_iniciais += 1
        return LLMResponse(content=json.dumps(_PAYLOAD_INICIAL, ensure_ascii=False))

    def is_alive(self):
        return True


def test_reproducao_exata_do_bug_expansao_nao_repete_lista_anterior(brain_store, monkeypatch):
    brain = _oportunidade_investigada(brain_store)
    session = "telegram:6460872429"

    monkeypatch.setattr(pat, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pat, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(pat, "set_foco_atual", lambda s, pid: None)

    fake = FakeLLMSequencial()
    monkeypatch.setattr(pat, "_get_llm_inteligente", lambda: fake)

    # --- Mensagem 1 (real): mostrar hipoteses, sem aprovar nenhuma ---
    resposta1 = pat.gerenciar_produto(
        "Cris, mostre as hipóteses de produto deste projeto com a "
        "justificativa de cada uma, sem aprovar nenhuma.",
        session,
    )
    assert "EBOOK" in resposta1
    assert "CURSO" in resposta1
    assert fake.chamadas_iniciais == 1
    assert fake.chamadas_expansao == 0

    tipos_apos_msg1 = {c["product_type"] for c in brain_store.load(brain.project_id).blueprint.candidates}
    assert tipos_apos_msg1 == {"ebook", "curso", "kit_digital", "produto_fisico", "comunidade"}

    # --- Mensagem 2 (real, EXATA): pedido de EXPANDIR + comparar ---
    resposta2 = pat.gerenciar_produto(
        "Cris, considerando esta mesma oportunidade, proponha também "
        "alternativas de produto mais interativas e diferenciadas, como "
        "mini-app, ferramenta ou sistema, se fizerem sentido. Não aprove "
        "nada. Compare com as hipóteses atuais usando as evidências que já temos.",
        session,
    )

    # NUNCA pode ser a mesma resposta de novo (esse era o bug real).
    assert resposta2 != resposta1

    # A expansao PRECISA ter chamado o LLM de novo -- nao pode ser bloqueada
    # pelo cache da solicitacao anterior ("mostrar hipoteses").
    assert fake.chamadas_expansao == 1

    recarregado = brain_store.load(brain.project_id)
    bp = recarregado.blueprint
    tipos_finais = {c["product_type"] for c in bp.candidates}

    # Hipoteses ANTERIORES nunca apagadas.
    assert {"ebook", "curso", "kit_digital", "produto_fisico", "comunidade"} <= tipos_finais
    # Hipoteses NOVAS (interativas) adicionadas de verdade.
    assert {"mini_app", "ferramenta_web"} <= tipos_finais
    assert len(bp.candidates) == 7

    # Nunca aprova nada automaticamente (pedido explicito "Não aprove nada").
    assert bp.recommended_product_type is None
    assert bp.decision_status != "APPROVED"
    assert bp.decision_status != "PENDING_APPROVAL"

    # Candidatos novos marcados como INFERENCIA (sem validacao externa).
    mini_app = next(c for c in bp.candidates if c["product_type"] == "mini_app")
    assert mini_app["is_inference"] is True
    assert "INFERÊNCIA" in mini_app["inference_note"]
    assert "INFERÊNCIA" in resposta2

    # Comparacao entre novos e existentes foi de fato gerada (nao inventada
    # do nada -- vem da resposta do LLM).
    assert bp.reasoning_summary and "concorrente" in bp.reasoning_summary.lower()
    assert "Observação:" in resposta2


def test_expansao_nunca_favorece_formato_do_concorrente_automaticamente(brain_store, monkeypatch):
    """O concorrente vende um LIVRO -- isso e evidencia de mercado, nao
    obrigacao de propor ebook. A expansao nao pode promover ebook a
    recomendacao so por causa disso (o payload de teste explicitamente NAO
    marca ready_for_approval para ebook)."""
    brain = _oportunidade_investigada(brain_store)
    session = "telegram:6460872429"

    monkeypatch.setattr(pat, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pat, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(pat, "set_foco_atual", lambda s, pid: None)
    fake = FakeLLMSequencial()
    monkeypatch.setattr(pat, "_get_llm_inteligente", lambda: fake)

    pat.gerenciar_produto("mostre as hipóteses de produto, sem aprovar nenhuma", session)
    pat.gerenciar_produto(
        "proponha alternativas mais interativas como mini-app ou ferramenta, "
        "compare com as hipóteses atuais, não aprove nada",
        session,
    )

    bp = brain_store.load(brain.project_id).blueprint
    assert bp.recommended_product_type != "ebook"
    assert bp.recommended_product_type is None


def test_pedido_de_ver_hipoteses_continua_usando_cache_normalmente(brain_store, monkeypatch):
    """Regressao: um pedido de so VER as hipoteses (sem pedir expansao)
    continua reaproveitando o cache -- a correcao nao pode fazer TODO pedido
    de 'alternativas' chamar o LLM de novo."""
    brain = _oportunidade_investigada(brain_store)
    session = "telegram:6460872429"

    monkeypatch.setattr(pat, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(pat, "get_foco_atual", lambda s: brain.project_id)
    monkeypatch.setattr(pat, "set_foco_atual", lambda s, pid: None)
    fake = FakeLLMSequencial()
    monkeypatch.setattr(pat, "_get_llm_inteligente", lambda: fake)

    pat.gerenciar_produto("mostre as hipóteses de produto, sem aprovar nenhuma", session)
    assert fake.chamadas_iniciais == 1

    pat.gerenciar_produto("quais são as alternativas de produto que temos?", session)
    assert fake.chamadas_iniciais == 1
    assert fake.chamadas_expansao == 0
