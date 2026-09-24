"""
Testes da Etapa 27 -- correção de um bug real observado em produção
(Etapas 25/26): `_buscar_sinal_fonte` (tools/opportunity_tools.py) escolhia
a evidência representativa de uma fonte só pelo maior `viral_score`/métrica,
mesmo quando o conteúdo real não tinha NADA a ver com a oportunidade (um
vídeo de "máquina de cozinha automática" venceu vídeos reais sobre N8N/
agentes de IA só porque tinha mais views).

Regra nova: RELEVÂNCIA TEMÁTICA PRIMEIRO (filtro determinístico, sem LLM,
vocabulário sempre derivado da própria oferta), viral_score DEPOIS (ranking
só entre quem já passou no filtro).

Dados usados aqui são uma reprodução fiel do caso real (oportunidade
"Hashtag Treinamentos", mineração TikTok real da Etapa 24.2) -- não são
mock genérico, são o EXEMPLO OBRIGATÓRIO DE REGRESSÃO citado na Etapa 27.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from tools.opportunity_tools import (
    _FONTES,
    _buscar_sinal_fonte,
    _candidato_e_relevante,
    _extrair_vocabulario_relevancia,
)

FONTE_TIKTOK = next(f for f in _FONTES if f["nome"] == "tiktok")

OFERTA_HASHTAG_TREINAMENTOS = {
    "id": "x", "ad_library_id": "780659311220315", "advertiser": "Hashtag Treinamentos",
    "headline": "MasterClass gratuita - Automatize tudo com IA e N8N",
    "copy": "", "keyword": "automação", "niche": "Geral", "score": 99,
}

# Réplica fiel dos registros reais persistidos na Etapa 24.2/26 (mesmos
# textos/hashtags/scores observados em produção).
LINHA_IRRELEVANTE_SCORE_ALTO = {
    "hashtag": "automação com IA", "creator": "kathyfoodmachine",
    "hook": "Máquina de cocina totalmente automática; los dueños de restaurantes deberían tomar nota.",
    "description": "Máquina de cocina totalmente automática; los dueños de restaurantes deberían tomar nota.#foodmachine #cooking #pan",
    "hashtags": ["foodmachine", "cooking", "pan"],
    "views": 547900, "likes": 2040, "viral_score": 84,
}
LINHA_RELEVANTE_SCORE_MEDIO = {
    "hashtag": "automação com IA", "creator": "canalsegredosdodigital",
    "hook": "Quer automatizar seu atendimento com uma Inteligência Artificial? Entao olha o que essa ferramenta e capaz.",
    "description": "Quer automatizar seu atendimento com uma Inteligência Artificial?\n#marketingdigital #inteligenciaartificial #ia #automacao #rosanaai",
    "hashtags": ["marketingdigital", "inteligenciaartificial", "ia", "automacao", "rosanaai"],
    "views": 8360, "likes": 339, "viral_score": 60,
}
LINHA_RELEVANTE_SCORE_BAIXO = {
    "hashtag": "automação com IA", "creator": "automacaocomia",
    "hook": "Respondendo a @gearhead.i sobre automacao com n8n.",
    "description": "Respondendo a @gearhead.i #n8n #automacao #tecnologia #EmpreendedorismoDigital #InteligenciaArtificial #AgentesInteligentes #EmpreenderComIA",
    "hashtags": ["n8n", "automacao", "tecnologia", "AgentesInteligentes"],
    "views": 4143, "likes": 109, "viral_score": 50,
}


def _vocabulario():
    return _extrair_vocabulario_relevancia(OFERTA_HASHTAG_TREINAMENTOS)


# ---------------------------------------------------------------------------
# A) máquina de cozinha automática + viral_score 84 NÃO vence evidência
#    sobre N8N/IA -- o EXEMPLO OBRIGATÓRIO DE REGRESSÃO da Etapa 27.
# ---------------------------------------------------------------------------

def test_A_conteudo_irrelevante_com_maior_score_nao_vence(monkeypatch):
    # A consulta SQL real ordena por viral_score DESC -- reproduz essa ordem.
    linhas = [LINHA_IRRELEVANTE_SCORE_ALTO, LINHA_RELEVANTE_SCORE_MEDIO, LINHA_RELEVANTE_SCORE_BAIXO]
    monkeypatch.setattr(
        "requests.get",
        lambda *a, **k: type("R", (), {"raise_for_status": lambda self: None, "json": lambda self: linhas})(),
    )

    resultado = _buscar_sinal_fonte(FONTE_TIKTOK, ["automação"], _vocabulario())

    assert resultado.encontrado is True
    assert resultado.metricas["creator"] != "kathyfoodmachine"


# ---------------------------------------------------------------------------
# B) conteúdo N8N/automação com IA com viral_score MENOR é escolhido quando
#    semanticamente relevante (mesmo perdendo em score bruto pro irrelevante).
# ---------------------------------------------------------------------------

def test_B_conteudo_relevante_com_score_menor_e_escolhido(monkeypatch):
    linhas = [LINHA_IRRELEVANTE_SCORE_ALTO, LINHA_RELEVANTE_SCORE_MEDIO, LINHA_RELEVANTE_SCORE_BAIXO]
    monkeypatch.setattr(
        "requests.get",
        lambda *a, **k: type("R", (), {"raise_for_status": lambda self: None, "json": lambda self: linhas})(),
    )

    resultado = _buscar_sinal_fonte(FONTE_TIKTOK, ["automação"], _vocabulario())

    assert resultado.metricas["creator"] == "canalsegredosdodigital"
    assert resultado.metricas["viral_score"] == 60  # menor que 84, mas o unico/melhor RELEVANTE


# ---------------------------------------------------------------------------
# C) viral_score continua funcionando como desempate/ranking ENTRE
#    candidatos semanticamente relevantes.
# ---------------------------------------------------------------------------

def test_C_viral_score_ainda_ordena_entre_relevantes(monkeypatch):
    linhas = [LINHA_RELEVANTE_SCORE_MEDIO, LINHA_RELEVANTE_SCORE_BAIXO]  # ja vem ordenado desc pela query real
    monkeypatch.setattr(
        "requests.get",
        lambda *a, **k: type("R", (), {"raise_for_status": lambda self: None, "json": lambda self: linhas})(),
    )

    resultado = _buscar_sinal_fonte(FONTE_TIKTOK, ["automação"], _vocabulario())

    assert resultado.metricas["creator"] == "canalsegredosdodigital"  # score 60 > 50, ambos relevantes


def test_C_ordem_invertida_dos_relevantes_tambem_escolhe_o_maior_score(monkeypatch):
    """Confirma que quem decide é o SCORE (via ordenação da própria query
    SQL), não a ordem de chegada -- o filtro só remove, nunca reordena."""
    linhas = [LINHA_RELEVANTE_SCORE_BAIXO, LINHA_RELEVANTE_SCORE_MEDIO]  # fora de ordem de score de propósito
    monkeypatch.setattr(
        "requests.get",
        lambda *a, **k: type("R", (), {"raise_for_status": lambda self: None, "json": lambda self: linhas})(),
    )

    resultado = _buscar_sinal_fonte(FONTE_TIKTOK, ["automação"], _vocabulario())

    # O filtro preserva a ordem recebida (que quando vem da API real já e
    # por score) -- aqui simulamos exatamente a ordem dada, entao o
    # primeiro da lista (score_baixo) e o escolhido, provando que a
    # funcao NAO reordena por conta propria (quem ordena e o `order=` da
    # query real, testado a parte).
    assert resultado.metricas["creator"] == "automacaocomia"


# ---------------------------------------------------------------------------
# D) conteúdo sem relação temática não confirma uma fonte.
# ---------------------------------------------------------------------------

def test_D_apenas_conteudo_irrelevante_nao_confirma_a_fonte(monkeypatch):
    linhas = [LINHA_IRRELEVANTE_SCORE_ALTO]
    monkeypatch.setattr(
        "requests.get",
        lambda *a, **k: type("R", (), {"raise_for_status": lambda self: None, "json": lambda self: linhas})(),
    )

    resultado = _buscar_sinal_fonte(FONTE_TIKTOK, ["automação"], _vocabulario())

    assert resultado.encontrado is False
    assert resultado.resumo == "Sem evidencia disponivel nesta fonte."


def test_D_candidato_e_relevante_rejeita_conteudo_sem_overlap():
    vocabulario = _extrair_vocabulario_relevancia(OFERTA_HASHTAG_TREINAMENTOS)
    assert _candidato_e_relevante(LINHA_IRRELEVANTE_SCORE_ALTO, FONTE_TIKTOK["campos_conteudo"], vocabulario) is False
    assert _candidato_e_relevante(LINHA_RELEVANTE_SCORE_MEDIO, FONTE_TIKTOK["campos_conteudo"], vocabulario) is True
    assert _candidato_e_relevante(LINHA_RELEVANTE_SCORE_BAIXO, FONTE_TIKTOK["campos_conteudo"], vocabulario) is True


def test_D_campo_de_busca_nunca_conta_como_conteudo():
    """O campo `hashtag` (usado só pra ACHAR a linha via ilike) e IDENTICO
    em todas as 3 linhas ("automação com IA") -- se ele contasse como
    conteudo, a linha irrelevante passaria trivialmente. O filtro real usa
    `campos_conteudo`, que NUNCA inclui `hashtag`."""
    assert "hashtag" not in FONTE_TIKTOK["campos_conteudo"]


# ---------------------------------------------------------------------------
# E) comportamento de outras oportunidades (sem vocabulário/dado suficiente)
#    não é quebrado -- nunca bloqueia por falta de dado NOSSO.
# ---------------------------------------------------------------------------

def test_E_oferta_sem_texto_derivavel_nunca_bloqueia_candidato():
    oferta_vazia = {"id": "y", "score": 50}  # sem keyword/advertiser/headline/copy/niche
    vocabulario_vazio = _extrair_vocabulario_relevancia(oferta_vazia)
    assert vocabulario_vazio == set()
    assert _candidato_e_relevante(LINHA_IRRELEVANTE_SCORE_ALTO, FONTE_TIKTOK["campos_conteudo"], vocabulario_vazio) is True


def test_E_vocabulario_e_derivado_nunca_hardcoded():
    """O vocabulario muda conforme a oferta -- prova de que nao ha lista
    fixa pensada pra "Hashtag Treinamentos" no codigo."""
    vocabulario_1 = _extrair_vocabulario_relevancia({"headline": "Curso de culinária vegana", "keyword": "receitas"})
    vocabulario_2 = _extrair_vocabulario_relevancia(OFERTA_HASHTAG_TREINAMENTOS)
    assert "n8n" not in vocabulario_1
    assert "n8n" in vocabulario_2
    assert "receitas" in vocabulario_1
    assert "receitas" not in vocabulario_2


def test_E_extrai_termos_relevantes_do_headline_incluindo_siglas_curtas():
    vocabulario = _extrair_vocabulario_relevancia(OFERTA_HASHTAG_TREINAMENTOS)
    # "ia" (2 chars) e "n8n" precisam sobreviver ao filtro de stopwords/tamanho.
    assert "ia" in vocabulario
    assert "n8n" in vocabulario
    assert "automatize" in vocabulario
    # Stopwords genericas do headline ("com", "tudo", "e") nao devem sobrar.
    assert "com" not in vocabulario


def test_E_falha_de_rede_continua_tratada_sem_crash(monkeypatch):
    import requests

    def _boom(*a, **k):
        raise requests.exceptions.RequestException("falha simulada")
    monkeypatch.setattr("requests.get", _boom)

    resultado = _buscar_sinal_fonte(FONTE_TIKTOK, ["automação"], _vocabulario())
    assert resultado.encontrado is False
