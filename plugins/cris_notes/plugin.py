"""
CRIS Notes — plugin de notas pessoais do CRIS OS.

Valida que um segundo plugin de dominio totalmente diferente
(email vs notas) funciona sobre o mesmo Core sem alteracoes.

Nao usa banco de dados — notas sao mantidas em memoria.
Interface limpa para futura persistencia real.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from core.application.core_api import CoreAPI
from core.capability.errors import CapabilityPermissionError
from core.plugins.base import PluginBase
from core.plugins.models import PluginManifest


class CrisNotesPlugin(PluginBase):
    """Plugin de notas pessoais do CRIS OS."""

    def __init__(self, manifest: PluginManifest, api: CoreAPI) -> None:
        super().__init__(manifest, api)
        self._notes: dict[str, dict] = {}
        self._started_at: float = 0.0
        self._metrics = {
            "total_created": 0,
            "total_read": 0,
            "total_searched": 0,
            "total_deleted": 0,
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
            self._metrics["total_deleted"] += 1  # rough error count placeholder
            self.api.record_failure(capability_name)
            return {"success": False, "error": str(exc)}
        finally:
            duration = self.api.now_ms() - t0
            self.api.record_call(capability_name, duration, success)

    def _dispatch(self, name: str, data: dict, ctx: dict) -> dict:
        # --- notes.create ---
        if name == "notes.create":
            note_id = uuid.uuid4().hex[:12]
            now = _ts()
            note = {
                "id": note_id,
                "title": data["title"],
                "content": data["content"],
                "tags": data.get("tags", []),
                "created_at": now,
                "updated_at": now,
            }
            self._notes[note_id] = note
            self._metrics["total_created"] += 1

            self.api.publish_event(
                "notes.created",
                note_id=note_id,
                title=note["title"],
                plugin=self.name,
            )
            self.log_info("Nota criada: %s", note["title"])
            return {
                "success": True,
                "id": note_id,
                "title": note["title"],
                "created_at": now,
            }

        # --- notes.read ---
        if name == "notes.read":
            note_id = data.get("note_id", "")
            note = self._notes.get(note_id)
            if not note:
                return {"success": False, "error": f"Nota {note_id} nao encontrada"}
            self._metrics["total_read"] += 1
            return {"success": True, **note}

        # --- notes.search ---
        if name == "notes.search":
            query = data.get("query", "").lower()
            max_results = data.get("max_results", 20)
            results = [
                n for n in self._notes.values()
                if query in n["title"].lower()
                or query in n["content"].lower()
                or any(query in t.lower() for t in n["tags"])
            ]
            self._metrics["total_searched"] += 1
            return {"success": True, "results": results[:max_results], "total": len(results)}

        # --- notes.delete ---
        if name == "notes.delete":
            self.api.require_permission("notes.delete")
            note_id = data.get("note_id", "")
            if note_id not in self._notes:
                return {"success": False, "error": f"Nota {note_id} nao encontrada"}
            title = self._notes[note_id]["title"]
            del self._notes[note_id]
            self._metrics["total_deleted"] += 1

            self.api.publish_event(
                "notes.deleted",
                note_id=note_id,
                title=title,
                plugin=self.name,
            )
            self.log_info("Nota removida: %s", title)
            return {"success": True, "status": "deleted", "note_id": note_id}

        # --- notes.health ---
        if name == "notes.health":
            uptime = int((time.monotonic() - self._started_at) * 1000)
            return {
                "success": True,
                "status": self.state.value,
                "total_notes": len(self._notes),
                "uptime_ms": uptime,
            }

        # --- notes.metrics ---
        if name == "notes.metrics":
            return {
                "success": True,
                **self._metrics,
                "active_notes": len(self._notes),
            }

        return {"success": False, "error": f"Capability desconhecida: {name}"}

    # ==================================================================
    # Eventos
    # ==================================================================

    def on_event(self, event: Any) -> None:
        if event.type == "notes.sync.requested":
            self.log_info("Sincronizacao de notas acionada via evento")
            self.api.publish_event(
                "notes.sync.completed",
                total_notes=len(self._notes),
                plugin=self.name,
            )

    # ==================================================================
    # Ciclo de vida
    # ==================================================================

    def on_install(self) -> None:
        self._started_at = time.monotonic()
        max_notes = self.api.get_config("max_notes", "1000")
        self.log_info("Plugin instalado. Max notas: %s", max_notes)

    def on_start(self) -> None:
        self._started_at = time.monotonic()
        self.log_info("Plugin de notas ativado")

    def on_stop(self) -> None:
        self.log_info("Plugin de notas desativado. Notas ativas: %d", len(self._notes))

    def on_uninstall(self) -> None:
        self.api.delete_config("max_notes")
        self._notes.clear()
        self.log_info("Plugin de notas removido")


def _ts() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()