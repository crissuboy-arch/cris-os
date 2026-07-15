"""
Camada de SKILLS do CRIS OS.

Descobre, valida, versiona, lista e (agora) carrega o executor das Skills
empacotadas em `skills/`. Paralela à descoberta de agentes (não altera o
PluginManager, o Event Bus, a Memory nem o Orquestrador).
"""

from .context import SkillContext  # noqa: F401
from .registry import SkillLoadError, SkillRegistry  # noqa: F401
from .skill import Skill, SkillStatus  # noqa: F401
