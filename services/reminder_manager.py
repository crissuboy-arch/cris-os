"""
ReminderManager — gerenciador de lembretes do CRIS OS.

Cria, lista, cancela e processa lembretes com recorrencia.
"""

import logging
from datetime import datetime, timedelta

from repositories.lembrete_repo import LembreteRepository

logger = logging.getLogger(__name__)

RECORRENCIAS_VALIDAS = {"", "diaria", "semanal", "mensal"}


class ReminderManager:
    """Gerenciador de lembretes com recorrencia."""

    def __init__(self) -> None:
        self.repo = LembreteRepository()

    def criar(self, usuario_id: str, titulo: str, data_hora: str,
              recorrencia: str = "", tarefa_id: int | None = None) -> dict:
        """Cria um novo lembrete."""
        if recorrencia not in RECORRENCIAS_VALIDAS:
            raise ValueError(f"Recorrencia invalida: {recorrencia!r}")
        lid = self.repo.criar(usuario_id, titulo, data_hora,
                              recorrencia, tarefa_id)
        lembrete = self.repo.get_by_id(lid)
        logger.info("Lembrete criado: '%s' (id=%d, data=%s, recorrencia=%s)",
                     titulo, lid, data_hora, recorrencia or "nenhuma")
        return dict(lembrete) if lembrete else {"id": lid, "titulo": titulo}

    def listar(self, usuario_id: str) -> list[dict]:
        """Lista lembretes ativos."""
        return self.repo.ativos(usuario_id)

    def cancelar(self, lembrete_id: int) -> bool:
        """Cancela um lembrete."""
        return self.repo.cancelar(lembrete_id)

    def devidos(self, usuario_id: str, ate: str | None = None) -> list[dict]:
        """Lista lembretes devidos ate uma data/hora."""
        ate = ate or datetime.now().isoformat()
        return self.repo.devidos(usuario_id, ate)

    def proxima_ocorrencia(self, data_hora: str, recorrencia: str) -> str:
        """Calcula a proxima ocorrencia de um lembrete recorrente."""
        dt = datetime.fromisoformat(data_hora)
        if recorrencia == "diaria":
            nova = dt + timedelta(days=1)
        elif recorrencia == "semanal":
            nova = dt + timedelta(weeks=1)
        elif recorrencia == "mensal":
            mes = dt.month % 12 + 1
            ano = dt.year + (1 if dt.month == 12 else 0)
            dia = min(dt.day, 28)
            nova = datetime(ano, mes, dia, dt.hour, dt.minute)
        else:
            raise ValueError(f"Recorrencia nao gera ocorrencia: {recorrencia!r}")
        return nova.isoformat()

    def processar_devidos(self, usuario_id: str) -> list[dict]:
        """Processa lembretes devidos: registra disparo e agenda recorrencia."""
        devidos = self.devidos(usuario_id)
        disparados: list[dict] = []
        for lembrete in devidos:
            disparados.append(lembrete)
            if lembrete.get("recorrencia"):
                nova_data = self.proxima_ocorrencia(
                    lembrete["data_hora"], lembrete["recorrencia"],
                )
                self.repo.update(lembrete["id"], data_hora=nova_data)
            else:
                self.repo.update(lembrete["id"], status="disparado")
        return disparados
