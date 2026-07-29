"""
ActivityLogger — registrador de atividades do CRIS OS.

Registra automaticamente:
  - agente utilizado
  - ferramenta utilizada
  - modelo utilizado
  - tempo de execucao
  - erros
"""

import logging
import time
from functools import wraps
from typing import Callable

from repositories.log_repo import LogRepository

logger = logging.getLogger(__name__)


class ActivityLogger:
    """Gerenciador de logs de atividade."""

    def __init__(self) -> None:
        self.repo = LogRepository()

    def log(self, usuario_id: str = "", agente: str = "",
            ferramenta: str = "", modelo: str = "",
            duracao_ms: int = 0, erro: str = "") -> int:
        """Registra uma atividade."""
        return self.repo.registrar(usuario_id, agente, ferramenta,
                                    modelo, duracao_ms, erro)

    def ultimos(self, limite: int = 50) -> list[dict]:
        """Retorna os ultimos logs."""
        return self.repo.ultimos(limite)

    def por_agente(self, agente: str, limite: int = 20) -> list[dict]:
        """Retorna logs filtrados por agente."""
        return self.repo.por_agente(agente, limite)

    def erros(self, limite: int = 20) -> list[dict]:
        """Retorna logs de erro."""
        return self.repo.erros(limite)

    def decorator(self, usuario_id: str = "", agente: str = "",
                  modelo: str = "") -> Callable:
        """Decorator para registrar execucao de funcao automaticamente."""
        def decorator(fn: Callable) -> Callable:
            @wraps(fn)
            def wrapper(*args, **kwargs):
                t0 = time.perf_counter()
                erro = ""
                try:
                    resultado = fn(*args, **kwargs)
                    return resultado
                except Exception as e:
                    erro = str(e)
                    raise
                finally:
                    elapsed = (time.perf_counter() - t0) * 1000
                    self.log(
                        usuario_id=usuario_id,
                        agente=agente,
                        ferramenta=fn.__name__,
                        modelo=modelo,
                        duracao_ms=int(elapsed),
                        erro=erro,
                    )
            return wrapper
        return decorator
