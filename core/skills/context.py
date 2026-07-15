"""
SkillContext — as dependências que uma Skill recebe ao executar.

Faz parte do SDK de Skills: padroniza COMO uma skill acessa a Memória e o Event
Log **sem acoplar** a skill às implementações (a skill recebe tudo pronto, por
injeção). NÃO altera Event Bus, Memory nem Orquestrador — apenas carrega
referências a eles para a skill usar.

Quem chama a skill (um agente, o Orquestrador ou um teste) monta este contexto e
o entrega ao `execute(payload, context)`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from core.domain.events import Event


@dataclass
class SkillContext:
    """Tudo que uma Skill precisa para rodar, montado por quem a chama."""

    session: str
    memory: object = None  # MemoryFacade (acesso a conversation/temporary/permanent/...)
    publish: Optional[Callable[[Event], None]] = None  # event_bus.publish (Event Log)
    correlation_id: str = ""
    caller: str = ""  # quem acionou a skill (agente, "orchestrator", etc.)
    extra: dict = field(default_factory=dict)
