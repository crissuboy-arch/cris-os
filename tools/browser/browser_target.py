"""
BrowserTarget — ExecutionTarget SOMENTE LEITURA para navegação (type=TOOL).

Pluga o BrowserTool no kernel de execução. Todas as ações são read-only; qualquer
verbo de escrita (click/fill/login/buy/publish/send/...) é RECUSADO com erro claro,
sem tocar a página. Como o passo é `Effect.READ_ONLY`, o ConfirmationGate o libera
sem pedir confirmação — leitura é segura.

`id` estável = "tool.browser" (logs/tracing/métricas). Para múltiplos browsers no
futuro (chrome/mobile/cloud), basta outro BrowserTarget com outro `id`.
"""

from __future__ import annotations

from core.domain.execution import ExecutionType
from core.models import ExecutionResult
from tools.browser.browser_tool import BrowserTool, PageSnapshot

# Ações de leitura permitidas.
_READ_ACTIONS = ("open", "snapshot", "title", "text", "links", "images", "screenshot")
# Verbos de escrita explicitamente proibidos (defesa em profundidade).
_FORBIDDEN = ("click", "fill", "type", "login", "submit", "buy", "purchase",
              "checkout", "publish", "post", "send", "upload", "delete")


class BrowserTarget:
    """Executor read-only de navegação. Recusa qualquer ação de escrita."""

    type = ExecutionType.TOOL

    def __init__(self, tool: BrowserTool | None = None, id: str = "tool.browser") -> None:
        self.id = id
        self.tool = tool or BrowserTool()

    def run(self, step, ctx) -> ExecutionResult:
        payload = step.payload or {}
        action = str(payload.get("action") or "snapshot").lower()
        url = payload.get("url", "")

        if action in _FORBIDDEN:
            return self._erro(url, f"Ação '{action}' não permitida: o Browser é SOMENTE LEITURA.")
        if action not in _READ_ACTIONS:
            return self._erro(url, f"Ação '{action}' desconhecida. Permitidas: {', '.join(_READ_ACTIONS)}.")

        snap = self.tool.read(url, want_screenshot=(action == "screenshot"))
        if not snap.ok:
            return self._erro(url, snap.error)

        return ExecutionResult(
            source=self.id, type=ExecutionType.TOOL, success=True,
            output=self._render(action, snap), data=self._data(snap),
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _render(action: str, s: PageSnapshot) -> str:
        if action == "title":
            return s.title
        if action == "text":
            return s.text
        if action == "links":
            return "\n".join(s.links)
        if action == "images":
            return "\n".join(s.images)
        if action == "screenshot":
            return f"Screenshot salvo em: {s.screenshot_path}" if s.screenshot_path else "(sem screenshot)"
        return f"{s.title or s.url} — {len(s.links)} links, {len(s.images)} imagens."  # open/snapshot

    @staticmethod
    def _data(s: PageSnapshot) -> dict:
        return {"url": s.url, "title": s.title, "links": s.links, "images": s.images,
                "screenshot_path": s.screenshot_path, "text_len": len(s.text)}

    def _erro(self, url, msg: str) -> ExecutionResult:
        return ExecutionResult(source=self.id, type=ExecutionType.TOOL, success=False,
                               error=msg, output=f"⚠️ {msg}", data={"url": url})
