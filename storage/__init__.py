"""
Backends de armazenamento (adaptadores de infraestrutura).

Fase atual: SQLite, dividido por responsabilidade:
  - SQLiteMemory   -> as 4 camadas de memória
  - SQLiteOpsStore -> event log, outbox, tasks e lease (auditoria/replicação)

Futuro: Postgres (outra implementação das mesmas portas) para a 2ª máquina.
"""

from .sqlite_memory import SQLiteMemory  # noqa: F401
from .sqlite_ops import SQLiteOpsStore  # noqa: F401
