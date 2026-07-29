"""
Camada de APLICAÇÃO (casos de uso) — Clean Architecture.

Orquestra o domínio e as portas, sem conhecer detalhes de infraestrutura. O
Orquestrador foi decomposto em três responsabilidades únicas (SRP):

  IntentRouter      -> identifica a intenção e decide quem trabalha
  WorkflowEngine    -> cria/rastreia tarefas e coordena a execução (agentes)
  SkillRunner       -> executa uma skill por nome (rastreio + eventos skill.*)
  ResponseComposer  -> entrega UMA resposta final
  Orchestrator      -> amarra os três e publica eventos
"""

from .core_api import CoreAPI  # noqa: F401
from .composer import ResponseComposer  # noqa: F401
from .confirmation import ConfirmationGate  # noqa: F401
from .dispatcher import ExecutionDispatcher, TargetRegistry  # noqa: F401
from .intent_router import IntentRouter  # noqa: F401
from .orchestrator import Orchestrator  # noqa: F401
from .skill_runner import SkillRunner  # noqa: F401
from .targets import AgentTarget, SkillTarget  # noqa: F401
from .workflow import WorkflowEngine  # noqa: F401
