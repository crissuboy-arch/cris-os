"""
Camada de memória do CRIS OS (4 camadas + facade de acesso escopado).

  L1 ConversationMemory / TemporaryMemory
  L2 ProjectMemory
  L3 PermanentMemory
  L4 KnowledgeBaseMemory
  MemoryFacade -> monta o contexto escopado de cada agente.
"""

from .facade import MemoryFacade  # noqa: F401
from .layers import (  # noqa: F401
    ConversationMemory,
    KnowledgeBaseMemory,
    PermanentMemory,
    ProjectMemory,
    TemporaryMemory,
)
from .skill_memory import FacadeSkillMemory  # noqa: F401
