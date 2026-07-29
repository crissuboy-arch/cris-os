from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from channels.telegram.client import TelegramClient, get_telegram_client
from core.application.core_api import CoreAPI
from core.capability.errors import CapabilityPermissionError
from core.plugins.base import PluginBase
from core.plugins.models import PluginManifest


class CrisTelegramPlugin(PluginBase):

    def __init__(self, manifest: PluginManifest, api: CoreAPI) -> None:
        super().__init__(manifest, api)
        self._client: TelegramClient = get_telegram_client()
        self._started_at: float = 0.0
        self._pending_confirms: dict[str, dict] = {}
        self._logs: list[dict] = []
        self._metrics = {
            "total_sent": 0,
            "total_replied": 0,
            "total_notified": 0,
            "total_confirmed": 0,
            "total_rejected": 0,
            "total_errors": 0,
        }

    def _add_log(self, level: str, message: str, **extra: Any) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            **extra,
        }
        self._logs.append(entry)
        if len(self._logs) > 500:
            self._logs = self._logs[-500:]

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
            self._metrics["total_errors"] += 1
            self._add_log("error", f"Erro em {capability_name}: {exc}")
            self.api.record_failure(capability_name)
            return {"success": False, "error": str(exc)}
        finally:
            duration = self.api.now_ms() - t0
            self.api.record_call(capability_name, duration, success)

    def _dispatch(self, name: str, data: dict, ctx: dict) -> dict:
        if name == "telegram.send":
            return self._handle_send(data)
        if name == "telegram.reply":
            return self._handle_reply(data)
        if name == "telegram.notify":
            return self._handle_notify(data)
        if name == "telegram.confirm":
            return self._handle_confirm(data)
        if name == "telegram.reject":
            return self._handle_reject(data)
        if name == "telegram.health":
            return self._handle_health()
        if name == "telegram.metrics":
            return self._handle_metrics()
        if name == "telegram.execute_agent":
            return self._handle_execute_agent(data)
        if name == "telegram.get_status":
            return self._handle_get_status()
        if name == "telegram.get_logs":
            return self._handle_get_logs(data)
        return {"success": False, "error": f"Capability desconhecida: {name}"}

    def _handle_send(self, data: dict) -> dict:
        text = data.get("text", "")
        chat_id = data.get("chat_id", "")
        parse_mode = data.get("parse_mode", "Markdown")
        result = self._client.send_message(text=text, chat_id=chat_id, parse_mode=parse_mode)
        if result.get("ok"):
            self._metrics["total_sent"] += 1
            msg_id = result.get("result", {}).get("message_id")
            self._add_log("info", f"Mensagem enviada: {text[:50]}...", message_id=msg_id)
            self.api.publish_event("telegram.message.sent", message_id=msg_id, text=text[:100], plugin=self.name)
            return {"success": True, "message_id": msg_id, "chat_id": chat_id or self._client.chat_id}
        else:
            self._metrics["total_errors"] += 1
            error = result.get("error", "Unknown error")
            self._add_log("error", f"Falha ao enviar: {error}")
            return {"success": False, "error": error}

    def _handle_reply(self, data: dict) -> dict:
        text = data.get("text", "")
        reply_to = data.get("reply_to_message_id")
        chat_id = data.get("chat_id", "")
        if not reply_to:
            return {"success": False, "error": "reply_to_message_id obrigatorio"}
        result = self._client.send_message(text=text, chat_id=chat_id, parse_mode="Markdown")
        if result.get("ok"):
            self._metrics["total_replied"] += 1
            msg_id = result.get("result", {}).get("message_id")
            self._add_log("info", f"Resposta enviada para msg {reply_to}", message_id=msg_id)
            self.api.publish_event("telegram.message.replied", message_id=msg_id, reply_to=reply_to, plugin=self.name)
            return {"success": True, "message_id": msg_id}
        else:
            self._metrics["total_errors"] += 1
            return {"success": False, "error": result.get("error", "Unknown error")}

    def _handle_notify(self, data: dict) -> dict:
        text = data.get("text", "")
        priority = data.get("priority", "normal")
        chat_id = data.get("chat_id", "")
        prefix = {"low": "I", "normal": "N", "high": "!"}.get(priority, "N")
        full_text = f"[{prefix}] Notificacao CRIS OS\n\n{text}"
        result = self._client.send_message(text=full_text, chat_id=chat_id, parse_mode="Markdown")
        if result.get("ok"):
            self._metrics["total_notified"] += 1
            notif_id = uuid.uuid4().hex[:12]
            sent_at = datetime.now(timezone.utc).isoformat()
            self._add_log("info", f"Notificacao enviada ({priority})", notification_id=notif_id)
            self.api.publish_event("telegram.notification.sent", notification_id=notif_id, priority=priority, plugin=self.name)
            return {"success": True, "notification_id": notif_id, "sent_at": sent_at}
        else:
            self._metrics["total_errors"] += 1
            return {"success": False, "error": result.get("error", "Unknown error")}

    def _handle_confirm(self, data: dict) -> dict:
        text = data.get("text", "")
        confirm_id = data.get("confirm_id", "")
        chat_id = data.get("chat_id", "")
        buttons = [[
            {"text": "Sim", "callback_data": f"confirm:{confirm_id}:yes"},
            {"text": "Nao", "callback_data": f"confirm:{confirm_id}:no"},
        ]]
        result = self._client.send_message_with_keyboard(
            text=f"Confirmacao\n\n{text}", buttons=buttons, chat_id=chat_id, parse_mode="Markdown",
        )
        if result.get("ok"):
            self._metrics["total_confirmed"] += 1
            msg_id = result.get("result", {}).get("message_id")
            self._pending_confirms[confirm_id] = {
                "text": text, "created_at": datetime.now(timezone.utc).isoformat(),
                "message_id": msg_id, "status": "pending",
            }
            self._add_log("info", f"Confirmacao pendente: {confirm_id}", message_id=msg_id)
            self.api.publish_event("telegram.confirmation.pending", confirm_id=confirm_id, message_id=msg_id, plugin=self.name)
            return {"success": True, "message_id": msg_id, "confirm_id": confirm_id}
        else:
            self._metrics["total_errors"] += 1
            return {"success": False, "error": result.get("error", "Unknown error")}

    def _handle_reject(self, data: dict) -> dict:
        confirm_id = data.get("confirm_id", "")
        reason = data.get("reason", "Sem motivo especificado")
        chat_id = data.get("chat_id", "")
        if confirm_id in self._pending_confirms:
            del self._pending_confirms[confirm_id]
        text = f"Acao Rejeitada\n\nMotivo: {reason}"
        result = self._client.send_message(text=text, chat_id=chat_id, parse_mode="Markdown")
        self._metrics["total_rejected"] += 1
        self._add_log("info", f"Acao rejeitada: {confirm_id}", reason=reason)
        self.api.publish_event("telegram.action.rejected", confirm_id=confirm_id, reason=reason, plugin=self.name)
        return {"success": True, "confirm_id": confirm_id, "status": "rejected"}

    def _handle_health(self) -> dict:
        uptime = int((time.monotonic() - self._started_at) * 1000)
        return {
            "success": True, "status": self.state.value, "connected": self._client.enabled,
            "uptime_ms": uptime, "token_configured": bool(self._client.token),
            "chat_id_configured": bool(self._client.chat_id),
        }

    def _handle_metrics(self) -> dict:
        return {"success": True, **self._metrics}

    def _handle_execute_agent(self, data: dict) -> dict:
        agent_name = data.get("agent_name", "")
        input_text = data.get("input_text", "")
        chat_id = data.get("chat_id", "")
        if not agent_name or not input_text:
            return {"success": False, "error": "agent_name e input_text obrigatorios"}
        self._add_log("info", f"Executando agente '{agent_name}'", input=input_text[:100])
        try:
            result = self.api.execute("agent.execute", {"agent_name": agent_name, "input_text": input_text})
            if result.get("success"):
                response = result.get("response", "")
                send_result = self._client.send_message(text=response, chat_id=chat_id)
                msg_id = send_result.get("result", {}).get("message_id") if send_result.get("ok") else None
                self._add_log("info", f"Agente '{agent_name}' executado com sucesso")
                self.api.publish_event("agent.execution.completed", agent_name=agent_name, response=response[:200], plugin=self.name)
                return {"success": True, "agent_name": agent_name, "response": response, "message_id": msg_id}
            else:
                error = result.get("error", "Execution failed")
                self._add_log("error", f"Agente '{agent_name}' falhou: {error}")
                return {"success": False, "error": error}
        except Exception as exc:
            self._add_log("error", f"Erro ao executar agente: {exc}")
            return {"success": False, "error": str(exc)}

    def _handle_get_status(self) -> dict:
        return {
            "success": True, "connected": self._client.enabled, "token_valid": bool(self._client.token),
            "chat_id": self._client.chat_id, "api_url": "https://api.telegram.org",
        }

    def _handle_get_logs(self, data: dict) -> dict:
        limit = data.get("limit", 50)
        level = data.get("level", "all")
        logs = self._logs
        if level != "all":
            logs = [l for l in logs if l.get("level") == level]
        return {"success": True, "logs": logs[-limit:], "total": len(logs)}

    def on_event(self, event: Any) -> None:
        if event.type == "telegram.message.received":
            self._add_log("info", "Mensagem recebida via evento", payload=event.payload)
        elif event.type == "agent.execution.completed":
            self._add_log("info", "Execucao de agente concluida via evento")

    def on_install(self) -> None:
        self._started_at = time.monotonic()
        self.log_info("Plugin instalado com %d capabilities", len(self.manifest.capabilities))

    def on_start(self) -> None:
        self._started_at = time.monotonic()
        self.log_info("Plugin de Telegram ativado")

    def on_stop(self) -> None:
        self.log_info("Plugin de Telegram desativado. Total enviado: %d", self._metrics["total_sent"])

    def on_uninstall(self) -> None:
        self._pending_confirms.clear()
        self._logs.clear()
        self.log_info("Plugin de Telegram removido")