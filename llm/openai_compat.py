"""
OpenAICompatProvider — Provedor LLM para APIs compativeis com OpenAI.

Funciona com OpenAI, Together AI, DeepSeek, e qualquer API que use o formato
/v1/chat/completions. Implementa a porta LLMProvider.

Uso:
    provider = OpenAICompatProvider(
        api_key="sk-...",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1"
    )
    resp = provider.chat([{"role": "user", "content": "Ola!"}])
"""

from __future__ import annotations

import json
import logging

import requests

from core.contracts.llm import LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class OpenAICompatError(Exception):
    """Erro ao falar com a API OpenAI-compativel."""


class OpenAICompatProvider:
    """
    Provedor LLM para APIs compativeis com OpenAI.

    Usa /v1/chat/completions com autenticacao Bearer token.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 120,
        role: str = "generation",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.role = role
        self._provider_name = "openai_compat"

    def is_alive(self) -> bool:
        """True se o endpoint responde (consulta /v1/models)."""
        try:
            r = requests.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=10,
            )
            return r.status_code == 200
        except requests.RequestException:
            return False

    def check_model(self) -> tuple[bool, list[str]]:
        """
        Verifica se o modelo configurado esta disponivel.

        Retorna (disponivel, [sugestoes]).
        """
        try:
            r = requests.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=10,
            )
            if r.status_code != 200:
                return False, []
            modelos = r.json().get("data", [])
            nomes = [m["id"] for m in modelos if "id" in m]
            if self.model in nomes:
                return True, []
            sugestoes = [m for m in nomes if any(
                p in m for p in self.model.replace(":", "").split("/")[-1].split("-")
            )][:3]
            return False, sugestoes
        except requests.RequestException:
            return False, []

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Envia mensagens ao modelo e devolve resposta."""
        return self._request_chat(messages, tools)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _request_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools

        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            r.raise_for_status()
        except requests.Timeout as exc:
            raise OpenAICompatError(
                f"O modelo demorou mais de {self.timeout}s para responder."
            ) from exc
        except requests.ConnectionError as exc:
            raise OpenAICompatError(
                "Nao consegui falar com a API. Verifique a URL e conexao."
            ) from exc
        except requests.HTTPError as exc:
            corpo = r.text or ""
            raise OpenAICompatError(
                f"API respondeu com erro: {r.status_code} {corpo[:500]}"
            ) from exc

        data = r.json()
        choice = (data.get("choices") or [{}])[0] or {}
        message = choice.get("message", {}) or {}
        content = (message.get("content") or "").strip()
        tool_calls = self._parse_tool_calls(message.get("tool_calls") or [])

        return LLMResponse(content=content, tool_calls=tool_calls)

    @staticmethod
    def _parse_tool_calls(brutos: list[dict]) -> list[ToolCall]:
        """Converte o formato OpenAI em ToolCall do nosso contrato."""
        chamadas: list[ToolCall] = []
        for c in brutos:
            fn = c.get("function", {}) or {}
            nome = fn.get("name")
            if not nome:
                continue
            args = fn.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args or "{}")
                except json.JSONDecodeError:
                    args = {}
            chamadas.append(ToolCall(name=nome, arguments=args or {}))
        return chamadas
