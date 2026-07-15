"""
Camada de COGNIÇÃO do CRIS OS (inteligência estratégica) — camada de aplicação.

Transforma o CRIS OS de "sistema de agentes" em "sistema operacional autônomo",
inserindo um ciclo de raciocínio acima da execução:

    Objetivo
      -> StrategicPlanner   (pensa: contexto + memória + estratégia -> Plano)
      -> ExecutionManager   (executa: distribui, monitora, reexecuta, timeout)
      -> QualitySupervisor  (avalia: aprova ou pede nova execução)
            ↑___________ loop de refação (re-execução) ___________|
      -> (aprovado) -> ResponseComposer -> Cris

⚠️ STATUS: ESQUELETO ARQUITETURAL. As funcionalidades ainda NÃO estão
implementadas (os componentes levantam NotImplementedError). O runtime continua
usando o pipeline v3; esta camada está pronta para ser revisada e, depois,
ativada. Todos os componentes usam o Event Bus já existente.
"""

from .cognitive_orchestrator import CognitiveOrchestrator  # noqa: F401
from .execution_manager import ExecutionManager  # noqa: F401
from .quality_supervisor import QualitySupervisor  # noqa: F401
from .strategic_planner import StrategicPlanner  # noqa: F401
