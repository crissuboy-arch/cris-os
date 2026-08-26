"""
Rotas de tarefas — CRUD completo + planejamento diário.
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
    agente: str = ""


class PlanejamentoRequest(BaseModel):
    data: str = ""
    prioridades: list[str] = []


@router.get("/tarefas")
def listar_tarefas():
    from services.task_manager import TaskManager
    return TaskManager().listar(USUARIO_PADRAO)


@router.get("/tarefas/pendentes")
def tarefas_pendentes():
    from services.task_manager import TaskManager
    return TaskManager().pendentes(USUARIO_PADRAO)


@router.get("/tarefas/hoje")
def tarefas_hoje():
    from services.task_manager import TaskManager
    from datetime import datetime
    hoje = datetime.now().strftime("%Y-%m-%d")
    tm = TaskManager()
    todas = tm.listar(USUARIO_PADRAO)
    return [t for t in todas if t.get("prazo", "").startswith(hoje) and t.get("status") != "concluida"]


@router.get("/tarefas/status/{status}")
def tarefas_por_status(status: str):
    from services.task_manager import TaskManager
    from database.connection import get_connection
    conn = get_connection()
    cur = conn.execute(
        "SELECT * FROM tarefas WHERE usuario_id=? AND status=? ORDER BY criado_em DESC",
        (USUARIO_PADRAO, status),
    )
    return [dict(r) for r in cur.fetchall()]


@router.get("/tarefas/{tarefa_id}")
def abrir_tarefa(tarefa_id: int):
    from services.task_manager import TaskManager
    return TaskManager().abrir(tarefa_id) or {"erro": "Tarefa nao encontrada"}


@router.post("/tarefas")
def criar_tarefa(req: TarefaRequest):
    from services.task_manager import TaskManager
    return TaskManager().criar(USUARIO_PADRAO, req.titulo, req.descricao,
                                req.prioridade, req.prazo, req.responsavel,
                                req.agente, req.projeto_id)


@router.put("/tarefas/{tarefa_id}")
def atualizar_tarefa(tarefa_id: int, req: TarefaRequest):
    from services.task_manager import TaskManager
    tm = TaskManager()
    tm.atualizar(tarefa_id, titulo=req.titulo, descricao=req.descricao,
                 prioridade=req.prioridade, prazo=req.prazo,
                 responsavel=req.responsavel, projeto_id=req.projeto_id,
                 agente=req.agente)
    return tm.abrir(tarefa_id)


@router.post("/tarefas/{tarefa_id}/concluir")
def concluir_tarefa(tarefa_id: int):
    from services.task_manager import TaskManager
    TaskManager().concluir(tarefa_id)
    return {"status": "ok"}


@router.post("/tarefas/{tarefa_id}/cancelar")
def cancelar_tarefa(tarefa_id: int):
    from services.task_manager import TaskManager
    tm = TaskManager()
    tm.cancelar(tarefa_id)
    return {"status": "ok"}


@router.post("/tarefas/{tarefa_id}/delegar")
def delegar_tarefa(tarefa_id: int, responsavel: str = "", agente: str = ""):
    from services.task_manager import TaskManager
    tm = TaskManager()
    tarefa = tm.delegar(tarefa_id, responsavel, agente)
    return tarefa or {"erro": "Tarefa nao encontrada"}


@router.delete("/tarefas/{tarefa_id}")
def excluir_tarefa(tarefa_id: int):
    from services.task_manager import TaskManager
    TaskManager().excluir(tarefa_id)
    return {"status": "ok"}


@router.post("/planejamento/diario")
def planejar_dia(req: PlanejamentoRequest):
    """Gera um plano diário baseado nas prioridades."""
    from services.task_manager import TaskManager
    from datetime import datetime

    data = req.data or datetime.now().strftime("%Y-%m-%d")
    tm = TaskManager()
    pendentes = tm.pendentes(USUARIO_PADRAO)

    plano = {
        "data": data,
        "tarefas": [],
        "prioridades": req.prioridades or [],
        "total_tarefas": len(pendentes),
        "total_alta": len([t for t in pendentes if t.get("prioridade") == "alta"]),
        "total_media": len([t for t in pendentes if t.get("prioridade") == "media"]),
        "total_baixa": len([t for t in pendentes if t.get("prioridade") == "baixa"]),
    }

    # Ordena por prioridade e prazo
    for t in pendentes[:10]:
        plano["tarefas"].append({
            "id": t["id"],
            "titulo": t["titulo"],
            "prioridade": t.get("prioridade", "media"),
            "prazo": t.get("prazo", ""),
            "projeto_id": t.get("projeto_id"),
            "agente": t.get("agente", ""),
            "status": t.get("status", "pendente"),
        })

    return plano


@router.get("/tarefas/atrasadas")
def tarefas_atrasadas():
    from services.task_manager import TaskManager
    return TaskManager().atrasadas(USUARIO_PADRAO)


@router.get("/revisao/semanal")
def revisao_semanal():
    from services.task_manager import TaskManager
    return TaskManager().revisao_semanal(USUARIO_PADRAO)


class LembreteRequest(BaseModel):
    titulo: str
    data_hora: str
    recorrencia: str = ""
    tarefa_id: Optional[int] = None


@router.get("/lembretes")
def listar_lembretes():
    from services.reminder_manager import ReminderManager
    return ReminderManager().listar(USUARIO_PADRAO)


@router.post("/lembretes")
def criar_lembrete(req: LembreteRequest):
    from services.reminder_manager import ReminderManager
    return ReminderManager().criar(USUARIO_PADRAO, req.titulo, req.data_hora,
                                    req.recorrencia, req.tarefa_id)


@router.post("/lembretes/{lembrete_id}/cancelar")
def cancelar_lembrete(lembrete_id: int):
    from services.reminder_manager import ReminderManager
    ReminderManager().cancelar(lembrete_id)
    return {"status": "ok"}


@router.get("/lembretes/devidos")
def lembretes_devidos():
    from services.reminder_manager import ReminderManager
    return ReminderManager().devidos(USUARIO_PADRAO)


@router.post("/lembretes/processar")
def processar_lembretes():
    from services.reminder_manager import ReminderManager
    return {"disparados": ReminderManager().processar_devidos(USUARIO_PADRAO)}
