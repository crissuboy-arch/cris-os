"""
Business Builder — transforma um Product Blueprint JA APROVADO em estrutura
comercial (Fase 4).

Fluxo: ScalaFlow -> Opportunity Analyst -> Decision Engine -> Product
Architect -> APROVACAO HUMANA -> BUSINESS BUILDER -> Product Factory.

Diferente do Product Architect (que decide QUAL FORMATO faz sentido), aqui a
pergunta e COMO transformar um formato ja aprovado em negocio: modelo,
oferta, monetizacao, funil, conteudo, lancamento. Como e uma tarefa de
ESTRUTURACAO em cima de dados ja existentes (nao uma escolha aberta entre 20+
opcoes), usa o OpenRouter tier ECONOMICO (nao precisa do tier INTELIGENTE,
mais caro, pedido explicito da Fase 4: "o Business Builder nao precisa usar
modelo caro para tarefas simples").

Regras que o prompt e o parsing IMPOEM (nao so pedem por favor):
  - NUNCA inventa vendas, receita, CPA, ROAS, conversao, demanda ou tamanho
    de mercado -- essas metricas so existiriam com trafego pago rodando
    (fora de escopo desta fase).
  - Preco SEM benchmark real e SEMPRE uma hipotese (`price_is_hypothesis`),
    nunca apresentado como fato.
  - Cada secao alimenta os campos de honestidade (`evidence`, `assumptions`,
    `missing_evidence`) em vez de inventar quando falta dado.
  - So funciona sobre um blueprint com `decision_status == "APPROVED"` --
    o gate e checado por quem chama (`tools/business_builder_tools.py`), nao
    aqui (este modulo e logica pura, sem I/O e sem side effects).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from core.evidence_guard import sanitizar_claims_herdadas
from memory.project_brain import BusinessPlan, ProjectBrain

logger = logging.getLogger(__name__)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def blueprint_aprovado(brain: ProjectBrain) -> bool:
    """Gate central (Fase 4, item 12): so faz sentido montar um negocio em
    cima de um FORMATO DE PRODUTO ja aprovado -- nunca avanca silenciosamente
    sem isso.

    Usa `ProductBlueprint.esta_aprovado()` (nao uma comparacao direta com
    "APPROVED") -- correcao de bug real: a Product Factory avanca
    `decision_status` para "IN_PRODUCTION" IMEDIATAMENTE apos a aprovacao
    (mesmo fluxo de `_aprovar`), entao checar so `== "APPROVED"` aqui
    bloqueava o Business Builder mesmo logo depois de uma aprovacao real e
    persistida."""
    return bool(brain.blueprint and brain.blueprint.esta_aprovado())


def _truncar(texto: str | None, limite: int) -> str | None:
    if not texto:
        return None
    texto = texto.strip()
    return texto if len(texto) <= limite else texto[: limite - 3].rstrip() + "..."


def _resumir_contexto(brain: ProjectBrain) -> dict:
    """Resumo compacto (cost-first: nunca manda o ProjectBrain inteiro) do
    que ja se sabe sobre o produto aprovado, para o LLM estruturar o
    negocio em cima -- nunca para reanalisar o formato (isso ja foi decidido
    pelo Product Architect)."""
    bp = brain.blueprint
    return {
        "formato_aprovado": bp.recommended_product_type,
        "conceito": bp.product_concept,
        "publico_alvo": bp.target_audience,
        "problema": bp.problem,
        "nicho": bp.niche,
        "pais": bp.country,
        "mercado": bp.market,
        "monetizacao_sugerida": bp.monetization_options,
        # Nomeado "DO_CONCORRENTE" (Fase 4 -- correcao pos-teste real): este
        # texto e do anuncio de OUTRA empresa (produto que JA EXISTE), so
        # EVIDENCIA DE MERCADO -- nunca fato/copy do produto novo. Ver
        # REGRA CRITICA no prompt abaixo.
        "headline_do_anuncio_DO_CONCORRENTE": _truncar(brain.origem.source_headline, 200),
        "copy_do_anuncio_DO_CONCORRENTE": _truncar(brain.origem.source_copy, 400),
        "evidencias_ja_coletadas": list(bp.evidence),
        "riscos_ja_identificados": list(bp.risks),
        "motivo_do_formato_aprovado": bp.reasoning_summary,
    }


def _prompt(contexto: dict) -> list[dict]:
    sistema = (
        "Voce e o Business Builder do CRIS OS. Recebe um FORMATO DE PRODUTO "
        "JA APROVADO (nao decida outro formato -- isso ja foi decidido) e "
        "organiza a estrutura comercial em torno dele.\n\n"
        "REGRAS OBRIGATORIAS:\n"
        "1. NUNCA invente vendas, receita, CPA, ROAS, conversao, demanda ou "
        "tamanho de mercado -- nenhum desses numeros existe ainda (nao ha "
        "trafego pago rodando).\n"
        "2. Preco SEM benchmark real DEVE ter `price_is_hypothesis: true` -- "
        "nunca apresente um preco como se fosse um fato confirmado.\n"
        "3. Toda promessa da pagina de vendas deve ser RESPONSAVEL -- nunca "
        "prometa resultado irreal ou nao verificavel.\n"
        "4. Quando faltar evidencia para uma secao, preencha `missing_evidence` "
        "em vez de inventar.\n"
        "5. REGRA CRITICA -- NUNCA HERDE ALEGACOES DO CONCORRENTE COMO FATO "
        "DO PRODUTO NOVO: `headline_do_anuncio_DO_CONCORRENTE`/"
        "`copy_do_anuncio_DO_CONCORRENTE` sao de OUTRA empresa, um produto "
        "que JA EXISTE e JA FOI VALIDADO. Use isso so pra entender publico/"
        "problema/mecanismo/linguagem de mercado/angulo -- NUNCA copie "
        "numero de clientes/alunos, 'ja ajudou X pessoas', garantias, "
        "'acesso vitalicio', 'fornecedor incluso' ou qualquer prova social/"
        "promessa do anuncio para dentro de `value_proposition`/`headline`/"
        "`promise`/`main_offer`/etc. como se fosse verdade sobre o produto "
        "NOVO. Isso e uma invencao de fato, nao uma hipotese -- o produto "
        "novo ainda nem foi produzido.\n"
        "6. Responda SOMENTE com um JSON valido (sem markdown, sem texto fora "
        "do JSON), EXATAMENTE neste formato:\n"
        "{\n"
        '  "business_model": "...", "value_proposition": "...",\n'
        '  "target_audience": "...", "problem": "...", "solution": "...",\n'
        '  "positioning": "...", "mechanism": "...", "main_offer": "...",\n'
        '  "monetization_format": "...",\n'
        '  "price": "..." ou null, "price_is_hypothesis": true ou false,\n'
        '  "bonuses": ["..."], "order_bump": "..." ou null,\n'
        '  "upsell": ["..."], "downsell": ["..."],\n'
        '  "acquisition_channels": ["..."], "sales_channels": ["..."],\n'
        '  "sales_page_structure": "...", "headline": "...", "promise": "...",\n'
        '  "key_arguments": ["..."],\n'
        '  "objections": [{"objecao": "...", "resposta": "..."}],\n'
        '  "cta": "...", "funnel_structure": "...",\n'
        '  "email_sequence": [\n'
        '    {"numero": 1, "objetivo": "...", "assunto": "...", "resumo": "..."}\n'
        "    // exatamente 5 itens\n"
        "  ],\n"
        '  "content_strategy": "...", "content_channels": ["..."],\n'
        '  "launch_strategy": "...",\n'
        '  "plan_30_days": [{"periodo": "dias 1-7", "acoes": ["..."]}],\n'
        '  "assumptions": ["..."], "missing_evidence": ["..."],\n'
        '  "risks": ["..."], "dependencies": ["..."], "next_steps": ["..."]\n'
        "}"
    )
    usuario = "Produto aprovado (dados reais):\n" + json.dumps(contexto, ensure_ascii=False, indent=2)
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


def _lista(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [str(v).strip()]


def _lista_dicts(v) -> list[dict]:
    if not v or not isinstance(v, list):
        return []
    return [x for x in v if isinstance(x, dict)]


def _texto_limpo(v) -> str | None:
    """Remove alegacoes herdadas do concorrente (Fase 4 -- correcao pos-teste
    real) de qualquer texto livre gerado pelo LLM."""
    return sanitizar_claims_herdadas(_str_ou_none(v))


def _lista_limpa(v) -> list[str]:
    return [t for t in (sanitizar_claims_herdadas(x) for x in _lista(v)) if t]


def _lista_dicts_limpa(v, campos_texto: tuple[str, ...]) -> list[dict]:
    limpos = []
    for d in _lista_dicts(v):
        novo = dict(d)
        for campo in campos_texto:
            if isinstance(novo.get(campo), str):
                novo[campo] = sanitizar_claims_herdadas(novo[campo])
        limpos.append(novo)
    return limpos


def _fallback_deterministico(brain: ProjectBrain) -> BusinessPlan:
    """Sem LLM disponivel: estrutura minima e HONESTA usando so os campos que
    ja existem no blueprint aprovado -- nunca finge uma analise de oferta que
    nao foi feita."""
    bp = brain.blueprint
    return BusinessPlan(
        project_id=brain.project_id,
        business_model=bp.monetization_options[0] if bp.monetization_options else None,
        target_audience=bp.target_audience,
        problem=bp.problem,
        main_offer=bp.product_concept,
        monetization_format=", ".join(bp.monetization_options) or None,
        price=None,
        price_is_hypothesis=True,
        evidence=list(bp.evidence),
        risks=list(bp.risks),
        missing_evidence=[
            "OpenRouter indisponivel nesta chamada -- plano de negocio limitado "
            "aos campos ja existentes no Product Blueprint, sem estruturacao "
            "de oferta/funil/lancamento via IA.",
        ],
        approval_status="DRAFT",
        generated_by="fallback_deterministico",
    )


def construir_plano_negocio(brain: ProjectBrain, llm=None) -> BusinessPlan:
    """
    Gera um BusinessPlan para o produto JA APROVADO em `brain.blueprint`.
    NUNCA lanca excecao -- qualquer falha do LLM cai no fallback
    deterministico. O gate (`blueprint_aprovado`) e responsabilidade de quem
    chama; esta funcao assume que ja foi checado.
    """
    if llm is None:
        return _fallback_deterministico(brain)

    contexto = _resumir_contexto(brain)

    try:
        resposta = llm.chat(_prompt(contexto))
    except Exception as exc:
        logger.warning("=== [BUSINESS_BUILDER] LLM falhou, usando fallback deterministico: %s ===", exc)
        return _fallback_deterministico(brain)

    dados = _extrair_json(resposta.content or "")
    if not dados:
        logger.warning("=== [BUSINESS_BUILDER] Resposta do LLM nao era JSON valido, usando fallback ===")
        return _fallback_deterministico(brain)

    preco = _str_ou_none(dados.get("price"))
    return BusinessPlan(
        project_id=brain.project_id,
        business_model=_texto_limpo(dados.get("business_model")),
        value_proposition=_texto_limpo(dados.get("value_proposition")),
        target_audience=_texto_limpo(dados.get("target_audience")) or brain.blueprint.target_audience,
        problem=_texto_limpo(dados.get("problem")) or brain.blueprint.problem,
        solution=_texto_limpo(dados.get("solution")),
        positioning=_texto_limpo(dados.get("positioning")),
        mechanism=_texto_limpo(dados.get("mechanism")),
        main_offer=_texto_limpo(dados.get("main_offer")),
        monetization_format=_str_ou_none(dados.get("monetization_format")),
        price=preco,
        # Nunca confia cegamente em `price_is_hypothesis: false` do LLM sem
        # preco nenhum -- so pode ser "fato" se houver um preco concreto.
        price_is_hypothesis=bool(dados.get("price_is_hypothesis", True)) or not preco,
        bonuses=_lista_limpa(dados.get("bonuses")),
        order_bump=_texto_limpo(dados.get("order_bump")),
        upsell=_lista_limpa(dados.get("upsell")),
        downsell=_lista_limpa(dados.get("downsell")),
        acquisition_channels=_lista(dados.get("acquisition_channels")),
        sales_channels=_lista(dados.get("sales_channels")),
        sales_page_structure=_texto_limpo(dados.get("sales_page_structure")),
        headline=_texto_limpo(dados.get("headline")),
        promise=_texto_limpo(dados.get("promise")),
        key_arguments=_lista_limpa(dados.get("key_arguments")),
        objections=_lista_dicts_limpa(dados.get("objections"), ("objecao", "resposta")),
        cta=_texto_limpo(dados.get("cta")),
        funnel_structure=_texto_limpo(dados.get("funnel_structure")),
        email_sequence=_lista_dicts_limpa(dados.get("email_sequence"), ("assunto", "resumo", "objetivo")),
        content_strategy=_texto_limpo(dados.get("content_strategy")),
        content_channels=_lista(dados.get("content_channels")),
        launch_strategy=_texto_limpo(dados.get("launch_strategy")),
        plan_30_days=_lista_dicts_limpa(dados.get("plan_30_days"), ("periodo",)),
        evidence=list(brain.blueprint.evidence),
        assumptions=_lista(dados.get("assumptions")),
        missing_evidence=_lista(dados.get("missing_evidence")),
        risks=_lista(dados.get("risks")) or list(brain.blueprint.risks),
        dependencies=_lista(dados.get("dependencies")),
        next_steps=_lista(dados.get("next_steps")),
        approval_status="READY_FOR_APPROVAL",
        generated_by=getattr(llm, "_provider_name", "llm"),
    )
