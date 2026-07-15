"""
Entidade de uma Skill carregada do disco (metadados do manifesto + validação).

É só dado (dataclass). A descoberta/validação ficam no SkillRegistry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class SkillStatus:
    """Ciclo de vida de uma Skill."""

    SCAFFOLD = "scaffold"      # só estrutura, sem implementação
    DRAFT = "draft"            # em construção
    PRODUCTION = "production"  # pronta para uso
    INVALID = "invalid"        # estrutura/manifesto inválido


@dataclass
class Skill:
    """Uma Skill descoberta em `skills/<nome>/`."""

    name: str
    title: str
    description: str
    version: str
    status: str
    enabled: bool
    category: str
    path: Path
    agents: list[str] = field(default_factory=list)  # agentes que podem usá-la
    tools: list[str] = field(default_factory=list)    # tools que ela usa
    valid: bool = True
    issues: list[str] = field(default_factory=list)   # problemas de validação
    executor: str = ""  # "modulo:Classe" do executor (vazio = sem execução ainda)
    domain: str = ""    # domínio p/ roteamento hierárquico (usado a partir do B7)
    input_schema: dict = field(default_factory=dict)  # JSON-Schema dos args (tools do IntentRouter)
    keywords: list[str] = field(default_factory=list)  # gatilhos de fallback determinístico (manifest)
