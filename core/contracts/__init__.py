"""
Contratos (portas) do CRIS OS — a fronteira da Clean Architecture.

O núcleo depende destas INTERFACES, nunca de implementações concretas. Trocar
Ollama por Claude, Telegram por WhatsApp, SQLite por Postgres ou ligar MCP vira
"plugar outro adaptador", sem tocar nas regras de negócio.
"""

from .agent import Agent, AgentContext  # noqa: F401
from .channel import Channel, Handler  # noqa: F401
from .cognition import ExecutionManager, QualitySupervisor, StrategicPlanner  # noqa: F401
from .events import EventBus, EventLog, Subscriber  # noqa: F401
from .execution import DispatchContext, ExecutionTarget  # noqa: F401
from .llm import LLMProvider, LLMResponse, ToolCall  # noqa: F401
from .memory import (  # noqa: F401
    ConversationStore,
    KnowledgeBase,
    PermanentStore,
    ProjectMemoryStore,
    TemporaryStore,
)
from .replication import Lease, LeaseStore, Replicator  # noqa: F401
from .routing import RouteCandidate, RouteScorer, ScoredRoute  # noqa: F401
from .skill import SkillExecutor, SkillMemory  # noqa: F401
from .task_store import TaskStore  # noqa: F401
from .tool import Tool  # noqa: F401
