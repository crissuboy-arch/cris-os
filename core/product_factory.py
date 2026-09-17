"""
Product Factory — FUNDACAO (Fase 3).

Recebe SOMENTE um Product Blueprint com `decision_status == "APPROVED"` e
monta um plano inicial de producao. Nesta fase NAO produz os ativos de
verdade (imagem, video, landing page, mini-app...) -- so:
  1. valida o gate de aprovacao (recusa qualquer coisa que nao esteja
     APPROVED -- "a Product Factory nao deve sair produzindo tudo
     automaticamente antes da aprovacao");
  2. monta um plano de producao (passos, cada um mapeado pra uma capability
     do Tool Registry, marcado disponivel/indisponivel);
  3. executa UM artefato textual simples de verdade (um brief do produto),
     via Tool Registry (`COPY_GENERATOR`);
  4. persiste tudo no Project Brain (nao cria memoria paralela).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.tool_registry import (
    CODE_GENERATOR,
    COPY_GENERATOR,
    DRIVE_STORAGE,
    GITHUB,
    IMAGE_GENERATOR,
    LANDING_PAGE_BUILDER,
    MINI_APP_BUILDER,
    VERCEL,
    VIDEO_GENERATOR,
    ToolRegistry,
)
from memory.project_brain import ProductBlueprint, ProjectBrain

# Passos previstos de um lancamento completo (visao -- Fase 3 so executa o
# primeiro de verdade). Cada um mapeia pra uma capability do Tool Registry.
_PASSOS_PREVISTOS = [
    ("Brief/copy inicial do produto", COPY_GENERATOR),
    ("Identidade visual (cores/fontes/logo)", IMAGE_GENERATOR),
    ("Mini-app / protótipo funcional", MINI_APP_BUILDER),
    ("Landing page", LANDING_PAGE_BUILDER),
    ("Código/integrações técnicas", CODE_GENERATOR),
    ("Vídeo/criativos", VIDEO_GENERATOR),
    ("Armazenamento de assets", DRIVE_STORAGE),
    ("Repositório de código", GITHUB),
    ("Publicação/deploy", VERCEL),
]


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PassoProducao:
    nome: str
    capability: str
    disponivel: bool
    status: str  # "concluido" | "pendente" | "indisponivel"
    resultado: str | None = None


@dataclass
class PlanoProducao:
    project_id: str
    product_type: str
    passos: list[PassoProducao] = field(default_factory=list)
    artefatos_gerados: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_agora)


class ProductFactoryError(Exception):
    """Recusa explicita da Product Factory (gate de aprovacao, etc.)."""


def gerar_copy_simples(blueprint: ProductBlueprint, llm=None) -> str:
    """
    Artefato textual simples: um brief curto do produto. Usa OpenRouter
    (tier ECONOMICO, se `llm` for passado) para redigir; sem LLM, monta um
    template deterministico direto dos campos do blueprint -- nunca inventa
    dado que o blueprint nao tem.
    """
    campos = {
        "tipo": blueprint.recommended_product_type or "(não definido)",
        "conceito": blueprint.product_concept or "(não definido)",
        "valor_central": blueprint.core_value or "(não definido)",
        "publico": blueprint.target_audience or "(não definido)",
        "diferenciacao": blueprint.differentiation or "(não definida)",
        "mvp": blueprint.mvp_scope or "(não definido)",
    }

    if llm is not None:
        try:
            resp = llm.chat([
                {
                    "role": "system",
                    "content": (
                        "Escreva um brief curto (max 4 frases) de um produto, em "
                        "portugues do Brasil, usando SOMENTE os dados fornecidos. "
                        "NAO invente nenhum dado (preco, prazo, numero) que nao "
                        "esteja aqui. Se um campo for '(não definido)', apenas "
                        "omita esse ponto, nao invente um valor pra ele."
                    ),
                },
                {"role": "user", "content": str(campos)},
            ])
            texto = (resp.content or "").strip()
            if texto:
                return texto
        except Exception:
            pass  # cai no template deterministico abaixo

    return (
        f"Produto proposto: {campos['tipo']}.\n"
        f"Conceito: {campos['conceito']}.\n"
        f"Valor central: {campos['valor_central']}.\n"
        f"Público-alvo: {campos['publico']}.\n"
        f"Diferenciação: {campos['diferenciacao']}.\n"
        f"Escopo do MVP: {campos['mvp']}."
    )


def criar_plano_inicial(
    brain: ProjectBrain,
    registry: ToolRegistry,
    llm_economico=None,
) -> PlanoProducao:
    """
    GATE: recusa (levanta ProductFactoryError) se o blueprint nao existir ou
    nao estiver APPROVED. So chega aqui depois de aprovacao humana explicita
    -- ver tools/product_architect_tools.py.
    """
    blueprint = brain.blueprint
    if not blueprint:
        raise ProductFactoryError("Nao ha Product Blueprint neste projeto para produzir.")
    if blueprint.decision_status != "APPROVED":
        raise ProductFactoryError(
            f"Blueprint nao esta aprovado (status atual: {blueprint.decision_status}). "
            "A Product Factory so inicia producao apos aprovacao explicita."
        )

    passos: list[PassoProducao] = []
    artefatos: list[str] = []
    for nome, capability in _PASSOS_PREVISTOS:
        disponivel = registry.disponivel(capability)
        if disponivel and capability == COPY_GENERATOR:
            resultado = registry.executar(capability, blueprint=blueprint, llm=llm_economico)
            passos.append(PassoProducao(nome, capability, True, "concluido", resultado))
            artefatos.append(resultado)
        elif disponivel:
            passos.append(PassoProducao(nome, capability, True, "pendente"))
        else:
            passos.append(PassoProducao(nome, capability, False, "indisponivel"))

    return PlanoProducao(
        project_id=brain.project_id,
        product_type=blueprint.recommended_product_type or "(não definido)",
        passos=passos,
        artefatos_gerados=artefatos,
    )
