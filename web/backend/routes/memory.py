"""
Rotas de memoria — CRUD de contexto e preferencias.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
USUARIO_PADRAO = "dashboard"


class MemoriaRequest(BaseModel):
    chave: str
    valor: str


@router.get("/memoria")
def listar_memoria():
    """Lista contexto recente + preferencias."""
    from services.memory_manager import MemoryManager
    mm = MemoryManager()
    return {
        "preferencias": mm.listar_preferencias(USUARIO_PADRAO),
        "contexto": mm.contexto_recente(USUARIO_PADRAO, 10),
    }


@router.post("/memoria")
def adicionar_memoria(req: MemoriaRequest):
    """Adiciona uma preferencia/contexto."""
    from services.memory_manager import MemoryManager
    mm = MemoryManager()
    mm.definir_preferencia(USUARIO_PADRAO, req.chave, req.valor)
    return {"status": "ok", "chave": req.chave, "valor": req.valor}


@router.put("/memoria/{chave}")
def atualizar_memoria(chave: str, req: MemoriaRequest):
    """Atualiza uma preferencia."""
    from services.memory_manager import MemoryManager
    mm = MemoryManager()
    mm.definir_preferencia(USUARIO_PADRAO, chave, req.valor)
    return {"status": "ok", "chave": chave, "valor": req.valor}


@router.delete("/memoria/{chave}")
def excluir_memoria(chave: str):
    """Exclui uma preferencia."""
    from database.connection import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM preferencias WHERE usuario_id=? AND chave=?", (USUARIO_PADRAO, chave))
    conn.commit()
    return {"status": "ok"}
