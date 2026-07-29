"""
Rotas de tarefas — CRUD completo.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
USUARIO_PADRAO = "dashboard"


class TarefaRequest(BaseModel):
    titulo: str
    descricao: str = ""
    prioridade: str = "media"
    prazo: str = ""
    responsavel: str = ""
    projeto_id: Optional[int] = None


@router.get("/tarefas")
def listar_tarefas():
    from services.task_manager import TaskManager
    return TaskManager().listar(USUARIO_PADRAO)


@router.get("/tarefas/pendentes")
def tarefas_pendentes():
    from services.task_manager import TaskManager
    return TaskManager().pendentes(USUARIO_PADRAO)


@router.get("/tarefas/{tarefa_id}")
def abrir_tarefa(tarefa_id: int):
    from services.task_manager import TaskManager
    return TaskManager().abrir(tarefa_id) or {"erro": "Tarefa nao encontrada"}


@router.post("/tarefas")
def criar_tarefa(req: TarefaRequest):
    from services.task_manager import TaskManager
    return TaskManager().criar(USUARIO_PADRAO, req.titulo, req.descricao,
                                req.prioridade, req.prazo, req.responsavel, req.projeto_id)


@router.put("/tarefas/{tarefa_id}")
def atualizar_tarefa(tarefa_id: int, req: TarefaRequest):
    from services.task_manager import TaskManager
    tm = TaskManager()
    tm.atualizar(tarefa_id, titulo=req.titulo, descricao=req.descricao,
                 prioridade=req.prioridade, prazo=req.prazo,
                 responsavel=req.responsavel, projeto_id=req.projeto_id)
    return tm.abrir(tarefa_id)


@router.post("/tarefas/{tarefa_id}/concluir")
def concluir_tarefa(tarefa_id: int):
    from services.task_manager import TaskManager
    TaskManager().concluir(tarefa_id)
    return {"status": "ok"}


@router.delete("/tarefas/{tarefa_id}")
def excluir_tarefa(tarefa_id: int):
    from services.task_manager import TaskManager
    TaskManager().excluir(tarefa_id)
    return {"status": "ok"}
