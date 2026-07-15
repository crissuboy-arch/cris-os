"""
Porta: agente especialista.

Cada "funcionário digital" implementa este contrato. O Orquestrador entrega uma
Task e recebe um AgentResult. O agente recebe o CONTEXTO já montado e ESCOPADO
pelo MemoryFacade — ele só enxerga a memória do(s) seu(s) domínio(s), além da
permanente e da base de conhecimento relevante. É assim que garantimos, por
arquitetura, que "nenhum agente conhece tudo" e que "agentes só falam com o
Orquestrador".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from core.models import AgentResult, KnowledgeItem, Passage, Task


@dataclass
class AgentContext:
    """Memória já montada e escopada que o agente recebe para trabalhar."""

    session: str
    conversation: list[dict] = field(default_factory=list)  # L1 diálogo
    temporary: list[str] = field(default_factory=list)  # L1 itens do dia
    project_memory: list[KnowledgeItem] = field(default_factory=list)  # L2 (escopado)
    permanent: list[KnowledgeItem] = field(default_factory=list)  # L3
    knowledge: list[Passage] = field(default_factory=list)  # L4 (recuperado)


@runtime_checkable
class Agent(Protocol):
    name: str
    description: str

    def handle(self, task: Task, context: AgentContext) -> AgentResult:
        """Executa a tarefa e devolve o resultado ao Orquestrador."""
        ...
