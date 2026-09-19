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

# Capabilities de PLANEJAMENTO (Fase 4) -- diferem das acima (producao de
# ATIVOS) por planejarem a ESTRUTURA comercial em torno do produto.
BUSINESS_BUILDER = "BUSINESS_BUILDER"
SALES_PAGE_PLANNER = "SALES_PAGE_PLANNER"
FUNNEL_PLANNER = "FUNNEL_PLANNER"
EMAIL_SEQUENCE_PLANNER = "EMAIL_SEQUENCE_PLANNER"
CONTENT_PLANNER = "CONTENT_PLANNER"
LAUNCH_PLANNER = "LAUNCH_PLANNER"

# Capability de PLANEJAMENTO de trafego pago (Fase 5). Diferente de
# BUSINESS_BUILDER/PRODUCT_FACTORY (agentes completos, invocados direto pelo
# orchestrator, deliberadamente NAO registrados aqui -- ver docstring de
# `criar_registry_padrao`), esta capability E registrada e EXECUTADA de
# verdade via `registry.executar(...)` por `tools/paid_traffic_tools.py`
# (pedido explicito da Fase 5) -- nao e uma capability "de mentirinha".
PAID_TRAFFIC_ARCHITECT = "PAID_TRAFFIC_ARCHITECT"

# Capability de EXECUCAO de campanha (Fase 6). Mesma excecao deliberada de
# PAID_TRAFFIC_ARCHITECT (nao BUSINESS_BUILDER/PRODUCT_FACTORY): pedido
# explicito da Fase 6 foi registra-la de verdade -- `tools/campaign_executor_tools.py`
# chama `registry.executar(CAMPAIGN_EXECUTOR, ...)` como o caminho REAL de
# geracao da especificacao (nunca executa nenhuma campanha real).
CAMPAIGN_EXECUTOR = "CAMPAIGN_EXECUTOR"

TODAS_AS_CAPABILITIES = (
    MINI_APP_BUILDER, IMAGE_GENERATOR, VIDEO_GENERATOR, COPY_GENERATOR,
    LANDING_PAGE_BUILDER, CODE_GENERATOR, DRIVE_STORAGE, GITHUB, VERCEL,
    BUSINESS_BUILDER, SALES_PAGE_PLANNER, FUNNEL_PLANNER,
    EMAIL_SEQUENCE_PLANNER, CONTENT_PLANNER, LAUNCH_PLANNER,
    PAID_TRAFFIC_ARCHITECT, CAMPAIGN_EXECUTOR,
)

# Status legivel de uma capability (Fase 4 -- pedido explicito: "cada
# capability deve indicar claramente AVAILABLE / AVAILABLE_MANUAL /
# NOT_CONNECTED"). Nao substitui `disponivel` (continua sendo o booleano que
# o resto do codigo usa para decidir se executa) -- e so uma etiqueta mais
# rica pra exibir/documentar.
STATUS_AVAILABLE = "AVAILABLE"
STATUS_AVAILABLE_MANUAL = "AVAILABLE_MANUAL"
STATUS_NOT_CONNECTED = "NOT_CONNECTED"


@dataclass
class ToolEntry:
    capability: str
    provider_name: str
    disponivel: bool
    executor: Callable[..., str] | None = None  # None = so cadastrado, sem implementacao
    observacao: str = ""
    status: str = ""  # AVAILABLE | AVAILABLE_MANUAL | NOT_CONNECTED (ver acima)
    # PLANNABLE (Fase 4 -- correcao pos-teste real): `disponivel=False`/
    # `NOT_CONNECTED` significa "nao posso EXECUTAR/CONSTRUIR automaticamente
    # com uma ferramenta externa" -- NAO significa "nao posso PLANEJAR ou
    # ESCREVER a especificacao". `plannable=True` numa capability indisponivel
    # sinaliza que a Product Factory ainda pode gerar uma especificacao/
    # brief REAL via LLM (ex.: especificacao funcional de um mini-app, brief
    # de branding, estrutura de landing page) mesmo sem builder conectado.
    plannable: bool = False

    def __post_init__(self) -> None:
        if not self.status:
            self.status = STATUS_AVAILABLE if self.disponivel else STATUS_NOT_CONNECTED


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
        status: str = "",
        plannable: bool = False,
    ) -> None:
        self._entries[capability] = ToolEntry(
            capability=capability, provider_name=provider_name,
            disponivel=disponivel, executor=executor, observacao=observacao,
            status=status, plannable=plannable,
        )

    def disponivel(self, capability: str) -> bool:
        entry = self._entries.get(capability)
        return bool(entry and entry.disponivel and entry.executor)

    def plannable(self, capability: str) -> bool:
        """True se a Product Factory pode PLANEJAR/ESPECIFICAR esta
        capability via LLM mesmo sem executor conectado (ver docstring de
        `ToolEntry.plannable`)."""
        entry = self._entries.get(capability)
        return bool(entry and entry.plannable)

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
        MINI_APP_BUILDER, provider_name="ferramenta manual da Cris", disponivel=False,
        status=STATUS_AVAILABLE_MANUAL, plannable=True,
        observacao=(
            "A Cris ja tem um criador proprio de mini-apps (prompt -> mini "
            "sistema/app/prototipo, conectavel a Supabase/Firebase). NAO "
            "integrado ainda -- falta interface/API definida. Disponivel "
            "MANUALMENTE (a Cris pode usar por fora); a Product Factory nao "
            "pode EXECUTAR/CONSTRUIR sozinha nesta fase, mas PLANEJA "
            "(especificacao funcional/prompt de build) via LLM."
        ),
    )
    # IMAGE_GENERATOR/VIDEO_GENERATOR: geracao de ASSET (pixel/frame) em si
    # nao acontece nesta fase -- mas a DIRECAO/BRIEF de branding (texto) e
    # PLANNABLE (pedido explicito da Fase 4: "BRANDING: DIRECAO/BRIEF =
    # PLANNABLE, GERACAO DE IMAGEM = NOT_CONNECTED").
    registry.registrar(
        IMAGE_GENERATOR, provider_name="(nao definido)", disponivel=False,
        plannable=True,
        observacao=(
            "Geracao real de imagem NAO acontece nesta fase. Direcao/brief "
            "de branding (cores, tom, referencias) e PLANNABLE via LLM."
        ),
    )
    registry.registrar(
        VIDEO_GENERATOR, provider_name="(nao definido)", disponivel=False,
        observacao="Assets caros (video) NAO gerados nem planejados em detalhe nesta fase.",
    )
    for cap in (LANDING_PAGE_BUILDER, CODE_GENERATOR, GITHUB):
        registry.registrar(
            cap, provider_name="(nao definido)", disponivel=False,
            plannable=True,
            observacao=(
                "Deploy/execucao automatica NAO acontece nesta fase. "
                "Copy/estrutura (landing), especificacao tecnica (codigo) "
                "e indice de documentacao sao PLANNABLE via LLM."
            ),
        )
    for cap in (DRIVE_STORAGE, VERCEL):
        registry.registrar(
            cap, provider_name="(nao definido)", disponivel=False,
            observacao="Fundacao apenas -- sem fornecedor definido nesta fase.",
        )
    # Capabilities de planejamento (Fase 4): SALES_PAGE_PLANNER/FUNNEL_PLANNER/
    # EMAIL_SEQUENCE_PLANNER/CONTENT_PLANNER/LAUNCH_PLANNER sao geradas hoje
    # INLINE, num unico calculo, pelo Business Builder (`core/business_builder.py`
    # -> `BusinessPlan.sales_page_structure/funnel_structure/email_sequence/
    # content_strategy/launch_strategy`) -- ainda nao sao capabilities
    # executaveis SEPARADAMENTE pelo Tool Registry. Registradas aqui so para
    # reservar o nome/expor a intencao futura (pedido explicito da Fase 4);
    # "Nada de capability falsa" -- por isso ficam marcadas indisponiveis.
    for cap in (SALES_PAGE_PLANNER, FUNNEL_PLANNER, EMAIL_SEQUENCE_PLANNER,
                CONTENT_PLANNER, LAUNCH_PLANNER):
        registry.registrar(
            cap, provider_name="(nao definido)", disponivel=False,
            observacao=(
                "Gerado hoje INLINE como parte do Business Plan unico "
                "(core/business_builder.py), nao como uma execucao separada "
                "desta capability. Reservado para quando isso virar uma "
                "execucao independente."
            ),
        )
    # BUSINESS_BUILDER e PRODUCT_FACTORY nao sao capabilities de PRODUCAO
    # (o que este registry cataloga) -- sao os proprios AGENTES/fases que
    # CONSOMEM este registry (ver docs/TOOL-REGISTRY.md). Registra-los aqui
    # seria uma capability "de mentirinha" (nunca executada via
    # `registry.executar`) -- por isso ficam de fora de proposito.
    #
    # PAID_TRAFFIC_ARCHITECT (Fase 5) E diferente: pedido explicito da Fase 5
    # foi registra-la de verdade -- `tools/paid_traffic_tools.py` chama
    # `registry.executar(PAID_TRAFFIC_ARCHITECT, ...)` como o caminho REAL de
    # geracao do plano (nao um wrapper cosmetico). Excecao documentada ao
    # padrao de `executor: Callable[..., str]`: o executor aqui devolve um
    # `TrafficPlan` (objeto estruturado), nao uma string -- `executar()` nao
    # forca o tipo, e o consumidor (tools/) sabe disso.
    from core.paid_traffic_architect import criar_plano_trafego

    registry.registrar(
        PAID_TRAFFIC_ARCHITECT, provider_name="openrouter", disponivel=True,
        executor=criar_plano_trafego,
        observacao="planejamento de trafego pago via OpenRouter (tier inteligente) -- nunca executa campanha",
    )

    # CAMPAIGN_EXECUTOR (Fase 6) -- mesma excecao documentada acima:
    # `tools/campaign_executor_tools.py` chama `registry.executar(CAMPAIGN_EXECUTOR, ...)`
    # como caminho REAL de geracao da CampaignSpec. O executor devolve um
    # `CampaignSpec` (objeto estruturado), nao uma string -- mesmo desvio ja
    # documentado para PAID_TRAFFIC_ARCHITECT.
    from core.campaign_executor import criar_campaign_spec

    registry.registrar(
        CAMPAIGN_EXECUTOR, provider_name="openrouter", disponivel=True,
        executor=criar_campaign_spec,
        observacao=(
            "transforma um TrafficPlan aprovado em especificacao de "
            "campanha via OpenRouter (tier inteligente) -- nunca publica, "
            "nunca conecta conta de anuncio, nunca gasta"
        ),
    )
    return registry
