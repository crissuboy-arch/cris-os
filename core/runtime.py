"""
Runtime — a "raiz de composição" (composition root) do CRIS OS.

Único lugar que conhece TODAS as peças concretas e as monta na ordem certa:

  config
   -> storage (SQLiteMemory + SQLiteOpsStore)
   -> EventBus (sobre o Event Log)  [+ assinante de auditoria]
   -> memória em 4 camadas + MemoryFacade
   -> LLM (Ollama via LLMRouter)
   -> PluginManager descobre os agentes
   -> IntentRouter + WorkflowEngine + ResponseComposer -> Orchestrator
   -> Gateway -> Canais (Telegram)

Montar tudo aqui mantém o resto desacoplado (cada peça recebe dependências
prontas). Trocar implementação (LLM, canal, banco) é mexer só neste arquivo.
"""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass

from agents.loader import carregar_agentes
from channels.telegram import TelegramChannel
from config.settings import settings
from core.application import (
    AgentTarget,
    ExecutionDispatcher,
    IntentRouter,
    Orchestrator,
    ResponseComposer,
    SkillRunner,
    SkillTarget,
    TargetRegistry,
    WorkflowEngine,
)
from core.cognition import (
    CognitiveOrchestrator,
    ExecutionManager,
    QualitySupervisor,
    StrategicPlanner,
)
from core.events import InProcessEventBus
from core.gateway import Gateway
from core.plugins import PluginManager
from core.router import Router
from tools.browser import BrowserTarget
from llm.nvidia import NVIDIAProvider
from llm.ollama import OllamaProvider
from llm.router import LLMRouter
from memory import (
    ConversationMemory,
    FacadeSkillMemory,
    KnowledgeBaseMemory,
    MemoryFacade,
    PermanentMemory,
    ProjectMemory,
    TemporaryMemory,
)
from core.skills import SkillRegistry
from memory.seed import seed_if_empty
from storage import SQLiteMemory, SQLiteOpsStore

logger = logging.getLogger(__name__)


class StartupError(RuntimeError):
    """Erro de inicialização com mensagem amigável para a Cris."""


@dataclass
class CrisOS:
    channels: list
    skills: SkillRegistry | None = None  # camada de Skills (catálogo)
    skill_runner: SkillRunner | None = None  # executor de skills (pronto; ligado ao Orquestrador no B5)

    def run(self) -> None:
        if not self.channels:
            raise StartupError("Nenhum canal configurado.")
        # Fase atual: um canal (Telegram), bloqueante.
        # TODO (multi-canal): rodar cada canal em sua própria thread.
        self.channels[0].run()


def _planner_prompt(registry) -> str:
    base = ""
    if settings.ORCHESTRATOR_PROMPT_FILE.exists():
        base = settings.ORCHESTRATOR_PROMPT_FILE.read_text(encoding="utf-8").strip()
    equipe = "\n".join(f"- {a.name}: {a.description}" for a in registry.all())
    return f"{base}\n\n----- EQUIPE DISPONÍVEL -----\n{equipe}"


def build(check_llm: bool = True) -> CrisOS:
    """Valida a configuração e monta o sistema inteiro."""
    problemas = settings.validate()
    if problemas:
        raise StartupError("Corrija o .env:\n  - " + "\n  - ".join(problemas))

    # 1) Armazenamento (memória + operacional, mesmo arquivo .db).
    mem_backend = SQLiteMemory(settings.DB_PATH)
    ops = SQLiteOpsStore(settings.DB_PATH)

    # 2) Backbone de eventos.
    event_bus = InProcessEventBus(event_log=ops)
    event_bus.subscribe("*", lambda e: logger.debug("evt %s corr=%s", e.type, e.correlation_id[:8]))

    # 3) Memória em 4 camadas + facade.
    conversation = ConversationMemory(mem_backend, settings.MEMORY_CONTEXT_MESSAGES)
    temporary = TemporaryMemory(mem_backend)
    project = ProjectMemory(mem_backend)
    permanent = PermanentMemory(mem_backend)
    knowledge_base = KnowledgeBaseMemory(mem_backend)
    seed_if_empty(permanent, project)
    facade = MemoryFacade(conversation, temporary, project, permanent, knowledge_base)

    # 4) LLM: NVIDIA (remoto, se configurado) + Ollama (local, fallback).
    #     Roteamento por papel:
    #       - "routing" → NVIDIA_ROUTER_MODEL (8B, rápido)
    #       - "generation" → NVIDIA_GENERATION_MODEL (70B, potente)
    ollama = OllamaProvider(settings.OLLAMA_HOST, settings.OLLAMA_MODEL,
                            settings.OLLAMA_TIMEOUT, num_gpu=settings.OLLAMA_NUM_GPU)
    nvidia_router = None
    nvidia_gen = None

    if settings.NVIDIA_API_KEY and settings.NVIDIA_API_KEY != "COLE_SUA_CHAVE_AQUI":
        # Modelo de roteamento (rápido).
        router_model = settings.NVIDIA_ROUTER_MODEL
        gen_model = settings.NVIDIA_GENERATION_MODEL
        try:
            nv_temp = NVIDIAProvider(
                api_key=settings.NVIDIA_API_KEY,
                model=router_model,
                base_url=settings.NVIDIA_BASE_URL,
                role="router",
            )
            ok, suggests = nv_temp.check_model()
            if not ok:
                logger.warning(
                    "Modelo de roteamento '%s' NAO disponivel na NVIDIA. "
                    "Disponiveis similar: %s",
                    router_model, ", ".join(suggests) if suggests else "(nenhum)",
                )
                # Tenta um modelo similar sugerido, se houver.
                if suggests:
                    alt = suggests[0]
                    logger.info("Usando '%s' como modelo de roteamento alternativo.", alt)
                else:
                    logger.warning("Nenhum modelo de roteamento viavel. Usando Ollama para roteamento.")
            else:
                nvidia_router = NVIDIAProvider(
                    api_key=settings.NVIDIA_API_KEY,
                    model=router_model,
                    base_url=settings.NVIDIA_BASE_URL,
                    role="router",
                )
                logger.info("NVIDIA router configurado: %s", router_model)
        except Exception as exc:
            logger.warning("Falha ao configurar NVIDIA router: %s", exc)

        # Modelo de geração (potente).
        try:
            nv_temp2 = NVIDIAProvider(
                api_key=settings.NVIDIA_API_KEY,
                model=gen_model,
                base_url=settings.NVIDIA_BASE_URL,
                role="generation",
            )
            ok2, suggests2 = nv_temp2.check_model()
            if not ok2:
                logger.warning(
                    "Modelo de geracao '%s' NAO disponivel na NVIDIA. "
                    "Disponiveis similar: %s",
                    gen_model, ", ".join(suggests2) if suggests2 else "(nenhum)",
                )
            else:
                nvidia_gen = NVIDIAProvider(
                    api_key=settings.NVIDIA_API_KEY,
                    model=gen_model,
                    base_url=settings.NVIDIA_BASE_URL,
                    role="generation",
                )
                logger.info("NVIDIA generation configurado: %s", gen_model)
        except Exception as exc:
            logger.warning("Falha ao configurar NVIDIA generation: %s", exc)

    providers: dict[str, object] = {"ollama": ollama}
    if nvidia_router:
        providers["nvidia_router"] = nvidia_router
    if nvidia_gen:
        providers["nvidia_gen"] = nvidia_gen

    if nvidia_gen is not None:
        default_llm = nvidia_gen
        policy = {"routing": "nvidia_router", "generation": "nvidia_gen"}
    elif nvidia_router is not None:
        default_llm = nvidia_router
        policy = {"routing": "nvidia_router"}
    else:
        default_llm = ollama
        policy = {}

    llm = LLMRouter(default=default_llm, providers=providers, policy=policy)

    if check_llm:
        vivo = llm.is_alive()
        if not vivo:
            if default_llm is not ollama:
                logger.warning("Provedor padrao nao respondeu, verificando Ollama como fallback...")
                if not ollama.is_alive():
                    raise StartupError(
                        "NVIDIA e Ollama estao inacessiveis. Verifique suas configuracoes."
                    )
                logger.info("Ollama OK. Usando Ollama como provedor ativo.")
                llm = LLMRouter(default=ollama, providers={"ollama": ollama})
            else:
                raise StartupError(
                    f"O Ollama nao respondeu em {settings.OLLAMA_HOST}. Rode 'ollama serve' "
                    f"e baixe o modelo: 'ollama pull {settings.OLLAMA_MODEL}'."
                )

    # 5) Plugins: carregar os agentes (composition root) e injetar no manager.
    #    Agentes usam o modelo de geração (NVIDIA_GENERATION_MODEL ou Ollama como fallback).
    llm_gen = llm.for_role("generation") if "generation" in llm.policy else llm
    plugins = PluginManager()
    registry = plugins.register_agents(carregar_agentes(settings.AGENTS_DIR, llm_gen))
    if not registry.all():
        raise StartupError("Nenhum agente encontrado em agents/.")

    # 6) Camada de SKILLS + executor (ANTES do Orquestrador: o IntentRouter passa a
    #    considerar skills habilitadas e o Dispatcher precisa do SkillRunner).
    skills = SkillRegistry().discover(settings.SKILLS_DIR)
    skill_runner = SkillRunner(skills, ops, event_bus, FacadeSkillMemory(facade))

    # 7) Orquestrador + kernel de execução (Dispatcher/Targets) + lease (2ª máquina).
    ops.acquire(owner=socket.gethostname(), ttl_seconds=settings.LEASE_TTL_SECONDS)
    # IntentRouter usa modelo de roteamento rápido (8B) com histórico reduzido.
    llm_route = llm.for_role("routing") if "routing" in llm.policy else llm
    intent_router = IntentRouter(
        llm_route, registry, Router(settings.DEFAULT_AGENT, registry.all()),
        settings.DEFAULT_AGENT, skills=skills,
        routing_ctx=settings.ROUTER_CONTEXT_MESSAGES,
    )
    workflow = WorkflowEngine(registry, ops, event_bus, facade, settings.DEFAULT_AGENT)
    targets = (TargetRegistry()
               .register(AgentTarget(workflow))
               .register(SkillTarget(skill_runner))
               .register(BrowserTarget()))  # navegação SOMENTE LEITURA (type=TOOL)
    dispatcher = ExecutionDispatcher(targets)
    composer = ResponseComposer(llm_gen)
    orchestrator = Orchestrator(
        intent_router, dispatcher, composer, conversation, event_bus, _planner_prompt(registry)
    )

    # 8) Camada de COGNIÇÃO (INATIVA por padrão). Construída SÓ quando habilitada,
    #    para não ficar no caminho quente do runtime. O atendimento à Cris segue
    #    pelo Orchestrator v3; a ativação real virá após a revisão da camada.
    handler = orchestrator
    if settings.COGNITION_ENABLED:
        planner = StrategicPlanner(llm, facade, intent_router, event_bus)
        executor = ExecutionManager(workflow, event_bus,
                                    settings.EXECUTION_DEFAULT_TIMEOUT, settings.EXECUTION_MAX_RETRIES)
        supervisor = QualitySupervisor(llm, event_bus, settings.QUALITY_MIN_SCORE)
        cognitive = CognitiveOrchestrator(  # noqa: F841 - construído, ativação pós-revisão
            planner, executor, supervisor, composer, conversation, event_bus, settings.MAX_REVISIONS
        )
        logger.warning("COGNITION_ENABLED=true, mas a camada ainda é esqueleto. Usando v3.")

    # (Skills montadas na etapa 6 e ligadas ao Orquestrador via Dispatcher/Targets.)
    logger.info("Skills: %d descobertas, %d ativas; ligadas ao Orquestrador (AgentTarget+SkillTarget).",
                len(skills.all()), len(skills.enabled()))

    # 9) Gateway + canais.
    allowed = {settings.TELEGRAM_ALLOWED_USER_ID} if settings.TELEGRAM_ALLOWED_USER_ID else set()
    gateway = Gateway(handler, allowed_senders=allowed)
    canais = [TelegramChannel(settings.TELEGRAM_BOT_TOKEN, gateway.handle)]

    logger.info("CRIS OS montado. Modelo: %s | Agentes: %s | Skills: %d | Cognição: inativa",
                settings.OLLAMA_MODEL, ", ".join(registry.names()), len(skills.all()))
    return CrisOS(channels=canais, skills=skills, skill_runner=skill_runner)
