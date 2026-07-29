"""
Rotas do CRIS Studio — Agent Builder visual.
Fase 3: execucao ponta a ponta, observabilidade, logs, memory, permissions.

Usa a facade AgentBuilder e os contratos publicos do Core.
Nao altera Core, Runtime ou Agent Builder.
"""

from __future__ import annotations

import logging
import time
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
_runtime: Any = None
_execution_log: Any = None


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
    _plugins_env = {"registry": registry, "loader": loader, "event_bus": bus}
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


def _get_runtime() -> Any:
    global _runtime
    if _runtime is not None:
        return _runtime
    from core.agent import AgentRuntime
    from core.registry import AgentRegistry

    env = _get_plugins_env()
    agent_reg = AgentRegistry()
    _runtime = AgentRuntime(
        agent_registry=agent_reg,
        plugin_loader=env["loader"],
        event_bus=env["event_bus"],
    )
    return _runtime


def _get_execution_log() -> Any:
    global _execution_log
    if _execution_log is not None:
        return _execution_log
    from agent_builder.execution_log import get_execution_log
    _execution_log = get_execution_log()
    return _execution_log


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
    source: str = "input"
    context_path: str = ""
    default_value: str = ""
    type_hint: str = ""


class InstructionsIn(BaseModel):
    role: str = ""
    objective: str = ""
    rules: list[str] = []
    restrictions: list[str] = []
    output_format: str = ""
    custom_prompt: str = ""


class MemoryIn(BaseModel):
    memory_type: str = "none"
    scope: list[str] = []
    read_enabled: bool = True
    write_enabled: bool = False
    project: str = ""


class PermissionsIn(BaseModel):
    allowed_capabilities: list[str] = []
    denied_capabilities: list[str] = []
    require_confirmation: list[str] = []


class ToolsIn(BaseModel):
    internal: list[str] = []
    http: list[dict] = []
    mcp: list[dict] = []


class UpdateAgentRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    bindings: list[BindingIn] | None = None
    config: dict | None = None
    metadata: dict | None = None
    instructions: InstructionsIn | None = None
    memory: MemoryIn | None = None
    permissions: PermissionsIn | None = None
    tools: ToolsIn | None = None


class ExecuteAgentRequest(BaseModel):
    instruction: str
    session: str = "studio"


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
        raise HTTPException(status_code=400, detail="Nome e obrigatorio")
    if len(name) < 3:
        raise HTTPException(status_code=400, detail="Nome deve ter pelo menos 3 caracteres")

    builder = _get_builder()
    if builder.get_by_name(name) is not None:
        raise HTTPException(status_code=409, detail=f"Ja existe um agente com o nome '{name}'")

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
        raise HTTPException(status_code=404, detail="Agente nao encontrado")
    return defn.to_dict()


@router.put("/studio/agents/{agent_id}")
def update_studio_agent(agent_id: str, req: UpdateAgentRequest):
    builder = _get_builder()
    defn = builder.get(agent_id)
    if defn is None:
        raise HTTPException(status_code=404, detail="Agente nao encontrado")

    kwargs: dict = {}

    if req.name is not None:
        name = req.name.strip()
        if len(name) < 3:
            raise HTTPException(status_code=400, detail="Nome deve ter pelo menos 3 caracteres")
        if name != defn.name and builder.get_by_name(name) is not None:
            raise HTTPException(status_code=409, detail=f"Ja existe um agente com o nome '{name}'")
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
                source=b.source,
                context_path=b.context_path,
                default_value=b.default_value,
                type_hint=b.type_hint,
            )
            for b in req.bindings
        ]

    if req.config is not None:
        allowed = {"timeout_ms", "max_iterations", "allow_fallback"}
        kwargs["config"] = {k: v for k, v in req.config.items() if k in allowed}

    if req.metadata is not None:
        kwargs["metadata"] = req.metadata

    # --- Fase 3 fields ---
    if req.instructions is not None:
        from agent_builder import AgentInstructions
        kwargs["instructions"] = AgentInstructions(
            role=req.instructions.role,
            objective=req.instructions.objective,
            rules=req.instructions.rules,
            restrictions=req.instructions.restrictions,
            output_format=req.instructions.output_format,
            custom_prompt=req.instructions.custom_prompt,
        )

    if req.memory is not None:
        from agent_builder import MemoryConfig
        kwargs["memory"] = MemoryConfig(
            memory_type=req.memory.memory_type,
            scope=req.memory.scope,
            read_enabled=req.memory.read_enabled,
            write_enabled=req.memory.write_enabled,
            project=req.memory.project,
        )

    if req.permissions is not None:
        from agent_builder import PermissionConfig
        kwargs["permissions"] = PermissionConfig(
            allowed_capabilities=req.permissions.allowed_capabilities,
            denied_capabilities=req.permissions.denied_capabilities,
            require_confirmation=req.permissions.require_confirmation,
        )

    if req.tools is not None:
        from agent_builder import ToolsConfig
        kwargs["tools"] = ToolsConfig(
            internal=req.tools.internal,
            http=req.tools.http,
            mcp=req.tools.mcp,
        )

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
        raise HTTPException(status_code=404, detail="Agente nao encontrado")
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
        raise HTTPException(status_code=404, detail="Agente nao encontrado")
    if not defn.bindings:
        raise HTTPException(
            status_code=400,
            detail="Nao e possivel publicar um agente sem bindings de capabilities",
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
# Execucao ponta a ponta (Fase 3)
# ----------------------------------------------------------------------

@router.post("/studio/agents/{agent_id}/execute")
def execute_studio_agent(agent_id: str, req: ExecuteAgentRequest):
    """Executa um agente criado no Studio via AgentRuntime real.

    Fluxo: monta contexto -> executa -> registra log -> retorna resultado + metadata.
    """
    from agent_builder.execution_log import get_execution_log

    builder = _get_builder()
    defn = builder.get(agent_id)
    if defn is None:
        raise HTTPException(status_code=404, detail="Agente nao encontrado")

    # Need published agent in registry
    agent_reg = builder._registry
    was_registered = agent_reg.get(defn.name) is not None
    if not was_registered:
        try:
            builder.publish(defn.agent_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Falha ao registrar agente: {exc}")

    # Create execution record
    exec_log = _get_execution_log()
    record = exec_log.create_record(
        agent_id=agent_id,
        agent_name=defn.name,
        instruction=req.instruction,
        session=req.session,
    )

    try:
        runtime = _get_runtime()
        t0 = time.perf_counter()

        # Build context with memory if configured
        context_overrides: dict[str, Any] = {}
        mem_config = defn.memory
        if mem_config.memory_type != "none":
            try:
                from memory.facade import MemoryFacade
                from memory.layers import (
                    ConversationMemory,
                    KnowledgeBaseMemory,
                    PermanentMemory,
                    ProjectMemory,
                    TemporaryMemory,
                )
                from storage.sqlite_memory import SQLiteMemory

                backend = SQLiteMemory()
                conv_mem = ConversationMemory(backend)
                temp_mem = TemporaryMemory(backend)
                proj_mem = ProjectMemory(backend)
                perm_mem = PermanentMemory(backend)
                kb_mem = KnowledgeBaseMemory(backend)
                facade = MemoryFacade(conv_mem, temp_mem, proj_mem, perm_mem, kb_mem)
                scope = mem_config.scope or ["*"] if mem_config.memory_type == "project" else []
                agent_context = facade.build_context(scope=scope, session=req.session, query=req.instruction)
                context_overrides = {
                    "conversation": agent_context.conversation,
                    "temporary": agent_context.temporary,
                    "project_memory": agent_context.project_memory,
                    "permanent": agent_context.permanent,
                    "knowledge": agent_context.knowledge,
                }
            except Exception as mem_exc:
                logger.warning("Falha ao carregar memoria para execucao: %s", mem_exc)

        result = runtime.execute(
            defn.name,
            req.instruction,
            session=req.session,
            correlation_id=record.id,
            context_overrides=context_overrides if context_overrides else None,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Extract execution_log from result metadata if present
        inner_log = {}
        system_prompt = ""
        if hasattr(result, "metadata") and isinstance(result.metadata, dict):
            inner_log = result.metadata.get("execution_log", {})
            system_prompt = result.metadata.get("system_prompt", "")

        # Update record
        record.status = "success" if result.success else "error"
        record.duration_ms = elapsed_ms
        record.output = result.output
        record.system_prompt = system_prompt
        record.bindings_attempted = inner_log.get("bindings_attempted", [])
        record.capabilities_called = inner_log.get("capabilities_called", [])
        record.permissions_checked = inner_log.get("permissions_checked", [])
        record.permissions_denied = inner_log.get("permissions_denied", [])
        record.memory_reads = inner_log.get("memory_reads", [])
        record.memory_writes = inner_log.get("memory_writes", [])
        record.errors = inner_log.get("errors", [])
        exec_log.add(record)

        # Unregister if we registered it temporarily
        if not was_registered:
            builder._unregister_agent(agent_id)

        return {
            "success": result.success,
            "output": result.output,
            "execution_id": record.id,
            "duration_ms": round(elapsed_ms, 2),
            "system_prompt": system_prompt,
            "metadata": {
                "bindings_attempted": record.bindings_attempted,
                "capabilities_called": record.capabilities_called,
                "permissions_checked": record.permissions_checked,
                "permissions_denied": record.permissions_denied,
                "memory_reads": record.memory_reads,
                "memory_writes": record.memory_writes,
                "errors": record.errors,
            },
        }

    except HTTPException:
        raise
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        record.status = "error"
        record.duration_ms = elapsed_ms
        record.errors.append(str(exc))
        record.output = str(exc)
        exec_log.add(record)

        if not was_registered:
            builder._unregister_agent(agent_id)

        logger.exception("Erro ao executar agente '%s': %s", defn.name, exc)
        raise HTTPException(status_code=500, detail=f"Erro ao executar agente: {exc}")


# ----------------------------------------------------------------------
# Observabilidade (Fase 3)
# ----------------------------------------------------------------------

@router.get("/studio/executions")
def list_executions(limit: int = 50):
    """Lista execucoes recentes do Studio."""
    exec_log = _get_execution_log()
    return exec_log.list_all(limit=limit)


@router.get("/studio/executions/stats")
def execution_stats():
    """Metricas basicas de execucoes."""
    exec_log = _get_execution_log()
    return exec_log.stats()


@router.get("/studio/executions/{execution_id}")
def get_execution(execution_id: str):
    """Obtem detalhes de uma execucao especifica."""
    exec_log = _get_execution_log()
    record = exec_log.get(execution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")
    return record.to_dict()


@router.get("/studio/agents/{agent_id}/executions")
def list_agent_executions(agent_id: str, limit: int = 20):
    """Lista execucoes de um agente especifico."""
    exec_log = _get_execution_log()
    return exec_log.get_by_agent(agent_id, limit=limit)


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
    """Lista ferramentas disponiveis por tipo."""
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
                "reason": "Ainda nao configurado — conectores HTTP serao adicionados em fase futura",
                "items": [],
            },
            {
                "type": "mcp",
                "label": "Ferramentas MCP",
                "available": False,
                "reason": "Ainda nao configurado — o contrato MCP existe, mas nenhum servidor MCP esta conectado",
                "items": [],
            },
        ]
    }
