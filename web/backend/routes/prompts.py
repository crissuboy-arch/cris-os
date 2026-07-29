"""
Rotas de biblioteca de prompts — CRUD completo.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
USUARIO_PADRAO = "dashboard"


class PromptRequest(BaseModel):
    titulo: str
    conteudo: str
    categoria: str = ""
    favorito: bool = False


@router.get("/prompts")
def listar_prompts(categoria: str = ""):
    from services.prompt_library import PromptLibrary
    pl = PromptLibrary()
    if categoria:
        return pl.por_categoria(USUARIO_PADRAO, categoria)
    return pl.listar(USUARIO_PADRAO)


@router.get("/prompts/buscar")
def buscar_prompts(termo: str):
    from services.prompt_library import PromptLibrary
    return PromptLibrary().buscar(USUARIO_PADRAO, termo)


@router.get("/prompts/favoritos")
def prompts_favoritos():
    from services.prompt_library import PromptLibrary
    return PromptLibrary().favoritos(USUARIO_PADRAO)


@router.post("/prompts")
def criar_prompt(req: PromptRequest):
    from services.prompt_library import PromptLibrary
    return PromptLibrary().adicionar(USUARIO_PADRAO, req.titulo, req.conteudo, req.categoria, req.favorito)


@router.put("/prompts/{prompt_id}")
def atualizar_prompt(prompt_id: int, req: PromptRequest):
    from services.prompt_library import PromptLibrary
    pl = PromptLibrary()
    pl.atualizar(prompt_id, titulo=req.titulo, conteudo=req.conteudo,
                 categoria=req.categoria, favorito=int(req.favorito))
    return {"status": "ok"}


@router.post("/prompts/{prompt_id}/favorito")
def alternar_favorito(prompt_id: int):
    from services.prompt_library import PromptLibrary
    PromptLibrary().alternar_favorito(prompt_id)
    return {"status": "ok"}


@router.delete("/prompts/{prompt_id}")
def excluir_prompt(prompt_id: int):
    from services.prompt_library import PromptLibrary
    PromptLibrary().excluir(prompt_id)
    return {"status": "ok"}
