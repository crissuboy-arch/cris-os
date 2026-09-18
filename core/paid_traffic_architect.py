"""
Paid Traffic Architect — transforma um projeto/produto/oferta ja existente
no Project Brain num PLANO DE TRAFEGO PAGO estruturado, baseado em
evidencias disponiveis, SEM executar nenhuma campanha (Fase 5).

Fluxo: Opportunity Analyst -> Decision Engine -> Product Architect ->
aprovacao humana -> (Business Builder) -> PAID TRAFFIC ARCHITECT -> Project
Brain -> resposta.

Principio de Skill (pedido explicito da Fase 5): este modulo NAO conhece
Telegram, nao conhece o orchestrator -- recebe um `ProjectBrain` e devolve
um `TrafficPlan`. A mesma funcao pode ser chamada de qualquer canal futuro
(API, automacao, interface web) sem mudar uma linha aqui.

Regras que o prompt e o parsing IMPOEM (nao so pedem por favor):
  - NUNCA inventa CTR/CPC/CPM/CPA/ROAS/CVR/vendas/receita/conversoes/
    demanda/lucro/volume de pesquisa/resultado historico -- nada disso e
    verificavel antes de uma campanha real rodar. Ver `core/evidence_guard.py`
    (categoria 5, especifica de trafego pago).
  - Todo canal (`channel`) e todo `role` de canal vem de vocabulario fechado
    (`TRAFFIC_CHANNELS`/`TRAFFIC_CHANNEL_ROLES`) -- validado, nunca aceito
    as cegas. "Nao usar preferencia fixa do desenvolvedor": a recomendacao
    de canal vem do LLM avaliando o projeto, nunca hardcoded aqui.
  - Orcamento SEM valor informado pelo usuario vira CENARIOS DE TESTE
    (LOW/STANDARD/EXPANDED) marcados `PLANNING_ASSUMPTION` -- nunca uma
    afirmacao de "orcamento ideal". Orcamento informado pelo usuario e
    preservado sem alteracao.
  - Evidencia do concorrente (headline/copy do anuncio original, sinais do
    ScalaFlow) e EVIDENCIA DE MERCADO/CRIATIVO -- nunca prova de resultado
    do produto novo. Ver `core/evidence_guard.py`.
  - So gera plano quando ha informacao minima suficiente (`avaliar_prontidao`);
    caso contrario devolve `NEEDS_INFORMATION` com lacunas objetivas, nunca
    fabrica um plano como se o projeto estivesse pronto.
  - `READY_FOR_APPROVAL` != `APPROVED` -- aprovacao e sempre um ato humano
    explicito (ver `tools/paid_traffic_tools.py`).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from core.evidence_guard import sanitizar_claims_herdadas
from memory.project_brain import (
    ProjectBrain,
    TRAFFIC_CHANNEL_ROLES,
    TRAFFIC_CHANNELS,
    TrafficPlan,
)

logger = logging.getLogger(__name__)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncar(texto: str | None, limite: int) -> str | None:
    if not texto:
        return None
    texto = texto.strip()
    return texto if len(texto) <= limite else texto[: limite - 3].rstrip() + "..."


def avaliar_prontidao(brain: ProjectBrain) -> list[str]:
    """
    Verifica se ha informacao MINIMA suficiente pra montar um plano de
    trafego real -- projeto em foco, decisao atual, produto/oferta,
    publico, pais/mercado, posicionamento, evidencias, status de aprovacao
    do blueprint, estagio atual do projeto. Devolve a lista de LACUNAS
    (vazia = pronto). NUNCA finge que o projeto esta pronto quando falta
    algo essencial.
    """
    lacunas: list[str] = []

    if not brain.blueprint:
        lacunas.append(
            "Nenhum Product Blueprint encontrado neste projeto -- e preciso "
            "decidir e aprovar um formato de produto antes de planejar trafego.",
        )
        return lacunas  # sem blueprint, o resto nao tem base pra avaliar

    if not brain.blueprint.esta_aprovado():
        lacunas.append(
            f"Product Blueprint ainda nao foi aprovado (status atual: "
            f"{brain.blueprint.decision_status}) -- trafego pago pressupoe "
            "um formato de produto ja decidido.",
        )

    if not brain.blueprint.recommended_product_type:
        lacunas.append("Formato de produto/oferta ainda nao definido.")

    publico = brain.blueprint.target_audience or (
        brain.business_plan.target_audience if brain.business_plan else None
    )
    if not publico:
        lacunas.append(
            "Publico-alvo ainda nao definido (nem no Product Blueprint, nem no Business Plan).",
        )

    pais = brain.blueprint.country or brain.mercado.target_country or brain.origem.source_country
    if not pais:
        lacunas.append("Pais/mercado-alvo ainda nao definido.")

    posicionamento = (
        (brain.business_plan.positioning if brain.business_plan else None)
        or brain.blueprint.differentiation
    )
    if not posicionamento:
        lacunas.append(
            "Posicionamento/diferenciacao ainda nao definido (o Business "
            "Builder ainda nao rodou, ou nao trouxe essa informacao).",
        )

    # Fonte CANONICA (correcao de bug real, Fase 5): antes so olhava
    # `blueprint.evidence`/`oportunidade.evidence` -- exclusivamente sinais
    # cross-plataforma do Opportunity Analyst. Um projeto real pode ter
    # headline/copy/score/nicho reais sem NENHUM sinal cross-plataforma
    # confirmado, e ainda assim ter informacao real o bastante pra planejar
    # trafego. Usa a MESMA lista que `core/artifact_manifest.py` usa pra
    # "01-Pesquisa" -- os dois nunca mais podem divergir pro mesmo projeto.
    evidencias = brain.coletar_evidencias_pesquisa()
    if not evidencias:
        lacunas.append("Nenhuma evidencia de mercado registrada para embasar o plano.")

    return lacunas


def _resumir_contexto(brain: ProjectBrain) -> dict:
    """Resumo compacto (cost-first) do que ja se sabe -- nunca manda o
    ProjectBrain inteiro nem dados brutos."""
    bp = brain.blueprint
    bplan = brain.business_plan
    return {
        "formato_aprovado": bp.recommended_product_type,
        "conceito": bp.product_concept,
        "publico_alvo": bp.target_audience or (bplan.target_audience if bplan else None),
        "problema": bp.problem,
        "posicionamento": (bplan.positioning if bplan else None) or bp.differentiation,
        "nicho": bp.niche,
        "pais": bp.country or brain.mercado.target_country,
        "idioma": bp.language or brain.mercado.target_language,
        "monetizacao": bp.monetization_options,
        "oferta_principal": bplan.main_offer if bplan else None,
        "canais_organicos_sugeridos": bplan.acquisition_channels if bplan else [],
        # Nomeado "DO_CONCORRENTE" (mesmo principio do Evidence Guard desde a
        # Fase 4) -- evidencia de mercado/criativo, nunca prova de resultado
        # do produto novo.
        "headline_do_anuncio_DO_CONCORRENTE": _truncar(brain.origem.source_headline, 200),
        "copy_do_anuncio_DO_CONCORRENTE": _truncar(brain.origem.source_copy, 400),
        "plataforma_de_origem_do_anuncio": brain.origem.source_platform,
        "evidencias_ja_coletadas": brain.coletar_evidencias_pesquisa(),
        "riscos_ja_identificados": list(bp.risks),
    }


def _prompt(contexto: dict, orcamento_informado: dict | None) -> list[dict]:
    canais = ", ".join(sorted(TRAFFIC_CHANNELS))
    papeis = ", ".join(sorted(TRAFFIC_CHANNEL_ROLES))
    orcamento_instrucao = (
        f"O usuario JA informou um orcamento real -- preserve-o SEM alterar "
        f"(nao gere cenarios LOW/STANDARD/EXPANDED, use este valor real): "
        f"{json.dumps(orcamento_informado, ensure_ascii=False)}"
        if orcamento_informado
        else (
            "O usuario NAO informou orcamento. Gere `budget_scenarios` com "
            "exatamente 3 itens rotulados LOW, STANDARD e EXPANDED -- cada um "
            "com `type: \"PLANNING_ASSUMPTION\"` explicito. NUNCA afirme que "
            "um valor garante resultado."
        )
    )
    sistema = (
        "Voce e o Paid Traffic Architect do CRIS OS. Recebe um produto/oferta "
        "JA APROVADO (dados REAIS, resumidos abaixo) e monta um PLANO DE "
        "TRAFEGO PAGO estruturado -- NUNCA executa nada, so planeja.\n\n"
        "REGRAS OBRIGATORIAS:\n"
        "1. NUNCA invente CTR, CPC, CPM, CPA, ROAS, CVR, vendas, receita, "
        "conversoes, demanda, lucro, volume de pesquisa ou qualquer resultado "
        "historico -- nada disso existe antes de uma campanha real rodar. "
        "Quando nao houver dado, use `\"NO_DATA\"` ou `\"UNKNOWN\"`.\n"
        "2. Todo `channel` DEVE vir exatamente desta lista (maiusculo, com "
        f"underscore): {canais}. Todo `role` de canal DEVE vir exatamente "
        f"desta lista: {papeis}. NUNCA recomende um canal so por preferencia "
        "-- justifique com o contexto/evidencia dado.\n"
        "3. NUNCA afirme que um canal 'vai funcionar' -- classifique cada "
        "canal como PRIMARY_TEST (o UNICO canal prioritario pra comecar o "
        "teste -- ESCOLHA NO MAXIMO UM, baseado na evidencia mais forte), "
        "SECONDARY_TEST (candidato solido, mas nao o primeiro a testar), "
        "LATER (candidato, mas sem evidencia suficiente ainda) ou "
        "NOT_RECOMMENDED_NOW. Se a evidencia nao for forte o bastante pra "
        "escolher UM canal principal com confianca, nao force -- deixe "
        "todos como SECONDARY_TEST/LATER (o sistema trata isso como "
        "informacao insuficiente automaticamente).\n"
        f"4. {orcamento_instrucao}\n"
        "5. REGRA CRITICA -- NUNCA HERDE ALEGACOES DO CONCORRENTE COMO FATO "
        "DO PRODUTO NOVO: `headline_do_anuncio_DO_CONCORRENTE`/"
        "`copy_do_anuncio_DO_CONCORRENTE` sao de OUTRA empresa (produto que "
        "JA EXISTE) -- so evidencia de mercado/criativo/angulo. NUNCA copie "
        "numero de clientes, 'produto comprovado', 'oferta vencedora' ou "
        "qualquer prova de resultado do anuncio pro produto NOVO. Da mesma "
        "forma, NUNCA afirme que o produto NOVO ja tem uma funcionalidade/"
        "acesso/parceria (ex.: 'acesso a fornecedores', 'rede de "
        "fornecedores') que ainda nao foi aprovada/construida -- isso e "
        "HIPOTESE, nao fato.\n"
        "6. Para Google Search: pode sugerir clusters de keywords/intencao/"
        "match strategy/negative keyword concepts, mas NUNCA invente search "
        "volume, CPC ou competition sem fonte real -- marque "
        "`\"REQUIRES_KEYWORD_DATA\"`.\n"
        "7. NAO gere imagem, video ou testimonial ficticio -- creative_matrix "
        "so ESPECIFICA o que precisa ser produzido (`asset_required: true`), "
        "nunca produz o asset em si. Testimonial SOMENTE se houver depoimento "
        "real nas evidencias (senao, nao inclua testimonial) -- na duvida, "
        "trate prova social como NAO disponivel.\n"
        "8. Responda SOMENTE com um JSON valido (sem markdown, sem texto fora "
        "do JSON), EXATAMENTE neste formato:\n"
        "{\n"
        '  "objective": "...", "audience_summary": "...",\n'
        '  "channels": [\n'
        "    {\n"
        f'      "channel": "...", "role": "...", "priority": "alta|media|baixa",\n'
        '      "rationale": "...", "campaign_objective": "...",\n'
        '      "campaign_structure": "...", "ad_sets_or_groups": ["..."],\n'
        '      "targeting_strategy": "...", "keyword_strategy": "..." ou null,\n'
        '      "placements": ["..."] ou [], "creative_requirements": ["..."],\n'
        '      "landing_destination": "...", "conversion_event": "...",\n'
        '      "test_hypothesis": "...", "evidence_used": ["..."],\n'
        '      "assumptions": ["..."], "risks": ["..."]\n'
        "    }\n"
        "  ],\n"
        '  "angles": ["..."], "hooks": ["..."],\n'
        '  "creative_matrix": [\n'
        '    {"angle": "...", "hook": "...", "format": "...", "channel": "...",\n'
        '     "audience": "...", "cta": "...", "evidence_or_hypothesis": "...",\n'
        '     "asset_required": true}\n'
        "  ],\n"
        '  "testing_plan": ["..."], "measurement_plan": ["..."],\n'
        '  "stop_conditions": ["..."], "scale_conditions": ["..."],\n'
        '  "budget_scenarios": [{"nome": "LOW|STANDARD|EXPANDED", "valor": "...", "type": "PLANNING_ASSUMPTION"}],\n'
        '  "assumptions": ["..."], "unknowns": ["..."], "risks": ["..."],\n'
        '  "approval_required_actions": ["..."]\n'
        "}"
    )
    usuario = "Produto/oferta aprovado (dados reais):\n" + json.dumps(contexto, ensure_ascii=False, indent=2)
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


def _validar_canal(bruto: dict) -> dict | None:
    canal = str(bruto.get("channel") or "").strip().upper()
    role = str(bruto.get("role") or "").strip().upper()
    if canal not in TRAFFIC_CHANNELS:
        logger.warning("=== [PAID_TRAFFIC] Canal fora do vocabulario fechado descartado: %r ===", canal)
        return None
    if role not in TRAFFIC_CHANNEL_ROLES:
        # LATER (nao NOT_RECOMMENDED_NOW) -- um role invalido/vazio nao e o
        # mesmo que "nao recomendado", so significa que a classificacao nao
        # veio certa; fica pra decidir depois, nunca promovido a PRIMARY_TEST
        # as cegas.
        role = "LATER"
    return {
        "channel": canal,
        "role": role,
        "priority": _str_ou_none(bruto.get("priority")),
        "rationale": _texto_limpo(bruto.get("rationale")),
        "campaign_objective": _texto_limpo(bruto.get("campaign_objective")),
        "campaign_structure": _texto_limpo(bruto.get("campaign_structure")),
        "ad_sets_or_groups": _lista_limpa(bruto.get("ad_sets_or_groups")),
        "targeting_strategy": _texto_limpo(bruto.get("targeting_strategy")),
        "keyword_strategy": _texto_limpo(bruto.get("keyword_strategy")),
        "placements": _lista(bruto.get("placements")),
        "creative_requirements": _lista_limpa(bruto.get("creative_requirements")),
        "landing_destination": _str_ou_none(bruto.get("landing_destination")),
        "conversion_event": _str_ou_none(bruto.get("conversion_event")),
        "test_hypothesis": _texto_limpo(bruto.get("test_hypothesis")),
        "evidence_used": _lista_limpa(bruto.get("evidence_used")),
        "assumptions": _lista_limpa(bruto.get("assumptions")),
        "risks": _lista_limpa(bruto.get("risks")),
    }


def _impor_um_unico_primary_test(canais: list[dict]) -> list[dict]:
    """
    CORRECAO pos-auditoria (priorizacao operacional): nunca confia no LLM
    pra respeitar sozinho "so um PRIMARY_TEST" -- se ele mandar mais de um,
    o PRIMEIRO fica, os demais sao rebaixados pra SECONDARY_TEST
    (deterministico, sempre a mesma escolha pro mesmo input).
    """
    ja_tem_primario = False
    ajustados = []
    for c in canais:
        if c["role"] == "PRIMARY_TEST":
            if ja_tem_primario:
                c = dict(c, role="SECONDARY_TEST")
            else:
                ja_tem_primario = True
        ajustados.append(c)
    return ajustados


def _validar_creative_matrix_item(bruto: dict) -> dict | None:
    if not isinstance(bruto, dict) or not bruto.get("angle"):
        return None
    return {
        "angle": _texto_limpo(bruto.get("angle")),
        "hook": _texto_limpo(bruto.get("hook")),
        "format": _str_ou_none(bruto.get("format")),
        "channel": _str_ou_none(bruto.get("channel")),
        "audience": _texto_limpo(bruto.get("audience")),
        "cta": _texto_limpo(bruto.get("cta")),
        "evidence_or_hypothesis": _texto_limpo(bruto.get("evidence_or_hypothesis")),
        # NUNCA gera asset nesta fase -- so especifica que precisa ser
        # produzido (sempre True; nunca "ja produzido").
        "asset_required": True,
    }


def _validar_budget_scenario(bruto: dict) -> dict | None:
    nome = str(bruto.get("nome") or "").strip().upper()
    if nome not in {"LOW", "STANDARD", "EXPANDED"}:
        return None
    return {
        "nome": nome,
        "valor": _str_ou_none(bruto.get("valor")),
        # SEMPRE PLANNING_ASSUMPTION -- nunca confia no LLM pra marcar isso
        # certo sozinho quando nao ha orcamento real informado.
        "type": "PLANNING_ASSUMPTION",
    }


_SEM_MERCADO = "REQUIRES_MARKET_DATA"


def _resolver_mercado(brain: ProjectBrain) -> str:
    """
    Correcao pos-auditoria (bug real): o plano renderizava "Mercado: ?"
    porque so olhava `blueprint.market` (raramente preenchido -- o
    Opportunity Analyst normalmente so seta `mercado.niche`/
    `mercado.target_country`, nao `mercado.market`). Agora tenta TODAS as
    fontes canonicas ja existentes antes de admitir que falta dado -- nunca
    inventa um mercado, so declara `REQUIRES_MARKET_DATA` quando realmente
    nao ha nenhuma.
    """
    bp = brain.blueprint
    candidatos = [
        bp.market if bp else None,
        brain.mercado.market,
        bp.niche if bp else None,
        brain.mercado.niche,
    ]
    for c in candidatos:
        if c:
            return c
    return _SEM_MERCADO


def _resolver_pais(brain: ProjectBrain) -> str:
    bp = brain.blueprint
    candidatos = [
        bp.country if bp else None,
        brain.mercado.target_country,
        brain.origem.source_country,
    ]
    for c in candidatos:
        if c:
            return c
    return _SEM_MERCADO


def _fallback_deterministico(brain: ProjectBrain, orcamento_informado: dict | None, versao: int) -> TrafficPlan:
    """Sem LLM disponivel: estrutura minima e HONESTA usando so os campos ja
    existentes -- nunca finge uma analise de canais que nao foi feita."""
    bp = brain.blueprint
    bplan = brain.business_plan
    return TrafficPlan(
        project_id=brain.project_id,
        version=versao,
        # NUNCA "READY_FOR_APPROVAL" aqui -- sem LLM, nenhum canal/angulo/
        # criativo foi avaliado; apresentar um plano vazio como "pronto pra
        # aprovar" seria fabricar prontidao que nao existe.
        status="NEEDS_INFORMATION",
        objective=None,
        market=_resolver_mercado(brain),
        country=_resolver_pais(brain),
        language=bp.language,
        audience_summary=bp.target_audience or (bplan.target_audience if bplan else None),
        channels=[],
        evidence_summary=brain.coletar_evidencias_pesquisa(),
        risks=list(bp.risks),
        budget_informado_pelo_usuario=orcamento_informado,
        budget_status="PROVIDED" if orcamento_informado else "REQUIRES_USER_INPUT",
        missing_information=[
            "OpenRouter indisponivel nesta chamada -- nenhum canal/angulo/"
            "criativo foi avaliado via IA. Peca uma nova tentativa quando o "
            "OpenRouter estiver disponivel.",
        ],
        generated_by="fallback_deterministico",
    )


def criar_plano_trafego(
    brain: ProjectBrain,
    llm=None,
    orcamento_informado: dict | None = None,
    versao_anterior: TrafficPlan | None = None,
) -> TrafficPlan:
    """
    Gera (ou expande, se `versao_anterior` for passado) um TrafficPlan para
    o produto/oferta aprovado em `brain.blueprint`. NUNCA lanca excecao --
    qualquer falha do LLM cai no fallback deterministico. NUNCA fabrica um
    plano quando falta informacao essencial (`avaliar_prontidao`).
    """
    versao = (versao_anterior.version + 1) if versao_anterior else 1

    lacunas = avaliar_prontidao(brain)
    if lacunas:
        return TrafficPlan(
            project_id=brain.project_id,
            version=versao,
            status="NEEDS_INFORMATION",
            market=_resolver_mercado(brain),
            country=_resolver_pais(brain),
            missing_information=lacunas,
            budget_informado_pelo_usuario=orcamento_informado,
            budget_status="PROVIDED" if orcamento_informado else "REQUIRES_USER_INPUT",
            generated_by="sem_informacao_suficiente",
        )

    if llm is None:
        return _fallback_deterministico(brain, orcamento_informado, versao)

    contexto = _resumir_contexto(brain)
    try:
        resposta = llm.chat(_prompt(contexto, orcamento_informado))
    except Exception as exc:
        logger.warning("=== [PAID_TRAFFIC] LLM falhou, usando fallback deterministico: %s ===", exc)
        return _fallback_deterministico(brain, orcamento_informado, versao)

    dados = _extrair_json(resposta.content or "")
    if not dados:
        logger.warning("=== [PAID_TRAFFIC] Resposta do LLM nao era JSON valido, usando fallback ===")
        return _fallback_deterministico(brain, orcamento_informado, versao)

    canais_brutos = dados.get("channels") or []
    canais = [c for c in (_validar_canal(c) for c in canais_brutos) if c]
    # Priorizacao operacional (correcao pos-auditoria): EXATAMENTE UM
    # PRIMARY_TEST por versao -- nunca confia no LLM sozinho pra respeitar
    # isso (ver `_impor_um_unico_primary_test`).
    canais = _impor_um_unico_primary_test(canais)

    creative_matrix = [c for c in (_validar_creative_matrix_item(c) for c in (dados.get("creative_matrix") or [])) if c]

    if orcamento_informado:
        cenarios = []
    else:
        cenarios = [c for c in (_validar_budget_scenario(c) for c in (dados.get("budget_scenarios") or [])) if c]

    missing: list[str] = []
    status = "READY_FOR_APPROVAL"
    # Se ha canais avaliados mas NENHUM foi classificado PRIMARY_TEST, a
    # evidencia nao foi suficiente pra escolher um canal principal -- pedido
    # explicito da auditoria: "nao inventar certeza", o plano inteiro volta
    # pra NEEDS_INFORMATION (preserva a analise ja feita, so nao a apresenta
    # como pronta pra aprovar).
    if canais and not any(c["role"] == "PRIMARY_TEST" for c in canais):
        status = "NEEDS_INFORMATION"
        missing.append(
            "Evidência insuficiente para escolher um único canal PRIMARY_TEST "
            "com confiança -- os canais avaliados ficaram como candidatos "
            "(SECONDARY_TEST/LATER), nenhum priorizado.",
        )

    bp = brain.blueprint
    return TrafficPlan(
        project_id=brain.project_id,
        version=versao,
        status=status,
        objective=_texto_limpo(dados.get("objective")),
        market=_resolver_mercado(brain),
        country=_resolver_pais(brain),
        language=bp.language,
        audience_summary=_texto_limpo(dados.get("audience_summary")) or bp.target_audience,
        channels=canais,
        angles=_lista_limpa(dados.get("angles")),
        hooks=_lista_limpa(dados.get("hooks")),
        creative_matrix=creative_matrix,
        testing_plan=_lista_limpa(dados.get("testing_plan")),
        measurement_plan=_lista(dados.get("measurement_plan")),
        stop_conditions=_lista_limpa(dados.get("stop_conditions")),
        scale_conditions=_lista_limpa(dados.get("scale_conditions")),
        budget_scenarios=cenarios,
        budget_informado_pelo_usuario=orcamento_informado,
        budget_status="PROVIDED" if orcamento_informado else "REQUIRES_USER_INPUT",
        # Sempre NOT_AVAILABLE nesta fase -- o Project Brain nao tem
        # (ainda) nenhum campo de prova social REAL (depoimento/avaliacao/
        # numero de clientes verificado). Nunca inventado.
        social_proof_status="NOT_AVAILABLE",
        evidence_summary=brain.coletar_evidencias_pesquisa(),
        assumptions=_lista_limpa(dados.get("assumptions")),
        unknowns=_lista_limpa(dados.get("unknowns")),
        risks=_lista_limpa(dados.get("risks")) or list(bp.risks),
        missing_information=missing,
        approval_required_actions=_lista_limpa(dados.get("approval_required_actions")) or [
            "Publicação/criação de campanha real",
            "Conexão de conta de anúncio (Meta/Google/TikTok)",
            "Gasto de orçamento real",
        ],
        generated_by=getattr(llm, "_provider_name", "llm"),
    )
