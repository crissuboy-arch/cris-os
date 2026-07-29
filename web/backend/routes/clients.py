"""
Rotas de clientes — CRUD completo.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
USUARIO_PADRAO = "dashboard"


class ClienteRequest(BaseModel):
    nome: str
    empresa: str = ""
    telefone: str = ""
    email: str = ""
    observacoes: str = ""


@router.get("/clientes")
def listar_clientes():
    from services.client_manager import ClientManager
    return ClientManager().listar(USUARIO_PADRAO)


@router.get("/clientes/{cliente_id}")
def abrir_cliente(cliente_id: int):
    from services.client_manager import ClientManager
    return ClientManager().abrir(cliente_id) or {"erro": "Cliente nao encontrado"}


@router.post("/clientes")
def criar_cliente(req: ClienteRequest):
    from services.client_manager import ClientManager
    return ClientManager().criar(USUARIO_PADRAO, req.nome, req.empresa, req.telefone, req.email, req.observacoes)


@router.put("/clientes/{cliente_id}")
def atualizar_cliente(cliente_id: int, req: ClienteRequest):
    from services.client_manager import ClientManager
    cm = ClientManager()
    cm.atualizar(cliente_id, nome=req.nome, empresa=req.empresa,
                 telefone=req.telefone, email=req.email, observacoes=req.observacoes)
    return cm.abrir(cliente_id)


@router.delete("/clientes/{cliente_id}")
def excluir_cliente(cliente_id: int):
    from services.client_manager import ClientManager
    ClientManager().excluir(cliente_id)
    return {"status": "ok"}
