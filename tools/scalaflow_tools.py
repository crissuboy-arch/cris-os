"""
Ferramentas do agente ScalaFlow Intel.

Le direto do Supabase do ScalaFlow Insights via API REST (PostgREST), usando
`requests` (ja e dependencia do projeto - nenhum pacote novo para instalar).

Fontes reais (produtos_minerados existe mas esta vazia -- NAO e usada aqui):
  collected_ads     -> anuncios coletados na Central de Mineracao (tem score,
                        created_at, advertiser, ad_url, etc.)
  user_ad_actions   -> acoes do usuario sobre um anuncio (ad_id -> collected_ads.id):
                        action = 'saved'    -> Ofertas Salvas
                        action = 'favorite' -> Favoritos

IMPORTANTE (confirmado lendo o codigo real do ScalaFlow em
escalaflow-insights/src/routes/_authenticated/ofertas-escaladas.tsx e
src/lib/queries.ts): "Ofertas Escaladas" NAO e uma acao salva em
user_ad_actions. A tela usa collected_ads.score >= 80 (limitado a 50 na UI).
Por isso "escalados" aqui filtra collected_ads por score, nao por acao.

Exige duas variaveis no .env:
  SUPABASE_URL          -> ex.: https://xxxxxxxx.supabase.co
  SUPABASE_SERVICE_KEY  -> a "service_role key" do projeto (Settings > API).
                            NAO pode ser a "anon key": as tabelas tem RLS
                            (auth.uid() = user_id) e o CRIS OS nao loga como
                            usuario nenhum, entao com a anon key o resultado
                            viria sempre vazio, sem erro nenhum aparecer.
"""

from __future__ import annotations

import logging
import re

try:
    # Faz o ssl/urllib3 confiarem no CA store do sistema operacional (Windows),
    # em vez do bundle publico do certifi. Necessario nesta maquina porque o
    # Avast (Web/Mail Shield) faz inspecao HTTPS e reassina os certificados com
    # uma CA propria -- o Windows/curl ja confia nela, mas o certifi (lista
    # publica da Mozilla) nao, e nao deveria. Isso NAO desativa verificacao de
    # certificado: so troca a fonte de confianca para a mesma que o SO usa.
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

import requests

from config.settings import settings
from tools.base import Tool

logger = logging.getLogger(__name__)

# Colunas pedidas para cada anuncio. Todas existem em collected_ads (schema
# real conferido em supabase/migrations); nenhuma e inventada.
_COLUNAS_ANUNCIO = [
    "id", "advertiser", "headline", "copy", "cta", "platform", "country",
    "niche", "keyword", "score", "status", "source", "created_at",
    "ad_url", "ad_library_id", "image_url", "video_url",
]

# score minimo real usado pela tela "Ofertas Escaladas" do ScalaFlow.
_SCORE_ESCALADO = 80

# Limite maximo aceito numa consulta (evita pedir "top 999" e travar o Telegram
# com uma mensagem gigante).
_LIMITE_MAXIMO = 20

_PAISES: dict[str, str] = {
    "brasil": "BR",
    "eua": "US",
    "estados unidos": "US",
    "usa": "US",
    "espanha": "ES",
    "mexico": "MX",
    "méxico": "MX",
    "portugal": "PT",
    "canada": "CA",
    "canadá": "CA",
    "franca": "FR",
    "frança": "FR",
    "alemanha": "DE",
    "italia": "IT",
    "itália": "IT",
    "reino unido": "GB",
    "inglaterra": "GB",
}

_PLATAFORMAS: dict[str, str] = {
    "facebook": "FACEBOOK",
    "instagram": "INSTAGRAM",
    "tiktok": "TIKTOK",
    "google": "GOOGLE",
    "youtube": "YOUTUBE",
}


def _buscar_anuncios(
    limite: int = 5,
    plataforma: str | None = None,
    pais: str | None = None,
    nicho: str | None = None,
    palavra_chave: str | None = None,
    score_minimo: int | None = None,
    somente_salvos: bool = False,
    somente_escalados: bool = False,
    somente_favoritos: bool = False,
) -> list[dict] | str:
    """
    Consulta os anuncios reais do ScalaFlow (collected_ads), ordenados por
    score DESC.

    - somente_salvos / somente_favoritos: filtram via user_ad_actions
      (action = saved/favorite) relacionado por ad_id.
    - somente_escalados: filtra collected_ads.score >= 80 (regra real da tela
      "Ofertas Escaladas" -- NAO existe acao 'scaled' na producao).

    Retorna lista de dicts (um por anuncio) ou uma string de erro/aviso.
    """
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SERVICE_KEY

    if not url or not key:
        return (
            "ScalaFlow Intel nao esta configurado ainda: falta SUPABASE_URL "
            "e/ou SUPABASE_SERVICE_KEY no arquivo .env do CRIS OS. "
            "Nenhum dado foi inventado -- e por isso que estou avisando em vez "
            "de responder com uma lista."
        )

    if somente_escalados:
        score_minimo = _SCORE_ESCALADO if score_minimo is None else max(score_minimo, _SCORE_ESCALADO)

    acao = None
    if somente_salvos:
        acao = "saved"
    elif somente_favoritos:
        acao = "favorite"

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    colunas = ",".join(_COLUNAS_ANUNCIO)

    if acao:
        endpoint = f"{url.rstrip('/')}/rest/v1/user_ad_actions"
        params: dict[str, str] = {
            "select": f"created_at,collected_ads!inner({colunas})",
            "action": f"eq.{acao}",
            "order": "collected_ads(score).desc,created_at.desc",
            "limit": str(limite),
        }
        prefixo = "collected_ads."
    else:
        endpoint = f"{url.rstrip('/')}/rest/v1/collected_ads"
        params = {
            "select": colunas,
            "order": "score.desc,created_at.desc",
            "limit": str(limite),
        }
        prefixo = ""

    if plataforma:
        params[f"{prefixo}platform"] = f"eq.{plataforma}"
    if pais:
        params[f"{prefixo}country"] = f"eq.{pais}"
    if nicho:
        params[f"{prefixo}niche"] = f"eq.{nicho}"
    if score_minimo is not None:
        params[f"{prefixo}score"] = f"gte.{score_minimo}"
    if palavra_chave:
        termo = palavra_chave.replace(",", " ").replace("(", " ").replace(")", " ").strip()
        campos = ("headline", "advertiser", "niche", "keyword")
        params[f"{prefixo}or"] = "(" + ",".join(f"{c}.ilike.*{termo}*" for c in campos) + ")"

    try:
        resp = requests.get(endpoint, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        dados = resp.json()
    except requests.exceptions.RequestException as exc:
        logger.exception("=== [SCALAFLOW_INTEL] Falha ao consultar Supabase ===")
        return f"Nao consegui consultar o ScalaFlow agora: {exc}"

    if acao:
        return [linha["collected_ads"] for linha in dados if linha.get("collected_ads")]
    return dados


def _resumir_copy(copy: str, limite_chars: int = 160) -> str:
    texto = " ".join(copy.split())
    if len(texto) > limite_chars:
        return texto[: limite_chars - 3].rstrip() + "..."
    return texto


def _formatar_anuncios(anuncios: list[dict], titulo: str) -> str:
    """Formata a lista de anuncios para leitura humana no Telegram (sem JSON)."""
    if not anuncios:
        return f"Consultei o ScalaFlow e nao encontrei anuncios para: {titulo}."

    blocos = [titulo, ""]
    for i, a in enumerate(anuncios, start=1):
        score = a.get("score")
        linhas = [f"#{i} -- SCORE {score if score is not None else '?'}"]

        if a.get("advertiser"):
            linhas.append(f"Anunciante: {a['advertiser']}")
        if a.get("headline"):
            linhas.append(f"Titulo: {a['headline']}")
        if a.get("platform"):
            linhas.append(f"Plataforma: {a['platform']}")
        if a.get("country"):
            linhas.append(f"Pais: {a['country']}")
        if a.get("niche"):
            linhas.append(f"Nicho: {a['niche']}")
        if a.get("copy"):
            linhas.append(f"Resumo da copy: {_resumir_copy(a['copy'])}")
        if a.get("ad_url"):
            linhas.append(f"Abrir anuncio: {a['ad_url']}")

        blocos.append("\n".join(linhas))
        blocos.append("")

    return "\n".join(blocos).strip()


def _extrair_limite(texto: str, default: int = 5) -> int:
    m = re.search(r"\d{1,3}", texto)
    if m:
        n = int(m.group())
        if 1 <= n <= _LIMITE_MAXIMO:
            return n
        if n > _LIMITE_MAXIMO:
            return _LIMITE_MAXIMO
    return default


def _extrair_pais(texto: str) -> str | None:
    for alias, codigo in _PAISES.items():
        if alias in texto:
            return codigo
    return None


def _extrair_plataforma(texto: str) -> str | None:
    for alias, codigo in _PLATAFORMAS.items():
        if alias in texto:
            return codigo
    return None


def _extrair_score_minimo(texto: str) -> int | None:
    m = re.search(
        r"score\s*(?:>=|maior ou igual a|acima de|a partir de)\s*(\d{1,3})",
        texto,
    )
    if m:
        return int(m.group(1))
    return None


def _extrair_palavra_chave(texto: str) -> str | None:
    """
    Extrai um nicho/palavra-chave de padroes simples como "anuncios de IA" ou
    "produtos de emagrecimento". So usa o final da frase para evitar pegar
    lixo do meio (ex.: "melhores ofertas dos Estados Unidos" nao tem "de X"
    no final, entao nao vira palavra-chave).
    """
    texto_limpo = texto.strip(" ?!.")
    m = re.search(r"\bde\s+([a-z0-9à-ÿ\-]+(?:\s+[a-z0-9à-ÿ\-]+){0,2})$", texto_limpo)
    if not m:
        return None
    termo = m.group(1).strip()
    if not termo or termo in _PAISES or termo in _PLATAFORMAS:
        return None
    return termo


def _buscar_top_produtos(entrada: str) -> str:
    """
    Busca os anuncios com maior score em collected_ads (ScalaFlow), com
    parsing determinístico (sem IA) de limite, pais, plataforma, nicho e
    filtros de salvos/escalados/favoritos a partir do texto do usuario.

    Nome mantido por compatibilidade com o Tool ja registrado como
    "top_produtos_scalaflow" -- internamente e uma busca de anuncios/ofertas,
    nao de "produtos_minerados" (tabela vazia, nao usada aqui).
    """
    texto = (entrada or "").strip().lower()

    limite = _extrair_limite(texto, default=5)
    somente_salvos = "salv" in texto
    somente_favoritos = "favorit" in texto
    somente_escalados = "escalad" in texto
    pais = _extrair_pais(texto)
    plataforma = _extrair_plataforma(texto)
    score_minimo = _extrair_score_minimo(texto)
    palavra_chave = _extrair_palavra_chave(texto)

    resultado = _buscar_anuncios(
        limite=limite,
        plataforma=plataforma,
        pais=pais,
        palavra_chave=palavra_chave,
        score_minimo=score_minimo,
        somente_salvos=somente_salvos,
        somente_escalados=somente_escalados,
        somente_favoritos=somente_favoritos,
    )
    if isinstance(resultado, str):
        return resultado

    if somente_salvos:
        titulo = "OFERTAS SALVAS -- ScalaFlow"
    elif somente_favoritos:
        titulo = "FAVORITOS -- ScalaFlow"
    elif somente_escalados:
        titulo = f"OFERTAS ESCALADAS (score >= {_SCORE_ESCALADO}) -- ScalaFlow"
    else:
        titulo = f"TOP {len(resultado)} ANUNCIOS -- ScalaFlow (por score)"

    return _formatar_anuncios(resultado, titulo)


def get_tools() -> list[Tool]:
    return [
        Tool(
            "top_produtos_scalaflow",
            "Busca os anuncios/ofertas com maior score no ScalaFlow "
            "(collected_ads), com filtro opcional de pais/plataforma/nicho e "
            "de salvos/escalados/favoritos",
            ["produto", "produtos", "anuncio", "anuncios", "anúncio", "anúncios",
             "quente", "quentes", "vencedor", "vencedores", "oferta", "ofertas",
             "scalaflow", "minerado", "minerados", "top", "top10", "lista",
             "listar", "melhores", "ranking", "salvos", "escalados", "escalada",
             "favoritos", "favorito"],
            _buscar_top_produtos,
        ),
    ]
