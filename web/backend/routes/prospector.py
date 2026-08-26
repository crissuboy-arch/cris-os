"""
Rotas do modulo Prospector (Máquina de Leads integrada ao CRIS OS).

Delegam para a fachada ProspectorService — nenhuma regra de negocio aqui.
Padrão de auth do CRIS OS Dashboard (mesmo dos demais routers).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class BuscaRequest(BaseModel):
    nicho: str
    cidade: str
    quantos: int | None = None
    simular: bool | None = None


class SlugRequest(BaseModel):
    slug: str
    simular: bool | None = None


class FecharRequest(BaseModel):
    slug: str
    valor: float
    manutencao: float | None = None


def _svc():
    from services.prospector.service import get_prospector_service
    return get_prospector_service()


@router.get("/prospector/status")
def prospector_status():
    return _svc().status()


@router.get("/prospector/leads")
def prospector_leads(status: str | None = None):
    return _svc().leads(status)


@router.get("/prospector/contratos")
def prospector_contratos():
    return _svc().contratos()


@router.get("/prospector/financeiro")
def prospector_financeiro():
    return _svc().financeiro()


@router.post("/prospector/search")
def prospector_search(req: BuscaRequest):
    return _svc().prospectar(req.nicho, req.cidade, req.quantos, req.simular)


@router.post("/prospector/redesign")
def prospector_redesign(req: SlugRequest):
    return _svc().redesenhar(req.slug, req.simular)


@router.post("/prospector/publish")
def prospector_publish(req: SlugRequest):
    return _svc().publicar(req.slug, req.simular)


@router.post("/prospector/proposal")
def prospector_proposal(req: SlugRequest):
    return _svc().proposta(req.slug, req.simular)


@router.post("/prospector/contracts")
def prospector_contracts(req: SlugRequest):
    return _svc().contrato(req.slug, req.simular)


@router.post("/prospector/followup")
def prospector_followup(simular: bool | None = None):
    return _svc().followups(simular)


@router.post("/prospector/fechar")
def prospector_fechar(req: FecharRequest):
    return _svc().fechar(req.slug, req.valor, req.manutencao)
