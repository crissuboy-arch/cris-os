"""
Evidence Guard — separa EVIDENCIA DE MERCADO (o que o concorrente/anuncio
original diz) de COPY DO PRODUTO NOVO (o que a Cris OS gera) (Fase 4,
correcao pos-teste real, 2 rodadas de correcao).

Principio (regra fundamental repetida pela Cris): o anuncio original e
EVIDENCIA DE MERCADO. Ele NUNCA e fonte de verdade sobre o produto que
estamos criando -- nada dele pode virar afirmacao factual sobre o produto
novo sem passar por aqui.

Este modulo classifica trechos de texto gerado por LLM em CATEGORIAS, cada
uma com uma ACAO diferente (nao e "uma lista de palavras proibidas" -- e
uma classificacao semantica por TIPO de problema):

  1. FATO INVENTADO (numero de clientes/vendas/faturamento/depoimentos) --
     nao pode nem virar hipotese (e uma alegacao de algo que JA aconteceu,
     e nao aconteceu) -- REMOVIDO.
  2. URGENCIA/ESCASSEZ/GARANTIA sem oferta real aprovada ("ultima chance",
     "desconto", "garantia", "acesso vitalicio") -- REMOVIDO (so volta a
     aparecer quando houver uma oferta REAL aprovada no Business Plan).
  3. PROMESSA DE RESULTADO/SUCESSO implicita ("aumenta sua chance de
     sucesso") -- REMOVIDO (promessa de resultado nunca e responsavel sem
     dado real).
  4. FUNCIONALIDADE AINDA NAO CONSTRUIDA ("fornecedores confiaveis",
     "comunidade de usuarios", "consultoria one-on-one") -- essas SAO ideias
     legitimas (o Product Architect/Business Builder podem sugerir
     funcionalidades futuras) -- mas precisam ficar EXPLICITAMENTE marcadas
     como hipotese/nao construida, entao sao REESCRITAS (nao removidas).

Uso: `sanitizar_claims_herdadas()` em qualquer texto gerado por LLM que
possa ter herdado contexto de um anuncio/concorrente ou inventado uma
funcionalidade como se ja existisse (candidatos do Product Architect, campos
do Business Plan, artefatos da Product Factory).
"""

from __future__ import annotations

import re

_MARCADOR_FATO_INVENTADO = "[CLAIM REMOVIDA — não verificada para este produto ainda]"
_MARCADOR_URGENCIA_GARANTIA = "[CLAIM DE URGÊNCIA/GARANTIA REMOVIDA — sem oferta aprovada real]"
_MARCADOR_PROMESSA_RESULTADO = "[PROMESSA DE RESULTADO REMOVIDA — não verificável]"
_MARCADOR_METRICA_TRAFEGO = "[MÉTRICA/RESULTADO DE TRÁFEGO REMOVIDA — sem campanha real rodando]"


def _wrap_hipotese_funcionalidade(match: re.Match) -> str:
    trecho = match.group(0)
    return f"[HIPÓTESE DE FUNCIONALIDADE: {trecho} — ainda não aprovada/construída]"


# ---------------------------------------------------------------------------
# Categoria 1: FATO INVENTADO -- numero de clientes/vendas/depoimentos/etc.
# Isso e uma alegacao de algo que JA aconteceu (prova social/resultado
# passado) -- nao ha como "virar hipotese" com sentido, so remover.
# ---------------------------------------------------------------------------
_PADROES_FATO_INVENTADO: tuple[re.Pattern, ...] = (
    re.compile(
        r"j[áa]\s+ajud(ou|aram)\s+(mais\s+de\s+)?[\d.,]+\s*(mil\s+)?"
        r"(pessoas|clientes|alunos|usu[áa]rios)",
        re.IGNORECASE,
    ),
    re.compile(
        r"[\d.,]+\s*(mil\s+)?(pessoas|clientes|alunos|usu[áa]rios)\s+"
        r"(j[áa]\s+)?(compraram|confiam|usam|adquiriram|aprovaram)",
        re.IGNORECASE,
    ),
    re.compile(r"n[úu]mero\s+de\s+(clientes|alunos|vendas|usu[áa]rios)", re.IGNORECASE),
    re.compile(r"(faturamento|lucro)\s+(mensal|anual|de\s+r\$)", re.IGNORECASE),
    re.compile(r"taxa\s+de\s+sucesso\s+(de\s+)?[\d.,]*%?", re.IGNORECASE),
    re.compile(r"depoimentos?\s+(reais|de\s+clientes|de\s+alunos)", re.IGNORECASE),
    re.compile(r"\bdepoimentos\b", re.IGNORECASE),
    re.compile(r"avalia[çc][õo]es\s+(positivas|de\s+\d)", re.IGNORECASE),
)

# ---------------------------------------------------------------------------
# Categoria 2: URGENCIA/ESCASSEZ/GARANTIA sem oferta real aprovada.
# ---------------------------------------------------------------------------
_PADROES_URGENCIA_GARANTIA: tuple[re.Pattern, ...] = (
    re.compile(r"acesso\s+vital[íi]cio", re.IGNORECASE),
    re.compile(r"lista\s+de\s+fornecedor(es)?\s+(inclus[oa]s?|inclu[íi]d[oa]s?)", re.IGNORECASE),
    re.compile(r"garantia\s+(de\s+)?(satisfa[çc][ãa]o|\d+\s*dias|incondicional)", re.IGNORECASE),
    re.compile(r"\[?[uú]ltima\s+chance\]?", re.IGNORECASE),
    re.compile(r"somente\s+hoje", re.IGNORECASE),
    re.compile(r"vagas?\s+limitadas?", re.IGNORECASE),
    re.compile(r"desconto\s+(exclusivo|especial|por\s+tempo)", re.IGNORECASE),
    re.compile(r"b[ôo]nus\s+exclusivos?", re.IGNORECASE),
    re.compile(r"webin[áa]rio\s+exclusivo", re.IGNORECASE),
)

# ---------------------------------------------------------------------------
# Categoria 3: PROMESSA DE RESULTADO/SUCESSO implicita.
# ---------------------------------------------------------------------------
_PADROES_PROMESSA_RESULTADO: tuple[re.Pattern, ...] = (
    re.compile(r"aumenta(ndo)?\s+(a\s+)?(sua\s+)?chance\s+de\s+sucesso", re.IGNORECASE),
    re.compile(r"chance\s+de\s+sucesso", re.IGNORECASE),
    re.compile(r"garante\s+(o\s+)?sucesso", re.IGNORECASE),
    re.compile(r"sucesso\s+garantido", re.IGNORECASE),
    re.compile(r"garante\s+venda", re.IGNORECASE),
    re.compile(r"(f[áa]cil|f[áa]ceis)\s+vender", re.IGNORECASE),
)

# ---------------------------------------------------------------------------
# Categoria 4: FUNCIONALIDADE AINDA NAO CONSTRUIDA -- ideia legitima, mas
# precisa ficar marcada como HIPOTESE em vez de apagada.
# ---------------------------------------------------------------------------
_PADROES_FUNCIONALIDADE_HIPOTETICA: tuple[re.Pattern, ...] = (
    re.compile(r"fornecedores?\s+conf[íi][áa]veis", re.IGNORECASE),
    re.compile(r"fornecedores?\s+de\s+alta\s+qualidade", re.IGNORECASE),
    re.compile(r"diret[óo]rio\s+de\s+fornecedores?", re.IGNORECASE),
    re.compile(r"comunidade\s+de\s+usu[áa]rios", re.IGNORECASE),
    re.compile(r"consultoria\s+one-?on-?one", re.IGNORECASE),
    re.compile(r"consultoria\s+individual", re.IGNORECASE),
    re.compile(r"mentoria\s+individual", re.IGNORECASE),
    # Fase 5 (Paid Traffic Architect) -- generico, nao especifico de nenhum
    # nicho: qualquer alegacao de JA TER acesso/parceria/rede com
    # fornecedores e uma funcionalidade/relacao que normalmente nao existe
    # antes do produto ser construido.
    re.compile(r"acesso\s+a\s+fornecedor(es)?", re.IGNORECASE),
    re.compile(r"parceria\s+com\s+fornecedor(es)?", re.IGNORECASE),
    re.compile(r"rede\s+de\s+fornecedores?", re.IGNORECASE),
)

# ---------------------------------------------------------------------------
# Categoria 5 (Fase 5 -- Paid Traffic Architect): METRICA/RESULTADO DE
# TRAFEGO PAGO inventado. Antes de qualquer campanha rodar, NENHUM numero de
# performance (CTR/CPC/CPM/CPA/ROAS/CVR) e verificavel -- e uma alegacao tao
# grave quanto um "fato inventado" (categoria 1), so que especifica de
# trafego pago. "Produto comprovado"/"oferta vencedora" tambem entram aqui:
# sao vereditos de sucesso que nao existem antes de uma campanha real.
# ---------------------------------------------------------------------------
_PADROES_METRICA_TRAFEGO_INVENTADA: tuple[re.Pattern, ...] = (
    re.compile(r"ctr\s+(ideal|esperado|previsto|estimado)?\s*(de)?\s*[\d.,]+\s*%", re.IGNORECASE),
    re.compile(r"roas\s+(ideal|esperado|previsto|estimado)?\s*(de)?\s*[\d.,]+\s*x?", re.IGNORECASE),
    re.compile(r"cpa\s+(ideal|esperado|previsto|estimado)?\s*(de)?\s*(r\$|us\$|\$)?\s*[\d.,]+", re.IGNORECASE),
    re.compile(r"cpc\s+(ideal|esperado|previsto|estimado)?\s*(de)?\s*(r\$|us\$|\$)?\s*[\d.,]+", re.IGNORECASE),
    re.compile(r"cpm\s+(ideal|esperado|previsto|estimado)?\s*(de)?\s*(r\$|us\$|\$)?\s*[\d.,]+", re.IGNORECASE),
    re.compile(r"cvr\s+(ideal|esperado|previsto|estimado)?\s*(de)?\s*[\d.,]+\s*%", re.IGNORECASE),
    re.compile(r"vai\s+converter", re.IGNORECASE),
    re.compile(r"alta\s+demanda", re.IGNORECASE),
    re.compile(r"produto\s+comprovado", re.IGNORECASE),
    re.compile(r"oferta\s+vencedora", re.IGNORECASE),
    re.compile(r"volume\s+de\s+pesquisa\s+(alto|de\s+[\d.,]+)", re.IGNORECASE),
)

# Prospectivas de risco (churn/escala/conversao) -- mantidas do round
# anterior (usadas por `core/product_architect.py`); reexportadas aqui pra
# nao duplicar a lista em dois lugares.
FRASES_PROSPECTIVAS_DE_RISCO = (
    "churn", "escalar", "escalonar", "conversão", "conversao",
    "converte bem", "primeiras vendas", "demanda comprovada",
    "garante venda", "sucesso garantido", "viraliza", "facil vender",
    "fácil vender",
)
MARCADORES_EXPLICITOS_DE_HIPOTESE = (
    "hipotese", "hipótese", "premissa", "a validar", "sem validacao",
    "sem validação", "inferencia", "inferência",
)


def sanitizar_claims_herdadas(texto: str | None) -> str | None:
    """
    Aplica as 5 categorias, nesta ordem: primeiro REESCREVE funcionalidades
    hipoteticas (preserva a ideia, marca como nao construida), depois REMOVE
    fatos inventados, urgencia/garantia sem oferta real, promessas de
    resultado e metricas/resultados de trafego pago inventados. Nunca deixa
    passar silenciosamente.
    """
    if not texto:
        return texto
    resultado = texto
    for padrao in _PADROES_FUNCIONALIDADE_HIPOTETICA:
        resultado = padrao.sub(_wrap_hipotese_funcionalidade, resultado)
    for padrao in _PADROES_FATO_INVENTADO:
        resultado = padrao.sub(_MARCADOR_FATO_INVENTADO, resultado)
    for padrao in _PADROES_URGENCIA_GARANTIA:
        resultado = padrao.sub(_MARCADOR_URGENCIA_GARANTIA, resultado)
    for padrao in _PADROES_PROMESSA_RESULTADO:
        resultado = padrao.sub(_MARCADOR_PROMESSA_RESULTADO, resultado)
    for padrao in _PADROES_METRICA_TRAFEGO_INVENTADA:
        resultado = padrao.sub(_MARCADOR_METRICA_TRAFEGO, resultado)
    return resultado


def contem_claim_herdada(texto: str | None) -> bool:
    """True se `texto` contem algum padrao de qualquer categoria (usado em
    testes/validacao, sem precisar sanitizar)."""
    if not texto:
        return False
    todos = (
        _PADROES_FATO_INVENTADO + _PADROES_URGENCIA_GARANTIA
        + _PADROES_PROMESSA_RESULTADO + _PADROES_FUNCIONALIDADE_HIPOTETICA
        + _PADROES_METRICA_TRAFEGO_INVENTADA
    )
    return any(p.search(texto) for p in todos)
