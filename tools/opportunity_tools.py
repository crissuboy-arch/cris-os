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
from memory import PendingApprovalStore, ProjectBrainStore, UserFocusStore
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

# "Oportunidade em foco": qual projeto a ultima investigacao/proposta desta
# CONVERSA tratou. Usado para resolver follow-ups como "isso aparece no
# TikTok?"/"qual caminho faz sentido pra essa oportunidade?" sem exigir que
# o usuario repita o link do anuncio a cada mensagem.
#
# CORRECAO (pos-teste real, Fase 3): isso costumava ser uma variavel Python
# global -- perdida a cada restart do processo e compartilhada por TODOS os
# usuarios/canais. Agora e persistido via `UserFocusStore` (mesma
# infraestrutura do Project Brain, `data/cris_os.db`), chaveado por
# `session` (`IncomingMessage.session`, ex.: "telegram:6460872429") --
# sobrevive a restart e nunca mistura o foco de duas sessoes diferentes.
_REFERENCIA_CONTEXTUAL = frozenset({
    "esta", "essa", "este", "esse", "isso", "aquela", "aquele", "aquilo",
    "dessa", "desse", "nessa", "nesse",
})


def _get_user_focus_store() -> UserFocusStore:
    """Reaproveita a MESMA `ProjectMemory` do ProjectBrainStore (nao abre
    uma segunda conexao/fonte de verdade). Construido a cada chamada (nao
    cacheado como singleton): e so um wrapper leve sobre a conexao ja
    existente, e nao cachear evita servir um backend antigo caso
    `get_project_brain_store` mude (ex.: testes trocando de banco)."""
    return UserFocusStore(_get_project_brain_store().project_memory)


def get_foco_atual(session: str = "") -> str | None:
    """Project_id da oportunidade em foco NESTA sessao (canal+usuario), ou
    None se nao houver nenhuma ainda (nunca inventa). Persistido -- sobrevive
    a restart do processo. Exposto para outros módulos (ex.:
    tools/product_architect_tools.py, Fase 3) reaproveitarem o MESMO
    mecanismo em vez de criar um estado paralelo."""
    if not session:
        return None
    return _get_user_focus_store().get_focus(session)


def set_foco_atual(session: str, project_id: str) -> None:
    """Persiste a oportunidade em foco desta sessao. Usado pelo Product
    Architect (Fase 3) quando ele mesmo dispara uma investigação nova antes
    de propor um produto."""
    if not session:
        logger.warning(
            "=== [OPPORTUNITY_ANALYST] set_foco_atual chamado sem `session` -- "
            "foco NAO sera persistido (evita misturar contexto entre sessoes) ==="
        )
        return
    _get_user_focus_store().set_focus(session, project_id)


def get_project_brain_store() -> ProjectBrainStore:
    """Alias público de `_get_project_brain_store` para outros módulos
    (Fase 3) reaproveitarem a mesma store/conexão em vez de abrir outra."""
    return _get_project_brain_store()


def get_pending_approval_store() -> PendingApprovalStore:
    """Reaproveita a MESMA `ProjectMemory` do ProjectBrainStore (Fase 6 --
    mesmo princípio de `_get_user_focus_store`, nenhum banco paralelo).
    Construído a cada chamada (não cacheado) para nunca servir um backend
    antigo caso `get_project_brain_store` mude (ex.: testes trocando de
    banco)."""
    return PendingApprovalStore(_get_project_brain_store().project_memory)


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


def detectar_ad_library_id(texto: str) -> str | None:
    """
    Alias público de `_extrair_ad_library_id` (Fase 3). Reconhece
    DETERMINISTICAMENTE (sem LLM) um link da Meta Ads Library ou um ID cru
    em qualquer mensagem -- usado em dois lugares:
      1. `agents/orchestrator.py` -- para rotear a mensagem pro
         opportunity_analyst mesmo quando ela nao tem nenhuma palavra-chave
         (ex.: a pessoa so cola o link).
      2. `Tool.matcher` do proprio `investigar_oportunidade_scalaflow` -- pra
         `SpecialistAgent._encontrar_ferramenta` tambem reconhecer a mesma
         mensagem (evita cair no LLM generico por a Tool nao "achar" a
         mensagem, mesmo com o agente certo ja escolhido).
    """
    return _extrair_ad_library_id(texto or "")


def _buscar_por_ad_library_id(ad_library_id: str) -> dict | str:
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


def _resolver_por_foco_atual(session: str) -> dict | str:
    """Reusa a oferta da ultima investigacao DESTA sessao (persistido -- ver
    `UserFocusStore`, sobrevive a restart)."""
    foco = get_foco_atual(session)
    if not foco:
        return (
            "Nao sei a qual oportunidade voce se refere -- ainda nao investiguei "
            "nenhuma nesta sessao. Indique um link do anuncio (Meta Ads Library) "
            "ou peca por 'minha melhor oferta' / 'meus favoritos' / 'minhas ofertas "
            "salvas' / 'minha oferta escalada' para eu comecar."
        )
    store = _get_project_brain_store()
    brain = store.load(foco)
    if not brain or not brain.origem.source_offer_id:
        return (
            "Nao consegui recuperar a oportunidade que estavamos discutindo. "
            "Indique novamente um link do anuncio ou peca por 'minha melhor oferta'."
        )
    return _buscar_por_ad_library_id(brain.origem.source_offer_id)


def _resolver_oferta(texto: str, session: str = "") -> dict | str:
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
        return _buscar_por_ad_library_id(ad_library_id)

    texto_lower = texto.lower()

    # Referencia contextual ("essa oportunidade", "isso", "dessa oferta", ...)
    # -- NAO reaproveita "melhor oferta" fresca; usa o que estava em foco.
    # Nunca inventa: se nao houver foco, pede pra indicar (ver
    # `_resolver_por_foco_atual`).
    palavras = set(texto_lower.split())
    if palavras & _REFERENCIA_CONTEXTUAL:
        return _resolver_por_foco_atual(session)

    if "favorit" in texto_lower:
        resultado = _buscar_anuncios(limite=1, somente_favoritos=True)
        vazio_msg = "Voce ainda nao tem favoritos no ScalaFlow."
        if isinstance(resultado, str):
            return resultado
        if not resultado:
            return vazio_msg
        return resultado[0]
    if "salv" in texto_lower:
        resultado = _buscar_anuncios(limite=1, somente_salvos=True)
        vazio_msg = "Voce ainda nao tem ofertas salvas no ScalaFlow."
        if isinstance(resultado, str):
            return resultado
        if not resultado:
            return vazio_msg
        return resultado[0]
    if "escalad" in texto_lower:
        resultado = _buscar_anuncios(limite=1, somente_escalados=True)
        vazio_msg = "Nao ha ofertas escaladas (score >= 80) no ScalaFlow no momento."
        if isinstance(resultado, str):
            return resultado
        if not resultado:
            return vazio_msg
        return resultado[0]

    # Sem filtro explicito ("minha melhor oportunidade"): NAO e so o maior
    # score -- ver `_selecionar_melhor_oportunidade`.
    return _selecionar_melhor_oportunidade()


def _pontuar_viabilidade(oferta: dict) -> float:
    """
    Pontuacao DETERMINISTICA (sem LLM, sem inventar nada) de "quao viavel e
    isso pra virar produto" -- so combina campos que JA EXISTEM no registro
    real do ScalaFlow. NAO e uma medida de sucesso de mercado, so de
    COMPLETUDE do que temos pra trabalhar (score sozinho nao mede isso: um
    anuncio score 99 sem headline/copy/keyword e menos util pro Product
    Architect do que um score 90 com dado completo).
    """
    score = oferta.get("score") or 0
    headline = (oferta.get("headline") or "").strip()
    advertiser = (oferta.get("advertiser") or "").strip()
    copy = (oferta.get("copy") or "").strip()
    keyword = (oferta.get("keyword") or "").strip()
    niche = (oferta.get("niche") or "").strip().lower()

    pontos = min(float(score), 100.0) * 0.5  # score ainda pesa, mas nao decide sozinho
    if headline and headline.lower() != advertiser.lower():
        pontos += 15  # headline real, nao so o nome do anunciante repetido
    if len(copy) >= 60:
        pontos += 20
    elif copy:
        pontos += 8
    if keyword:
        pontos += 10  # keyword e o que permite cruzar sinais no Opportunity Analyst
    if niche and niche != "geral":
        pontos += 5
    return pontos


def _selecionar_melhor_oportunidade(pais: str | None = None) -> dict | str:
    """
    Escolhe "a melhor oportunidade" considerando score + completude dos
    dados (headline/copy/keyword/nicho) -- nao so o maior score bruto.
    Avalia um shortlist (top 10 por score, uma unica consulta) e pontua
    cada um deterministicamente; nunca inventa metrica que o registro nao
    tem.
    """
    candidatos = _buscar_anuncios(limite=10, pais=pais)
    if isinstance(candidatos, str):
        return candidatos
    if not candidatos:
        return "Nao encontrei nenhum anuncio no ScalaFlow para investigar."
    return max(candidatos, key=_pontuar_viabilidade)


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


def investigar_oportunidade(entrada: str, session: str = "") -> str:
    """Investiga uma oferta do ScalaFlow e devolve um resumo pronto pro Telegram.

    `session` (Fase 3): identifica canal+usuario (`IncomingMessage.session`).
    Usado pra persistir/recuperar QUAL oportunidade fica em foco PARA ESSA
    sessao especificamente (ver `UserFocusStore`) -- sem isso, "essa
    oportunidade" numa mensagem seguinte nao teria como saber a qual anuncio
    se refere, e restart do processo perderia o contexto (bug real corrigido
    na Fase 3).
    """
    oferta = _resolver_oferta(entrada, session)
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
    brain.origem.source_headline = oferta.get("headline")
    brain.origem.source_copy = oferta.get("copy")
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
    set_foco_atual(session, brain.project_id)

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


def solicitar_mineracao_complementar(entrada: str, session: str = "") -> str:
    """
    Ponte Etapa 23 (`core/scalaflow_mining_client.py`): quando a oportunidade
    em foco ficou em INVESTIGATE_MORE por falta de evidência cruzada, pede
    ao ScalaFlow (server-to-server, endpoint já em produção) para minerar as
    fontes que faltam -- reaproveita o MESMO termo de busca já usado pela
    investigação original (`_extrair_termos_busca`), nunca inventa um novo.

    NUNCA é chamado automaticamente por `investigar_oportunidade` -- exige
    um pedido explícito desta Tool. NUNCA reavalia a decisão sozinho (isso
    fica para uma nova investigação, pedida separadamente) -- esta função
    termina na solicitação de mineração, exatamente como definido na Etapa
    23 ("esta etapa termina na ponte funcional").
    """
    from core.scalaflow_mining_client import FONTES_MINERACAO_VALIDAS, solicitar_mineracao

    oferta = _resolver_por_foco_atual(session)
    if isinstance(oferta, str):
        return oferta

    foco = get_foco_atual(session)
    store = _get_project_brain_store()
    brain = store.load(foco)
    if not brain:
        return "Não consegui recuperar o projeto em foco."

    if brain.decisao.recommended_path != "INVESTIGATE_MORE":
        return (
            f"Esta oportunidade não está em INVESTIGATE_MORE (caminho atual: "
            f"{brain.decisao.recommended_path}) -- mineração complementar não se aplica."
        )

    fontes_faltantes = [f for f in (brain.oportunidade.risks or []) if f in FONTES_MINERACAO_VALIDAS]
    if not fontes_faltantes:
        return "Nenhuma fonte pendente de mineração para esta oportunidade."

    termos = _extrair_termos_busca(oferta)
    if not termos:
        return "Não há termo de busca derivável desta oferta -- mineração não solicitada."
    termo = termos[0]

    linhas = [
        f"Solicitando mineração complementar ao ScalaFlow (termo: '{termo}') "
        f"para: {', '.join(fontes_faltantes)}",
        "",
    ]
    for fonte in fontes_faltantes:
        resultado = solicitar_mineracao(fonte, termo)
        if resultado.ok:
            linhas.append(f"{fonte}: solicitado com sucesso -- {resultado.dados}")
        else:
            linhas.append(f"{fonte}: {resultado.status} -- {resultado.erro}")

    linhas += [
        "",
        "Nenhuma reavaliação automática foi feita -- peça para investigar esta "
        "oportunidade de novo depois para o motor recalcular a decisão com os "
        "dados novos.",
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
            [
                "investigue", "investigar", "investigacao", "analise", "analisar",
                "analisa", "oportunidade", "oportunidades", "sinais", "sinal",
                "caminho", "decisao", "decision",
                # Continuacao de uma investigacao ja em andamento (ex.: "isso
                # aparece no TikTok?"). So chegam aqui mensagens que o
                # orchestrator ja roteou pro opportunity_analyst (ver
                # `_CONTINUACAO_OPORTUNIDADE_KEYWORDS` em agents/orchestrator.py) --
                # essa lista precisa ser um superset da de la, senao o
                # SpecialistAgent nao acha a Tool e cai no LLM (Ollama).
                "tiktok", "meta", "facebook", "instagram", "youtube", "google",
                "trends", "tendencia", "tendencias", "aparece", "evidencia",
                "evidencias", "fonte", "fontes", "esta", "essa", "este", "esse",
                "isso", "aquela", "aquele", "aquilo", "dessa", "desse", "nessa",
                "nesse",
            ],
            investigar_oportunidade,
            # Reconhece um link/ID da Meta Ads Library em QUALQUER mensagem,
            # mesmo sem nenhuma das palavras acima (ex.: a pessoa so cola o
            # link). Sem isso, mesmo com o orchestrator roteando certo pro
            # opportunity_analyst, a Tool nao "achava" a mensagem e caia no
            # LLM generico -- que responde "nao consigo abrir links
            # externos" (bug real encontrado no teste da Fase 3).
            matcher=lambda t: detectar_ad_library_id(t) is not None,
        ),
        Tool(
            "solicitar_mineracao_complementar",
            "Pede ao ScalaFlow para minerar as fontes que ainda faltam "
            "(TikTok/Instagram/YouTube/Google Trends) para a oportunidade em "
            "foco quando ela está em INVESTIGATE_MORE",
            [
                "minere evidencia", "minere evidência", "minerar evidencia",
                "minerar evidência", "mineracao complementar", "mineração complementar",
                "buscar evidencia cruzada", "buscar evidência cruzada",
                "minerar fontes", "minere as fontes", "minere fontes que faltam",
            ],
            solicitar_mineracao_complementar,
        ),
    ]
