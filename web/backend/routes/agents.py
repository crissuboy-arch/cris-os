"""
Rotas de agentes — lista, detalhe, teste rapido.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class TesteRequest(BaseModel):
    mensagem: str


@router.get("/agents")
def listar_agentes():
    """Lista todos os agentes com status e ferramentas."""
    from agents import AGENT_MODULES, GENERAL_MODULE

    resultado = []
    for mod_path in AGENT_MODULES:
        try:
            import importlib
            mod = importlib.import_module(mod_path)
            nome = getattr(mod, "name", mod_path.split(".")[-1])
            desc = getattr(mod, "description", "")
            tools = []
            try:
                tools_mod = __import__(f"tools.{nome}_tools", fromlist=["get_tools"])
                tools = [t.name for t in tools_mod.get_tools()]
            except Exception:
                pass
            resultado.append({
                "nome": nome,
                "descricao": desc,
                "status": "ativo",
                "ferramentas": tools,
            })
        except Exception as exc:
            resultado.append({
                "nome": mod_path.split(".")[-1],
                "descricao": "",
                "status": f"erro: {exc}",
                "ferramentas": [],
            })

    try:
        import importlib
        mod = importlib.import_module(GENERAL_MODULE)
        resultado.append({
            "nome": getattr(mod, "name", "geral"),
            "descricao": getattr(mod, "description", ""),
            "status": "ativo",
            "ferramentas": [],
        })
    except Exception:
        pass

    return resultado


@router.get("/agents/{nome}")
def detalhe_agente(nome: str):
    """Detalhe de um agente especifico."""
    from agents import AGENT_MODULES, GENERAL_MODULE
    import importlib

    for mod_path in list(AGENT_MODULES) + [GENERAL_MODULE]:
        try:
            mod = importlib.import_module(mod_path)
            if getattr(mod, "name", "") == nome:
                desc = getattr(mod, "description", "")
                tools = []
                try:
                    tools_mod = __import__(f"tools.{nome}_tools", fromlist=["get_tools"])
                    tools = [
                        {"nome": t.name, "descricao": t.description, "keywords": t.keywords}
                        for t in tools_mod.get_tools()
                    ]
                except Exception:
                    pass
                return {
                    "nome": nome,
                    "descricao": desc,
                    "status": "ativo",
                    "ferramentas": tools,
                }
        except Exception:
            pass
    return {"erro": "Agente nao encontrado"}


@router.post("/agents/testar")
def testar_agente(req: TesteRequest):
    """Testa um agente com uma mensagem."""
    return {"resposta": f"Teste: {req.mensagem}"}
