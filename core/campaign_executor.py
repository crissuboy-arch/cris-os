"""
Campaign Executor -- transforma um TrafficPlan JA APROVADO (Fase 5 -- Paid
Traffic Architect) numa ESPECIFICACAO de campanha (`CampaignSpec`), SEM
executar/publicar/gastar nada (Fase 6).

Fluxo: Paid Traffic Architect -> TrafficPlan APPROVED -> aprovacao humana
explicita -> CAMPAIGN EXECUTOR -> CampaignSpec -> DRY-RUN/PREVIEW ->
aprovacao humana explicita (da ESPECIFICACAO) -> [conector externo futuro,
DESABILITADO nesta fase] -> Meta/Google/YouTube/TikTok.

Principio de Skill (mesmo da Fase 5): este modulo NAO conhece Telegram, nao
conhece o orchestrator -- recebe um `ProjectBrain` e devolve uma
`CampaignSpec`.

GATE MAIS IMPORTANTE DESTA FASE: nenhuma `CampaignSpec` deve ser
criada/persistida enquanto `brain.traffic_plan` nao estiver
`esta_aprovado() == True` (`status == "APPROVED"` -- READY_FOR_APPROVAL/
NEEDS_INFORMATION NAO contam). `avaliar_prontidao_campanha` e a fonte
CANONICA dessa checagem; `tools/campaign_executor_tools.py` chama essa
funcao ANTES de qualquer chamada de LLM e ANTES de qualquer escrita no
Project Brain -- se houver lacuna, a resposta e deterministica e NADA e
persistido.

REGRA MAIS IMPORTANTE DA FASE 6 -- NAO EXISTE AUTORIZACAO PARA GASTAR
DINHEIRO: nenhuma linha deste arquivo (nem de
`tools/campaign_executor_tools.py`) chama qualquer API de Meta/Google/
TikTok Ads, publica campanha, cria/altera conta de anuncio, ou executa
qualquer mutacao externa -- mesmo depois de `CampaignSpec.esta_aprovado()`.
`execution_mode` fica sempre `EXTERNAL_EXECUTION_DISABLED` nesta fase.
"""

from __future__ import annotations

import json
import logging
import re

from core.evidence_guard import sanitizar_claims_herdadas
from memory.project_brain import CampaignSpec, ProjectBrain, novo_campaign_id

logger = logging.getLogger(__name__)


def avaliar_prontidao_campanha(brain: ProjectBrain) -> list[str]:
    """
    GATE central (correcao de escopo -- nunca espalhar essa checagem por
    varios lugares): uma CampaignSpec so pode ser criada quando `TrafficPlan`
    existe E ja foi APROVADO (`esta_aprovado()`), com pelo menos um canal
    classificado PRIMARY_TEST (garantido pelo proprio Paid Traffic Architect
    antes de `READY_FOR_APPROVAL`, mas revalidado aqui em vez de confiar
    cegamente). Devolve a lista de lacunas (vazia = pronto).
    """
    lacunas: list[str] = []
    tp = brain.traffic_plan
    if not tp:
        lacunas.append(
            "Ainda não existe nenhum plano de tráfego (TrafficPlan) para "
            "este projeto -- crie e aprove um plano de tráfego primeiro.",
        )
        return lacunas
    if not tp.esta_aprovado():
        lacunas.append(
            f"O plano de tráfego ainda não foi aprovado (status atual: "
            f"{tp.status}) -- é preciso aprovar o plano de tráfego antes de "
            "preparar uma campanha.",
        )
        return lacunas
    if not _canal_primario(tp):
        lacunas.append(
            "Nenhum canal foi classificado como PRIMARY_TEST no plano de "
            "tráfego aprovado -- não há canal definido para montar a "
            "especificação de campanha.",
        )
    return lacunas


def _canal_primario(tp) -> dict | None:
    for c in tp.channels:
        if c.get("role") == "PRIMARY_TEST":
            return c
    return None


def _resumir_contexto_campanha(brain: ProjectBrain, canal: dict) -> dict:
    tp = brain.traffic_plan
    return {
        "canal": canal.get("channel"),
        "objetivo_do_plano_de_trafego": tp.objective,
        "objetivo_de_campanha_sugerido": canal.get("campaign_objective"),
        "publico_resumo": tp.audience_summary,
        "segmentacao_sugerida": canal.get("targeting_strategy"),
        "pais": tp.country,
        "idioma": tp.language,
        "destino_sugerido": canal.get("landing_destination"),
        "evento_de_conversao_sugerido": canal.get("conversion_event"),
        "estrutura_sugerida": canal.get("campaign_structure"),
        "ad_sets_ou_grupos_sugeridos": canal.get("ad_sets_or_groups"),
        "posicionamentos_sugeridos": canal.get("placements"),
        "criativos_necessarios_sugeridos": canal.get("creative_requirements"),
        "estrategia_de_keyword_sugerida": canal.get("keyword_strategy"),
        "hipotese_de_teste": canal.get("test_hypothesis"),
        "angulos": tp.angles,
        "hooks": tp.hooks,
        "creative_matrix": tp.creative_matrix,
        "evidencias_usadas_no_canal": canal.get("evidence_used"),
        "evidencias_ja_coletadas": brain.coletar_evidencias_pesquisa(),
        "riscos_ja_identificados": canal.get("risks"),
    }


def _prompt_campanha(contexto: dict, canal_nome: str, orcamento_informado: dict | None) -> list[dict]:
    orcamento_instrucao = (
        f"O orçamento JÁ foi informado pela usuária e é tratado à parte "
        f"(NÃO invente nem sugira outro valor): {json.dumps(orcamento_informado, ensure_ascii=False)}"
        if orcamento_informado
        else "Orçamento ainda NÃO foi informado -- NÃO invente um valor, isso é tratado à parte."
    )
    keyword_instrucao = (
        "Para GOOGLE_SEARCH: pode sugerir clusters de keywords/match-type/"
        "negative keywords, mas NUNCA invente volume de busca, CPC ou "
        "competição sem fonte real -- inclua sempre \"REQUIRES_KEYWORD_DATA\" "
        "em `keyword_requirements`."
        if canal_nome == "GOOGLE_SEARCH"
        else "Este canal não é Google Search -- `keyword_requirements` pode ficar vazio."
    )
    sistema = (
        "Você é o Campaign Executor do CRIS OS. Recebe um canal JÁ ESCOLHIDO "
        "(PRIMARY_TEST) de um plano de tráfego JÁ APROVADO e TRANSFORMA a "
        "estratégia numa ESPECIFICAÇÃO DETALHADA de campanha -- NUNCA "
        "executa, publica ou conecta nada externo, só especifica.\n\n"
        "REGRAS OBRIGATÓRIAS:\n"
        "1. NUNCA invente CTR, CPC, CPM, CPA, ROAS, CVR, vendas, receita, "
        "conversões, demanda, lucro ou qualquer resultado histórico -- nada "
        "disso existe antes de uma campanha real rodar.\n"
        f"2. {keyword_instrucao}\n"
        f"3. {orcamento_instrucao}\n"
        "4. REGRA CRÍTICA -- NUNCA HERDE ALEGAÇÕES DO CONCORRENTE COMO FATO "
        "DO PRODUTO NOVO: qualquer evidência vinda do anúncio original é "
        "EVIDÊNCIA DE MERCADO/CRIATIVO, nunca prova de resultado do produto "
        "novo.\n"
        "5. NÃO gere imagem, vídeo ou testimonial fictício -- "
        "`creative_requirements`/`copy_requirements` só ESPECIFICAM o que "
        "precisa ser produzido, nunca produzem o ativo em si.\n"
        "6. Responda SOMENTE com um JSON válido (sem markdown, sem texto "
        "fora do JSON), EXATAMENTE neste formato:\n"
        "{\n"
        '  "campaign_structure": "...",\n'
        '  "ad_sets": ["..."], "audience_hypotheses": ["..."],\n'
        '  "placements": ["..."], "creative_requirements": ["..."],\n'
        '  "copy_requirements": ["..."], "keyword_requirements": ["..."],\n'
        '  "tracking_requirements": ["..."], "schedule": "...",\n'
        '  "experiments": ["..."], "risks": ["..."], "missing_data": ["..."]\n'
        "}"
    )
    usuario = "Canal escolhido e contexto do plano de tráfego aprovado:\n" + json.dumps(contexto, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": sistema},
        {"role": "user", "content": usuario},
    ]


def _extrair_json(texto: str) -> dict | None:
    texto = texto.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip(), flags=re.MULTILINE)
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
        return None


def _str_ou_none(v) -> str | None:
    if v is None:
        return None
    texto = str(v).strip()
    return texto or None


def _texto_limpo(v) -> str | None:
    return sanitizar_claims_herdadas(_str_ou_none(v))


def _lista(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [str(v).strip()]


def _lista_limpa(v) -> list[str]:
    return [t for t in (sanitizar_claims_herdadas(x) for x in _lista(v)) if t]


def _validar_keyword_requirements(canal_nome: str, lista: list[str]) -> list[str]:
    """GOOGLE_SEARCH sem fonte real de keyword volume/CPC/competição SEMPRE
    inclui `REQUIRES_KEYWORD_DATA` -- nunca confia no LLM sozinho pra
    lembrar disso."""
    if canal_nome == "GOOGLE_SEARCH" and "REQUIRES_KEYWORD_DATA" not in lista:
        lista = list(lista) + ["REQUIRES_KEYWORD_DATA"]
    return lista


_BUDGET_VAZIO = {"currency": None, "daily": None, "total": None, "source": None, "status": "REQUIRES_BUDGET"}
_ACOES_QUE_EXIGEM_APROVACAO = [
    "Conexão de conta de anúncio real",
    "Publicação da campanha",
    "Gasto de orçamento real",
]


def _fallback_deterministico_campanha(
    brain: ProjectBrain, canal: dict, orcamento_informado: dict | None, versao: int,
) -> CampaignSpec:
    """Sem LLM disponível: estrutura mínima e HONESTA -- nunca finge uma
    especificação de campanha que não foi avaliada."""
    tp = brain.traffic_plan
    return CampaignSpec(
        campaign_id=novo_campaign_id(),
        project_id=brain.project_id,
        version=versao,
        status="NEEDS_INFORMATION",
        source_traffic_plan_version=tp.version,
        channel=canal.get("channel"),
        country=tp.country,
        language=tp.language,
        budget=orcamento_informado or dict(_BUDGET_VAZIO),
        evidence_summary=brain.coletar_evidencias_pesquisa(),
        missing_data=[
            "OpenRouter indisponível nesta chamada -- nenhuma estrutura de "
            "campanha foi avaliada via IA. Peça uma nova tentativa quando o "
            "OpenRouter estiver disponível.",
        ],
        execution_mode="EXTERNAL_EXECUTION_DISABLED",
        external_execution_status="NOT_EXECUTED",
        generated_by="fallback_deterministico",
    )


def criar_campaign_spec(
    brain: ProjectBrain,
    llm=None,
    orcamento_informado: dict | None = None,
    versao_anterior: CampaignSpec | None = None,
) -> CampaignSpec:
    """
    Gera (ou revisa, se `versao_anterior` for passado) uma CampaignSpec para
    o canal PRIMARY_TEST do TrafficPlan aprovado em `brain.traffic_plan`.
    NUNCA lança exceção -- qualquer falha do LLM cai no fallback
    determinístico. NUNCA fabrica uma especificação quando o TrafficPlan
    ainda não está aprovado (`avaliar_prontidao_campanha`).
    """
    versao = (versao_anterior.version + 1) if versao_anterior else 1

    lacunas = avaliar_prontidao_campanha(brain)
    if lacunas:
        # Defesa extra -- o GATE real já é checado ANTES desta função ser
        # chamada, em `tools/campaign_executor_tools.py` (ver docstring do
        # módulo). Se mesmo assim chegar aqui sem pré-requisito, NUNCA
        # fabrica uma campanha.
        return CampaignSpec(
            campaign_id=novo_campaign_id(),
            project_id=brain.project_id,
            version=versao,
            status="NEEDS_INFORMATION",
            missing_data=lacunas,
            budget=orcamento_informado or dict(_BUDGET_VAZIO),
            generated_by="sem_informacao_suficiente",
        )

    tp = brain.traffic_plan
    canal = _canal_primario(tp)

    if llm is None:
        return _fallback_deterministico_campanha(brain, canal, orcamento_informado, versao)

    contexto = _resumir_contexto_campanha(brain, canal)
    try:
        resposta = llm.chat(_prompt_campanha(contexto, canal.get("channel"), orcamento_informado))
    except Exception as exc:
        logger.warning("=== [CAMPAIGN_EXECUTOR] LLM falhou, usando fallback determinístico: %s ===", exc)
        return _fallback_deterministico_campanha(brain, canal, orcamento_informado, versao)

    dados = _extrair_json(resposta.content or "")
    if not dados:
        logger.warning("=== [CAMPAIGN_EXECUTOR] Resposta do LLM não era JSON válido, usando fallback ===")
        return _fallback_deterministico_campanha(brain, canal, orcamento_informado, versao)

    keyword_requirements = _validar_keyword_requirements(
        canal.get("channel"), _lista_limpa(dados.get("keyword_requirements")),
    )
    budget = orcamento_informado or dict(_BUDGET_VAZIO)

    return CampaignSpec(
        campaign_id=novo_campaign_id(),
        project_id=brain.project_id,
        version=versao,
        status="READY_FOR_APPROVAL",
        source_traffic_plan_version=tp.version,
        channel=canal.get("channel"),
        objective=_texto_limpo(tp.objective) or _texto_limpo(canal.get("campaign_objective")),
        country=tp.country,
        language=tp.language,
        destination=_str_ou_none(canal.get("landing_destination")),
        conversion_event=_str_ou_none(canal.get("conversion_event")),
        campaign_structure=_texto_limpo(dados.get("campaign_structure")) or _texto_limpo(canal.get("campaign_structure")),
        ad_sets=_lista_limpa(dados.get("ad_sets")) or _lista_limpa(canal.get("ad_sets_or_groups")),
        audience_hypotheses=_lista_limpa(dados.get("audience_hypotheses")),
        placements=_lista(dados.get("placements")) or _lista(canal.get("placements")),
        creative_requirements=_lista_limpa(dados.get("creative_requirements")) or _lista_limpa(canal.get("creative_requirements")),
        copy_requirements=_lista_limpa(dados.get("copy_requirements")),
        keyword_requirements=keyword_requirements,
        tracking_requirements=_lista_limpa(dados.get("tracking_requirements")),
        budget=budget,
        schedule=_str_ou_none(dados.get("schedule")),
        experiments=_lista_limpa(dados.get("experiments")),
        risks=_lista_limpa(dados.get("risks")) or _lista_limpa(canal.get("risks")),
        evidence_summary=brain.coletar_evidencias_pesquisa(),
        missing_data=_lista_limpa(dados.get("missing_data")),
        approval_required=list(_ACOES_QUE_EXIGEM_APROVACAO),
        execution_mode="EXTERNAL_EXECUTION_DISABLED",
        external_execution_status="NOT_EXECUTED",
        generated_by=getattr(llm, "_provider_name", "llm"),
    )
