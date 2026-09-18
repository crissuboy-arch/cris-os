"""
Ferramentas do agente Product Architect (Fase 3).

Fluxo: ScalaFlow -> Opportunity Analyst -> Decision Engine -> PRODUCT
ARCHITECT -> APROVACAO HUMANA -> PRODUCT FACTORY.

Este modulo e o "cola" entre:
  - tools/opportunity_tools.py (reaproveita a mesma oferta/foco em vez de
    duplicar logica de investigacao);
  - core/product_architect.py (decide o formato do produto, com LLM quando
    disponivel);
  - core/product_factory.py + core/tool_registry.py (so entra em jogo DEPOIS
    de aprovacao explicita);
  - memory/project_brain.py (persistencia -- sem memoria paralela).

Regra de ouro respeitada aqui: NUNCA interpreta conversa ambigua como
aprovacao. So um conjunto fechado de palavras/frases conta como aprovacao
ou rejeicao (ver `_PALAVRAS_APROVACAO`/`_FRASES_REJEICAO`).
"""

from __future__ import annotations

import logging

from config.settings import settings
from core.product_architect import (
    promover_candidato_para_blueprint,
    expandir_candidatos,
    promover_proxima_alternativa,
    propor_produto,
)
from core.product_factory import ProductFactoryError
from memory.project_brain import ProjectBrain
from tools.base import Tool
from tools.opportunity_tools import (
    get_foco_atual,
    get_project_brain_store,
    investigar_oportunidade,
    set_foco_atual,
)
from tools.product_factory_tools import preparar_plano_producao

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

logger = logging.getLogger(__name__)

_PALAVRAS_APROVACAO = frozenset({
    "aprovado", "aprovada", "aprovo", "autorizado", "autorizo",
    "confirmado", "confirmo",
})
_FRASES_APROVACAO = (
    "pode criar", "pode seguir", "pode produzir", "pode comecar",
    "pode começar", "bora criar",
)

_PALAVRAS_REJEICAO = frozenset({"rejeitado", "rejeitada", "rejeito"})
_FRASES_REJEICAO = (
    "nao gostei", "não gostei", "quero outra", "outra alternativa",
    "nao aprovado", "não aprovado", "nao curti", "não curti",
)

_PALAVRAS_EXPLICAR = frozenset({"porque", "motivo", "justificativa"})
_FRASES_EXPLICAR = ("por que",)

_PALAVRAS_ALTERNATIVAS = frozenset({
    "alternativas", "alternativa", "opcoes", "opções", "candidatos",
    "candidato", "possibilidades", "hipoteses", "hipóteses",
})
_FRASES_ALTERNATIVAS = ("compare", "comparar")

# EXPANSAO de hipoteses (correcao pos-teste real, Fase 4): um pedido pra
# EXPANDIR as hipoteses com formatos novos/diferentes (nunca so "mostrar o
# que ja existe") precisa de deteccao PROPRIA, checada ANTES da checagem de
# "alternativas" (view/cache) -- senao um pedido de expansao caia no mesmo
# cache de "so mostrar hipoteses ja calculadas" e devolvia a lista antiga,
# sem gerar nada novo (bug real: "proponha tambem alternativas mais
# interativas... compare com as hipoteses atuais" devolveu a mesma lista
# comecando de novo por ebook).
#
# Palavras de formato especifico (mini-app, ferramenta, etc.) tambem contam
# como pedido de expansao: mencionar um formato que AINDA NAO esta entre os
# candidatos calculados e um sinal claro de "quero que voce considere isso",
# nao "so me mostre de novo o que ja calculou".
_PALAVRAS_EXPANSAO = frozenset({
    "mini-app", "miniapp", "mini_app", "ferramenta", "sistema",
    "calculadora", "gerador", "quiz", "dashboard", "extensao", "extensão",
    "agente", "micro-saas", "microsaas", "micro_saas",
})
_FRASES_EXPANSAO = (
    "novas alternativas", "outras alternativas", "alternativas diferentes",
    "mais interativ", "diferenciad", "alem dessas", "além dessas",
    "compare com as hipoteses atuais", "compare com as hipóteses atuais",
    "compare com as hipoteses", "compare com as hipóteses",
)

_PALAVRAS_PENDENTES = frozenset({"aguardando", "pendentes", "pendente"})


def _headers_ok() -> bool:
    return bool(settings.OPENROUTER_API_KEY) and settings.OPENROUTER_API_KEY != "COLE_SUA_CHAVE_AQUI"


def _tentar_criar_openrouter(tier: str, model: str):
    """Constroi um OpenRouterProvider se a chave existir e o healthcheck
    passar. Nunca lanca excecao -- None em qualquer falha (mesma postura de
    `core/runtime.py:_configurar_openrouter`, duplicada aqui em pequeno para
    nao criar uma dependencia de `tools/` sobre `core/runtime.py`, que e a
    composition root)."""
    if not _headers_ok():
        return None
    try:
        from llm.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            api_key=settings.OPENROUTER_API_KEY,
            model=model,
            base_url=settings.OPENROUTER_BASE_URL,
            timeout=settings.OPENROUTER_TIMEOUT,
            tier=tier,
        )
        if not provider.is_alive():
            return None
        return provider
    except Exception as exc:
        logger.warning("=== [PRODUCT_ARCHITECT] Falha ao configurar OpenRouter (%s): %s ===", tier, exc)
        return None


_llm_inteligente_cache = None


def _get_llm_inteligente():
    global _llm_inteligente_cache
    if _llm_inteligente_cache is None:
        from llm.openrouter import MODELO_PADRAO_INTELIGENTE

        _llm_inteligente_cache = _tentar_criar_openrouter(
            "inteligente", settings.OPENROUTER_MODEL_INTELIGENTE or MODELO_PADRAO_INTELIGENTE,
        )
    return _llm_inteligente_cache


def _contains_any(texto: str, palavras: frozenset[str], frases: tuple = ()) -> bool:
    tokens = set(texto.split())
    if tokens & palavras:
        return True
    return any(f in texto for f in frases)


def _eh_pedido_expansao(texto: str, tipos_ja_existentes: set[str]) -> bool:
    """
    Detecta um pedido de EXPANDIR hipoteses (formatos novos/diferentes +
    comparacao) -- distinto de um pedido de so VER as hipoteses ja
    calculadas. Ver comentario de `_PALAVRAS_EXPANSAO` sobre o bug real que
    isso corrige.
    """
    if any(f in texto for f in _FRASES_EXPANSAO):
        return True
    # Mencionar um formato especifico que NAO esta entre os candidatos
    # ja calculados e um pedido implicito de considerar esse formato --
    # nao adianta so reexibir o que ja existe.
    tokens = set(texto.split())
    for palavra in _PALAVRAS_EXPANSAO:
        if palavra in tokens or palavra in texto:
            tipo_normalizado = palavra.replace("-", "_")
            if tipo_normalizado not in tipos_ja_existentes:
                return True
    return False


def _resolver_projeto_para_propor(entrada: str, session: str) -> ProjectBrain | str:
    """
    Resolve QUAL projeto propor um produto. Reaproveita o foco existente
    (mesmo mecanismo de tools/opportunity_tools.py, persistido e isolado por
    `session`). Se nao houver foco ainda e a mensagem pedir explicitamente
    "uma das minhas melhores oportunidades", dispara a investigacao primeiro
    (reaproveitando investigar_oportunidade -- nao duplica logica de
    consulta ao ScalaFlow).

    IMPORTANTE: um ID/link novo na mensagem SEMPRE tem prioridade sobre um
    foco antigo -- senao, mandar um link novo enquanto ja existe foco de uma
    oportunidade anterior seria ignorado silenciosamente (bug corrigido na
    revisao da Fase 3).
    """
    from tools.opportunity_tools import detectar_ad_library_id

    foco = get_foco_atual(session)
    store = get_project_brain_store()

    if foco and detectar_ad_library_id(entrada) is None:
        brain = store.load(foco)
        if brain:
            return brain

    # Sem foco (ou foco perdido): dispara uma investigacao nova, igual ao
    # Opportunity Analyst faria para "minha melhor oferta".
    resultado = investigar_oportunidade(entrada, session)
    if isinstance(resultado, str) and "Projeto:" not in resultado:
        return resultado  # erro/aviso da propria investigacao (ex.: Supabase fora do ar)

    novo_foco = get_foco_atual(session)
    if not novo_foco:
        return "Não consegui identificar uma oportunidade para propor um produto."
    brain = store.load(novo_foco)
    if not brain:
        return "Não consegui recuperar a oportunidade investigada para propor um produto."
    return brain


def _formatar_proposta(brain: ProjectBrain) -> str:
    bp = brain.blueprint
    if not bp:
        return "Não há proposta de produto para este projeto ainda."

    # So realmente "sem nada" quando nao ha candidato NENHUM (nem headline,
    # copy, nicho ou score pra raciocinar em cima). Ter POUCA evidencia para
    # RECOMENDAR nao e o mesmo que nao ter evidencia pra levantar hipoteses.
    if not bp.candidates:
        linhas = [
            "🧩 PRODUTO: EVIDÊNCIA INSUFICIENTE",
            "",
            f"Projeto: {brain.project_id}",
            "Não tenho evidência suficiente nem para formular hipóteses de produto.",
        ]
        if bp.missing_evidence:
            linhas.append("Falta: " + "; ".join(bp.missing_evidence))
        return "\n".join(linhas)

    if bp.decision_status == "PENDING_APPROVAL" and bp.recommended_product_type:
        return _formatar_recomendacao(brain, bp)

    return _formatar_hipoteses(brain, bp)


def _formatar_recomendacao(brain: ProjectBrain, bp) -> str:
    """Ha evidencia forte o bastante pra recomendar UM formato (nao so
    hipoteses) -- so aqui que faz sentido pedir aprovacao."""
    linhas = [
        "🧩 PROPOSTA DE PRODUTO",
        "",
        f"Produto/oportunidade: {brain.identidade.name}",
        f"Formato recomendado: {bp.recommended_product_type}",
    ]
    if bp.alternative_product_types:
        linhas.append("Alternativas: " + ", ".join(bp.alternative_product_types))
    if bp.reasoning_summary:
        linhas.append(f"Motivo: {bp.reasoning_summary}")
    if bp.risks:
        linhas.append("Riscos: " + "; ".join(bp.risks))
    linhas.append(f"Status: {bp.decision_status}")
    linhas.append("")
    linhas.append(f"Projeto: {brain.project_id}")
    linhas.append('Responda "Aprovado" para eu iniciar o plano de produção, ou "Não gostei, quero outra alternativa".')
    return "\n".join(linhas)


def _formatar_hipoteses(brain: ProjectBrain, bp) -> str:
    """Evidencia ainda nao justifica UMA recomendacao -- mostra os
    candidatos como HIPOTESES, deixando explicito que nenhuma foi aprovada
    (pedido explicito da correcao pos-teste real da Fase 3)."""
    linhas = [
        "🧪 HIPÓTESES DE PRODUTO (nenhuma aprovada ainda)",
        "",
        f"Projeto: {brain.project_id}",
        "",
    ]
    for i, c in enumerate(bp.candidates, start=1):
        linhas.append(f"{i}. {c['product_type'].upper()} — confiança: {c.get('confidence') or '?'}")
        if c.get("inference_note"):
            linhas.append(f"   ⚠️ {c['inference_note']}")
        if c.get("audience_hypothesis"):
            linhas.append(f"   Público (hipótese): {c['audience_hypothesis']}")
        if c.get("problem"):
            linhas.append(f"   Problema: {c['problem']}")
        if c.get("why_it_fits"):
            linhas.append(f"   Por que pode fazer sentido: {c['why_it_fits']}")
        if c.get("functional_proposal"):
            linhas.append(f"   Proposta funcional: {c['functional_proposal']}")
        if c.get("production_difficulty"):
            linhas.append(f"   Dificuldade de produção: {c['production_difficulty']}")
        if c.get("estimated_speed_to_mvp"):
            linhas.append(f"   Velocidade estimada até o MVP (estimativa, não fato): {c['estimated_speed_to_mvp']}")
        if c.get("monetization"):
            linhas.append(f"   Monetização possível: {', '.join(c['monetization'])}")
        if c.get("supporting_evidence"):
            linhas.append(f"   Evidências a favor: {'; '.join(c['supporting_evidence'])}")
        if c.get("risks"):
            linhas.append(f"   Riscos: {'; '.join(c['risks'])}")
        if c.get("missing_evidence"):
            linhas.append(f"   Evidências ainda ausentes: {'; '.join(c['missing_evidence'])}")
        linhas.append("")

    linhas.append("São hipóteses de produto. Nenhuma foi aprovada.")
    if bp.reasoning_summary:
        linhas.append(f"Observação: {bp.reasoning_summary}")
    tipos = ", ".join(c["product_type"] for c in bp.candidates)
    linhas.append(f'Para aprovar uma delas, diga por ex. "Aprovo o formato {bp.candidates[0]["product_type"]}" (opções: {tipos}).')
    linhas.append(f"Status: {bp.decision_status}")
    return "\n".join(linhas)


def _listar_pendentes() -> str:
    store = get_project_brain_store()
    pendentes = [
        b for b in store.list_all()
        if b.blueprint and b.blueprint.decision_status == "PENDING_APPROVAL"
    ]
    if not pendentes:
        return "Nenhum projeto aguardando sua aprovação no momento."
    linhas = ["📋 PROJETOS AGUARDANDO APROVAÇÃO", ""]
    for b in pendentes:
        linhas.append(f"- {b.identidade.name} ({b.project_id}) -> {b.blueprint.recommended_product_type}")
    return "\n".join(linhas)


def gerenciar_produto(entrada: str, session: str = "") -> str:
    """Ponto de entrada unico da Tool (propor / explicar / alternativas /
    listar pendentes / aprovar / rejeitar).

    `session` (Fase 3): identifica canal+usuario. O foco (qual oportunidade/
    projeto esta sendo discutido) e persistido e isolado POR sessao -- ver
    `tools/opportunity_tools.py:UserFocusStore`. Sem `session`, o
    comportamento e o de sempre pedir pra indicar a oportunidade (nunca
    inventa qual e).
    """
    texto = (entrada or "").strip().lower()
    if not texto:
        return ""

    if _contains_any(texto, _PALAVRAS_PENDENTES):
        return _listar_pendentes()

    foco = get_foco_atual(session)
    store = get_project_brain_store()
    brain_focado = store.load(foco) if foco else None

    if brain_focado and brain_focado.blueprint:
        if _contains_any(texto, _PALAVRAS_APROVACAO, _FRASES_APROVACAO):
            return _aprovar(brain_focado, texto)
        if _contains_any(texto, _PALAVRAS_REJEICAO, _FRASES_REJEICAO):
            return _rejeitar(brain_focado, texto)
        if _contains_any(texto, _PALAVRAS_EXPLICAR, _FRASES_EXPLICAR):
            return _formatar_proposta(brain_focado)
        # EXPANSAO (Fase 4): checada ANTES do "ver alternativas ja
        # calculadas" -- um pedido de EXPANDIR (formatos novos/diferentes +
        # comparacao) nunca pode ser respondido com o cache de "so mostrar o
        # que ja existe" (bug real corrigido: ver `_PALAVRAS_EXPANSAO`).
        if brain_focado.blueprint.candidates and _eh_pedido_expansao(
            texto, {c["product_type"] for c in brain_focado.blueprint.candidates},
        ):
            return _expandir(brain_focado, entrada)
        if _contains_any(texto, _PALAVRAS_ALTERNATIVAS, _FRASES_ALTERNATIVAS):
            if brain_focado.blueprint.candidates:
                # ja temos candidatos calculados -- reexibe SEM gastar de
                # novo no OpenRouter (cost-first).
                return _formatar_proposta(brain_focado)
            # ainda nao exploramos nada pra esse projeto -- cai no default
            # abaixo, que chama o LLM pela primeira vez.

    # Default: propor/explorar um produto (para o foco atual, ou
    # investigando uma oportunidade nova se nao houver foco). Sempre tenta
    # popular hipoteses (`candidates`); so vira uma recomendacao unica
    # quando a evidencia justificar (ver core/product_architect.py).
    brain = _resolver_projeto_para_propor(texto, session)
    if isinstance(brain, str):
        return brain

    llm = _get_llm_inteligente()
    blueprint = propor_produto(brain, llm=llm)
    brain.blueprint = blueprint
    resumo_run = (
        f"Propos formato '{blueprint.recommended_product_type}'"
        if blueprint.recommended_product_type
        else f"Explorou {len(blueprint.candidates)} candidato(s) de produto"
    )
    brain.registrar_run("product_architect", resumo_run)
    store.save(brain)
    set_foco_atual(session, brain.project_id)
    return _formatar_proposta(brain)


def _aprovar(brain: ProjectBrain, texto: str) -> str:
    bp = brain.blueprint
    store = get_project_brain_store()

    if not bp.recommended_product_type:
        # Estamos em modo HIPOTESES (nenhuma recomendacao unica ainda) --
        # nunca adivinha qual candidato o usuario quis aprovar. So aceita
        # se ele citar o nome do formato explicitamente na propria mensagem.
        candidato_citado = None
        for c in bp.candidates:
            tipo = c["product_type"]
            if tipo in texto or tipo.replace("_", " ") in texto:
                candidato_citado = tipo
                break
        if not candidato_citado:
            tipos = ", ".join(c["product_type"] for c in bp.candidates)
            return (
                "Ainda são só hipóteses -- não tenho uma recomendação única pra aprovar. "
                f'Diga qual formato quer aprovar, por ex. "Aprovo o formato {bp.candidates[0]["product_type"] if bp.candidates else "..."}"'
                f" (opções: {tipos})."
            )
        outras = [c["product_type"] for c in bp.candidates if c["product_type"] != candidato_citado]
        bp.recommended_product_type = candidato_citado
        bp.alternative_product_types = outras
        # Promove os campos ricos do candidato citado pro blueprint -- sem
        # isso, aprovar por nome (modo hipoteses) nunca preenchia
        # product_concept/target_audience/etc., e o artefato/plano de
        # negocio saiam genericos mesmo com uma analise especifica ja feita
        # (bug real, Fase 4).
        candidato_dict = next(c for c in bp.candidates if c["product_type"] == candidato_citado)
        promover_candidato_para_blueprint(bp, candidato_dict)

    bp.decision_status = "APPROVED"
    brain.registrar_aprovacao("APPROVED")
    store.save(brain)

    try:
        plano = preparar_plano_producao(brain)
    except ProductFactoryError as exc:
        return f"Aprovação registrada, mas a Product Factory recusou: {exc}"

    bp.decision_status = "IN_PRODUCTION"
    store.save(brain)

    linhas = [
        "✅ APROVADO",
        "",
        f"Iniciando plano de produção para: {bp.recommended_product_type}",
        "",
        "Passos previstos:",
    ]
    for passo in plano.passos:
        marcador = {"concluido": "✔", "planejado": "📋", "pendente": "…", "indisponivel": "✗"}[passo.status]
        linhas.append(f"{marcador} {passo.nome} ({passo.status})")
    concluidos = [p.resultado for p in plano.passos if p.status == "concluido" and p.resultado]
    if concluidos:
        linhas.append("")
        linhas.append("Artefato gerado:")
        linhas.append(concluidos[0])
    planejados = [p.resultado for p in plano.passos if p.status == "planejado" and p.resultado]
    if planejados:
        linhas.append("")
        linhas.append("Especificação planejada (NOT_CONNECTED = sem execução automática, não sem planejamento):")
        linhas.append(planejados[0])
    linhas.append("")
    linhas.append(f"Projeto: {brain.project_id} | Status: {bp.decision_status}")
    return "\n".join(linhas)


def _rejeitar(brain: ProjectBrain, motivo_texto: str) -> str:
    store = get_project_brain_store()
    brain.registrar_aprovacao("REJECTED", motivo_texto)
    bp = promover_proxima_alternativa(brain.blueprint, motivo_texto)
    brain.blueprint = bp
    store.save(brain)

    if bp.decision_status == "NEEDS_RESEARCH":
        return (
            "Entendido, descartei essa alternativa. Não tenho mais alternativas já "
            "analisadas para essa oportunidade -- preciso investigar de novo para "
            f"propor algo novo.\n\nProjeto: {brain.project_id}"
        )
    return _formatar_proposta(brain)


def _expandir(brain: ProjectBrain, pedido_original: str) -> str:
    """
    Expande as hipoteses ja existentes com formatos NOVOS/diferentes e
    compara com as ja calculadas -- SEMPRE chama o LLM de novo (esta e uma
    intencao diferente de "so mostrar o que ja existe", entao o cache de
    `_PALAVRAS_ALTERNATIVAS` nao se aplica aqui). Nunca apaga hipoteses
    anteriores, nunca aprova nada automaticamente.
    """
    store = get_project_brain_store()
    llm = _get_llm_inteligente()
    blueprint = expandir_candidatos(brain, pedido_original, llm=llm)
    brain.blueprint = blueprint
    brain.registrar_run(
        "product_architect",
        f"Expandiu hipoteses de produto ({len(blueprint.candidates)} candidato(s) no total)",
    )
    store.save(brain)
    return _formatar_proposta(brain)


def get_tools() -> list[Tool]:
    return [
        Tool(
            "product_architect",
            "Propoe formato de produto para uma oportunidade investigada, "
            "gerencia aprovacao/rejeicao e aciona a Product Factory quando aprovado",
            [
                "produto", "produtos", "blueprint", "propos", "proposta",
                "formato", "arquitet",
                "alternativas", "alternativa", "opcoes", "opções",
                "aprovacao", "aprovação", "aguardando", "pendentes", "pendente",
                # continuacao (so relevante quando o ultimo agente ja era o
                # product_architect -- ver agents/orchestrator.py). Inclui
                # tambem as FRASES (nao so palavras soltas), porque
                # Tool.matches faz substring-check em cada item da lista --
                # sem isso, "Pode criar." sozinho nao bateria com nenhuma
                # palavra solta daqui (mesmo bug ja corrigido na Fase 2 para
                # tools/opportunity_tools.py).
                "aprovado", "aprovada", "aprovo", "autorizado", "autorizo",
                "confirmado", "confirmo", "rejeitado", "rejeitada", "rejeito",
                "porque", "motivo", "justificativa",
                "pode criar", "pode seguir", "pode produzir", "pode comecar",
                "pode começar", "bora criar", "nao gostei", "não gostei",
                "quero outra", "outra alternativa", "por que",
                # Expansao de hipoteses (Fase 4) -- superset das frases/
                # palavras de `_PALAVRAS_EXPANSAO`/`_FRASES_EXPANSAO`.
                "mini-app", "miniapp", "ferramenta", "sistema", "calculadora",
                "gerador", "quiz", "dashboard", "extensao", "extensão",
                "agente", "micro-saas", "microsaas",
                "novas alternativas", "outras alternativas",
                "alternativas diferentes", "mais interativ", "diferenciad",
                "alem dessas", "além dessas", "compare com as hipoteses",
                "compare com as hipóteses",
            ],
            gerenciar_produto,
            # Reconhece um link/ID da Meta Ads Library em qualquer mensagem
            # (ex.: "aqui esta o anuncio: <link>, que produto criamos?"),
            # mesmo se nenhuma palavra-chave acima aparecer.
            matcher=lambda t: _detectar_ad_library_id_lazy(t) is not None,
        ),
    ]


def _detectar_ad_library_id_lazy(texto: str) -> str | None:
    from tools.opportunity_tools import detectar_ad_library_id

    return detectar_ad_library_id(texto)
