"""
Pacote de Agentes Especialistas do CRIS OS.

Contem:
  - AgentOrchestrator: orquestrador que roteia mensagens para o agente certo
  - SpecialistAgent: classe base para agentes especialistas
  - 8 agentes especialistas: marketing, social_media, vendas, atendimento,
    programador, pesquisador, copywriter, produtividade
  - prompts.py: todos os prompts especializados

Uso:
    from agents.orchestrator import AgentOrchestrator
    from agents.base_specialist import SpecialistAgent, create_agent
"""

from agents.base_specialist import SpecialistAgent, create_agent
from agents.orchestrator import AgentOrchestrator

# Lista de modulos de agentes para descoberta automatica
AGENT_MODULES = [
    "agents.marketing",
    "agents.social_media",
    "agents.vendas",
    "agents.atendimento",
    "agents.programador",
    "agents.pesquisador",
    "agents.copywriter",
    "agents.produtividade",
]
GENERAL_MODULE = "agents.geral"


def discover_agents(llm: object) -> list[SpecialistAgent]:
    """
    Descobre e instancia todos os agentes especialistas disponiveis.
    """
    import importlib

    agentes: list[SpecialistAgent] = []
    for modulo_path in AGENT_MODULES:
        try:
            modulo = importlib.import_module(modulo_path)
            if hasattr(modulo, "create"):
                agente = modulo.create(llm)
                agentes.append(agente)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Falha ao carregar agente '%s': %s", modulo_path, exc,
            )
    return agentes


def discover_general_agent(llm: object) -> SpecialistAgent | None:
    """Instancia o agente geral de fallback."""
    import importlib
    try:
        modulo = importlib.import_module(GENERAL_MODULE)
        if hasattr(modulo, "create"):
            return modulo.create(llm)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Falha ao carregar agente geral: %s", exc,
        )
    return None
