"""
Project Brain — memoria estruturada por projeto/oportunidade.

Fase 2 (Opportunity Analyst + Decision Engine). Guarda, de forma progressiva,
tudo que o CRIS OS aprende sobre uma oportunidade/projeto: de onde veio, que
mercado e, que sinais existem, qual caminho foi decidido, e (mais pra frente)
produto/marca/assets/trafego.

Design deliberado:
  - NAO cria tabela nova nem mexe no schema do Supabase/ScalaFlow. Guarda tudo
    LOCAL, reaproveitando a camada L2 que ja existe (`memory.layers.ProjectMemory`
    -> `storage.SQLiteMemory.remember_project/recall_project`, tabela
    `project_memory` que ja existia antes desta fase).
  - Cada projeto vira UM KnowledgeItem com `type="project_brain"` e `content`
    em JSON. O `id` do KnowledgeItem e deterministico (`brain:<project_id>`),
    entao salvar de novo faz UPSERT (INSERT OR REPLACE ja existente no
    backend) em vez de acumular historico duplicado.
  - Muitos campos ficam vazios no inicio de propósito (nao inventamos dado).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from core.models import KnowledgeItem

_TYPE = "project_brain"


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def novo_project_id() -> str:
    return "proj_" + uuid.uuid4().hex[:12]


@dataclass
class Identidade:
    project_id: str
    name: str = ""
    type: str = ""  # ex.: "opportunity", "product", "client"
    status: str = "new"
    created_at: str = field(default_factory=_agora)
    updated_at: str = field(default_factory=_agora)


@dataclass
class Origem:
    source_offer_id: str | None = None  # ex.: collected_ads.id ou ad_library_id
    source_platform: str | None = None
    source_url: str | None = None
    source_country: str | None = None
    source_language: str | None = None
    # Headline/copy CRUS do anuncio (Fase 3): sem isso o Product Architect so
    # tinha nome do anunciante/score/sinais -- pouco pra propor um formato de
    # produto com responsabilidade (na pratica, virava NEEDS_RESEARCH sempre).
    # Continua sendo dado REAL do ScalaFlow, nao inventado.
    source_headline: str | None = None
    source_copy: str | None = None


@dataclass
class Mercado:
    niche: str | None = None
    market: str | None = None
    target_country: str | None = None
    target_language: str | None = None
    target_audience: str | None = None


@dataclass
class Oportunidade:
    score: float | None = None
    signals: dict = field(default_factory=dict)  # ex.: {"meta": {...}, "tiktok": {...}}
    evidence: list[str] = field(default_factory=list)  # frases curtas, sempre rastreaveis
    risks: list[str] = field(default_factory=list)
    competition: dict = field(default_factory=dict)
    trend_signals: dict = field(default_factory=dict)


@dataclass
class Decisao:
    recommended_path: str | None = None  # CREATE_OWN_PRODUCT | AFFILIATE | COMMERCE_RESALE | INVESTIGATE_MORE | DISCARD
    reasoning_summary: str | None = None
    evidence_level: str | None = None  # "baixo" | "medio" | "alto"
    decision_status: str = "PENDING_APPROVAL"
    user_approved: bool | None = None


@dataclass
class Produto:
    product_type: str | None = None
    product_name: str | None = None
    positioning: str | None = None
    offer: str | None = None
    price: str | None = None
    business_model: str | None = None


@dataclass
class Brand:
    brand_name: str | None = None
    slogan: str | None = None
    colors: list[str] = field(default_factory=list)
    fonts: list[str] = field(default_factory=list)
    visual_direction: str | None = None


@dataclass
class Assets:
    landing_page: str | None = None
    creatives: list[str] = field(default_factory=list)
    videos: list[str] = field(default_factory=list)
    documents: list[str] = field(default_factory=list)
    drive_folder: str | None = None


@dataclass
class Trafego:
    channels: list[str] = field(default_factory=list)
    campaigns: list[str] = field(default_factory=list)
    budgets: dict = field(default_factory=dict)
    results: dict = field(default_factory=dict)


@dataclass
class Historico:
    decisions: list[dict] = field(default_factory=list)
    approvals: list[dict] = field(default_factory=list)
    agent_runs: list[dict] = field(default_factory=list)


# Estados validos do Product Blueprint (Fase 3). A criacao SEMPRE termina em
# PENDING_APPROVAL -- o Product Architect nunca aprova a propria proposta.
BLUEPRINT_ESTADOS_VALIDOS = frozenset({
    "DRAFT", "PENDING_APPROVAL", "APPROVED", "REJECTED",
    "NEEDS_RESEARCH", "IN_PRODUCTION", "COMPLETED",
})

# Estados que significam "a aprovacao humana JA aconteceu" (Fase 4 --
# correcao de bug real: a Product Factory avanca `decision_status` de
# "APPROVED" para "IN_PRODUCTION" IMEDIATAMENTE apos a aprovacao, no mesmo
# fluxo. Qualquer consumidor posterior -- Business Builder, Product Factory
# sob demanda -- que checasse so `== "APPROVED"` via um espelho proprio via
# um "ja passou por aprovacao" real, sempre um `False` incorreto pra
# projetos ja aprovados). Esta e a UNICA fonte de verdade sobre aprovacao --
# nenhum campo novo foi criado; so os estados que ja existiam desde a Fase 3
# foram agrupados corretamente.
BLUEPRINT_ESTADOS_APROVADOS = frozenset({"APPROVED", "IN_PRODUCTION", "COMPLETED"})


@dataclass
class ProductBlueprint:
    """
    Proposta estruturada de produto (Fase 3 -- Product Architect).

    Campos "user_id/tenant_id" e "opportunity_id" existem para o blueprint
    ser autocontido (poder ser lido/exportado sem precisar do ProjectBrain
    inteiro), mesmo hoje sendo sempre preenchidos a partir do
    ProjectBrain que o contem (`identidade.project_id`,
    `origem.source_offer_id`). NAO ha isolamento multi-tenant real ainda --
    ver "Build for one today, architecture for many tomorrow" em
    docs/PRODUCT-BLUEPRINT.md.
    """

    project_id: str = ""
    user_id: str | None = None
    tenant_id: str | None = None
    opportunity_id: str | None = None  # referencia (source_offer_id da oportunidade)
    created_at: str = field(default_factory=_agora)
    updated_at: str = field(default_factory=_agora)

    # --- mercado/contexto (herdado da oportunidade, sem reinventar) ---
    market: str | None = None
    country: str | None = None
    language: str | None = None
    niche: str | None = None
    target_audience: str | None = None
    problem: str | None = None
    opportunity_summary: str | None = None

    # --- formato de produto ---
    recommended_product_type: str | None = None
    alternative_product_types: list[str] = field(default_factory=list)

    # --- conceito ---
    product_concept: str | None = None
    core_value: str | None = None
    transformation: str | None = None
    mechanism: str | None = None
    differentiation: str | None = None

    # --- producao ---
    mvp_scope: str | None = None
    production_complexity: str | None = None  # "baixa" | "media" | "alta"
    estimated_speed_to_mvp: str | None = None  # texto livre (ex.: "1-2 dias")
    required_tools: list[str] = field(default_factory=list)
    required_integrations: list[str] = field(default_factory=list)

    # --- monetizacao ---
    monetization_options: list[str] = field(default_factory=list)
    suggested_offer_structure: str | None = None

    # --- honestidade (nunca inventar) ---
    evidence: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)

    # --- decisao/aprovacao ---
    decision_status: str = "DRAFT"
    reasoning_summary: str | None = None  # por que esse formato (para "por que X?")

    # --- hipoteses de formato (correcao pos-teste real da Fase 3) ---
    # EVIDENCIA INSUFICIENTE PARA DECIDIR/APROVAR != evidencia insuficiente
    # para GERAR HIPOTESES. `candidates` guarda de 3 a 5 formatos plausiveis
    # (cada um com publico/problema/motivo/dificuldade/monetizacao/
    # evidencias a favor e ausentes/confianca), sempre que houver QUALQUER
    # evidencia real pra raciocinar em cima -- mesmo quando nenhum deles e
    # confiavel o bastante pra virar `recommended_product_type`. So fica
    # vazio quando realmente nao ha nada (nem headline, nem copy, nem
    # nicho, nem score).
    candidates: list[dict] = field(default_factory=list)

    # --- rastreabilidade da geracao (nao e segredo, e metadado de custo) ---
    generated_by: str | None = None  # "openrouter:inteligente" | "fallback_deterministico" | ...

    def esta_aprovado(self) -> bool:
        """True se a aprovacao humana JA aconteceu -- inclui `APPROVED` e
        qualquer estado posterior (`IN_PRODUCTION`, `COMPLETED`). Use isto
        (nunca `decision_status == "APPROVED"` direto) em qualquer gate que
        precise saber "este produto ja foi aprovado", pois `decision_status`
        avanca para `IN_PRODUCTION` assim que a Product Factory roda o
        primeiro artefato -- checar so `== "APPROVED"` bloqueia
        incorretamente qualquer consumidor (Business Builder, Product
        Factory sob demanda) que rode DEPOIS desse avanco (bug real,
        Fase 4)."""
        return self.decision_status in BLUEPRINT_ESTADOS_APROVADOS


# Estados validos do Business Plan (Fase 4). Diferente do Product Blueprint,
# nao existe hoje uma acao concreta que dependa de "BusinessPlan aprovado"
# (nada e publicado/comprado nesta fase) -- por isso a criacao normal termina
# em READY_FOR_APPROVAL (plano pronto pra revisao humana), nao em
# PENDING_APPROVAL/APPROVED como o blueprint. Os estados existem desde ja
# para quando uma fase futura precisar deles (ex.: liberar producao paga).
BUSINESS_PLAN_ESTADOS_VALIDOS = frozenset({
    "DRAFT", "READY_FOR_REVIEW", "READY_FOR_APPROVAL", "APPROVED", "REJECTED",
})


@dataclass
class BusinessPlan:
    """
    Plano de negocio (Fase 4 -- Business Builder). Recebe um Product Blueprint
    JA APROVADO e organiza a estrutura comercial em torno dele: modelo de
    negocio, oferta, monetizacao, funil, conteudo, lancamento.

    Regra de ouro (igual ao Product Blueprint): NUNCA inventa vendas, receita,
    CPA, ROAS, conversao, demanda ou tamanho de mercado. Preco sem benchmark
    real fica marcado `price_is_hypothesis=True` -- nunca vira um numero
    apresentado como fato.
    """

    project_id: str = ""
    created_at: str = field(default_factory=_agora)
    updated_at: str = field(default_factory=_agora)

    # --- modelo/oferta ---
    business_model: str | None = None
    value_proposition: str | None = None
    target_audience: str | None = None
    problem: str | None = None
    solution: str | None = None
    positioning: str | None = None
    mechanism: str | None = None  # diferencial/mecanismo unico
    main_offer: str | None = None
    monetization_format: str | None = None

    # --- preco (SEMPRE hipotese quando nao ha benchmark real -- nunca fato) ---
    price: str | None = None
    price_is_hypothesis: bool = True
    bonuses: list[str] = field(default_factory=list)
    order_bump: str | None = None
    upsell: list[str] = field(default_factory=list)
    downsell: list[str] = field(default_factory=list)

    # --- aquisicao/venda ---
    acquisition_channels: list[str] = field(default_factory=list)
    sales_channels: list[str] = field(default_factory=list)

    # --- pagina de vendas ---
    sales_page_structure: str | None = None
    headline: str | None = None
    promise: str | None = None  # promessa RESPONSAVEL (nunca prometer resultado irreal)
    key_arguments: list[str] = field(default_factory=list)
    objections: list[dict] = field(default_factory=list)  # [{"objecao":..., "resposta":...}]
    cta: str | None = None

    # --- funil/conteudo/lancamento ---
    funnel_structure: str | None = None
    email_sequence: list[dict] = field(default_factory=list)  # 5 emails: {"numero","objetivo","assunto","resumo"}
    content_strategy: str | None = None
    content_channels: list[str] = field(default_factory=list)  # ex.: YouTube/TikTok/Instagram
    launch_strategy: str | None = None
    plan_30_days: list[dict] = field(default_factory=list)  # [{"periodo":"dias 1-7", "acoes":[...]}]

    # --- honestidade (DADO / EVIDENCIA / HIPOTESE / PENDENCIA -- nunca inventar) ---
    evidence: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)  # hipoteses assumidas
    missing_evidence: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    approval_status: str = "DRAFT"  # DRAFT | READY_FOR_REVIEW | READY_FOR_APPROVAL | APPROVED | REJECTED
    generated_by: str | None = None

    # -----------------------------------------------------------------
    # Fase 7 -- Business Builder (estrategia de negocio ampliada).
    #
    # Extensao ADITIVA e retrocompativel: nenhum campo/estado existente foi
    # removido ou renomeado. Conceitos ja cobertos por um campo existente NAO
    # ganham um segundo campo duplicado (core_problem->`problem`,
    # unique_mechanism->`mechanism`, core_offer->`main_offer`,
    # monetization_model->`monetization_format`, funnel_strategy->
    # `funnel_structure`, recommended_next_actions->`next_steps`,
    # status->`approval_status`) -- so os conceitos GENUINAMENTE novos pedidos
    # pela Fase 7 ganham campo proprio.
    # -----------------------------------------------------------------

    # --- identificacao/handoff ---
    opportunity_id: str | None = None  # referencia (mesma convencao do ProductBlueprint)
    product_blueprint_id: str | None = None  # referencia explicita ao blueprint de origem
    name: str | None = None
    version: int = 1

    # --- mercado (herdado do blueprint/oportunidade -- nao reinventa fonte) ---
    market: str | None = None
    niche: str | None = None
    subniche: str | None = None
    desired_outcome: str | None = None

    # --- oferta ampliada (SEMPRE estrategia/hipotese, nunca preco/numero fato) ---
    offer_type: str | None = None
    pricing_strategy: str | None = None
    estimated_price_range: str | None = None
    bonuses_strategy: str | None = None
    guarantee_strategy: str | None = None
    urgency_strategy: str | None = None

    # --- canais/modelo de venda ---
    primary_channel: str | None = None
    secondary_channels: list[str] = field(default_factory=list)
    sales_model: str | None = None

    # --- economia (SEMPRE estimativa -- nenhum numero e fato sem trafego real
    # rodando; mesmo principio de `price`/`price_is_hypothesis` acima) ---
    estimated_ticket: str | None = None
    estimated_margin: str | None = None
    estimated_cac_target: str | None = None
    estimated_break_even: str | None = None
    revenue_scenarios: list[dict] = field(default_factory=list)  # [{"nome","descricao","type":"PLANNING_ASSUMPTION"}]

    # --- competicao ---
    competitors: list[str] = field(default_factory=list)
    differentiation: str | None = None
    market_gaps: list[str] = field(default_factory=list)
    barriers: list[str] = field(default_factory=list)

    # --- validacao ampliada ---
    validation_requirements: list[str] = field(default_factory=list)
    confidence_score: str | None = None  # "baixo" | "medio" | "alto" -- nunca inventado sem base nas evidencias

    # --- execucao futura (ESPECIFICA o que precisa existir -- nunca produz) ---
    required_assets: list[str] = field(default_factory=list)
    kpis: list[str] = field(default_factory=list)

    def esta_aprovado(self) -> bool:
        """True SOMENTE se `approval_status == "APPROVED"` -- diferente de
        `ProductBlueprint.esta_aprovado()`, aqui NAO ha um estado posterior
        equivalente a "IN_PRODUCTION" (nenhum fluxo desta fase avanca o
        Business Plan sozinho). `READY_FOR_APPROVAL` NUNCA conta como
        aprovado -- e so um sinal de "pronto pra revisao humana". Existe
        para consistencia de nomenclatura com `ProductBlueprint` e para
        qualquer gate futuro (ex.: publicacao) que precise checar isso."""
        return self.approval_status == "APPROVED"


# Estados validos do Production Plan (Fase 4). So chega a existir depois do
# Product Blueprint estar APPROVED (mesmo gate da Product Factory, Fase 3) --
# por isso comeca sempre em IN_PRODUCTION (o unico artefato real desta fase,
# o brief textual, ja foi executado nesse ponto). READY_TO_PUBLISH/PUBLISHED
# sao estados reservados para fases futuras (nenhuma publicacao acontece aqui).
PRODUCTION_PLAN_ESTADOS_VALIDOS = frozenset({
    "DRAFT", "IN_PRODUCTION", "READY_TO_PUBLISH", "PUBLISHED",
})


@dataclass
class ProductionPlan:
    """
    Plano de producao persistido (Fase 4). Complementa `core/product_factory.py`
    (que continua sendo a UNICA logica de decisao de passos/execucao) guardando
    o resultado no Project Brain -- sem isso, o plano so existia na memoria de
    uma resposta do Telegram e se perdia depois de enviado.
    """

    project_id: str = ""
    product_type: str = ""
    created_at: str = field(default_factory=_agora)
    updated_at: str = field(default_factory=_agora)
    steps: list[dict] = field(default_factory=list)  # [{"nome","capability","disponivel","status","resultado"}]
    deliverables: list[str] = field(default_factory=list)  # nomes dos entregaveis previstos para este tipo
    dependencies: list[str] = field(default_factory=list)
    status: str = "DRAFT"  # DRAFT | IN_PRODUCTION | READY_TO_PUBLISH | PUBLISHED


# Estados validos do Traffic Plan (Fase 5). A criacao SEMPRE termina em
# NEEDS_INFORMATION (faltou algo essencial) ou READY_FOR_APPROVAL (evidencia
# suficiente pra montar um plano) -- NUNCA em APPROVED: aprovacao e sempre um
# ato humano explicito, e "so os que se transformam em APPROVED por texto
# EXATO" (ver `esta_aprovado()`).
TRAFFIC_PLAN_ESTADOS_VALIDOS = frozenset({
    "DRAFT", "NEEDS_INFORMATION", "READY_FOR_APPROVAL", "APPROVED", "REJECTED",
})

# Canais suportados (vocabulario fechado, mesmo principio do
# `core/product_architect.py:PRODUCT_TYPES` -- "nao usar preferencia fixa do
# desenvolvedor", todo canal recomendado pelo LLM e validado contra esta
# lista, nunca aceito as cegas).
TRAFFIC_CHANNELS = frozenset({
    "META_ADS", "GOOGLE_SEARCH", "GOOGLE_DISPLAY", "YOUTUBE_ADS", "TIKTOK_ADS",
})

# Papel de um canal dentro do plano (nunca "vai funcionar" -- so uma dessas
# classificacoes honestas). Correcao pos-auditoria (Fase 5): renomeado de
# CANDIDATE/PRIORITY_TEST/INSUFFICIENT_INFO para deixar a PRIORIZACAO
# OPERACIONAL explicita -- o plano nunca pode dar a impressao de que varios
# canais devem comecar ao mesmo tempo. EXATAMENTE UM canal por versao do
# plano pode ser PRIMARY_TEST (imposto em `core/paid_traffic_architect.py`,
# nunca confiado ao LLM sozinho); pode haver varios SECONDARY_TEST.
TRAFFIC_CHANNEL_ROLES = frozenset({
    "PRIMARY_TEST", "SECONDARY_TEST", "LATER", "NOT_RECOMMENDED_NOW",
})


@dataclass
class TrafficPlan:
    """
    Plano de trafego pago estruturado (Fase 5 -- Paid Traffic Architect).
    NUNCA executa campanha, NUNCA conecta conta de anuncio, NUNCA inventa
    metrica/orcamento como fato -- so estrutura HIPOTESES/PLANEJAMENTO em
    cima de evidencia real ja coletada no Project Brain.
    """

    project_id: str = ""
    version: int = 1
    status: str = "DRAFT"  # DRAFT | NEEDS_INFORMATION | READY_FOR_APPROVAL | APPROVED | REJECTED
    created_at: str = field(default_factory=_agora)
    updated_at: str = field(default_factory=_agora)

    # --- contexto/objetivo ---
    objective: str | None = None
    # `market`/`country` NUNCA ficam em branco silenciosamente (correcao
    # pos-auditoria real: renderizar "Mercado: ?" e pior que ser honesto).
    # Quando o Project Brain genuinamente nao tem essa informacao ainda,
    # `core/paid_traffic_architect.py` preenche com o literal
    # "REQUIRES_MARKET_DATA" em vez de deixar `None`.
    market: str | None = None
    country: str | None = None
    language: str | None = None
    audience_summary: str | None = None

    # --- canais (cada item: role/priority/rationale/campaign_objective/
    # campaign_structure/ad_sets_or_groups/targeting_strategy/
    # keyword_strategy/placements/creative_requirements/landing_destination/
    # conversion_event/test_hypothesis/evidence_used/assumptions/risks) ---
    channels: list[dict] = field(default_factory=list)

    # --- criativo ---
    angles: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)
    creative_matrix: list[dict] = field(default_factory=list)  # angle/hook/format/channel/audience/cta/evidence_or_hypothesis/asset_required

    # --- teste/mensuracao ---
    testing_plan: list[str] = field(default_factory=list)
    measurement_plan: list[str] = field(default_factory=list)  # QUAIS metricas observar, nunca resultados
    stop_conditions: list[str] = field(default_factory=list)
    scale_conditions: list[str] = field(default_factory=list)

    # --- orcamento -- NUNCA fato, sempre hipotese/preservacao do real ---
    budget_scenarios: list[dict] = field(default_factory=list)  # [{"nome": "LOW|STANDARD|EXPANDED", "valor": "...", "type": "PLANNING_ASSUMPTION"}]
    budget_informado_pelo_usuario: dict | None = None  # {"currency","daily_budget","total_test_budget"} -- preservado sem alteracao quando existir
    # REQUIRES_USER_INPUT | PROVIDED -- correcao pos-auditoria: nunca deixar
    # implicito que um orcamento existe so porque ha cenarios de exemplo.
    budget_status: str = "REQUIRES_USER_INPUT"

    # NOT_AVAILABLE | AVAILABLE -- correcao pos-auditoria: prova social
    # (depoimentos/avaliacoes/numero de clientes) so pode ser AVAILABLE se
    # o Project Brain tiver um registro REAL disso (hoje nao ha nenhum campo
    # assim em `ProjectBrain` -- por isso comeca e permanece NOT_AVAILABLE
    # ate uma fase futura trazer essa fonte de dado).
    social_proof_status: str = "NOT_AVAILABLE"

    # --- honestidade (DADO / EVIDENCIA / HIPOTESE / DESCONHECIDO -- nunca inventar) ---
    evidence_summary: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)  # lacunas objetivas quando NEEDS_INFORMATION
    approval_required_actions: list[str] = field(default_factory=list)

    generated_by: str | None = None

    def esta_aprovado(self) -> bool:
        """SOMENTE `status == "APPROVED"` retorna verdadeiro -- pedido
        explicito da Fase 5, nunca confundir `READY_FOR_APPROVAL` com
        aprovacao real."""
        return self.status == "APPROVED"


def novo_campaign_id() -> str:
    return "camp_" + uuid.uuid4().hex[:12]


# Estados validos da CampaignSpec (Fase 6 -- Campaign Executor). SOMENTE
# criada depois que o TrafficPlan (Fase 5) ja estiver `esta_aprovado()`
# (checado ANTES de qualquer chamada de LLM/escrita -- ver
# `core/campaign_executor.py`). NUNCA existe um estado "PUBLISHED"/"LIVE"
# nesta fase -- publicacao externa esta fora de escopo.
CAMPAIGN_SPEC_ESTADOS_VALIDOS = frozenset({
    "NOT_STARTED", "NEEDS_INFORMATION", "READY_FOR_APPROVAL", "APPROVED",
})

# Modo de execucao (Fase 6). `READY_FOR_EXTERNAL_EXECUTION` e um estado
# RESERVADO para uma fase futura com um conector real conectado -- nesta
# fase `execution_mode` fica SEMPRE `EXTERNAL_EXECUTION_DISABLED` (mesmo
# depois de `CampaignSpec.esta_aprovado()`). `DRY_RUN` e usado so na
# EXIBICAO do preview (nunca persistido como o modo real da spec).
CAMPAIGN_EXECUTION_MODES = frozenset({
    "DRY_RUN", "EXTERNAL_EXECUTION_DISABLED", "READY_FOR_EXTERNAL_EXECUTION",
})


@dataclass
class CampaignSpec:
    """
    Especificacao executavel de UMA campanha (Fase 6 -- Campaign Executor),
    derivada do canal PRIMARY_TEST de um TrafficPlan JA APROVADO. NUNCA
    executa/publica/gasta nada -- so estrutura a especificacao. Dois gates
    separados existem: GATE A (aprovacao do TrafficPlan, Fase 5) e GATE B
    (aprovacao desta CampaignSpec como ESPECIFICACAO) -- nenhum dos dois
    libera execucao externa nesta fase (`execution_mode` permanece
    `EXTERNAL_EXECUTION_DISABLED` mesmo apos `esta_aprovado()`).
    """

    campaign_id: str = ""
    project_id: str = ""
    version: int = 1
    status: str = "NOT_STARTED"  # NOT_STARTED | NEEDS_INFORMATION | READY_FOR_APPROVAL | APPROVED
    created_at: str = field(default_factory=_agora)
    updated_at: str = field(default_factory=_agora)

    source_traffic_plan_version: int | None = None
    channel: str | None = None  # um dos TRAFFIC_CHANNELS (canal PRIMARY_TEST do plano)
    objective: str | None = None
    country: str | None = None
    language: str | None = None
    destination: str | None = None
    conversion_event: str | None = None

    campaign_structure: str | None = None
    ad_sets: list[str] = field(default_factory=list)
    audience_hypotheses: list[str] = field(default_factory=list)
    placements: list[str] = field(default_factory=list)
    creative_requirements: list[str] = field(default_factory=list)
    copy_requirements: list[str] = field(default_factory=list)
    # Para GOOGLE_SEARCH sem fonte real de volume de busca/CPC: sempre
    # contem "REQUIRES_KEYWORD_DATA" (imposto deterministicamente, nunca
    # confiado ao LLM sozinho -- ver `core/campaign_executor.py`).
    keyword_requirements: list[str] = field(default_factory=list)
    tracking_requirements: list[str] = field(default_factory=list)

    # {"currency", "daily", "total", "source", "status"} -- "status" e
    # REQUIRES_BUDGET quando nao informado pela usuaria, PROVIDED quando
    # extraido deterministicamente da propria mensagem (nunca via LLM).
    budget: dict = field(default_factory=lambda: {
        "currency": None, "daily": None, "total": None,
        "source": None, "status": "REQUIRES_BUDGET",
    })
    schedule: str | None = None
    experiments: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    evidence_summary: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    approval_required: list[str] = field(default_factory=list)

    # SEMPRE "EXTERNAL_EXECUTION_DISABLED" nesta fase -- nao existe conector
    # real conectado (ver `core/campaign_platform_adapter.py`).
    execution_mode: str = "EXTERNAL_EXECUTION_DISABLED"
    # Nunca muda nesta fase -- nenhuma chamada externa acontece.
    external_execution_status: str = "NOT_EXECUTED"

    generated_by: str | None = None

    def esta_aprovado(self) -> bool:
        """SOMENTE `status == "APPROVED"` -- mesma regra do TrafficPlan.
        `READY_FOR_APPROVAL` NUNCA conta como aprovado. IMPORTANTE: mesmo
        `esta_aprovado() == True` significa SOMENTE 'aprovada como
        ESPECIFICACAO' -- nunca autoriza nenhuma execucao externa (ver
        `execution_mode`, que permanece `EXTERNAL_EXECUTION_DISABLED`)."""
        return self.status == "APPROVED"


# Fonte de um PerformanceSnapshot (Fase 6). REAL/IMPORTED sao utilizaveis
# para diagnostico; SIMULATED e SOMENTE para testes -- nunca apresentado
# como se fosse dado real, e nunca misturado com um snapshot REAL/IMPORTED
# no mesmo diagnostico.
PERFORMANCE_SNAPSHOT_FONTES = frozenset({"REAL", "SIMULATED", "IMPORTED"})


@dataclass
class PerformanceSnapshot:
    """
    Snapshot normalizado de metricas de UMA campanha, em UM periodo (Fase 6
    -- Performance Agent, fundacao). NUNCA inventado -- campos ausentes
    ficam `None` (o Performance Agent formata como `NOT_AVAILABLE` na
    exibicao, nunca como zero/vazio silencioso).
    """

    platform: str | None = None
    campaign_id: str | None = None
    date_range: str | None = None
    spend: str | None = None
    impressions: str | None = None
    reach: str | None = None
    clicks: str | None = None
    ctr: str | None = None
    cpc: str | None = None
    cpm: str | None = None
    leads: str | None = None
    purchases: str | None = None
    revenue: str | None = None
    cpl: str | None = None
    cpa: str | None = None
    cvr: str | None = None
    roas: str | None = None
    # REAL | SIMULATED | IMPORTED -- nunca ambiguo.
    source: str = "IMPORTED"
    collected_at: str = field(default_factory=_agora)


def novo_execution_id() -> str:
    return "exec_" + uuid.uuid4().hex[:12]


def novo_task_id() -> str:
    return "task_" + uuid.uuid4().hex[:8]


# Estados validos de uma Task (Fase 8 -- Execution Engine). Vocabulario
# FECHADO -- nunca uma string solta espalhada pelo codigo.
TASK_ESTADOS_VALIDOS = frozenset({
    "PENDING", "READY", "RUNNING", "BLOCKED", "COMPLETED", "FAILED",
    "SKIPPED", "CANCELLED",
})

# Estados TERMINAIS -- uma task nesses estados nunca e reexecutada
# automaticamente (garante idempotencia: reprocessar um ExecutionPlan so
# olha tasks PENDING/READY, nunca uma ja terminal).
TASK_ESTADOS_TERMINAIS = frozenset({"COMPLETED", "FAILED", "SKIPPED", "CANCELLED"})


@dataclass
class Task:
    """
    Unidade de trabalho de um ExecutionPlan (Fase 8). NUNCA e reexecutada
    automaticamente depois de chegar a um estado TERMINAL
    (`TASK_ESTADOS_TERMINAIS`) -- a propria identidade (`task_id`,
    atribuido uma unica vez na criacao do plano e persistido) mais essa
    checagem de estado SAO o mecanismo de idempotencia (nao existe uma
    "idempotency key" separada porque nunca ha um caminho que gere um
    `task_id` novo para a MESMA unidade de trabalho).

    `requires_approval`/`approved` sao dois campos DISTINTOS de proposito:
    `requires_approval` e uma propriedade fixa da tarefa (definida na
    criacao do plano); `approved` e o resultado de uma decisao humana
    explicita, aplicada SOMENTE por `core/approval_router.py` (nunca por
    adivinhacao, nunca por quem executa o plano). Uma task com
    `requires_approval=True` e `approved=False` fica com `status="READY"`
    (pronta, mas aguardando aprovacao) -- o motor NUNCA a executa nesse
    estado, mesmo que todas as dependencias estejam completas.
    """

    task_id: str = field(default_factory=novo_task_id)
    title: str = ""
    description: str | None = None
    objective: str | None = None  # contrato de entrada
    agent: str | None = None  # agente/especialista nominalmente responsavel
    dependencies: list[str] = field(default_factory=list)  # task_ids
    priority: str = "media"  # "baixa" | "media" | "alta"
    status: str = "PENDING"

    # --- contrato de entrada/saida ---
    input_refs: list[str] = field(default_factory=list)  # = context_refs
    output_refs: list[str] = field(default_factory=list)  # = artifact_refs
    constraints: list[str] = field(default_factory=list)
    result: str | None = None
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    # --- execucao externa (SEMPRE desabilitada nesta fase) ---
    requires_approval: bool = False
    external_action: bool = False
    approved: bool = False
    approved_at: str | None = None
    # True quando uma task `external_action=True` foi "concluida" via
    # DRY_RUN/MOCK -- NUNCA True para uma execucao externa real (que nao
    # existe nesta fase).
    simulated: bool = False

    # --- custo (SEMPRE estimativa -- nunca fato sem execucao real) ---
    estimated_cost: str | None = None
    actual_cost: str | None = None

    # --- retry ---
    retry_count: int = 0
    max_retries: int = 2

    created_at: str = field(default_factory=_agora)
    updated_at: str = field(default_factory=_agora)


# Estados validos de um ExecutionPlan (Fase 8). A criacao SEMPRE termina em
# READY_FOR_APPROVAL -- nunca APPROVED automaticamente (mesmo principio de
# TrafficPlan/CampaignSpec/BusinessPlan: aprovacao e sempre um ato humano
# explicito).
EXECUTION_PLAN_ESTADOS_VALIDOS = frozenset({
    "DRAFT", "READY_FOR_APPROVAL", "APPROVED", "RUNNING", "PAUSED",
    "BLOCKED", "COMPLETED", "FAILED", "CANCELLED",
})

# Tipos de artefato que podem ser a origem de um ExecutionPlan -- fechado de
# proposito, nunca uma string livre.
EXECUTION_SOURCE_ARTIFACT_TIPOS = frozenset({
    "BUSINESS_PLAN", "TRAFFIC_PLAN", "CAMPAIGN_SPEC", "PRODUCT_BLUEPRINT",
})


@dataclass
class ExecutionPlan:
    """
    Converte um artefato JA APROVADO (BusinessPlan/TrafficPlan/CampaignSpec/
    ProductBlueprint) numa sequencia de Tasks com dependencias explicitas
    (Fase 8 -- Execution Engine). NUNCA executa nenhuma acao externa real --
    tasks com `external_action=True` so podem ser "concluidas" via
    simulacao (DRY_RUN/MOCK), e mesmo assim exigem aprovacao humana
    explicita por TASK (nao so aprovacao do plano inteiro).

    `total_tasks`/`completed_tasks`/`failed_tasks`/`blocked_tasks`/
    `pending_tasks` (o "SUMMARY" pedido) sao deliberadamente CALCULADOS
    (`resumo()`), nunca persistidos como campos separados -- mesmo
    principio de "nunca uma segunda fonte de verdade" ja aplicado ao
    Artifact Manifest (Fase 4) e a `ProjectBrain.coletar_evidencias_pesquisa`
    (Fase 5): um contador guardado à parte da lista real de tasks
    inevitavelmente destoa dela mais cedo ou mais tarde.
    """

    execution_id: str = field(default_factory=novo_execution_id)
    project_id: str = ""
    source_artifact_type: str | None = None  # ver EXECUTION_SOURCE_ARTIFACT_TIPOS
    source_artifact_id: str | None = None
    objective: str | None = None
    status: str = "DRAFT"
    version: int = 1
    created_at: str = field(default_factory=_agora)
    updated_at: str = field(default_factory=_agora)

    tasks: list[Task] = field(default_factory=list)

    # --- controle humano ---
    requires_human_approval: bool = True
    approved_at: str | None = None
    execution_started_at: str | None = None
    execution_finished_at: str | None = None

    def esta_aprovado(self) -> bool:
        """SOMENTE `status == "APPROVED"` conta -- mas note que, diferente
        dos outros artefatos, o ExecutionPlan CONTINUA em uso depois disso
        (avanca para RUNNING/PAUSED/COMPLETED/etc.) -- use
        `esta_liberado_para_rodar()` para saber se o motor pode processar
        tasks agora."""
        return self.status == "APPROVED"

    def esta_liberado_para_rodar(self) -> bool:
        """Estados em que o motor PODE processar tasks prontas -- nunca em
        DRAFT/READY_FOR_APPROVAL (falta aprovacao humana) nem em
        PAUSED/CANCELLED/COMPLETED/FAILED (parado de proposito ou
        definitivamente encerrado)."""
        return self.status in {"APPROVED", "RUNNING"}

    def resumo(self) -> dict:
        contagem = {"PENDING": 0, "READY": 0, "RUNNING": 0, "BLOCKED": 0,
                    "COMPLETED": 0, "FAILED": 0, "SKIPPED": 0, "CANCELLED": 0}
        for t in self.tasks:
            contagem[t.status] = contagem.get(t.status, 0) + 1
        return {
            "total_tasks": len(self.tasks),
            "completed_tasks": contagem["COMPLETED"],
            "failed_tasks": contagem["FAILED"],
            "blocked_tasks": contagem["BLOCKED"],
            "pending_tasks": contagem["PENDING"] + contagem["READY"],
            "running_tasks": contagem["RUNNING"],
            "cancelled_tasks": contagem["CANCELLED"],
            "skipped_tasks": contagem["SKIPPED"],
        }


def novo_handoff_id() -> str:
    return "handoff_" + uuid.uuid4().hex[:12]


def novo_work_order_id() -> str:
    return "wo_" + uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# ProductionWorkOrder -- ponte Cris OS -> executores especializados
# (PageForge, Pink Logic, Criador-de-App, ForgeHub, NEXORA). NENHUM desses
# executores e chamado por este modulo -- e so o CONTRATO de dados canonico
# que permitira conecta-los depois, sem reconstruir nada existente.
# ---------------------------------------------------------------------------

# Vocabulario FECHADO de estados. "NEEDS_ROUTING" existe quando o
# `asset_type` normalizado nao mapeia para nenhum executor conhecido --
# nunca inventa um executor so pra "resolver" algo ambiguo. Nesta fase,
# NENHUMA WorkOrder avanca alem de READY (nenhum executor real conectado
# ainda) -- DISPATCHED/RUNNING/COMPLETED/FAILED existem para quando um
# adapter real existir (ver `core/executor_adapter.py`).
PRODUCTION_WORK_ORDER_ESTADOS_VALIDOS = frozenset({
    "CREATED", "READY", "WAITING_APPROVAL", "DISPATCHED", "RUNNING",
    "COMPLETED", "FAILED", "CANCELLED", "NEEDS_ROUTING",
})

# Vocabulario FECHADO de asset_type -- normalizado a partir do texto livre
# de `required_assets` (ver `core/production_router.py:normalizar_asset_type`).
# "UNKNOWN" e o unico valor que NUNCA mapeia para um executor (vira sempre
# NEEDS_ROUTING).
PRODUCTION_ASSET_TYPES_VALIDOS = frozenset({
    "APP", "LANDING_PAGE", "EBOOK", "CAROUSEL", "MARKETING_MATERIAL",
    "DISTRIBUTION", "CRM", "UNKNOWN",
})

# Vocabulario FECHADO de executor_type (Secao 3 da missao -- mapeamento
# inicial). "NEEDS_ROUTING" nao e um executor de verdade -- e o sinal
# explicito de "ninguem sabe processar isto ainda".
PRODUCTION_EXECUTOR_TYPES_VALIDOS = frozenset({
    "APP_BUILDER", "PAGEFORGE", "PINK_LOGIC", "FORGEHUB", "NEXORA", "NEEDS_ROUTING",
})


@dataclass
class ProductionWorkOrder:
    """
    Ordem de produção interna e rastreável (Secao 1 da missao) -- transforma
    UM item de `required_assets` (BusinessPlan/Task) numa unidade de
    trabalho endereçável a um executor especializado externo, sem o Cris OS
    nunca virar ele mesmo um construtor de landing page/gerador de
    criativos/etc.

    Identidade preservada, ponta a ponta: `handoff_id` -> `project_id` ->
    `execution_plan_id` -> `source_task_id` -> esta WorkOrder -> (futuro)
    executor -> resultado. `global_project_id` é um campo RESERVADO (Secao 2
    -- preparo explícito para uma identidade cross-sistema futura, sem
    quebrar nada hoje); `project_id` continua sendo a identidade canônica
    real usada em todo o resto do sistema.
    """

    work_order_id: str = field(default_factory=novo_work_order_id)
    project_id: str = ""
    global_project_id: str | None = None  # reservado para evolução futura -- nao usado ainda
    handoff_id: str | None = None
    execution_plan_id: str | None = None
    source_task_id: str | None = None

    asset_type: str = "UNKNOWN"  # ver PRODUCTION_ASSET_TYPES_VALIDOS
    executor_type: str = "NEEDS_ROUTING"  # ver PRODUCTION_EXECUTOR_TYPES_VALIDOS

    title: str = ""
    objective: str | None = None
    requirements: list[str] = field(default_factory=list)  # texto original (nunca perdido na normalização)

    input_refs: list[str] = field(default_factory=list)
    output_refs: list[str] = field(default_factory=list)  # ver core/executor_adapter.py para o contrato de retorno

    status: str = "CREATED"  # ver PRODUCTION_WORK_ORDER_ESTADOS_VALIDOS
    requires_approval: bool = False
    approved: bool = False
    approved_at: str | None = None

    created_at: str = field(default_factory=_agora)
    updated_at: str = field(default_factory=_agora)

    attempts: int = 0
    last_error: str | None = None

    metadata: dict = field(default_factory=dict)  # provenance -- ex.: {"origem": "task_required_assets", "requisito_original": "..."}

    def esta_pronta_para_dispatch(self) -> bool:
        """`READY` e o único estado desta fase em que um FUTURO executor
        poderia legitimamente receber trabalho -- `NEEDS_ROUTING` nunca é
        despachável (ninguém sabe processar), e estados posteriores
        (`DISPATCHED`+) significam que já foi (ou está sendo) processada."""
        return self.status == "READY" and not (self.requires_approval and not self.approved)


# Vocabulario FECHADO de "verification before trust" (Fase 9) -- toda
# evidencia/afirmacao vinda do ScalaFlow precisa ser classificada, nunca
# aceita como fato so porque foi afirmada.
EVIDENCE_TIPOS_VALIDOS = frozenset({"OBSERVED", "DERIVED", "INFERRED", "UNKNOWN"})
CONFIDENCE_NIVEIS_VALIDOS = frozenset({"LOW", "MEDIUM", "HIGH", "UNKNOWN"})

# Estados de um MarketIntelligenceHandoff (Fase 9). RECEIVED e transitorio
# (antes da validacao); todo handoff processado termina em um dos outros --
# NUNCA silenciosamente ignorado.
MARKET_INTELLIGENCE_ESTADOS_VALIDOS = frozenset({
    "RECEIVED", "VALIDATED", "REJECTED", "DUPLICATE", "PERSISTED", "NEEDS_REVIEW",
})

SCHEMA_VERSIONS_SUPORTADAS = frozenset({"1.0"})


@dataclass
class Evidence:
    """
    Uma evidencia RASTREAVEL (Fase 9) -- nunca uma afirmacao solta.
    `evidence_type` classifica o QUANTO essa evidencia pode ser confiada:
    OBSERVED (visto diretamente na fonte), DERIVED (calculado a partir de
    evidencia real), INFERRED (conclusao de um modelo/agente -- a mais
    fraca), UNKNOWN (sem evidencia suficiente pra classificar). NUNCA
    "FACT"/"TRUE" -- esse vocabulario nao existe de proposito.
    """

    evidence_id: str = field(default_factory=lambda: "ev_" + uuid.uuid4().hex[:8])
    source_type: str | None = None  # ex.: "AD_LIBRARY", "TIKTOK", "GOOGLE_TRENDS"
    source_name: str | None = None
    source_url: str | None = None
    captured_at: str | None = None
    raw_reference: str | None = None
    metric_name: str | None = None
    metric_value: str | None = None
    metric_unit: str | None = None
    evidence_type: str = "UNKNOWN"
    confidence_level: str = "UNKNOWN"


@dataclass
class MarketIntelligenceHandoff:
    """
    Contrato CANONICO de entrada de inteligencia de mercado vinda do
    ScalaFlow (Fase 9) -- fronteira de integracao explicita entre os dois
    sistemas. NUNCA e tratado como fato confiavel automaticamente: todo
    campo de evidencia/confianca precisa vir classificado (ver `Evidence`,
    `confidence_level`), e um handoff so e persistido depois de passar por
    validacao + deduplicacao + resolucao de projeto (ver
    `core/market_intelligence.py`).

    Campos ausentes na fonte ficam `None`/lista vazia -- NUNCA inventados
    pra preencher o contrato.
    """

    handoff_id: str = field(default_factory=novo_handoff_id)
    schema_version: str = "1.0"
    source_system: str | None = None  # ex.: "SCALAFLOW"
    source_module: str | None = None  # ex.: "tiktok_miner", "ad_library_miner"
    created_at: str | None = None  # quando a fonte gerou o handoff
    received_at: str = field(default_factory=_agora)  # quando o CRIS OS recebeu

    project_id: str | None = None
    external_project_ref: str | None = None

    opportunity_id: str | None = None
    title: str | None = None
    market: str | None = None
    niche: str | None = None
    subniche: str | None = None
    country: str | None = None
    language: str | None = None
    description: str | None = None

    trend_signals: dict = field(default_factory=dict)
    demand_signals: dict = field(default_factory=dict)
    competition_signals: dict = field(default_factory=dict)
    ad_signals: dict = field(default_factory=dict)
    social_signals: dict = field(default_factory=dict)
    search_signals: dict = field(default_factory=dict)

    product_name: str | None = None
    offer_type: str | None = None
    price: str | None = None
    currency: str | None = None
    commission: str | None = None
    platform: str | None = None
    sales_page_url: str | None = None

    competitors: list[str] = field(default_factory=list)
    competitor_urls: list[str] = field(default_factory=list)
    observed_offers: list[str] = field(default_factory=list)

    evidence: list[dict] = field(default_factory=list)  # cada item = Evidence serializada (dict)

    confidence_score: float | None = None
    confidence_level: str = "UNKNOWN"
    confidence_reason: str | None = None

    opportunity_score: float | None = None
    score_components: dict = field(default_factory=dict)
    scoring_version: str | None = None

    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    status: str = "RECEIVED"
    rejection_reason: str | None = None


@dataclass
class ProjectBrain:
    identidade: Identidade
    origem: Origem = field(default_factory=Origem)
    mercado: Mercado = field(default_factory=Mercado)
    oportunidade: Oportunidade = field(default_factory=Oportunidade)
    decisao: Decisao = field(default_factory=Decisao)
    produto: Produto = field(default_factory=Produto)
    blueprint: ProductBlueprint | None = None
    business_plan: BusinessPlan | None = None
    production_plan: ProductionPlan | None = None
    traffic_plan: TrafficPlan | None = None
    campaign_spec: CampaignSpec | None = None
    performance_snapshots: list[PerformanceSnapshot] = field(default_factory=list)
    execution_plan: ExecutionPlan | None = None
    market_intelligence: list[MarketIntelligenceHandoff] = field(default_factory=list)
    production_work_orders: list[ProductionWorkOrder] = field(default_factory=list)
    artifact_manifest: dict | None = None
    brand: Brand = field(default_factory=Brand)
    assets: Assets = field(default_factory=Assets)
    trafego: Trafego = field(default_factory=Trafego)
    historico: Historico = field(default_factory=Historico)

    @property
    def project_id(self) -> str:
        return self.identidade.project_id

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectBrain":
        blueprint_dict = d.get("blueprint")
        business_plan_dict = d.get("business_plan")
        production_plan_dict = d.get("production_plan")
        traffic_plan_dict = d.get("traffic_plan")
        campaign_spec_dict = d.get("campaign_spec")
        execution_plan_dict = d.get("execution_plan")
        execution_plan = None
        if execution_plan_dict:
            tarefas = [Task(**t) for t in execution_plan_dict.get("tasks", [])]
            execution_plan = ExecutionPlan(**{**execution_plan_dict, "tasks": tarefas})
        return cls(
            identidade=Identidade(**d["identidade"]),
            origem=Origem(**d.get("origem", {})),
            mercado=Mercado(**d.get("mercado", {})),
            oportunidade=Oportunidade(**d.get("oportunidade", {})),
            decisao=Decisao(**d.get("decisao", {})),
            produto=Produto(**d.get("produto", {})),
            blueprint=ProductBlueprint(**blueprint_dict) if blueprint_dict else None,
            business_plan=BusinessPlan(**business_plan_dict) if business_plan_dict else None,
            production_plan=ProductionPlan(**production_plan_dict) if production_plan_dict else None,
            traffic_plan=TrafficPlan(**traffic_plan_dict) if traffic_plan_dict else None,
            campaign_spec=CampaignSpec(**campaign_spec_dict) if campaign_spec_dict else None,
            performance_snapshots=[PerformanceSnapshot(**s) for s in d.get("performance_snapshots", [])],
            execution_plan=execution_plan,
            market_intelligence=[MarketIntelligenceHandoff(**h) for h in d.get("market_intelligence", [])],
            production_work_orders=[ProductionWorkOrder(**w) for w in d.get("production_work_orders", [])],
            artifact_manifest=d.get("artifact_manifest"),
            brand=Brand(**d.get("brand", {})),
            assets=Assets(**d.get("assets", {})),
            trafego=Trafego(**d.get("trafego", {})),
            historico=Historico(**d.get("historico", {})),
        )

    def registrar_run(self, agente: str, resumo: str) -> None:
        self.historico.agent_runs.append({
            "agente": agente, "resumo": resumo, "timestamp": _agora(),
        })
        self.identidade.updated_at = _agora()

    def registrar_decisao(self, path: str, motivo: str) -> None:
        self.historico.decisions.append({
            "path": path, "motivo": motivo, "timestamp": _agora(),
        })
        self.identidade.updated_at = _agora()

    def registrar_aprovacao(self, status: str, motivo: str = "") -> None:
        """Registra uma aprovacao/rejeicao do blueprint no historico (Fase 3)."""
        self.historico.approvals.append({
            "status": status, "motivo": motivo, "timestamp": _agora(),
        })
        self.identidade.updated_at = _agora()

    def coletar_evidencias_pesquisa(self) -> list[str]:
        """
        Fonte CANONICA de "quais evidencias de pesquisa este projeto tem"
        (Fase 5 -- correcao de bug real). Antes disso existir, cada
        consumidor calculava isso do seu proprio jeito:
          - o Artifact Manifest ("01-Pesquisa") contava headline/copy/score/
            caminho_decidido;
          - o Paid Traffic Architect (`avaliar_prontidao`) so olhava
            `oportunidade.evidence` (exclusivamente sinais cross-plataforma
            do Opportunity Analyst -- TikTok/Instagram/YouTube/Trends).
        Um projeto real pode ter headline/copy/score/nicho reais mas ZERO
        sinal cross-plataforma confirmado (nenhuma fonte externa bateu) --
        os dois metodos chegavam a respostas DIFERENTES pro MESMO projeto
        (manifesto dizia "4 evidencias", Paid Traffic Architect dizia
        "nenhuma evidencia"). Agora os dois usam ESTA MESMA lista.

        NUNCA inventa dado -- so agrega o que ja existe em outros campos do
        ProjectBrain (nao e uma segunda fonte de verdade, e uma VISAO
        derivada).
        """
        itens: list[str] = []
        if self.origem.source_headline:
            itens.append(f"headline: {self.origem.source_headline}")
        if self.origem.source_copy:
            itens.append(f"copy: {self.origem.source_copy}")
        if self.oportunidade.score is not None:
            itens.append(f"score_scalaflow: {self.oportunidade.score}")
        if self.mercado.niche:
            itens.append(f"nicho: {self.mercado.niche}")
        itens.extend(self.oportunidade.evidence)
        if self.decisao.recommended_path:
            itens.append(f"caminho_decidido: {self.decisao.recommended_path}")
        return itens


class ProjectBrainStore:
    """Persiste/recupera ProjectBrain reaproveitando `ProjectMemory` (L2)."""

    def __init__(self, project_memory) -> None:
        self._pm = project_memory

    @property
    def project_memory(self):
        """Expoe a `ProjectMemory` (L2) usada por este store, para que
        `UserFocusStore` (Fase 3) reaproveite a MESMA conexao/backend em vez
        de abrir uma segunda -- garante que os dois sempre apontam pro
        mesmo `data/cris_os.db` (ou pro mesmo banco de teste, quando
        monkeypatchado)."""
        return self._pm

    @staticmethod
    def _item_id(project_id: str) -> str:
        return f"brain:{project_id}"

    def save(self, brain: ProjectBrain) -> None:
        brain.identidade.updated_at = _agora()
        payload = json.dumps(brain.to_dict(), ensure_ascii=False)
        item = KnowledgeItem(
            id=self._item_id(brain.project_id),
            type=_TYPE,
            title=brain.identidade.name or brain.project_id,
            content=payload,
            tags=[brain.identidade.type or "opportunity", brain.identidade.status],
        )
        self._pm.backend.remember_project(brain.project_id, item)

    def load(self, project_id: str) -> ProjectBrain | None:
        for item in self._pm.recall(project_id):
            if item.type == _TYPE:
                return ProjectBrain.from_dict(json.loads(item.content))
        return None

    def create(self, name: str, tipo: str = "opportunity") -> ProjectBrain:
        project_id = novo_project_id()
        brain = ProjectBrain(identidade=Identidade(project_id=project_id, name=name, type=tipo))
        self.save(brain)
        return brain

    def list_all(self) -> list[ProjectBrain]:
        out: list[ProjectBrain] = []
        for project_id in self._pm.all_projects():
            brain = self.load(project_id)
            if brain:
                out.append(brain)
        return out


# ---------------------------------------------------------------------------
# Foco por usuario/canal (correcao pos-teste real da Fase 3)
# ---------------------------------------------------------------------------
#
# Problema corrigido: "qual oportunidade esta em foco" vivia so numa
# variavel Python em `tools/opportunity_tools.py` -- perdida a cada restart
# do processo, e compartilhada por TODOS os usuarios (nunca isolada por
# pessoa/canal). `UserFocusStore` persiste isso reaproveitando a MESMA
# infraestrutura do Project Brain (`ProjectMemory`/`project_memory`,
# `data/cris_os.db`) -- nao cria uma segunda fonte de verdade, so usa uma
# outra "gaveta" (chave logica) dentro da mesma tabela: cada foco vira um
# `KnowledgeItem` com `type="user_focus"`, guardado sob uma "project key"
# pseudo `__focus__:<session>` (nunca colide com um `project_id` real, que
# sempre comeca com "proj_").
_FOCUS_TYPE = "user_focus"


def _focus_pseudo_project(session: str) -> str:
    return f"__focus__:{session}"


class UserFocusStore:
    """Persiste/recupera 'qual projeto esta em foco' POR sessao (canal+
    usuario, ex.: "telegram:6460872429") -- preparado para multiusuario:
    cada sessao tem seu proprio foco, nunca um global compartilhado."""

    def __init__(self, project_memory) -> None:
        self._pm = project_memory

    @staticmethod
    def _item_id(session: str) -> str:
        return f"focus:{session}"

    def set_focus(self, session: str, project_id: str, opportunity_id: str | None = None) -> None:
        if not session:
            return  # sem sessao (ex.: teste antigo sem contexto) -- nao persiste as cegas
        payload = json.dumps({
            "session": session,
            "project_id": project_id,
            "opportunity_id": opportunity_id,
            "updated_at": _agora(),
        }, ensure_ascii=False)
        item = KnowledgeItem(
            id=self._item_id(session),
            type=_FOCUS_TYPE,
            title=f"foco:{session}",
            content=payload,
            tags=[session],
        )
        self._pm.backend.remember_project(_focus_pseudo_project(session), item)

    def get_focus(self, session: str) -> str | None:
        if not session:
            return None
        for item in self._pm.recall(_focus_pseudo_project(session)):
            if item.type == _FOCUS_TYPE:
                try:
                    dados = json.loads(item.content)
                except json.JSONDecodeError:
                    return None
                return dados.get("project_id")
        return None


# ---------------------------------------------------------------------------
# Aprovacao pendente por sessao (Fase 6 -- correcao estrutural de bug real)
# ---------------------------------------------------------------------------
#
# Bug real corrigido: uma aprovacao curta ("Aprovado") nao tinha como saber
# A QUAL artefato (TrafficPlan? CampaignSpec?) ela se referia -- o
# AgentOrchestrator nao tinha nenhuma interceptacao deterministica pra
# "Aprovado" sozinho fora do mecanismo de continuidade do Product Architect
# (Fase 3, baseado em `last_agents`, em memoria, nao persistido), entao a
# mensagem caia no assistente generico. `PendingApprovalStore` persiste QUAL
# aprovacao esta pendente, POR SESSAO -- reaproveitando a MESMA
# infraestrutura do Project Brain/UserFocusStore (nenhum banco paralelo):
# cada pendencia vira um `KnowledgeItem` com `type="pending_approval"`,
# guardado sob uma "project key" pseudo `__pending_approval__:<session>`
# (nunca colide com um `project_id` real).
_PENDING_APPROVAL_TYPE = "pending_approval"


def _pending_approval_pseudo_project(session: str) -> str:
    return f"__pending_approval__:{session}"


class PendingApprovalStore:
    """Persiste/recupera QUAL aprovacao esta pendente (project_id +
    artifact_type + action), POR sessao -- nunca deixa uma aprovacao curta
    ("Aprovado") ser aplicada por adivinhacao. Usado por
    `core/approval_router.py` (Fase 6)."""

    def __init__(self, project_memory) -> None:
        self._pm = project_memory

    @staticmethod
    def _item_id(session: str) -> str:
        return f"pending_approval:{session}"

    def set_pending(
        self, session: str, project_id: str, artifact_type: str,
        action: str = "APPROVE", task_id: str | None = None,
        handoff_id: str | None = None,
    ) -> None:
        """`task_id` (Fase 8) e opcional -- so usado quando `artifact_type`
        e "EXECUTION_TASK" (a Task nao e um atributo direto do
        ProjectBrain, entao precisa desse identificador extra pra
        `core/approval_router.py` localiza-la sem ambiguidade). `handoff_id`
        (integracao ScalaFlow) e opcional -- quando a pendencia se origina
        de um `MarketIntelligenceHandoff`, registra o vinculo explicito
        project_id+handoff_id na propria pendencia (nunca so implicito via
        lookup), para auditoria/rastreabilidade sem ambiguidade."""
        if not session:
            return  # sem sessao -- nao persiste as cegas (mesmo principio do UserFocusStore)
        payload = json.dumps({
            "project_id": project_id,
            "artifact_type": artifact_type,
            "action": action,
            "task_id": task_id,
            "handoff_id": handoff_id,
            "created_at": _agora(),
        }, ensure_ascii=False)
        item = KnowledgeItem(
            id=self._item_id(session),
            type=_PENDING_APPROVAL_TYPE,
            title=f"pending_approval:{session}",
            content=payload,
            tags=[session],
        )
        self._pm.backend.remember_project(_pending_approval_pseudo_project(session), item)

    def get_pending(self, session: str) -> dict | None:
        if not session:
            return None
        for item in self._pm.recall(_pending_approval_pseudo_project(session)):
            if item.type == _PENDING_APPROVAL_TYPE:
                try:
                    return json.loads(item.content)
                except json.JSONDecodeError:
                    return None
        return None

    def clear_pending(self, session: str) -> None:
        """Sobrescreve com `null` -- mesma "gaveta" (upsert), nunca deixa
        uma pendencia ja consumida disponivel pra reuso."""
        if not session:
            return
        item = KnowledgeItem(
            id=self._item_id(session),
            type=_PENDING_APPROVAL_TYPE,
            title=f"pending_approval:{session}",
            content=json.dumps(None),
            tags=[session],
        )
        self._pm.backend.remember_project(_pending_approval_pseudo_project(session), item)


# ---------------------------------------------------------------------------
# Indice global de handoffs de inteligencia de mercado (Fase 9 -- idempotencia)
# ---------------------------------------------------------------------------
#
# Deduplicacao PRECISA funcionar mesmo ANTES de saber a qual projeto um
# handoff pertence (um handoff duplicado enviado sem `project_id` ainda
# precisa ser reconhecido como duplicata). Por isso este indice e chaveado
# GLOBALMENTE por `handoff_id` -- nao por sessao nem por projeto -- mesma
# infraestrutura (`ProjectMemory`/`KnowledgeItem`), mesma "gaveta" pseudo-
# projeto, nenhum banco paralelo.
_INTELLIGENCE_HANDOFF_TYPE = "intelligence_handoff_index"


def _intelligence_handoff_pseudo_project(handoff_id: str) -> str:
    return f"__intelligence_handoff__:{handoff_id}"


class IntelligenceHandoffStore:
    """Indice GLOBAL (por `handoff_id`, nao por sessao/projeto) de handoffs
    de inteligencia de mercado ja processados -- usado por
    `core/market_intelligence.py` para deduplicacao/idempotencia e para
    `get_intelligence(handoff_id)`."""

    def __init__(self, project_memory) -> None:
        self._pm = project_memory

    @staticmethod
    def _item_id(handoff_id: str) -> str:
        return f"intelligence_handoff:{handoff_id}"

    def registrar(self, handoff_id: str, project_id: str, status: str) -> None:
        if not handoff_id:
            return
        payload = json.dumps({
            "handoff_id": handoff_id,
            "project_id": project_id,
            "status": status,
            "registered_at": _agora(),
        }, ensure_ascii=False)
        item = KnowledgeItem(
            id=self._item_id(handoff_id),
            type=_INTELLIGENCE_HANDOFF_TYPE,
            title=f"intelligence_handoff:{handoff_id}",
            content=payload,
            tags=[handoff_id],
        )
        self._pm.backend.remember_project(_intelligence_handoff_pseudo_project(handoff_id), item)

    def buscar(self, handoff_id: str) -> dict | None:
        if not handoff_id:
            return None
        for item in self._pm.recall(_intelligence_handoff_pseudo_project(handoff_id)):
            if item.type == _INTELLIGENCE_HANDOFF_TYPE:
                try:
                    return json.loads(item.content)
                except json.JSONDecodeError:
                    return None
        return None

    def ja_processado(self, handoff_id: str) -> bool:
        return self.buscar(handoff_id) is not None
