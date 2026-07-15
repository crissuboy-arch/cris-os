"""
Camada de DOMÍNIO do CRIS OS (Clean Architecture).

É o centro: entidades e eventos puros, sem nenhuma dependência externa (nem de
frameworks, nem de banco, nem de LLM). Tudo nas camadas de fora pode mudar; isto
aqui é estável.
"""

from .events import Event, EventType  # noqa: F401
from .planning import (  # noqa: F401
    ExecutionReport,
    Objective,
    Plan,
    PlanStep,
    QualityVerdict,
    StepResult,
    Strategy,
)
