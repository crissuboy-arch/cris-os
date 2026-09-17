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


@dataclass
class ProjectBrain:
    identidade: Identidade
    origem: Origem = field(default_factory=Origem)
    mercado: Mercado = field(default_factory=Mercado)
    oportunidade: Oportunidade = field(default_factory=Oportunidade)
    decisao: Decisao = field(default_factory=Decisao)
    produto: Produto = field(default_factory=Produto)
    blueprint: ProductBlueprint | None = None
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
        return cls(
            identidade=Identidade(**d["identidade"]),
            origem=Origem(**d.get("origem", {})),
            mercado=Mercado(**d.get("mercado", {})),
            oportunidade=Oportunidade(**d.get("oportunidade", {})),
            decisao=Decisao(**d.get("decisao", {})),
            produto=Produto(**d.get("produto", {})),
            blueprint=ProductBlueprint(**blueprint_dict) if blueprint_dict else None,
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
