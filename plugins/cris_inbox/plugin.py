"""
CRIS Inbox — plugin de e-mail oficial do CRIS OS.

Simula um provedor de e-mail para validar toda a arquitetura do Core:
  - CapabilityRegistry (6 capabilities registradas)
  - EventBus (publica/consome eventos)
  - PluginConfigStore (configuracoes do plugin)
  - SimplePermissionChecker (valida permissoes de send/archive)
  - Health tracking e metricas
  - Ciclo de vida (install, start, stop)

Nao integra Gmail nem Outlook — dados sao simulados em memoria.
Interface limpa para futura integracao real.
"""

from __future__ import annotations

import time
from typing import Any

from core.application.core_api import CoreAPI
from core.capability.errors import CapabilityPermissionError
from core.plugins.base import PluginBase
from core.plugins.models import PluginManifest


# Dados simulados de e-mail
_INBOX: list[dict] = [
    {"id": "msg-001", "from": "cliente@exemplo.com", "subject": "Orcamento",
     "body": "Gostaria de um orcamento para o projeto.", "date": "2026-07-27T10:00:00Z"},
    {"id": "msg-002", "from": "fornecedor@exemplo.com", "subject": "Fatura",
     "body": "Fatura do mes de junho em anexo.", "date": "2026-07-27T11:30:00Z"},
    {"id": "msg-003", "from": "cris@crisos.com", "subject": "Lembrete",
     "body": "Reuniao com equipe as 14h.", "date": "2026-07-28T08:00:00Z"},
    {"id": "msg-004", "from": "newsletter@tech.com", "subject": "Novidades da semana",
     "body": "Confira as novidades em tecnologia esta semana.", "date": "2026-07-28T09:15:00Z"},
]


class CrisInboxPlugin(PluginBase):
    """Plugin de e-mail do CRIS OS."""

    def __init__(self, manifest: PluginManifest, api: CoreAPI) -> None:
        super().__init__(manifest, api)
        self._started_at: float = 0.0
        self._metrics = {
            "total_sent": 0,
            "total_read": 0,
            "total_searched": 0,
            "total_archived": 0,
            "errors": 0,
        }

    # ==================================================================
    # PluginBase: execute()
    # ==================================================================

    def execute(self, capability_name: str, input_data: dict, context: dict | None = None) -> dict:
        t0 = self.api.now_ms()
        success = False
        try:
            result = self._dispatch(capability_name, input_data, context or {})
            success = True
            return result
        except CapabilityPermissionError:
            raise
        except Exception as exc:
            self._metrics["errors"] += 1
            self.api.record_failure(capability_name)
            return {"success": False, "error": str(exc)}
        finally:
            duration = self.api.now_ms() - t0
            self.api.record_call(capability_name, duration, success)

    def _dispatch(self, name: str, data: dict, ctx: dict) -> dict:
        # --- email.read ---
        if name == "email.read":
            msg_id = data["message_id"]
            for msg in _INBOX:
                if msg["id"] == msg_id:
                    self._metrics["total_read"] += 1
                    return {"success": True, **msg}
            return {"success": False, "error": f"Mensagem {msg_id} nao encontrada"}

        # --- email.search ---
        if name == "email.search":
            query = data.get("query", "").lower()
            max_results = data.get("max_results", 10)
            results = [m for m in _INBOX if query in m["subject"].lower() or query in m["body"].lower()]
            self._metrics["total_searched"] += 1
            return {"success": True, "results": results[:max_results], "total": len(results)}

        # --- email.send ---
        if name == "email.send":
            self.api.require_permission("email.send")
            to = data.get("to", "")
            subject = data.get("subject", "")
            body = data.get("body", "")
            new_id = f"msg-out-{int(time.time())}"
            self._metrics["total_sent"] += 1
            # Publica evento de email enviado
            self.api.publish_event(
                "email.sent",
                message_id=new_id,
                to=to,
                subject=subject,
                plugin=self.name,
            )
            return {
                "success": True,
                "message_id": new_id,
                "status": "sent",
                "to": to,
                "subject": subject,
            }

        # --- email.archive ---
        if name == "email.archive":
            self.api.require_permission("email.archive")
            msg_id = data.get("message_id", "")
            self._metrics["total_archived"] += 1
            return {"success": True, "status": "archived", "message_id": msg_id}

        # --- email.health ---
        if name == "email.health":
            uptime = int((time.monotonic() - self._started_at) * 1000)
            return {
                "success": True,
                "status": self.state.value,
                "provider": "simulado",
                "uptime_ms": uptime,
            }

        # --- email.metrics ---
        if name == "email.metrics":
            return {"success": True, **self._metrics}

        return {"success": False, "error": f"Capability desconhecida: {name}"}

    # ==================================================================
    # Eventos
    # ==================================================================

    def on_event(self, event: Any) -> None:
        if event.type == "email.send.requested":
            payload = event.payload
            result = self.execute("email.send", {
                "to": payload.get("to", ""),
                "subject": payload.get("subject", ""),
                "body": payload.get("body", ""),
            })
            self.api.publish_event(
                "email.send.completed",
                request_id=event.id,
                result=result,
            )
            self.log_info("Email enviado via evento: %s", payload.get("subject"))

        elif event.type == "email.sync.triggered":
            self.log_info("Sincronizacao da caixa de entrada acionada")

    # ==================================================================
    # Ciclo de vida
    # ==================================================================

    def on_install(self) -> None:
        self._started_at = time.monotonic()
        # Carrega configuracoes do plugin (simulado)
        provider = self.api.get_config("email_provider", "simulado")
        self.log_info("Plugin instalado. Provedor configurado: %s", provider)

    def on_start(self) -> None:
        self._started_at = time.monotonic()
        self.log_info("Plugin de e-mail ativado")

    def on_stop(self) -> None:
        self.log_info("Plugin de e-mail desativado. Total enviado: %d", self._metrics["total_sent"])

    def on_uninstall(self) -> None:
        self.api.delete_config("email_provider")
        self.log_info("Plugin de e-mail removido")