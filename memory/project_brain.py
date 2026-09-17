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


@dataclass
class ProjectBrain:
    identidade: Identidade
    origem: Origem = field(default_factory=Origem)
    mercado: Mercado = field(default_factory=Mercado)
    oportunidade: Oportunidade = field(default_factory=Oportunidade)
    decisao: Decisao = field(default_factory=Decisao)
    produto: Produto = field(default_factory=Produto)
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
        return cls(
            identidade=Identidade(**d["identidade"]),
            origem=Origem(**d.get("origem", {})),
            mercado=Mercado(**d.get("mercado", {})),
            oportunidade=Oportunidade(**d.get("oportunidade", {})),
            decisao=Decisao(**d.get("decisao", {})),
            produto=Produto(**d.get("produto", {})),
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


class ProjectBrainStore:
    """Persiste/recupera ProjectBrain reaproveitando `ProjectMemory` (L2)."""

    def __init__(self, project_memory) -> None:
        self._pm = project_memory

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
