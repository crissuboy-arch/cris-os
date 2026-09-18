"""
Product Architect — decide QUAL FORMATO DE PRODUTO faz sentido para uma
oportunidade ja investigada (Fase 3).

Diferente do Decision Engine (Fase 2, 100% deterministico): aqui a pergunta
("mini-app, ebook, template, afiliado, ..." -- entre 20+ formatos, pesando
publico/problema/evidencias/complexidade/velocidade de MVP) exige
julgamento que uma tabela de regras simples nao cobre com honestidade. Por
isso, quando disponivel, usa o OpenRouter (tier INTELIGENTE, a mesma
arquitetura da Fase 2.5) -- e tem um FALLBACK deterministico quando o
OpenRouter nao estiver disponivel, para nunca travar o fluxo.

CORRECAO pos-teste real (Fase 3): "evidencia insuficiente para DECIDIR/
APROVAR" NAO e o mesmo que "evidencia insuficiente para GERAR HIPOTESES".
Por isso o contrato do LLM separa duas coisas:
  - `candidates`: 3 a 5 formatos plausiveis, cada um com sua propria
    hipotese de publico/problema/motivo/dificuldade/monetizacao/evidencias/
    confianca. Populado sempre que houver QUALQUER evidencia real (headline,
    copy, nicho ou score) -- mesmo que nenhum deles seja confiavel o
    bastante pra recomendar.
  - `recommendation`: so vira `recommended_product_type` (e
    `decision_status = PENDING_APPROVAL`) quando o proprio LLM sinaliza
    `ready_for_approval = true` -- ou seja, quando a evidencia realmente
    justifica uma recomendacao, nao so hipoteses.
`candidates` so fica vazio quando REALMENTE nao ha nada pra raciocinar em
cima (nem headline, nem copy, nem nicho, nem score) -- so nesse caso o
blueprint fica em NEEDS_RESEARCH sem nenhum candidato.

Regras que o prompt e o parsing IMPOEM (nao so pedem por favor):
  - NUNCA inventa vendas, faturamento, demanda, viralidade, concorrentes,
    metricas. Evidencia ausente vira `missing_evidence`, nao um numero.
  - Todo `product_type` (em candidates e na recommendation) SEMPRE vem do
    vocabulario fechado `PRODUCT_TYPES` (a resposta do LLM e validada; um
    tipo fora da lista e descartado, nunca aceito as cegas).
  - O Product Architect NUNCA aprova a propria proposta -- aprovacao e
    sempre um ato humano explicito (ver tools/product_architect_tools.py).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from core.evidence_guard import sanitizar_claims_herdadas
from memory.project_brain import ProductBlueprint, ProjectBrain

logger = logging.getLogger(__name__)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()

# Vocabulario fechado de formatos (pedido explicito da Fase 3 -- nao
# assumir que todo produto e ebook). "afiliado" e "comercio_revenda" cobrem
# os caminhos AFFILIATE/COMMERCE_RESALE do Decision Engine.
PRODUCT_TYPES = frozenset({
    "mini_app", "ferramenta_web", "calculadora", "gerador", "quiz",
    "dashboard", "micro_saas", "app", "agente_ia", "skill",
    "extensao_navegador", "template", "biblioteca_templates", "kit_digital",
    "ebook", "guia", "curso", "comunidade", "assinatura", "servico",
    "produto_hibrido", "produto_fisico", "afiliado", "comercio_revenda",
})

_SEM_EVIDENCIA_SUFICIENTE = "NEEDS_RESEARCH"
_CAMPOS_CANDIDATO = (
    "product_type", "audience_hypothesis", "problem", "why_it_fits",
    "production_difficulty", "estimated_speed_to_mvp", "monetization",
    "supporting_evidence", "missing_evidence", "confidence",
)


def _truncar(texto: str | None, limite: int) -> str | None:
    if not texto:
        return None
    texto = texto.strip()
    return texto if len(texto) <= limite else texto[: limite - 3].rstrip() + "..."


def _resumir_evidencia(brain: ProjectBrain) -> dict:
    """
    Extrai/resume SO o que ja foi coletado (Opportunity Analyst/Decision
    Engine) em algo compacto para mandar pro LLM -- cost-first: nunca manda
    o ProjectBrain inteiro nem dados brutos de centenas de registros.
    """
    sinais_encontrados = {
        fonte: dado.get("resumo")
        for fonte, dado in (brain.oportunidade.signals or {}).items()
        if dado.get("encontrado")
    }
    return {
        "produto_origem": brain.identidade.name,
        # Nomeado explicitamente "DO_CONCORRENTE" (Fase 4 -- correcao
        # pos-teste real): este texto e EVIDENCIA DE MERCADO de um anuncio
        # de OUTRA empresa, nunca fato/copy do produto novo que a Cris OS
        # vai propor. Ver REGRAS OBRIGATORIAS em `_prompt`.
        "headline_do_anuncio_DO_CONCORRENTE": _truncar(brain.origem.source_headline, 200),
        "copy_do_anuncio_DO_CONCORRENTE": _truncar(brain.origem.source_copy, 500),
        "pais": brain.mercado.target_country or brain.origem.source_country,
        "nicho": brain.mercado.niche,
        "score_scalaflow": brain.oportunidade.score,
        "caminho_decidido": brain.decisao.recommended_path,
        "motivo_da_decisao": brain.decisao.reasoning_summary,
        "nivel_de_evidencia": brain.decisao.evidence_level,
        "sinais_confirmados": sinais_encontrados,
        "evidencias": list(brain.oportunidade.evidence),
        "riscos_ja_identificados": list(brain.oportunidade.risks),
        "concorrencia_interna_scalaflow": brain.oportunidade.competition.get("scalaflow_interno"),
    }


def _tem_evidencia_minima(contexto: dict) -> bool:
    """So chamamos o LLM se houver ALGO real pra raciocinar (economiza
    custo quando obviamente nao ha nada)."""
    return any([
        contexto.get("headline_do_anuncio_DO_CONCORRENTE"),
        contexto.get("copy_do_anuncio_DO_CONCORRENTE"),
        contexto.get("nicho"),
        contexto.get("score_scalaflow"),
    ])


def _prompt(contexto: dict) -> list[dict]:
    tipos = ", ".join(sorted(PRODUCT_TYPES))
    sistema = (
        "Voce e o Product Architect do CRIS OS. Recebe uma oportunidade ja "
        "investigada (dados REAIS, resumidos abaixo).\n\n"
        "DISTINCAO OBRIGATORIA:\n"
        "'Evidencia insuficiente para DECIDIR/APROVAR' NAO significa "
        "'evidencia insuficiente para GERAR HIPOTESES'. Sempre que houver "
        "QUALQUER evidencia (headline, copy, nicho ou score), gere de 3 a 5 "
        "candidatos de formato PLAUSIVEIS -- mesmo que nenhum deles seja "
        "confiavel o bastante pra recomendar. So deixe `candidates` vazio "
        "se REALMENTE nao houver nada (sem headline, sem copy, sem nicho, "
        "sem score).\n\n"
        "REGRAS OBRIGATORIAS:\n"
        "1. NUNCA invente vendas, faturamento, demanda, viralidade, "
        "concorrentes ou qualquer numero que nao esteja no contexto dado.\n"
        "2. Todo `product_type` (em candidates e em recommendation) DEVE "
        f"vir exatamente desta lista (minusculo, com underscore): {tipos}\n"
        "3. `recommendation.ready_for_approval` SO pode ser `true` se a "
        "evidencia for REALMENTE forte (nao apenas um unico anuncio "
        "isolado sem sinal cruzado). Na duvida, `false` -- e melhor "
        "apresentar hipoteses honestas do que uma recomendacao precipitada.\n"
        "4. Cada candidato deve ter `missing_evidence` proprio: o que "
        "falta especificamente pra confiar MAIS nesse formato.\n"
        "5. Se a oportunidade veio de um concorrente/anuncio que vende um "
        "formato especifico (ex.: um ebook), isso e EVIDENCIA DE MERCADO "
        "(existe demanda pelo problema/nicho) -- NUNCA obrigacao de propor "
        "o MESMO formato. Considere formatos diferentes com a mesma "
        "seriedade.\n"
        "6. REGRA CRITICA -- NUNCA HERDE ALEGACOES DO CONCORRENTE COMO FATO "
        "DO PRODUTO NOVO: os campos `headline_do_anuncio_DO_CONCORRENTE`/"
        "`copy_do_anuncio_DO_CONCORRENTE` sao texto de OUTRA empresa, um "
        "produto que JA EXISTE. Use isso so pra entender publico/problema/"
        "mecanismo/linguagem de mercado -- NUNCA copie numero de clientes, "
        "quantidade de pessoas atendidas, garantias, 'acesso vitalicio', "
        "'fornecedor incluso' ou qualquer prova social/promessa do anuncio "
        "para dentro de `why_it_fits`/`audience_hypothesis`/`problem` como "
        "se fosse verdade sobre o produto NOVO (que ainda nem existe). Isso "
        "e uma invencao de fato, nao uma hipotese.\n"
        "7. Responda SOMENTE com um JSON valido (sem markdown, sem texto "
        "fora do JSON), EXATAMENTE neste formato:\n"
        "{\n"
        '  "candidates": [\n'
        "    {\n"
        '      "product_type": "...", "audience_hypothesis": "...",\n'
        '      "problem": "...", "why_it_fits": "...",\n'
        '      "production_difficulty": "baixa|media|alta",\n'
        '      "estimated_speed_to_mvp": "...", "monetization": ["..."],\n'
        '      "supporting_evidence": ["..."], "missing_evidence": ["..."],\n'
        '      "confidence": "BAIXO|MEDIO|ALTO"\n'
        "    }\n"
        "    // 3 a 5 itens\n"
        "  ],\n"
        '  "recommendation": {\n'
        '    "product_type": "..." ou null,\n'
        '    "reasoning_summary": "...",\n'
        '    "ready_for_approval": true ou false\n'
        "  },\n"
        '  "assumptions": ["..."],\n'
        '  "risks": ["..."]\n'
        "}"
    )
    usuario = "Oportunidade investigada (dados reais):\n" + json.dumps(contexto, ensure_ascii=False, indent=2)
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


def _validar_tipo(tipo: str | None) -> str | None:
    if tipo and str(tipo).strip().lower() in PRODUCT_TYPES:
        return str(tipo).strip().lower()
    return None


# Afirmacoes PROSPECTIVAS (beneficio futuro/qualidade de negocio) que esta
# fase NAO tem dado nenhum pra sustentar como fato -- nao ha trafego pago
# rodando, entao nada sobre churn/escala/conversao/demanda e verificavel
# ainda. Correcao pos-teste real (Fase 4): frases como "pode reduzir churn",
# "faceis de escalar com trafego pago", "pode facilitar primeiras vendas"
# apareceram como se fossem conclusao, mesmo com um "pode" (hedge fraco
# demais) -- precisam de um marcador EXPLICITO, nao so um advertio sutil.
_FRASES_PROSPECTIVAS_DE_RISCO = (
    "churn", "escalar", "escalonar", "conversão", "conversao",
    "converte bem", "primeiras vendas", "demanda comprovada",
    "garante venda", "sucesso garantido", "viraliza", "facil vender",
    "fácil vender",
)
_MARCADORES_EXPLICITOS_DE_HIPOTESE = (
    "hipotese", "hipótese", "premissa", "a validar", "sem validacao",
    "sem validação", "inferencia", "inferência",
)
_SUFIXO_HIPOTESE_PREMISSA = " [HIPÓTESE/PREMISSA — A VALIDAR, sem evidência direta]"


def _endurecer_afirmacao_prospectiva(texto: str | None) -> str | None:
    """
    Anexa um marcador EXPLICITO quando o texto faz uma afirmacao prospectiva
    de risco (churn/escala/conversao/demanda/etc.) sem ja trazer um marcador
    explicito de hipotese/premissa. NAO bloqueia nem reescreve o texto --
    so torna a incerteza visivel (pedido explicito: "nao transforme isso em
    bloqueio excessivo").
    """
    if not texto:
        return texto
    texto_lower = texto.lower()
    tem_risco = any(f in texto_lower for f in _FRASES_PROSPECTIVAS_DE_RISCO)
    if not tem_risco:
        return texto
    tem_marcador_explicito = any(m in texto_lower for m in _MARCADORES_EXPLICITOS_DE_HIPOTESE)
    if tem_marcador_explicito:
        return texto
    return texto.rstrip(". ") + _SUFIXO_HIPOTESE_PREMISSA


def _texto_limpo(bruto) -> str | None:
    """Pipeline de honestidade aplicado a todo texto livre gerado pelo LLM
    para um candidato: 1) remove alegacoes herdadas do concorrente (Fase 4 --
    fato inventado sobre um produto que ainda nao existe, ex.: '13.000
    pessoas', 'acesso vitalicio'); 2) sinaliza afirmacoes prospectivas sem
    evidencia (churn/escala/conversao) com marcador explicito."""
    return _endurecer_afirmacao_prospectiva(sanitizar_claims_herdadas(_str_ou_none(bruto)))


def _validar_candidato(bruto: dict) -> dict | None:
    tipo = _validar_tipo(bruto.get("product_type"))
    if not tipo:
        return None
    return {
        "product_type": tipo,
        "audience_hypothesis": _texto_limpo(bruto.get("audience_hypothesis")),
        "problem": _texto_limpo(bruto.get("problem")),
        "why_it_fits": _texto_limpo(bruto.get("why_it_fits")),
        # `functional_proposal`/`risks` (Fase 4 -- correcao de expansao de
        # hipoteses) sao opcionais: `propor_produto` nao pede isso ao LLM,
        # entao ficam None/[] nesse fluxo; `expandir_candidatos` pede.
        "functional_proposal": _texto_limpo(bruto.get("functional_proposal")),
        "production_difficulty": _str_ou_none(bruto.get("production_difficulty")),
        "estimated_speed_to_mvp": _str_ou_none(bruto.get("estimated_speed_to_mvp")),
        "monetization": _lista(bruto.get("monetization")),
        "supporting_evidence": _lista(bruto.get("supporting_evidence")),
        "missing_evidence": _lista(bruto.get("missing_evidence")),
        "risks": _lista(bruto.get("risks")),
        "confidence": _str_ou_none(bruto.get("confidence")),
    }


def _validar_candidato_expansao(bruto: dict) -> dict | None:
    """Igual a `_validar_candidato`, mas tambem carrega o marcador de
    inferencia (Fase 4 -- correcao de expansao de hipoteses): um candidato
    novo pode fazer sentido so como INFERENCIA (sem validacao externa real),
    e isso precisa ficar EXPLICITO na resposta, nunca escondido."""
    base = _validar_candidato(bruto)
    if not base:
        return None
    eh_inferencia = bool(bruto.get("is_inference"))
    base["is_inference"] = eh_inferencia
    base["inference_note"] = (
        "INFERÊNCIA / HIPÓTESE — ainda sem validação externa." if eh_inferencia else None
    )
    return base


def _fallback_deterministico(brain: ProjectBrain) -> ProductBlueprint:
    """
    Sem LLM disponivel: proposta minima e HONESTA, sem fingir analise que
    nao foi feita. Usa so o caminho ja decidido pelo Decision Engine
    (Fase 2) -- que ja exigiu 2+ fontes reais de evidencia para chegar em
    AFFILIATE/COMMERCE_RESALE, entao mapear isso pra um formato e razoavel
    mesmo sem chamar o LLM de novo.
    """
    caminho = brain.decisao.recommended_path
    mapa = {"AFFILIATE": "afiliado", "COMMERCE_RESALE": "comercio_revenda"}
    tipo = mapa.get(caminho or "")

    candidatos = []
    if tipo:
        candidatos.append({
            "product_type": tipo,
            "audience_hypothesis": None,
            "problem": None,
            "why_it_fits": f"Caminho '{caminho}' ja decidido pelo Decision Engine com evidencia real.",
            "production_difficulty": None,
            "estimated_speed_to_mvp": None,
            "monetization": [],
            "supporting_evidence": list(brain.oportunidade.evidence),
            "missing_evidence": ["Analise de formato de produto via IA (OpenRouter indisponivel nesta tentativa)."],
            "confidence": "MEDIO",
        })

    blueprint = ProductBlueprint(
        project_id=brain.project_id,
        opportunity_id=brain.origem.source_offer_id,
        market=brain.mercado.market,
        country=brain.mercado.target_country or brain.origem.source_country,
        niche=brain.mercado.niche,
        recommended_product_type=tipo or None,
        alternative_product_types=[],
        candidates=candidatos,
        reasoning_summary=(
            "OpenRouter indisponivel nesta chamada -- proposta limitada ao "
            "caminho ja decidido pelo Decision Engine, sem analise "
            "qualitativa de formato de produto."
        ),
        assumptions=[],
        risks=list(brain.oportunidade.risks),
        missing_evidence=[] if tipo else [
            "Analise de formato de produto (requer IA -- OpenRouter indisponivel nesta tentativa)",
        ],
        decision_status="PENDING_APPROVAL" if tipo else _SEM_EVIDENCIA_SUFICIENTE,
        generated_by="fallback_deterministico",
    )
    if tipo:
        promover_candidato_para_blueprint(blueprint, candidatos[0])
    return blueprint


def promover_candidato_para_blueprint(blueprint: ProductBlueprint, candidato: dict) -> None:
    """
    Copia os campos ricos do candidato VENCEDOR (o que virou
    `recommended_product_type`) para os campos de TOPO do blueprint
    (`product_concept`, `target_audience`, `problem`, `mvp_scope`, etc.).

    Correcao de bug real (Fase 4): sem isso, esses campos de topo ficavam
    sempre `None` (nunca eram preenchidos em lugar nenhum), mesmo com uma
    analise rica ja feita pelo LLM dentro de `candidates` -- e downstream
    (`core/product_factory.py:gerar_copy_simples`,
    `core/business_builder.py:_resumir_contexto`) so LEEM os campos de topo,
    entao produziam texto generico ("(não definido)") mesmo com contexto
    especifico disponivel (ex.: nicho de velas artesanais).

    Sempre sobrescreve com o candidato ATUAL (nao so preenche se vazio):
    se uma alternativa diferente for promovida depois (rejeicao), os campos
    de topo devem refletir a nova escolha, nao a antiga.
    """
    if candidato.get("audience_hypothesis"):
        blueprint.target_audience = candidato["audience_hypothesis"]
    if candidato.get("problem"):
        blueprint.problem = candidato["problem"]
    if candidato.get("why_it_fits"):
        blueprint.product_concept = candidato["why_it_fits"]
        blueprint.core_value = candidato["why_it_fits"]
    if candidato.get("functional_proposal"):
        blueprint.mvp_scope = candidato["functional_proposal"]
    if candidato.get("production_difficulty"):
        blueprint.production_complexity = candidato["production_difficulty"]
    if candidato.get("estimated_speed_to_mvp"):
        blueprint.estimated_speed_to_mvp = candidato["estimated_speed_to_mvp"]
    if candidato.get("monetization"):
        blueprint.monetization_options = list(candidato["monetization"])


def propor_produto(brain: ProjectBrain, llm=None) -> ProductBlueprint:
    """
    Gera um ProductBlueprint para a oportunidade em `brain`: sempre tenta
    popular `candidates` (hipoteses) quando ha evidencia minima; so promove
    um deles a `recommended_product_type` (PENDING_APPROVAL) quando o LLM
    sinaliza confianca real (`ready_for_approval`). NUNCA lanca excecao --
    qualquer falha do LLM cai no fallback deterministico.
    """
    contexto = _resumir_evidencia(brain)

    if llm is None:
        return _fallback_deterministico(brain)

    if not _tem_evidencia_minima(contexto):
        return ProductBlueprint(
            project_id=brain.project_id,
            opportunity_id=brain.origem.source_offer_id,
            decision_status=_SEM_EVIDENCIA_SUFICIENTE,
            missing_evidence=[
                "Nenhum dado suficiente (headline/copy/nicho/score) para "
                "sequer formular hipoteses de produto.",
            ],
            generated_by="sem_evidencia",
        )

    try:
        resposta = llm.chat(_prompt(contexto))
    except Exception as exc:
        logger.warning("=== [PRODUCT_ARCHITECT] LLM falhou, usando fallback deterministico: %s ===", exc)
        return _fallback_deterministico(brain)

    dados = _extrair_json(resposta.content or "")
    if not dados:
        logger.warning("=== [PRODUCT_ARCHITECT] Resposta do LLM nao era JSON valido, usando fallback ===")
        return _fallback_deterministico(brain)

    candidatos_brutos = dados.get("candidates") or []
    candidatos = [c for c in (_validar_candidato(c) for c in candidatos_brutos) if c]

    if not candidatos:
        logger.warning("=== [PRODUCT_ARCHITECT] LLM nao devolveu candidatos validos, usando fallback ===")
        return _fallback_deterministico(brain)

    recomendacao = dados.get("recommendation") or {}
    tipo_recomendado = _validar_tipo(recomendacao.get("product_type"))
    tipos_candidatos = {c["product_type"] for c in candidatos}
    pronto_para_aprovar = bool(recomendacao.get("ready_for_approval")) and tipo_recomendado in tipos_candidatos

    if pronto_para_aprovar:
        alternativas = [c["product_type"] for c in candidatos if c["product_type"] != tipo_recomendado]
        status = "PENDING_APPROVAL"
        # Preserva o missing_evidence PROPRIO do candidato vencedor -- uma
        # recomendacao confiavel ainda pode ter incertezas pontuais; nao
        # escondemos isso so porque o status avancou.
        vencedor = next(c for c in candidatos if c["product_type"] == tipo_recomendado)
        missing = list(vencedor["missing_evidence"])
    else:
        tipo_recomendado = None
        alternativas = [c["product_type"] for c in candidatos]
        status = _SEM_EVIDENCIA_SUFICIENTE
        # missing_evidence agregado (deduplicado, mantendo ordem) dos candidatos
        vistos: set[str] = set()
        missing = []
        for c in candidatos:
            for m in c["missing_evidence"]:
                if m not in vistos:
                    vistos.add(m)
                    missing.append(m)

    blueprint = ProductBlueprint(
        project_id=brain.project_id,
        opportunity_id=brain.origem.source_offer_id,
        market=brain.mercado.market,
        country=brain.mercado.target_country or brain.origem.source_country,
        niche=brain.mercado.niche,
        target_audience=brain.mercado.target_audience,
        recommended_product_type=tipo_recomendado,
        alternative_product_types=alternativas,
        candidates=candidatos,
        evidence=list(brain.oportunidade.evidence),
        assumptions=_lista(dados.get("assumptions")),
        risks=_lista(dados.get("risks")) or list(brain.oportunidade.risks),
        missing_evidence=missing,
        reasoning_summary=_str_ou_none(recomendacao.get("reasoning_summary")),
        decision_status=status,
        generated_by=getattr(llm, "_provider_name", "llm"),
    )
    if pronto_para_aprovar:
        promover_candidato_para_blueprint(blueprint, vencedor)
    return blueprint


def _prompt_expansao(contexto: dict, candidatos_existentes: list[dict], pedido_usuario: str) -> list[dict]:
    """
    Prompt de EXPANSAO (Fase 4 -- correcao pos-teste real): usado quando a
    pessoa pede EXPLICITAMENTE formatos novos/diferentes/mais interativos e
    quer comparar com as hipoteses ja existentes -- nunca deve so repetir a
    lista anterior (bug real: "proponha tambem alternativas mais interativas
    (mini-app/ferramenta/sistema)... compare com as hipoteses atuais" caiu no
    cache de "mostrar hipoteses" e devolveu a mesma lista, comecando de novo
    por ebook).
    """
    tipos = ", ".join(sorted(PRODUCT_TYPES))
    existentes_resumo = [
        {
            "product_type": c["product_type"],
            "confidence": c.get("confidence"),
            "why_it_fits": c.get("why_it_fits"),
        }
        for c in candidatos_existentes
    ]
    sistema = (
        "Voce e o Product Architect do CRIS OS. Ja existem hipoteses de "
        "formato de produto levantadas para esta oportunidade (listadas "
        "abaixo, em 'Hipoteses ja existentes'). A pessoa pediu EXPLICITAMENTE "
        "para EXPANDIR essas hipoteses com formatos NOVOS/diferentes, e "
        "COMPARAR com as ja existentes usando as MESMAS evidencias -- sem "
        "escolher uma vencedora automaticamente.\n\n"
        "REGRAS OBRIGATORIAS:\n"
        "1. NAO REPITA as hipoteses ja existentes -- proponha de 3 a 5 "
        "candidatos NOVOS, coerentes com o pedido da pessoa (ver campo "
        "'Pedido da pessoa').\n"
        "2. NUNCA favoreca um formato so porque um concorrente analisado usa "
        "esse formato -- o formato do concorrente e EVIDENCIA DE MERCADO "
        "(existe demanda pelo problema/nicho), NAO obrigacao de copiar o "
        "formato dele.\n"
        "3. Se um formato novo (ex.: mini-app, ferramenta, sistema) so faz "
        "sentido como INFERENCIA (sem validacao externa real disponivel), "
        "marque `\"is_inference\": true` nesse candidato.\n"
        "4. NUNCA invente vendas, faturamento, demanda, viralidade, "
        "concorrentes ou qualquer numero que nao esteja no contexto dado.\n"
        "5. Todo `product_type` DEVE vir exatamente desta lista (minusculo, "
        f"com underscore): {tipos}\n"
        "6. `recommendation.ready_for_approval` SO pode ser `true` se a "
        "evidencia for REALMENTE forte. Na duvida, `false` -- a pessoa pediu "
        "explicitamente para nao aprovar nada nesta rodada.\n"
        "7. REGRA CRITICA -- NUNCA HERDE ALEGACOES DO CONCORRENTE COMO FATO "
        "DO PRODUTO NOVO: qualquer headline/copy de anuncio no contexto e de "
        "OUTRA empresa (produto que JA EXISTE) -- e so EVIDENCIA DE MERCADO. "
        "NUNCA copie numero de clientes, garantias, 'acesso vitalicio' ou "
        "qualquer prova social/promessa do anuncio como se fosse verdade "
        "sobre o produto NOVO.\n"
        "8. Preencha `comparison`: um texto comparando os candidatos NOVOS "
        "com os EXISTENTES (vantagens/desvantagens relativas de cada grupo), "
        "sem eleger um vencedor.\n"
        "9. Responda SOMENTE com um JSON valido (sem markdown, sem texto "
        "fora do JSON), EXATAMENTE neste formato:\n"
        "{\n"
        '  "candidates": [\n'
        "    {\n"
        '      "product_type": "...", "audience_hypothesis": "...",\n'
        '      "problem": "...", "why_it_fits": "...",\n'
        '      "functional_proposal": "...",\n'
        '      "production_difficulty": "baixa|media|alta",\n'
        '      "estimated_speed_to_mvp": "...", "monetization": ["..."],\n'
        '      "supporting_evidence": ["..."], "missing_evidence": ["..."],\n'
        '      "risks": ["..."], "is_inference": true ou false,\n'
        '      "confidence": "BAIXO|MEDIO|ALTO"\n'
        "    }\n"
        "    // 3 a 5 itens, formatos NOVOS -- nao repita os existentes\n"
        "  ],\n"
        '  "comparison": "...",\n'
        '  "recommendation": {\n'
        '    "product_type": "..." ou null,\n'
        '    "reasoning_summary": "...",\n'
        '    "ready_for_approval": true ou false\n'
        "  },\n"
        '  "assumptions": ["..."],\n'
        '  "risks": ["..."]\n'
        "}"
    )
    usuario = (
        "Oportunidade investigada (dados reais):\n"
        + json.dumps(contexto, ensure_ascii=False, indent=2)
        + "\n\nHipoteses ja existentes (NAO repita, compare com elas):\n"
        + json.dumps(existentes_resumo, ensure_ascii=False, indent=2)
        + "\n\nPedido da pessoa (segue o texto literal):\n"
        + pedido_usuario
    )
    return [
        {"role": "system", "content": sistema},
        {"role": "user", "content": usuario},
    ]


def expandir_candidatos(brain: ProjectBrain, pedido_usuario: str, llm=None) -> ProductBlueprint:
    """
    Expande as hipoteses JA existentes com candidatos NOVOS (nunca apaga as
    anteriores) e compara os dois grupos usando as MESMAS evidencias, sem
    promover automaticamente uma recomendacao (a pessoa pediu explicitamente
    pra nao aprovar nada). NUNCA lanca excecao -- qualquer falha do LLM
    mantem o blueprint como estava (nunca perde o que ja existia).

    Correcao pos-teste real (Fase 4): antes, um pedido de expansao (ex.:
    "proponha tambem alternativas mais interativas... compare com as
    hipoteses atuais") caia no mesmo cache de "so mostrar hipoteses ja
    calculadas" e devolvia a lista antiga sem gerar nada novo. Esta funcao e
    um caminho SEPARADO -- quem chama (`tools/product_architect_tools.py`)
    decide, por deteccao de intencao, se o pedido e "ver o que ja existe"
    (cache, sem custo) ou "expandir/comparar" (sempre chama o LLM de novo).
    """
    bp = brain.blueprint
    if not bp or not bp.candidates:
        # Sem base pra expandir -- comportamento identico a propor do zero.
        return propor_produto(brain, llm=llm)

    if llm is None:
        bp.assumptions = list(bp.assumptions) + [
            "Pedido de expansao de hipoteses recebido, mas OpenRouter "
            "indisponivel -- hipoteses NAO expandidas nesta tentativa "
            "(as anteriores foram mantidas, nada foi inventado).",
        ]
        bp.updated_at = _agora()
        return bp

    contexto = _resumir_evidencia(brain)
    try:
        resposta = llm.chat(_prompt_expansao(contexto, bp.candidates, pedido_usuario))
    except Exception as exc:
        logger.warning(
            "=== [PRODUCT_ARCHITECT] Expansao: LLM falhou, mantendo hipoteses existentes: %s ===", exc,
        )
        return bp

    dados = _extrair_json(resposta.content or "")
    if not dados:
        logger.warning(
            "=== [PRODUCT_ARCHITECT] Expansao: resposta do LLM nao era JSON valido, mantendo hipoteses existentes ===",
        )
        return bp

    novos_brutos = dados.get("candidates") or []
    novos = [c for c in (_validar_candidato_expansao(c) for c in novos_brutos) if c]
    if not novos:
        logger.warning(
            "=== [PRODUCT_ARCHITECT] Expansao: LLM nao devolveu candidatos novos validos, mantendo hipoteses existentes ===",
        )
        return bp

    # Merge: substitui candidatos do MESMO tipo (evita duplicar a mesma
    # analise) e ACRESCENTA os tipos novos -- nunca apaga tipos que a nova
    # resposta simplesmente nao mencionou.
    tipos_novos = {c["product_type"] for c in novos}
    candidatos_finais = [c for c in bp.candidates if c["product_type"] not in tipos_novos] + novos
    bp.candidates = candidatos_finais

    comparacao = _str_ou_none(dados.get("comparison"))
    if comparacao:
        bp.reasoning_summary = comparacao

    recomendacao = dados.get("recommendation") or {}
    tipo_recomendado = _validar_tipo(recomendacao.get("product_type"))
    tipos_candidatos = {c["product_type"] for c in candidatos_finais}
    if bool(recomendacao.get("ready_for_approval")) and tipo_recomendado in tipos_candidatos:
        bp.recommended_product_type = tipo_recomendado
        bp.alternative_product_types = [t for t in tipos_candidatos if t != tipo_recomendado]
        bp.decision_status = "PENDING_APPROVAL"
        vencedor = next(c for c in candidatos_finais if c["product_type"] == tipo_recomendado)
        promover_candidato_para_blueprint(bp, vencedor)
    else:
        # Pedido de expansao/comparacao NUNCA aprova nada sozinho -- volta
        # (ou permanece) em modo hipoteses.
        bp.recommended_product_type = None
        bp.alternative_product_types = [t for t in tipos_candidatos]
        bp.decision_status = _SEM_EVIDENCIA_SUFICIENTE

    novas_suposicoes = _lista(dados.get("assumptions"))
    if novas_suposicoes:
        bp.assumptions = list(dict.fromkeys(list(bp.assumptions) + novas_suposicoes))
    novos_riscos = _lista(dados.get("risks"))
    if novos_riscos:
        bp.risks = list(dict.fromkeys(list(bp.risks) + novos_riscos))

    bp.generated_by = getattr(llm, "_provider_name", "llm")
    bp.updated_at = _agora()
    return bp


def promover_proxima_alternativa(blueprint: ProductBlueprint, motivo_rejeicao: str = "") -> ProductBlueprint:
    """
    Rejeicao ("nao gostei, quero outra"): promove a PROXIMA alternativa ja
    proposta para `recommended_product_type`, sem chamar o LLM de novo
    (mais barato, e as alternativas ja foram raciocinadas na mesma chamada).
    Se nao houver mais alternativas, marca NEEDS_RESEARCH -- nunca inventa
    uma alternativa nova sem reanalisar de verdade.
    """
    if not blueprint.alternative_product_types:
        blueprint.decision_status = _SEM_EVIDENCIA_SUFICIENTE
        blueprint.missing_evidence = list(blueprint.missing_evidence) + [
            "Sem mais alternativas propostas -- pedir nova analise ao Product Architect.",
        ]
        blueprint.updated_at = _agora()
        return blueprint

    novo_tipo = blueprint.alternative_product_types[0]
    restantes = blueprint.alternative_product_types[1:]
    anterior = blueprint.recommended_product_type

    blueprint.recommended_product_type = novo_tipo
    blueprint.alternative_product_types = (
        restantes + [anterior] if anterior else restantes
    )
    blueprint.decision_status = "PENDING_APPROVAL"
    blueprint.reasoning_summary = (
        f"Alternativa promovida apos rejeicao de '{anterior}'"
        + (f" ({motivo_rejeicao})" if motivo_rejeicao else "")
        + f". Formato anterior volta como alternativa."
    )
    novo_candidato = next((c for c in blueprint.candidates if c["product_type"] == novo_tipo), None)
    if novo_candidato:
        promover_candidato_para_blueprint(blueprint, novo_candidato)
    blueprint.updated_at = _agora()
    return blueprint


def _str_ou_none(v) -> str | None:
    if v is None:
        return None
    texto = str(v).strip()
    return texto or None


def _lista(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [str(v).strip()]
