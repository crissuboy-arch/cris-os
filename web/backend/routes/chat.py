"""
Rotas de chat — enviar mensagem, historico, novo chat.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class MensagemRequest(BaseModel):
    mensagem: str
    agente: str = "auto"
    modelo: str = ""
    usuario_id: str = "dashboard"


@router.post("/chat/enviar")
def enviar_mensagem(req: MensagemRequest):
    """Envia mensagem para um agente e retorna resposta."""
    from agents import discover_agents, discover_general_agent, AgentOrchestrator
    from core.llm_providers.ollama import OllamaProvider
    from core.config import get_settings
    from core.models import IncomingMessage

    settings = get_settings()
    modelo = req.modelo or settings.OLLAMA_MODEL
    ollama = OllamaProvider(model=modelo, base_url=settings.OLLAMA_HOST)

    especialistas = discover_agents(ollama)
    geral = discover_general_agent(ollama)

    orch = AgentOrchestrator(
        llm=ollama, agents=especialistas, general_agent=geral,
    )

    if req.agente != "auto":
        orch.set_active_agent(req.usuario_id, req.agente)

    msg = IncomingMessage("dashboard", req.usuario_id, req.mensagem)
    resposta = orch.handle(msg)

    return {
        "resposta": resposta,
        "agente": orch.get_active_agent(req.usuario_id),
        "modelo": modelo,
    }


@router.get("/chat/historico/{usuario_id}")
def historico(usuario_id: str = "dashboard", limite: int = 50):
    """Historico de conversas do usuario."""
    from services.memory_manager import MemoryManager
    mm = MemoryManager()
    return mm.historico(usuario_id, limite)


@router.delete("/chat/historico/{usuario_id}")
def limpar_historico(usuario_id: str = "dashboard"):
    """Limpa historico do usuario."""
    from services.memory_manager import MemoryManager
    mm = MemoryManager()
    mm.limpar_conversas(usuario_id)
    return {"status": "ok"}
