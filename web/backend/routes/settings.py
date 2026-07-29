"""
Rotas de configuracoes — get/set configuracoes do sistema.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
USUARIO_PADRAO = "dashboard"


class ConfigRequest(BaseModel):
    chave: str
    valor: str


@router.get("/configuracoes")
def listar_configuracoes():
    from services.config_manager import ConfigManager
    return ConfigManager().listar(USUARIO_PADRAO)


@router.post("/configuracoes")
def definir_configuracao(req: ConfigRequest):
    from services.config_manager import ConfigManager
    ConfigManager().set(USUARIO_PADRAO, req.chave, req.valor)
    return {"status": "ok", "chave": req.chave, "valor": req.valor}


@router.post("/configuracoes/resetar")
def resetar_configuracoes():
    from services.config_manager import ConfigManager
    ConfigManager().resetar(USUARIO_PADRAO)
    return {"status": "ok"}
