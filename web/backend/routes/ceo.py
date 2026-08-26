"""
Rotas do CEO Mode — objetivos, planos, progresso e relatorios.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
USUARIO_PADRAO = "dashboard"


class ObjetivoRequest(BaseModel):
    objetivo: str
    confirmado: bool = False


@router.post("/ceo/executar")
def ceo_executar(req: ObjetivoRequest):
    from services.ceo_mode import CeoMode
    return CeoMode().executar(req.objetivo, USUARIO_PADRAO,
                              confirmado=req.confirmado)


@router.post("/ceo/planejar")
def ceo_planejar(req: ObjetivoRequest):
    from services.ceo_mode import CeoMode
    return CeoMode().planejar(req.objetivo)


@router.get("/ceo/objetivos")
def ceo_objetivos():
    from services.ceo_mode import CeoMode
    return CeoMode().listar(USUARIO_PADRAO)


@router.get("/ceo/objetivos/{objetivo_id}")
def ceo_objetivo(objetivo_id: int):
    from services.ceo_mode import CeoMode
    return CeoMode().relatorio(objetivo_id)


@router.get("/ceo/objetivos/{objetivo_id}/progresso")
def ceo_progresso(objetivo_id: int):
    from services.ceo_mode import CeoMode
    return CeoMode().progresso(objetivo_id)


@router.get("/ceo/objetivos/{objetivo_id}/proxima-acao")
def ceo_proxima_acao(objetivo_id: int):
    from services.ceo_mode import CeoMode
    return {"proxima_acao": CeoMode().proxima_acao(objetivo_id)}


@router.get("/ceo/objetivos/{objetivo_id}/confirmacoes")
def ceo_confirmacoes(objetivo_id: int):
    from services.ceo_mode import CeoMode
    return CeoMode().confirmacoes_pendentes(objetivo_id)
