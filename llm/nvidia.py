"""
NVIDIAProvider — fala com a API da NVIDIA AI (OpenAI-compatível) cumprindo
a porta LLMProvider.

Endpoint OpenAI-compatível: POST {base_url}/chat/completions
Autenticação: Bearer token (NVIDIA_API_KEY)

Suporta:
  - chat() para requests blocking com tool-calling
  - chat_stream() para respostas progressivas (infra)
  - check_model() para validar disponibilidade do modelo

Catálogo de modelos: https://build.nvidia.com
"""

from __future__ import annotations

import json
import logging
from typing import Generator

import requests

from core.contracts.llm import LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class NVIDIAError(Exception):
    """Erro ao falar com a API da NVIDIA (offline, auth, timeout, etc.)."""


class NVIDIAProvider:
    """Implementação de LLMProvider sobre a API OpenAI-compatível da NVIDIA."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        timeout: int = 120,
        role: str = "",
    ) -> None:
        if not api_key:
            raise NVIDIAError("NVIDIA_API_KEY está vazia. Preencha no .env.")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.role = role  # "router" | "generation" para logging
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        self._provider_name = f"nvidia/{role}" if role else "nvidia"

    # ------------------------------------------------------------------
    def is_alive(self) -> bool:
        """True se a API da NVIDIA responde e a chave é válida."""
        try:
            r = self._session.get(
                f"{self.base_url}/models",
                timeout=10,
            )
            return r.status_code == 200
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------
    def check_model(self) -> tuple[bool, list[str]]:
        """Valida se self.model está disponível no provedor.
        
        Retorna (disponivel, [sugestoes]).
        Sugestões são modelos alternativos disponíveis (máx 5).
        """
        try:
            r = self._session.get(f"{self.base_url}/models", timeout=15)
            if r.status_code != 200:
                return False, []
            data = r.json()
            available = []
            for item in data.get("data", []):
                mid = item.get("id", "")
                if mid:
                    available.append(mid)
            if self.model in available:
                return True, []
            limit = 5
            suggestions = [m for m in available if "llama" in m.lower() or "8b" in m.lower() or "70b" in m.lower()][:limit]
            return False, suggestions or available[:limit]
        except requests.RequestException:
            return False, []

    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Envia as mensagens para a API da NVIDIA e devolve texto e/ou tool_calls."""
        return self._request_chat(messages, tools)

    # ------------------------------------------------------------------
    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Generator[str, None, LLMResponse]:
        """Gera resposta progressiva (streaming). A cada passo yield o texto parcial.
        
        No final, retorna o LLMResponse completo (incluindo tool_calls).
        Uso:
            gerador = provider.chat_stream(mensagens)
            for trecho in gerador:
                print(trecho, end="")  # texto parcial
            resposta_completa = gerador.send(None)  # LLMResponse final
        """
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        try:
            r = self._session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=self.timeout,
                stream=True,
            )
            r.raise_for_status()
        except requests.RequestException as exc:
            raise NVIDIAError(f"Erro no streaming: {exc}") from exc

        content_parts: list[str] = []
        tool_calls_raw: list[dict] = []
        tool_calls_buffer: dict[int, dict] = {}

        for line in r.iter_lines(decode_unicode=True):
            if not line or line.startswith(":"):
                continue
            if line == "data: [DONE]":
                break
            if line.startswith("data: "):
                try:
                    chunk = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                text = delta.get("content", "")
                if text:
                    content_parts.append(text)
                    yield text
                tc_list = delta.get("tool_calls", [])
                for tc in tc_list:
                    idx = tc.get("index", 0)
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = tc
                    else:
                        existing = tool_calls_buffer[idx]
                        fn = tc.get("function", {})
                        existing_fn = existing.get("function", {})
                        existing_fn["name"] = existing_fn.get("name", "") + fn.get("name", "")
                        existing_fn["arguments"] = existing_fn.get("arguments", "") + fn.get("arguments", "")
                        existing["function"] = existing_fn

        final_content = "".join(content_parts).strip()
        all_tc = self._parse_tool_calls([v for _, v in sorted(tool_calls_buffer.items())])
        return LLMResponse(content=final_content, tool_calls=all_tc)

    # ------------------------------------------------------------------
    def _request_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        try:
            r = self._session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()
        except requests.Timeout as exc:
            raise NVIDIAError(
                f"A NVIDIA demorou mais de {self.timeout}s para responder."
            ) from exc
        except requests.ConnectionError as exc:
            raise NVIDIAError(
                "Nao consegui falar com a API da NVIDIA. "
                "Verifique sua conexao com a internet."
            ) from exc
        except requests.HTTPError as exc:
            status = r.status_code
            corpo = r.text or ""
            if status == 401:
                raise NVIDIAError(
                    "Credencial rejeitada pela NVIDIA (401). "
                    "Verifique se NVIDIA_API_KEY esta correta no .env."
                ) from exc
            if status == 402:
                raise NVIDIAError(
                    "Saldo insuficiente na conta NVIDIA (402 Payment Required)."
                ) from exc
            raise NVIDIAError(
                f"A NVIDIA respondeu com erro: {status} {corpo}"
            ) from exc

        data = r.json()
        choice = (data.get("choices") or [{}])[0] or {}
        message = choice.get("message", {}) or {}
        content = (message.get("content") or "").strip()
        tool_calls = self._parse_tool_calls(message.get("tool_calls") or [])
        return LLMResponse(content=content, tool_calls=tool_calls)

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_tool_calls(brutos: list[dict]) -> list[ToolCall]:
        """Converte formato OpenAI (NVIDIA) em ToolCall do nosso contrato."""
        chamadas: list[ToolCall] = []
        for c in brutos:
            fn = c.get("function", {}) or {}
            nome = fn.get("name")
            if not nome:
                continue
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args or "{}")
                except json.JSONDecodeError:
                    args = {}
            chamadas.append(ToolCall(name=nome, arguments=args or {}))
        return chamadas
