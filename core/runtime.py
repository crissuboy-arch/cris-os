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

from agents import AgentOrchestrator, discover_agents, discover_general_agent
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
from llm.openai_compat import OpenAICompatProvider
from llm.router import LLMRouter
from services.ods_client import ODSClient
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
    ods_client: ODSClient | None = None
    skills: SkillRegistry | None = None  # camada de Skills (catálogo)
    skill_runner: SkillRunner | None = None  # executor de skills (pronto; ligado ao Orquestrador no B5)

    def run(self) -> None:
        if not self.channels:
            raise StartupError("Nenhum canal configurado.")
        # Fase atual: um canal (Telegram), bloqueante.
        # TODO (multi-canal): rodar cada canal em sua própria thread.
        self.channels[0].run()


def _configurar_nvidia() -> tuple:
    """Configura provedores NVIDIA (router + generation). Retorna (nvidia_router, nvidia_gen)."""
    nvidia_router = None
    nvidia_gen = None
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
            if suggests:
                alt = suggests[0]
                logger.info("Usando '%s' como modelo de roteamento alternativo.", alt)
            else:
                logger.warning("Nenhum modelo de roteamento viavel.")
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

    return nvidia_router, nvidia_gen


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

    # 4) ODS Client: deteccao e monitoramento do Osmantic Deployment System.
    ods_client = ODSClient(
        enabled=settings.ODS_ENABLED,
        base_url=settings.ODS_BASE_URL,
        fallback_url=settings.ODS_FALLBACK_URL,
        webui_url=settings.ODS_WEBUI_URL,
        timeout=settings.ODS_TIMEOUT,
        model=settings.ODS_MODEL,
    )

    if settings.ODS_ENABLED:
        ods_status = ods_client.check_all()
        if ods_status.active_ollama_url:
            logger.info(
                "ODS detectado em %s | Modelo: %s",
                ods_status.active_ollama_url, ods_status.active_model or "(nenhum)",
            )
        else:
            logger.warning("ODS nao respondeu: %s", ods_status.error or "desconhecido")
    else:
        logger.info("ODS esta desabilitado (ODS_ENABLED=false)")

    # 5) LLM: NVIDIA / OpenAI / Ollama (local, fallback).
    #     Usa a URL detectada pelo ODS ou a configurada manualmente.
    ollama_host = ods_client.get_active_url() if settings.ODS_ENABLED else settings.OLLAMA_HOST
    if settings.ODS_ENABLED and ollama_host != settings.OLLAMA_HOST:
        logger.info(
            "Usando URL do ODS para Ollama: %s (configurado: %s)",
            ollama_host, settings.OLLAMA_HOST,
        )

    ollama = OllamaProvider(ollama_host, settings.OLLAMA_MODEL,
                            settings.OLLAMA_TIMEOUT, num_gpu=settings.OLLAMA_NUM_GPU)

    # Provedores de fallback (nuvem) sao configurados conforme disponibilidade.
    providers: dict[str, object] = {"ollama": ollama}
    default_llm = ollama
    policy: dict[str, str] = {}

    # --- NVIDIA ---
    nvidia_router = None
    nvidia_gen = None
    if settings.NVIDIA_API_KEY and settings.NVIDIA_API_KEY != "COLE_SUA_CHAVE_AQUI":
        nvidia_router, nvidia_gen = _configurar_nvidia()

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

    # --- OpenAI (fallback alternativo) ---
    openai_provider = None
    if settings.OPENAI_API_KEY and settings.ODS_FALLBACK_PROVIDER == "openai":
        try:
            openai_provider = OpenAICompatProvider(
                api_key=settings.OPENAI_API_KEY,
                model=settings.OPENAI_MODEL,
                base_url=settings.OPENAI_BASE_URL,
                timeout=settings.OPENAI_TIMEOUT,
                role="generation",
            )
            ok, _ = openai_provider.check_model()
            if ok:
                providers["openai"] = openai_provider
                logger.info("OpenAI fallback configurado: %s", settings.OPENAI_MODEL)
                if default_llm is ollama:
                    default_llm = openai_provider
            else:
                logger.warning("OpenAI modelo '%s' nao disponivel.", settings.OPENAI_MODEL)
                openai_provider = None
        except Exception as exc:
            logger.warning("Falha ao configurar OpenAI fallback: %s", exc)
            openai_provider = None

    llm = LLMRouter(default=default_llm, providers=providers, policy=policy)

    if check_llm:
        vivo = llm.is_alive()
        if not vivo:
            if default_llm is not ollama:
                logger.warning("Provedor padrao nao respondeu, verificando Ollama como fallback...")
                if not ollama.is_alive():
                    msg_erro = "Todos os provedores estao inacessiveis."
                    if settings.ODS_ENABLED:
                        msg_erro += (
                            f" ODS foi detectado como offline. "
                            f"Verifique se o ODS esta rodando ou ajuste ODS_ENABLED=false "
                            f"para usar apenas provedores remotos."
                        )
                    raise StartupError(msg_erro)
                logger.info("Ollama OK. Usando Ollama como provedor ativo.")
                llm = LLMRouter(default=ollama, providers={"ollama": ollama})
            else:
                raise StartupError(
                    f"O Ollama nao respondeu em {ollama_host}. "
                    f"Rode 'ollama serve' e baixe o modelo: 'ollama pull {settings.OLLAMA_MODEL}'."
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

    # 9b) Se DEFAULT_AGENT=auto, cria o AgentOrchestrator (novo sistema de especialistas).
    agent_orchestrator = None
    if settings.DEFAULT_AGENT == "auto":
        # Usa o provedor local (Ollama via ODS) para os agentes especialistas.
        local_llm = ollama
        especialistas = discover_agents(local_llm)
        agente_geral = discover_general_agent(local_llm)
        if especialistas:
            agent_orchestrator = AgentOrchestrator(
                llm=local_llm, agents=especialistas,
                general_agent=agente_geral,
            )
            n_agentes = len(especialistas) + (1 if agente_geral else 0)
            logger.info(
                "AgentOrchestrator ativo com %d agentes (%d especialistas + geral) "
                "(modelo: %s via %s)",
                n_agentes, len(especialistas), settings.OLLAMA_MODEL, ollama_host,
            )
            handler = agent_orchestrator.handle
        else:
            logger.warning("Nenhum agente especialista carregado. Usando orquestrador classico.")

    # 10) Gateway + canais.
    allowed = {settings.TELEGRAM_ALLOWED_USER_ID} if settings.TELEGRAM_ALLOWED_USER_ID else set()
    gateway = Gateway(handler, allowed_senders=allowed)
    canais = [TelegramChannel(
        settings.TELEGRAM_BOT_TOKEN,
        gateway.handle,
        ods_client=ods_client if settings.ODS_ENABLED else None,
        agent_orchestrator=agent_orchestrator,
    )]

    modo = f"auto ({len(agent_orchestrator.agents)} especialistas)" if agent_orchestrator else settings.DEFAULT_AGENT
    ods_info = f" | ODS: {'ativo' if settings.ODS_ENABLED else 'inativo'}"
    logger.info("CRIS OS montado. Modo: %s | Modelo: %s | Agentes: %s | Skills: %d%s",
                modo, settings.OLLAMA_MODEL, ", ".join(registry.names()), len(skills.all()), ods_info)
    return CrisOS(channels=canais, ods_client=ods_client, skills=skills, skill_runner=skill_runner)
