"""
Tool Registry — catalogo de ferramentas de PRODUCAO que a Product Factory
pode usar, sem acoplar a Factory a nenhum fornecedor especifico (Fase 3).

Nao confundir com `tools/base.py:Tool` (as ferramentas dos AGENTES do
Telegram, ex.: `top_produtos_scalaflow`). Este registry e sobre ferramentas
de PRODUCAO de ativos (gerar imagem, gerar video, publicar site, etc.) --
um conceito novo desta fase.

Principio: "nao hardcodar fornecedor". A Product Factory pede uma
CAPABILITY (ex.: `COPY_GENERATOR`) e recebe quem estiver registrado para
ela -- hoje pode ser o OpenRouter, amanha pode ser outra coisa, sem mudar o
codigo da Factory.

Nesta fase, a maioria das capabilities fica **registrada mas indisponivel**
de proposito (`disponivel=False`) -- construir de verdade fica para fases
futuras. Ver docs/TOOL-REGISTRY.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# Nomes de capability conhecidos (podem crescer sem quebrar nada -- o
# registry aceita qualquer string, isto e so documentacao/autocomplete).
MINI_APP_BUILDER = "MINI_APP_BUILDER"
IMAGE_GENERATOR = "IMAGE_GENERATOR"
VIDEO_GENERATOR = "VIDEO_GENERATOR"
COPY_GENERATOR = "COPY_GENERATOR"
LANDING_PAGE_BUILDER = "LANDING_PAGE_BUILDER"
CODE_GENERATOR = "CODE_GENERATOR"
DRIVE_STORAGE = "DRIVE_STORAGE"
GITHUB = "GITHUB"
VERCEL = "VERCEL"

TODAS_AS_CAPABILITIES = (
    MINI_APP_BUILDER, IMAGE_GENERATOR, VIDEO_GENERATOR, COPY_GENERATOR,
    LANDING_PAGE_BUILDER, CODE_GENERATOR, DRIVE_STORAGE, GITHUB, VERCEL,
)


@dataclass
class ToolEntry:
    capability: str
    provider_name: str
    disponivel: bool
    executor: Callable[..., str] | None = None  # None = so cadastrado, sem implementacao
    observacao: str = ""


class ToolRegistry:
    """Registro simples {capability -> ToolEntry}. Uma capability pode ter
    no maximo um provider ativo por vez nesta fase (trocar = registrar de
    novo, sobrescrevendo)."""

    def __init__(self) -> None:
        self._entries: dict[str, ToolEntry] = {}

    def registrar(
        self,
        capability: str,
        provider_name: str,
        disponivel: bool,
        executor: Callable[..., str] | None = None,
        observacao: str = "",
    ) -> None:
        self._entries[capability] = ToolEntry(
            capability=capability, provider_name=provider_name,
            disponivel=disponivel, executor=executor, observacao=observacao,
        )

    def disponivel(self, capability: str) -> bool:
        entry = self._entries.get(capability)
        return bool(entry and entry.disponivel and entry.executor)

    def obter(self, capability: str) -> ToolEntry | None:
        return self._entries.get(capability)

    def executar(self, capability: str, **kwargs) -> str:
        """Executa a capability se disponivel; nunca lanca excecao "crua" --
        devolve uma mensagem clara se a capability nao existir/nao estiver
        pronta (a Product Factory NUNCA trava por causa disso)."""
        entry = self._entries.get(capability)
        if not entry:
            return f"Capability '{capability}' nao esta registrada no Tool Registry."
        if not entry.disponivel or not entry.executor:
            motivo = entry.observacao or "ainda nao implementada"
            return f"Capability '{capability}' registrada mas indisponivel ({motivo})."
        try:
            return entry.executor(**kwargs)
        except Exception as exc:  # nunca derruba a Factory por falha de uma tool
            return f"Falha ao executar '{capability}': {exc}"

    def listar(self) -> list[ToolEntry]:
        return list(self._entries.values())


def criar_registry_padrao() -> ToolRegistry:
    """
    Registry padrao da Product Factory nesta fase: quase tudo cadastrado
    como indisponivel de proposito (fundacao, nao construcao). O unico
    executor real e um COPY_GENERATOR textual simples via OpenRouter
    (tier ECONOMICO), usado para provar o contrato de ponta a ponta
    (pedido explicito da Fase 3: "execucao de pelo menos um artefato
    textual simples").
    """
    from core.product_factory import gerar_copy_simples

    registry = ToolRegistry()
    registry.registrar(
        COPY_GENERATOR, provider_name="openrouter", disponivel=True,
        executor=gerar_copy_simples,
        observacao="texto simples via OpenRouter (tier economico)",
    )
    registry.registrar(
        MINI_APP_BUILDER, provider_name="(nao definido)", disponivel=False,
        observacao=(
            "A Cris ja tem um criador proprio de mini-apps (prompt -> mini "
            "sistema/app/prototipo, conectavel a Supabase/Firebase). NAO "
            "integrado ainda -- falta interface/API definida. Registrado "
            "aqui so para reservar o nome da capability."
        ),
    )
    for cap in (IMAGE_GENERATOR, VIDEO_GENERATOR):
        registry.registrar(
            cap, provider_name="(nao definido)", disponivel=False,
            observacao="Assets caros (imagem/video) NAO gerados automaticamente nesta fase.",
        )
    for cap in (LANDING_PAGE_BUILDER, CODE_GENERATOR, DRIVE_STORAGE, GITHUB, VERCEL):
        registry.registrar(
            cap, provider_name="(nao definido)", disponivel=False,
            observacao="Fundacao apenas -- sem fornecedor definido nesta fase.",
        )
    return registry
