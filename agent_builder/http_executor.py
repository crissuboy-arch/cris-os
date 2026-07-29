"""
StudioHttpExecutor — executa ferramentas HTTP configuradas no Studio.

Suporta GET, POST, PUT, DELETE com headers customizados.
Valida URL, timeout, e tratamento de erros.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 30
MAX_RESPONSE_BYTES = 1024 * 1024  # 1MB


@dataclass
class HttpRequest:
    """Parametros de uma requisicao HTTP."""
    name: str
    url: str
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    body: str | dict | None = None
    timeout_s: int = DEFAULT_TIMEOUT_S


@dataclass
class HttpResponse:
    """Resposta de uma requisicao HTTP."""
    status: int
    body: str
    headers: dict[str, str] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: str = ""


class StudioHttpExecutor:
    """Executor de ferramentas HTTP do Studio."""

    def __init__(self, default_timeout_s: int = DEFAULT_TIMEOUT_S) -> None:
        self._default_timeout = default_timeout_s
        self._registered: dict[str, HttpRequest] = {}

    def register(self, config: dict) -> HttpRequest:
        """Registra uma ferramenta HTTP a partir de configuracao do Studio."""
        req = HttpRequest(
            name=config.get("name", "unnamed"),
            url=config.get("url", ""),
            method=config.get("method", "GET").upper(),
            headers=config.get("headers", {}),
            body=config.get("body"),
            timeout_s=config.get("timeout_s", self._default_timeout),
        )
        if not req.url:
            raise ValueError(f"Ferramenta HTTP '{req.name}' precisa de uma URL")
        self._registered[req.name] = req
        logger.info("HTTP tool registered: %s %s", req.method, req.url)
        return req

    def unregister(self, name: str) -> bool:
        if name in self._registered:
            del self._registered[name]
            return True
        return False

    def list_registered(self) -> list[dict]:
        return [
            {"name": r.name, "url": r.url, "method": r.method}
            for r in self._registered.values()
        ]

    def execute(self, name: str, params: dict | None = None) -> dict:
        """Executa uma ferramenta HTTP registrada."""
        req = self._registered.get(name)
        if req is None:
            return {"success": False, "error": f"Ferramenta HTTP '{name}' nao registrada"}

        try:
            response = self._do_request(req, params or {})
            if response.error:
                return {"success": False, "error": response.error, "status": response.status}

            # Try to parse JSON
            try:
                body = json.loads(response.body)
            except (json.JSONDecodeError, ValueError):
                body = {"raw": response.body}

            return {
                "success": 200 <= response.status < 400,
                "status": response.status,
                "data": body,
                "duration_ms": round(response.duration_ms, 2),
            }
        except Exception as e:
            logger.exception("HTTP tool '%s' failed", name)
            return {"success": False, "error": str(e)}

    def _do_request(self, req: HttpRequest, params: dict) -> HttpResponse:
        """Executa a requisicao HTTP real."""
        t0 = time.perf_counter()

        # Build URL with params
        url = req.url
        if params and req.method == "GET":
            query = "&".join(f"{k}={v}" for k, v in params.items() if v)
            if query:
                url = f"{url}?{query}"

        # Build request
        headers = dict(req.headers)
        data = None
        if req.body and req.method in ("POST", "PUT", "PATCH"):
            if isinstance(req.body, dict):
                body = {**req.body, **params}
            else:
                body = req.body
            data = json.dumps(body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        elif params and req.method == "GET":
            pass  # params already in URL

        try:
            http_req = urllib.request.Request(
                url, data=data, headers=headers, method=req.method,
            )
            with urllib.request.urlopen(http_req, timeout=req.timeout_s) as resp:
                body = resp.read(MAX_RESPONSE_BYTES).decode("utf-8", errors="replace")
                resp_headers = dict(resp.headers)
                elapsed = (time.perf_counter() - t0) * 1000
                return HttpResponse(
                    status=resp.status,
                    body=body,
                    headers=resp_headers,
                    duration_ms=elapsed,
                )
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read(MAX_RESPONSE_BYTES).decode("utf-8", errors="replace")
            except Exception:
                pass
            elapsed = (time.perf_counter() - t0) * 1000
            return HttpResponse(
                status=e.code,
                body=body,
                duration_ms=elapsed,
                error=f"HTTP {e.code}: {e.reason}",
            )
        except urllib.error.URLError as e:
            elapsed = (time.perf_counter() - t0) * 1000
            return HttpResponse(
                status=0, body="", duration_ms=elapsed,
                error=f"URL error: {e.reason}",
            )
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            return HttpResponse(
                status=0, body="", duration_ms=elapsed,
                error=str(e),
            )
