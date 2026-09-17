"""
Ferramentas do agente Opportunity Analyst.

Investiga uma oferta real do ScalaFlow (Meta/collected_ads) cruzando sinais
das tabelas de mineracao que ja existem no Supabase do ScalaFlow -- TikTok,
Instagram, YouTube e Google Trends (`*_minerados`). NAO reconstroi radar
nenhum: so LE (SELECT) o que ja foi minerado.

Sem LLM nesta fase (Fase 2): a correlacao entre o anuncio e as outras fontes
e feita por PALAVRA-CHAVE (o campo `keyword` que o proprio ScalaFlow salvou
ao minerar o anuncio, ou o nome do anunciante) -- nao existe uma chave
estrangeira real entre `collected_ads` e as tabelas `*_minerados`. Isso e
declarado explicitamente no relatorio: e uma correlacao por termo de busca,
nao um link garantido.

Secoes que exigiriam interpretar o TEXTO do anuncio (publico, problema,
promessa, mecanismo, angulos, padroes criativos) NAO sao preenchidas por
IA nesta fase -- ficam marcadas como "sem analise qualitativa disponivel"
em vez de inventadas.
"""

from __future__ import annotations

import logging
import re

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

import requests

from config.settings import settings
from core.decision_engine import (
    SinalPlataforma,
    decidir,
    preparar_analise_afiliacao,
    preparar_analise_comercio,
)
from memory import ProjectBrainStore
from memory.layers import ProjectMemory
from storage import SQLiteMemory
from tools.base import Tool
from tools.scalaflow_tools import _buscar_anuncios

logger = logging.getLogger(__name__)

_SEM_ANALISE_QUALITATIVA = "Sem analise qualitativa disponivel nesta fase (requer IA, nao habilitada)."

_FONTES = [
    {
        "nome": "tiktok",
        "tabela": "tiktok_minerados",
        "campo_busca": "hashtag",
        "colunas": "hashtag,creator,video_url,views,likes,viral_score,created_at",
        "ordem": "viral_score.desc",
        "metrica_principal": "viral_score",
    },
    {
        "nome": "instagram",
        "tabela": "instagram_minerados",
        "campo_busca": "search",
        "colunas": "search,owner_username,post_url,likes_count,engagement_score,created_at",
        "ordem": "engagement_score.desc",
        "metrica_principal": "engagement_score",
    },
    {
        "nome": "youtube",
        "tabela": "youtube_minerados",
        "campo_busca": "query",
        "colunas": "query,channel_name,video_url,views,viral_score,created_at",
        "ordem": "viral_score.desc",
        "metrica_principal": "viral_score",
    },
    {
        "nome": "google_trends",
        "tabela": "google_trends_minerados",
        "campo_busca": "keyword",
        "colunas": "keyword,geo,trend,avg_interest,peak_interest,created_at",
        "ordem": "avg_interest.desc",
        "metrica_principal": "avg_interest",
    },
]

_PATH_LABEL = {
    "CREATE_OWN_PRODUCT": ("PRODUTO PROPRIO", "\U0001f3d7️"),
    "AFFILIATE": ("AFILIACAO", "\U0001f4b0"),
    "COMMERCE_RESALE": ("COMERCIO/REVENDA", "\U0001f4e6"),
    "INVESTIGATE_MORE": ("INVESTIGAR MAIS", "\U0001f50d"),
    "DISCARD": ("DESCARTAR", "\U0001f6ab"),
}

_project_brain_store: ProjectBrainStore | None = None


def _get_project_brain_store() -> ProjectBrainStore:
    """Store lazy e reaproveitado (mesma conexao SQLite, WAL) por processo."""
    global _project_brain_store
    if _project_brain_store is None:
        backend = SQLiteMemory(settings.DB_PATH)
        _project_brain_store = ProjectBrainStore(ProjectMemory(backend))
    return _project_brain_store


def _headers() -> dict:
    return {
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
    }


def _extrair_ad_library_id(texto: str) -> str | None:
    m = re.search(r"ads/library/\?id=(\d+)", texto)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{12,20})\b", texto)
    if m:
        return m.group(1)
    return None


def _resolver_oferta(texto: str) -> dict | str:
    """
    Resolve qual anuncio investigar a partir do texto do usuario. Reaproveita
    `_buscar_anuncios` (tools/scalaflow_tools.py) -- nao duplica logica de
    consulta ao Supabase.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return (
            "ScalaFlow Intel nao esta configurado ainda: falta SUPABASE_URL "
            "e/ou SUPABASE_SERVICE_KEY no .env."
        )

    ad_library_id = _extrair_ad_library_id(texto)
    if ad_library_id:
        url = settings.SUPABASE_URL.rstrip("/")
        try:
            resp = requests.get(
                f"{url}/rest/v1/collected_ads",
                headers=_headers(),
                params={"select": "*", "ad_library_id": f"eq.{ad_library_id}", "limit": "1"},
                timeout=15,
            )
            resp.raise_for_status()
            linhas = resp.json()
        except requests.exceptions.RequestException as exc:
            return f"Nao consegui consultar o ScalaFlow agora: {exc}"
        if linhas:
            return linhas[0]
        return f"Nao encontrei nenhum anuncio com ad_library_id={ad_library_id} no ScalaFlow."

    texto_lower = texto.lower()
    if "favorit" in texto_lower:
        resultado = _buscar_anuncios(limite=1, somente_favoritos=True)
        vazio_msg = "Voce ainda nao tem favoritos no ScalaFlow."
    elif "salv" in texto_lower:
        resultado = _buscar_anuncios(limite=1, somente_salvos=True)
        vazio_msg = "Voce ainda nao tem ofertas salvas no ScalaFlow."
    elif "escalad" in texto_lower:
        resultado = _buscar_anuncios(limite=1, somente_escalados=True)
        vazio_msg = "Nao ha ofertas escaladas (score >= 80) no ScalaFlow no momento."
    else:
        resultado = _buscar_anuncios(limite=1)
        vazio_msg = "Nao encontrei nenhum anuncio no ScalaFlow para investigar."

    if isinstance(resultado, str):
        return resultado
    if not resultado:
        return vazio_msg
    return resultado[0]


def _extrair_termos_busca(oferta: dict) -> list[str]:
    termos = []
    if oferta.get("keyword"):
        termos.append(oferta["keyword"])
    nicho = oferta.get("niche")
    if nicho and nicho.strip().lower() not in ("geral", ""):
        termos.append(nicho)
    if oferta.get("advertiser"):
        termos.append(oferta["advertiser"])
    # remove duplicados mantendo ordem
    vistos: set[str] = set()
    unicos = []
    for t in termos:
        chave = t.strip().lower()
        if chave and chave not in vistos:
            vistos.add(chave)
            unicos.append(t.strip())
    return unicos


def _buscar_sinal_fonte(fonte: dict, termos: list[str]) -> SinalPlataforma:
    url = settings.SUPABASE_URL.rstrip("/")
    for termo in termos:
        params = {
            "select": fonte["colunas"],
            fonte["campo_busca"]: f"ilike.*{termo}*",
            "order": fonte["ordem"],
            "limit": "3",
        }
        try:
            resp = requests.get(
                f"{url}/rest/v1/{fonte['tabela']}", headers=_headers(),
                params=params, timeout=15,
            )
            resp.raise_for_status()
            linhas = resp.json()
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "=== [OPPORTUNITY_ANALYST] Falha ao consultar %s: %s ===",
                fonte["tabela"], exc,
            )
            continue
        if linhas:
            melhor = linhas[0]
            metrica = melhor.get(fonte["metrica_principal"])
            resumo = (
                f"{len(linhas)} resultado(s) para '{termo}' -- "
                f"{fonte['metrica_principal']}: {metrica}"
            )
            return SinalPlataforma(
                fonte=fonte["nome"], encontrado=True, resumo=resumo,
                metricas=melhor, termo_busca=termo,
            )
    return SinalPlataforma(
        fonte=fonte["nome"], encontrado=False,
        resumo="Sem evidencia disponivel nesta fonte.", termo_busca=None,
    )


def _contar_concorrencia_scalaflow(keyword: str | None, excluir_id: str) -> str:
    """Proxy OBJETIVO e limitado: quantos outros anuncios no proprio ScalaFlow
    usam o mesmo termo de busca. NAO e concorrencia de mercado real."""
    if not keyword:
        return "Sem `keyword` no anuncio para comparar com outros do ScalaFlow."
    url = settings.SUPABASE_URL.rstrip("/")
    try:
        resp = requests.get(
            f"{url}/rest/v1/collected_ads", headers=_headers(),
            params={"select": "id", "keyword": f"eq.{keyword}", "limit": "50"},
            timeout=15,
        )
        resp.raise_for_status()
        linhas = [r for r in resp.json() if r.get("id") != excluir_id]
    except requests.exceptions.RequestException as exc:
        return f"Nao consegui checar concorrencia interna: {exc}"
    return f"{len(linhas)} outro(s) anuncio(s) no ScalaFlow usando o termo '{keyword}' (contagem interna, nao e concorrencia de mercado real)."


def investigar_oportunidade(entrada: str) -> str:
    """Investiga uma oferta do ScalaFlow e devolve um resumo pronto pro Telegram."""
    oferta = _resolver_oferta(entrada)
    if isinstance(oferta, str):
        return oferta

    termos = _extrair_termos_busca(oferta)
    sinais = [_buscar_sinal_fonte(fonte, termos) for fonte in _FONTES]

    concorrencia_texto = _contar_concorrencia_scalaflow(oferta.get("keyword"), oferta.get("id", ""))

    decisao = decidir(oferta.get("score"), sinais)
    afiliacao = preparar_analise_afiliacao(sinais)
    comercio = preparar_analise_comercio(sinais)

    store = _get_project_brain_store()
    brain = None
    for existente in store.list_all():
        if existente.origem.source_offer_id == (oferta.get("ad_library_id") or oferta.get("id")):
            brain = existente
            break
    if brain is None:
        nome = oferta.get("advertiser") or oferta.get("headline") or "Oportunidade ScalaFlow"
        brain = store.create(name=nome, tipo="opportunity")

    brain.origem.source_offer_id = oferta.get("ad_library_id") or oferta.get("id")
    brain.origem.source_platform = oferta.get("platform")
    brain.origem.source_url = oferta.get("ad_url")
    brain.origem.source_country = oferta.get("country")
    brain.mercado.niche = oferta.get("niche")
    brain.mercado.target_country = oferta.get("country")
    brain.oportunidade.score = oferta.get("score")
    brain.oportunidade.signals = {s.fonte: {
        "encontrado": s.encontrado, "resumo": s.resumo, "termo_busca": s.termo_busca,
        "metricas": s.metricas,
    } for s in sinais}
    brain.oportunidade.evidence = [s.resumo for s in sinais if s.encontrado]
    brain.oportunidade.competition = {"scalaflow_interno": concorrencia_texto}
    brain.oportunidade.risks = list(decisao.dados_faltantes)
    brain.decisao.recommended_path = decisao.path
    brain.decisao.reasoning_summary = decisao.motivo
    brain.decisao.evidence_level = decisao.evidence_level
    brain.decisao.decision_status = "PENDING_APPROVAL"
    brain.registrar_run("opportunity_analyst", f"Investigou oferta {brain.origem.source_offer_id}")
    brain.registrar_decisao(decisao.path, decisao.motivo)
    store.save(brain)

    label, emoji = _PATH_LABEL.get(decisao.path, (decisao.path, ""))
    if decisao.dados_faltantes:
        risco_principal = "Faltam fontes: " + ", ".join(decisao.dados_faltantes)
    else:
        risco_principal = f"Nenhum sinal objetivo faltante, mas {_SEM_ANALISE_QUALITATIVA.lower()}"

    if decisao.path == "DISCARD":
        proximo_passo = "Nenhuma acao recomendada -- oportunidade descartada (motivo registrado no Project Brain)."
    elif decisao.path == "INVESTIGATE_MORE":
        proximo_passo = "Buscar evidencia nas fontes que faltam antes de decidir um caminho."
    elif decisao.path == "AFFILIATE":
        proximo_passo = "Buscar programa de afiliados real para este produto/nicho antes de investir em criativos."
    else:
        proximo_passo = "Avaliar manualmente -- este caminho exige dado que o ScalaFlow sozinho nao fornece."

    linhas = [
        "\U0001f50e OPORTUNIDADE ANALISADA",
        "",
        f"Produto: {oferta.get('advertiser') or oferta.get('headline') or '(sem nome)'}",
        f"Mercado: {oferta.get('country') or '?'}",
        f"Score: {oferta.get('score', '?')}",
        "",
        "Sinais:",
    ]
    for s in sinais:
        linhas.append(f"{s.fonte.capitalize()}: {s.resumo}")
    linhas.append(f"Concorrencia (ScalaFlow, interno): {concorrencia_texto}")
    linhas += [
        "",
        f"CAMINHO: {emoji} {label}",
        f"Motivo: {decisao.motivo}",
        f"Risco principal: {risco_principal}",
        f"Proximo passo: {proximo_passo}",
        "",
        f"Projeto: {brain.project_id}",
    ]
    return "\n".join(linhas)


def get_tools() -> list[Tool]:
    return [
        Tool(
            "investigar_oportunidade_scalaflow",
            "Investiga uma oferta do ScalaFlow cruzando sinais reais de "
            "TikTok/Instagram/YouTube/Google Trends e recomenda um caminho "
            "(sem inventar dado, sem LLM)",
            ["investigue", "investigar", "investigacao", "analise", "analisar",
             "analisa", "oportunidade", "oportunidades", "sinais", "sinal",
             "caminho", "decisao", "decision"],
            investigar_oportunidade,
        ),
    ]
