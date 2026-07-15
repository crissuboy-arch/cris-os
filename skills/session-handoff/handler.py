"""
Session Handoff — executor da Skill.

Empacota o estado da sessão atual (conversa recente, itens do dia, notas e
próximos passos) para **retomar depois ou em outra máquina**, e retoma a partir
do último pacote salvo.

Integra com:
  - **Memory** (via porta estreita `SkillMemory`): lê conversa (L1) e itens do
    dia (L1 temporária); grava/recupera o pacote na memória permanente
    (L3, type="handoff"). A skill NÃO conhece `MemoryFacade`, camadas nem SQLite
    — só as 4 operações da porta. Como o backend vive no SQLite
    (`data/cris_os.db`), o handoff é naturalmente replicável (2ª máquina).
  - **Event Log**: publica `skill.session_handoff.created` / `...resumed` via o
    `publish` recebido no contexto.

NÃO altera Memory, Event Bus nem Orquestrador — usa tudo pelo `SkillContext`.
Cumpre (estruturalmente) a porta `core.contracts.skill.SkillExecutor` e depende
(estruturalmente) da porta `core.contracts.skill.SkillMemory`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from core.domain.events import Event

EVT_CREATED = "skill.session_handoff.created"
EVT_RESUMED = "skill.session_handoff.resumed"
HANDOFF_TYPE = "handoff"  # tipo do item na memória permanente (L3)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionHandoffSkill:
    """Skill: empacota/retoma o estado da sessão."""

    name = "session-handoff"
    version = "1.0.0"

    # ------------------------------------------------------------------
    def execute(self, payload: dict, context) -> dict:
        """Ações: 'save' (empacotar) ou 'resume' (retomar)."""
        payload = payload or {}
        action = payload.get("action", "save")
        if action == "save":
            return self._save(payload, context)
        if action == "resume":
            return self._resume(payload, context)
        return {"ok": False, "skill": self.name, "error": f"ação desconhecida: {action}"}

    # ------------------------------------------------------------------
    def _save(self, payload: dict, context) -> dict:
        mem = context.memory
        session = context.session

        conversa = mem.recent_conversation(session) if mem else []
        hoje = mem.today_items(session) if mem else []
        next_steps = list(payload.get("next_steps", []))
        notas = payload.get("notes", "")

        pacote = {
            "session": session,
            "created_at": _now(),
            "by": context.caller or "desconhecido",
            "notes": notas,
            "next_steps": next_steps,
            "conversation_tail": conversa[-6:],
            "today": hoje,
        }

        handoff_id = None
        if mem:
            titulo = f"Handoff {session} @ {pacote['created_at']}"
            item = mem.remember(
                HANDOFF_TYPE, titulo, json.dumps(pacote, ensure_ascii=False),
                tags=["handoff", session],
            )
            handoff_id = item.id

        self._emit(context, EVT_CREATED, {
            "session": session, "handoff_id": handoff_id, "next_steps": next_steps,
        })

        return {
            "ok": True, "skill": self.name, "action": "save",
            "handoff_id": handoff_id, "summary": self._render_save(pacote), "data": pacote,
        }

    # ------------------------------------------------------------------
    def _resume(self, payload: dict, context) -> dict:
        mem = context.memory
        session = context.session

        candidatos = [i for i in (mem.recall(HANDOFF_TYPE) if mem else [])
                      if session in i.tags]
        if not candidatos:
            self._emit(context, EVT_RESUMED, {"session": session, "found": False})
            return {"ok": True, "skill": self.name, "action": "resume", "found": False,
                    "summary": "Nenhum handoff salvo para esta sessão ainda."}

        ultimo = candidatos[-1]  # recall vem ordenado por created_at
        pacote = json.loads(ultimo.content)
        self._emit(context, EVT_RESUMED, {
            "session": session, "found": True, "handoff_id": ultimo.id,
        })
        return {"ok": True, "skill": self.name, "action": "resume", "found": True,
                "handoff_id": ultimo.id, "summary": self._render_resume(pacote), "data": pacote}

    # ------------------------------------------------------------------
    def _emit(self, context, tipo: str, payload: dict) -> None:
        if getattr(context, "publish", None):
            context.publish(Event(
                type=tipo, correlation_id=getattr(context, "correlation_id", "") or "",
                source="skill:session-handoff", payload=payload,
            ))

    @staticmethod
    def _render_save(p: dict) -> str:
        passos = "; ".join(p["next_steps"]) if p["next_steps"] else "(nenhum)"
        notas = p["notes"] or "(sem notas)"
        return (f"Sessão empacotada ✅ Próximos passos: {passos} | Notas: {notas} "
                f"| {len(p['conversation_tail'])} msgs, {len(p['today'])} itens do dia.")

    @staticmethod
    def _render_resume(p: dict) -> str:
        passos = "; ".join(p.get("next_steps", [])) or "(nenhum)"
        notas = p.get("notes") or "(sem notas)"
        return (f"Retomando de {p.get('created_at')} (por {p.get('by')}). "
                f"Próximos passos: {passos} | Notas: {notas}.")
