"""
Rotas de projetos — CRUD completo.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
USUARIO_PADRAO = "dashboard"


class ProjetoRequest(BaseModel):
    nome: str
    descricao: str = ""
    contexto: str = ""


@router.get("/projetos")
def listar_projetos():
    from services.project_manager import ProjectManager
    return ProjectManager().listar(USUARIO_PADRAO)


@router.get("/projetos/{projeto_id}")
def abrir_projeto(projeto_id: int):
    from services.project_manager import ProjectManager
    return ProjectManager().abrir(projeto_id) or {"erro": "Projeto nao encontrado"}


@router.post("/projetos")
def criar_projeto(req: ProjetoRequest):
    from services.project_manager import ProjectManager
    return ProjectManager().criar(USUARIO_PADRAO, req.nome, req.descricao, req.contexto)


@router.put("/projetos/{projeto_id}")
def atualizar_projeto(projeto_id: int, req: ProjetoRequest):
    from services.project_manager import ProjectManager
    pm = ProjectManager()
    pm.atualizar(projeto_id, nome=req.nome, descricao=req.descricao, contexto=req.contexto)
    return pm.abrir(projeto_id)


@router.delete("/projetos/{projeto_id}")
def excluir_projeto(projeto_id: int):
    from services.project_manager import ProjectManager
    ProjectManager().excluir(projeto_id)
    return {"status": "ok"}
