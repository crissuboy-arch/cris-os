"""
Rotas do CRIS Studio — Agent Builder visual.
Usa a facade AgentBuilder e os contratos publicos do Core
(CapabilityRegistry, PluginLoader, AgentRegistry).
Nao altera Core, Runtime ou Agent Builder.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent.parent.parent
AGENTS_DIR = ROOT / "agent_builder" / "agents_studio"
PLUGINS_DIR = ROOT / "plugins"
TOOLS_MODULES = [
    "coding_tools", "research_tools", "productivity_tools",
    "sales_tools", "service_tools", "social_tools", "copy_tools",
]

logger = logging.getLogger(__name__)

router = APIRouter()

_builder: Any = None
_plugins_env: dict[str, Any] | None = None


def _get_plugins_env() -> dict[str, Any]:
    """Carrega o ambiente de plugins UMA vez (registry + loader).

    Usa apenas contratos publicos do Core.
    """
    global _plugins_env
    if _plugins_env is not None:
        return _plugins_env
    from core.capability import CapabilityRegistry
    from core.events import InProcessEventBus
    from core.plugins.loader import PluginLoader

    registry = CapabilityRegistry()
    bus = InProcessEventBus(event_log=None)
    loader = PluginLoader(registry, bus, plugins_dir=str(PLUGINS_DIR))
    loader.load_all()
    loader.start_all()
    _plugins_env = {"registry": registry, "loader": loader}
    return _plugins_env


def _get_builder() -> Any:
    global _builder
    if _builder is not None:
        return _builder
    from agent_builder import AgentBuilder, AgentStore
    from core.registry import AgentRegistry

    env = _get_plugins_env()
    store = AgentStore(str(AGENTS_DIR))
    registry = AgentRegistry()
    _builder = AgentBuilder(
        store=store,
        agent_registry=registry,
        plugin_loader=env["loader"],
    )
    return _builder


def _capability_names() -> set[str]:
    env = _get_plugins_env()
    return {c.name for c in env["registry"].list_all()}


# ----------------------------------------------------------------------
# Schemas de entrada
# ----------------------------------------------------------------------

class CreateAgentRequest(BaseModel):
    name: str
    description: str = ""


class BindingIn(BaseModel):
    keyword: str
    capability: str
    input_template: dict = {}
    description: str = ""
    priority: int = 50


class UpdateAgentRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    bindings: list[BindingIn] | None = None
    config: dict | None = None
    metadata: dict | None = None


# ----------------------------------------------------------------------
# Agentes: CRUD + ciclo de vida
# ----------------------------------------------------------------------

@router.get("/studio/agents")
def list_studio_agents():
    try:
        builder = _get_builder()
        return [a.to_dict() for a in builder.list()]
    except Exception as exc:
        logger.error("Erro ao listar agentes: %s", exc)
        raise HTTPException(status_code=500, detail="Erro interno ao listar agentes")


@router.post("/studio/agents", status_code=201)
def create_studio_agent(req: CreateAgentRequest):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nome é obrigatório")
    if len(name) < 3:
        raise HTTPException(status_code=400, detail="Nome deve ter pelo menos 3 caracteres")

    builder = _get_builder()
    if builder.get_by_name(name) is not None:
        raise HTTPException(status_code=409, detail=f"Já existe um agente com o nome '{name}'")

    try:
        defn = builder.create(name=name, description=req.description.strip())
        return defn.to_dict()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Erro ao criar agente: %s", exc)
        raise HTTPException(status_code=500, detail="Erro interno ao criar agente")


@router.get("/studio/agents/{agent_id}")
def get_studio_agent(agent_id: str):
    builder = _get_builder()
    defn = builder.get(agent_id)
    if defn is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    return defn.to_dict()


@router.put("/studio/agents/{agent_id}")
def update_studio_agent(agent_id: str, req: UpdateAgentRequest):
    builder = _get_builder()
    defn = builder.get(agent_id)
    if defn is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    kwargs: dict = {}

    if req.name is not None:
        name = req.name.strip()
        if len(name) < 3:
            raise HTTPException(status_code=400, detail="Nome deve ter pelo menos 3 caracteres")
        if name != defn.name and builder.get_by_name(name) is not None:
            raise HTTPException(status_code=409, detail=f"Já existe um agente com o nome '{name}'")
        kwargs["name"] = name

    if req.description is not None:
        kwargs["description"] = req.description.strip()

    if req.bindings is not None:
        known = _capability_names()
        unknown = [b.capability for b in req.bindings if b.capability not in known]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Capabilities inexistentes: {', '.join(sorted(set(unknown)))}",
            )
        for b in req.bindings:
            if not b.keyword.strip():
                raise HTTPException(status_code=400, detail="Todo binding precisa de uma keyword")
        from agent_builder import CapabilityBinding
        kwargs["bindings"] = [
            CapabilityBinding(
                keyword=b.keyword.strip(),
                capability=b.capability,
                input_template=b.input_template or {"input": "{instruction}"},
                description=b.description,
                priority=b.priority,
            )
            for b in req.bindings
        ]

    if req.config is not None:
        allowed = {"timeout_ms", "max_iterations", "allow_fallback"}
        kwargs["config"] = {k: v for k, v in req.config.items() if k in allowed}

    if req.metadata is not None:
        kwargs["metadata"] = req.metadata

    try:
        updated = builder.update(agent_id, **kwargs)
        return updated.to_dict()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Erro ao atualizar agente: %s", exc)
        raise HTTPException(status_code=500, detail="Erro interno ao atualizar agente")


@router.delete("/studio/agents/{agent_id}")
def delete_studio_agent(agent_id: str):
    builder = _get_builder()
    if builder.get(agent_id) is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    try:
        builder.delete(agent_id)
        return {"deleted": True}
    except Exception as exc:
        logger.error("Erro ao remover agente: %s", exc)
        raise HTTPException(status_code=500, detail="Erro interno ao remover agente")


@router.post("/studio/agents/{agent_id}/publish")
def publish_studio_agent(agent_id: str):
    builder = _get_builder()
    defn = builder.get(agent_id)
    if defn is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    if not defn.bindings:
        raise HTTPException(
            status_code=400,
            detail="Não é possível publicar um agente sem bindings de capabilities",
        )
    try:
        published = builder.publish(agent_id)
        return published.to_dict()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Erro ao publicar agente: %s", exc)
        raise HTTPException(status_code=500, detail="Erro interno ao publicar agente")


# ----------------------------------------------------------------------
# Catalogo: capabilities, plugins, tools
# ----------------------------------------------------------------------

@router.get("/studio/capabilities")
def list_studio_capabilities():
    try:
        env = _get_plugins_env()
        caps = env["registry"].list_all()
        return [
            {
                "name": c.name,
                "version": c.version,
                "plugin": c.plugin_id,
                "domain": c.name.split(".")[0] if "." in c.name else c.name,
                "description": c.description,
                "priority": c.priority,
                "health": c.health.value,
                "status": c.status.value,
                "timeout_ms": c.timeout_ms,
                "idempotent": c.idempotent,
                "input_schema": c.input_schema,
                "output_schema": c.output_schema,
            }
            for c in sorted(caps, key=lambda x: x.name)
        ]
    except Exception as exc:
        logger.error("Erro ao listar capabilities: %s", exc)
        raise HTTPException(status_code=500, detail="Erro interno ao listar capabilities")


@router.get("/studio/plugins")
def list_studio_plugins():
    try:
        env = _get_plugins_env()
        loader = env["loader"]
        result = []
        for name in loader.list_loaded():
            plugin = loader.get(name)
            manifest = plugin.manifest
            result.append({
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "author": manifest.author,
                "state": plugin.state.value,
                "capabilities": [
                    {"name": c.name, "version": c.version, "description": c.description}
                    for c in manifest.capabilities
                ],
            })
        return sorted(result, key=lambda p: p["name"])
    except Exception as exc:
        logger.error("Erro ao listar plugins: %s", exc)
        raise HTTPException(status_code=500, detail="Erro interno ao listar plugins")


@router.get("/studio/tools")
def list_studio_tools():
    """Lista ferramentas disponiveis por tipo.

    Honesto: internal vem dos modulos reais em tools/;
    http e mcp ainda nao estao configurados no backend.
    """
    internal: list[dict] = []
    errors: list[str] = []
    for mod_name in TOOLS_MODULES:
        try:
            import importlib
            mod = importlib.import_module(f"tools.{mod_name}")
            if hasattr(mod, "get_tools"):
                for t in mod.get_tools():
                    internal.append({
                        "name": t.name,
                        "description": getattr(t, "description", ""),
                        "module": mod_name,
                    })
        except Exception as exc:
            errors.append(f"{mod_name}: {exc}")

    return {
        "types": [
            {
                "type": "internal",
                "label": "Ferramentas internas",
                "available": True,
                "items": internal,
                "errors": errors,
            },
            {
                "type": "http",
                "label": "Ferramentas HTTP",
                "available": False,
                "reason": "Ainda não configurado — conectores HTTP serão adicionados em fase futura",
                "items": [],
            },
            {
                "type": "mcp",
                "label": "Ferramentas MCP",
                "available": False,
                "reason": "Ainda não configurado — o contrato MCP existe, mas nenhum servidor MCP está conectado",
                "items": [],
            },
        ]
    }