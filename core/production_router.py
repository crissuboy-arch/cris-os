"""
Production Router (ExecutorRouter) -- decide QUAL EXECUTOR ESPECIALIZADO
deveria processar um requisito de ativo (`required_assets`), sem o Cris OS
nunca produzir o ativo ele mesmo.

Duas etapas SEPARADAS, de propósito (pedido explícito da missão -- "não
decidir apenas por string frágil"):
  1. `normalizar_asset_type`: texto livre -> vocabulário FECHADO
     (`PRODUCTION_ASSET_TYPES_VALIDOS`). Só aqui existe interpretação de
     texto -- 100% determinístico (busca por palavras-chave), sem LLM, sem
     custo, sem ambiguidade escondida.
  2. `resolver_executor`: asset_type já normalizado -> executor_type
     (`PRODUCTION_EXECUTOR_TYPES_VALIDOS`), por uma tabela FIXA -- nenhuma
     lógica condicional espalhada, nenhuma adivinhação.

NENHUM executor (PageForge, Pink Logic, Criador-de-App, ForgeHub, NEXORA) é
chamado por este módulo -- ele só CLASSIFICA. Ver `core/executor_adapter.py`
para o contrato de dispatch (ainda sem nenhuma implementação real).
"""

from __future__ import annotations

from memory.project_brain import PRODUCTION_EXECUTOR_TYPES_VALIDOS

# Ordem IMPORTA: grupos mais específicos primeiro, para evitar colisão de
# palavra-chave (ex.: "landing page com prova SOCIAL" nunca pode cair em
# MARKETING_MATERIAL só porque contém "social" -- LANDING_PAGE é checado
# antes). Cada item: (palavras-chave, asset_type).
_REGRAS_NORMALIZACAO: tuple[tuple[tuple[str, ...], str], ...] = (
    (("mini_app", "mini-app", "mini app", "aplicativo", "app", "software", "sistema web", "web app"), "APP"),
    (("landing_page", "landing page", "sales page", "página de vendas", "pagina de vendas", "página de venda", "pagina de venda"), "LANDING_PAGE"),
    (("ebook", "e-book", "e book"), "EBOOK"),
    (("carrossel", "carousel"), "CAROUSEL"),
    (("empacotamento", "distribuição", "distribuicao", "package", "embalagem digital"), "DISTRIBUTION"),
    (("crm", "lead", "follow-up", "follow up", "acompanhamento de clientes"), "CRM"),
    (
        ("criativo", "creative", "conteúdo", "conteudo", "carrossel", "post", "material de marketing",
         "materiais de marketing", "marketing digital", "social media", "mídia social", "midia social",
         "marketing_material", "social_content"),
        "MARKETING_MATERIAL",
    ),
)

# Mapeamento FIXO asset_type -> executor_type (Seção 3 da missão). "UNKNOWN"
# nunca aparece aqui de propósito -- cai no default abaixo.
_EXECUTOR_POR_ASSET_TYPE: dict[str, str] = {
    "APP": "APP_BUILDER",
    "LANDING_PAGE": "PAGEFORGE",
    "EBOOK": "PINK_LOGIC",
    "CAROUSEL": "PINK_LOGIC",
    "MARKETING_MATERIAL": "PINK_LOGIC",
    "DISTRIBUTION": "FORGEHUB",
    "CRM": "NEXORA",
}


def normalizar_asset_type(requisito: str) -> str:
    """
    Classifica um requisito em texto livre (ex.: "Landing page com prova
    social") num `asset_type` do vocabulário fechado. `UNKNOWN` quando
    nenhuma palavra-chave conhecida bate -- NUNCA adivinha, nunca usa IA.
    """
    texto = (requisito or "").strip().lower()
    if not texto:
        return "UNKNOWN"
    for palavras, asset_type in _REGRAS_NORMALIZACAO:
        if any(p in texto for p in palavras):
            return asset_type
    return "UNKNOWN"


def resolver_executor(asset_type: str) -> str:
    """`asset_type` já normalizado -> `executor_type`. `NEEDS_ROUTING` para
    qualquer `asset_type` sem executor conhecido (inclui `UNKNOWN`) -- nunca
    escolhe um executor por padrão/chute."""
    executor = _EXECUTOR_POR_ASSET_TYPE.get(asset_type, "NEEDS_ROUTING")
    assert executor in PRODUCTION_EXECUTOR_TYPES_VALIDOS
    return executor


def classificar_requisito(requisito: str) -> tuple[str, str]:
    """Atalho: devolve `(asset_type, executor_type)` para um requisito em
    texto livre, numa única chamada."""
    asset_type = normalizar_asset_type(requisito)
    return asset_type, resolver_executor(asset_type)
