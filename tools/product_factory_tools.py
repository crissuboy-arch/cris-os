"""
Ferramentas do agente Product Factory (Fase 4).

IMPORTANTE: este modulo NAO reimplementa a Product Factory -- `core/
product_factory.py` (Fase 3) continua sendo a UNICA logica de decisao de
passos/execucao. Este modulo so expoe essa logica ja existente como comando
direto do Telegram ("prepare o plano de producao", "quais artefatos
precisamos"), e persiste o resultado no Project Brain (Fase 4 -- Fase 3 so
mostrava o plano uma vez no chat, sem guardar).

`preparar_plano_producao` e reaproveitada tambem por
`tools/product_architect_tools.py:_aprovar` (o fluxo automatico que ja
disparava a Product Factory logo apos a aprovacao humana) -- uma unica
implementacao, dois pontos de entrada (automatico apos aprovar, ou sob
demanda depois).
"""

from __future__ import annotations

import logging

from config.settings import settings
from core.artifact_manifest import formatar_manifesto_get_current, gerar_manifest
from core.product_factory import (
    PlanoProducao,
    ProductFactoryError,
    criar_plano_inicial,
    persistir_plano,
)
from core.tool_registry import criar_registry_padrao
from memory.project_brain import ProjectBrain
from tools.base import Tool
from tools.opportunity_tools import get_foco_atual, get_project_brain_store

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

logger = logging.getLogger(__name__)

_PALAVRAS_ARTEFATOS = frozenset({
    "artefatos", "entregaveis", "entregáveis", "manifest", "manifesto",
})
_FRASES_ARTEFATOS = (
    "quais artefatos", "o que precisa ser produzido",
    "qual o status do projeto", "qual é o status do projeto",
    "mostre a estrutura atual do projeto", "estrutura atual do projeto",
)

_registry = criar_registry_padrao()


def _headers_ok() -> bool:
    return bool(settings.OPENROUTER_API_KEY) and settings.OPENROUTER_API_KEY != "COLE_SUA_CHAVE_AQUI"


_llm_economico_cache = None


def _get_llm_economico():
    """Mesmo padrao de `tools/product_architect_tools.py` (duplicado em
    pequeno de proposito -- evita acoplar `tools/` a `core/runtime.py`, que e
    a composition root)."""
    global _llm_economico_cache
    if _llm_economico_cache is None:
        if not _headers_ok():
            return None
        try:
            from llm.openrouter import MODELO_PADRAO_ECONOMICO, OpenRouterProvider

            provider = OpenRouterProvider(
                api_key=settings.OPENROUTER_API_KEY,
                model=settings.OPENROUTER_MODEL_ECONOMICO or MODELO_PADRAO_ECONOMICO,
                base_url=settings.OPENROUTER_BASE_URL,
                timeout=settings.OPENROUTER_TIMEOUT,
                tier="economico",
            )
            _llm_economico_cache = provider if provider.is_alive() else None
        except Exception as exc:
            logger.warning("=== [PRODUCT_FACTORY] Falha ao configurar OpenRouter: %s ===", exc)
            _llm_economico_cache = None
    return _llm_economico_cache


def _contains_any(texto: str, palavras: frozenset[str], frases: tuple = ()) -> bool:
    """CORRECAO de bug real (5o round): faltava o check de SUBSTRING contra
    `palavras` -- so existia o check por token exato (`tokens & palavras`),
    que falha com qualquer pontuacao colada na palavra (ex.: "manifesto."
    com ponto final, "projeto?" com interrogacao -- exatamente a frase real
    do teste do Telegram). Agora espelha a mesma logica de duas camadas ja
    usada em `Tool.matches()`/`agents/orchestrator.py`."""
    tokens = set(texto.split())
    if tokens & palavras:
        return True
    if any(p in texto for p in palavras):
        return True
    return any(f in texto for f in frases)


def _eh_pedido_status_projeto(texto: str) -> bool:
    """"status"/"estrutura" + "projeto" juntos (qualquer fraseado) -- ver
    `agents/orchestrator.py:_eh_comando_product_factory` (mesma logica,
    duplicada aqui em pequeno pra servir de `Tool.matcher`)."""
    texto_lower = texto.lower()
    return ("status" in texto_lower or "estrutura" in texto_lower) and "projeto" in texto_lower


def preparar_plano_producao(brain: ProjectBrain) -> PlanoProducao:
    """
    Ponto unico de preparacao do plano de producao (Fase 4): chama a Product
    Factory ja existente (Fase 3, sem duplicar), persiste o resultado no
    Project Brain (`brain.production_plan`) e deriva o Artifact Manifest
    (`brain.artifact_manifest`) -- NAO salva (quem chama decide quando salvar,
    igual ao padrao ja usado para `brain.blueprint`).
    """
    plano = criar_plano_inicial(brain, _registry, llm_economico=_get_llm_economico())
    persistir_plano(brain, plano)
    brain.artifact_manifest = gerar_manifest(brain)
    return plano


def _formatar_plano(brain: ProjectBrain, plano: PlanoProducao | None = None) -> str:
    pp = brain.production_plan
    if not pp:
        return "Ainda não preparei um plano de produção para este projeto."
    linhas = [
        "🏭 PLANO DE PRODUÇÃO",
        "",
        f"Produto/formato: {pp.product_type}",
        "",
        "Passos previstos:",
    ]
    marcador = {"concluido": "✔", "planejado": "📋", "pendente": "…", "indisponivel": "✗"}
    for passo in pp.steps:
        linhas.append(f"{marcador.get(passo['status'], '?')} {passo['nome']} ({passo['status']})")
    concluidos = [p["resultado"] for p in pp.steps if p["status"] == "concluido" and p.get("resultado")]
    if concluidos:
        linhas.append("")
        linhas.append("Artefato gerado:")
        linhas.append(concluidos[0])
    planejados = [p for p in pp.steps if p["status"] == "planejado" and p.get("resultado")]
    if planejados:
        linhas.append("")
        linhas.append("Especificação planejada (NOT_CONNECTED = sem execução automática, não sem planejamento):")
        linhas.append(planejados[0]["resultado"])
    if pp.dependencies:
        linhas.append("")
        linhas.append("Dependências/pendências: " + "; ".join(pp.dependencies))
    linhas.append("")
    linhas.append(f"Projeto: {brain.project_id} | Status da produção: {pp.status}")
    return "\n".join(linhas)


def get_current_project_manifest(brain: ProjectBrain) -> str:
    """
    GET_CURRENT_PROJECT_MANIFEST (Fase 4 -- correcao pos-teste real): leitura
    PURA e deterministica do manifesto atual. ZERO LLM, ZERO OpenRouter,
    ZERO regeneracao de plano, ZERO alteracao no projeto -- so le o
    `ProjectBrain` ja carregado em memoria e formata. `gerar_manifest` e uma
    funcao pura (sem I/O nenhum); esta funcao tampouco salva nada de volta
    no store -- correcao de bug real: a versao anterior chamava
    `store.save(brain)` a cada leitura, o que a pessoa relatou como uma
    "alteracao no projeto" indesejada so por PERGUNTAR o manifesto.

    Funciona mesmo sem `production_plan` ainda preparado -- as pastas
    correspondentes simplesmente aparecem "vazias", nunca bloqueia a
    leitura do que ja existe (blueprint/business plan)."""
    manifest = gerar_manifest(brain)
    return formatar_manifesto_get_current(manifest)


def gerenciar_producao(entrada: str, session: str = "") -> str:
    """Ponto de entrada unico da Tool (preparar / mostrar plano / listar
    artefatos). So funciona sobre um Product Blueprint ja APROVADO -- mesmo
    gate da Product Factory desde a Fase 3 (nunca produz sem aprovacao)."""
    texto = (entrada or "").strip().lower()
    if not texto:
        return ""

    foco = get_foco_atual(session)
    if not foco:
        return (
            "Não sei a qual projeto você se refere. Investigue uma "
            "oportunidade e aprove um formato de produto primeiro."
        )
    store = get_project_brain_store()
    brain = store.load(foco)
    if not brain:
        return "Não consegui recuperar o projeto em foco."

    # `esta_aprovado()` (nao `== "APPROVED"` direto) -- correcao de bug real:
    # apos aprovar, `decision_status` avanca pra "IN_PRODUCTION" no mesmo
    # fluxo; checar so "APPROVED" bloqueava "mostre o plano de producao"
    # mesmo com a aprovacao ja persistida.
    if not brain.blueprint or not brain.blueprint.esta_aprovado():
        return (
            "Esse produto ainda não foi aprovado. Primeiro precisamos "
            "aprovar o Product Blueprint (Product Architect) antes de "
            "preparar o plano de produção."
        )

    if _contains_any(texto, _PALAVRAS_ARTEFATOS, _FRASES_ARTEFATOS) or _eh_pedido_status_projeto(texto):
        # GET_CURRENT_PROJECT_MANIFEST -- leitura pura, ZERO LLM, ZERO
        # escrita no Project Brain (ver docstring da funcao).
        return get_current_project_manifest(brain)

    if brain.production_plan:
        # Ja preparado -- reexibe sem rodar a Product Factory de novo
        # (cost-first: nao regenera artefato/manifest a toa).
        return _formatar_plano(brain)

    try:
        preparar_plano_producao(brain)
    except ProductFactoryError as exc:
        return f"A Product Factory recusou: {exc}"
    brain.registrar_run("product_factory", f"Preparou plano de produção para '{brain.blueprint.recommended_product_type}'")
    store.save(brain)
    return _formatar_plano(brain)


def get_tools() -> list[Tool]:
    return [
        Tool(
            "product_factory",
            "Prepara e mostra o plano de producao (entregaveis por tipo de "
            "produto) e o artifact manifest de um produto ja aprovado",
            [
                "producao", "produção", "artefatos", "entregaveis",
                "entregáveis", "manifest", "manifesto",
                # Precisa ser um SUPERSET das frases que o orchestrator
                # reconhece (`_PRODUCT_FACTORY_FRASES`) -- senao o agente ja
                # escolhido cai no LLM generico por a propria Tool nao "achar"
                # a mensagem (mesmo bug ja corrigido 3x na Fase 3). "produzido"
                # NAO e substring de "produção" -- precisa entrar explicitamente.
                "produzido", "produzir", "o que precisa ser produzido",
                "plano de producao", "plano de produção", "quais artefatos",
                "manifesto atual", "manifesto deste projeto",
                "manifesto do projeto", "mostre o manifesto",
                "mostre somente o manifesto",
                "qual o status do projeto", "qual é o status do projeto",
                "mostre a estrutura atual do projeto",
                "estrutura atual do projeto",
            ],
            gerenciar_producao,
            # "status"/"estrutura" + "projeto" juntos (qualquer fraseado) --
            # mesma logica de co-ocorrencia do orchestrator
            # (`_eh_comando_product_factory`), reaproveitada aqui via
            # `matcher` pra Tool.matches() reconhecer variacoes como "qual o
            # status DESTE projeto" que nao batem nenhuma frase fixa da
            # lista acima.
            matcher=_eh_pedido_status_projeto,
        ),
    ]
