"""
OllamaProvider — fala com o Ollama (modelos de IA locais) cumprindo a porta
LLMProvider.

Suporta tool-calling (function calling): quando recebemos `tools`, o modelo pode
responder escolhendo uma função em vez de texto puro. É isso que permite ao
Orquestrador "delegar" para um agente como se chamasse uma função.

Requer um modelo que suporte ferramentas (ex.: llama3.1). Se o modelo ignorar as
ferramentas, devolvemos só o texto — e quem chamou decide o fallback.

Resiliência de GPU: se o Ollama responder com "CUDA out of memory", religamos o
MESMO modelo em CPU (options.num_gpu=0) e tentamos de novo automaticamente. Não
trocamos de modelo nem mexemos nos agentes — só o carregamento muda de GPU p/ CPU.
"""

from __future__ import annotations

import json
import logging

import requests

from core.contracts.llm import LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Erro ao falar com o Ollama (offline, modelo ausente, timeout, etc.)."""


class OllamaProvider:
    """Implementação de LLMProvider sobre a API REST do Ollama."""

    def __init__(
        self,
        host: str,
        model: str,
        timeout: int = 120,
        num_gpu: int | None = None,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        # num_gpu: None = Ollama decide; 0 = força CPU; N = N camadas na GPU.
        self.num_gpu = num_gpu
        # Vira True após um "CUDA out of memory": passamos a rodar em CPU (sticky).
        self._cpu_fallback = False
        self._provider_name = "ollama"

    # ------------------------------------------------------------------
    def is_alive(self) -> bool:
        """True se o servidor Ollama responde."""
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Envia as mensagens ao modelo e devolve texto e/ou tool_calls.

        Em caso de "CUDA out of memory", religa este modelo em CPU e tenta de novo.
        """
        return self._request_chat(messages, tools, permite_fallback=True)

    def _opcoes(self) -> dict | None:
        """Monta o bloco 'options' do Ollama (controle de GPU/CPU)."""
        n = 0 if self._cpu_fallback else self.num_gpu
        return {"num_gpu": n} if n is not None else None

    @staticmethod
    def _is_oom(texto: str) -> bool:
        """Detecta mensagem de falta de memória de GPU vinda do Ollama."""
        t = (texto or "").lower()
        return any(s in t for s in ("out of memory", "cuda error", "cudamalloc", "vram"))

    def _request_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        permite_fallback: bool,
    ) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        opcoes = self._opcoes()
        if opcoes:
            payload["options"] = opcoes

        try:
            r = requests.post(
                f"{self.host}/api/chat", json=payload, timeout=self.timeout
            )
            r.raise_for_status()
        except requests.Timeout as exc:
            raise OllamaError(
                f"O modelo demorou mais de {self.timeout}s para responder."
            ) from exc
        except requests.ConnectionError as exc:
            raise OllamaError(
                "Nao consegui falar com o Ollama. Ele esta rodando? "
                "Tente 'ollama serve'."
            ) from exc
        except requests.HTTPError as exc:
            corpo = r.text or ""
            # Fallback automático: GPU sem memória -> religa em CPU e tenta 1x.
            if permite_fallback and not self._cpu_fallback and self._is_oom(corpo):
                logger.warning(
                    "CUDA out of memory no modelo '%s'. Religando em CPU "
                    "(num_gpu=0) e tentando novamente.",
                    self.model,
                )
                self._cpu_fallback = True
                return self._request_chat(messages, tools, permite_fallback=False)
            raise OllamaError(
                f"O Ollama respondeu com erro: {r.status_code} {corpo}"
            ) from exc

        mensagem = r.json().get("message", {}) or {}
        content = (mensagem.get("content") or "").strip()
        tool_calls = self._parse_tool_calls(mensagem.get("tool_calls") or [])

        return LLMResponse(content=content, tool_calls=tool_calls)

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_tool_calls(brutos: list[dict]) -> list[ToolCall]:
        """Converte o formato do Ollama em ToolCall do nosso contrato."""
        chamadas: list[ToolCall] = []
        for c in brutos:
            fn = c.get("function", {}) or {}
            nome = fn.get("name")
            if not nome:
                continue
            args = fn.get("arguments", {})
            # O Ollama costuma devolver dict; algumas versões devolvem string JSON.
            if isinstance(args, str):
                try:
                    args = json.loads(args or "{}")
                except json.JSONDecodeError:
                    args = {}
            chamadas.append(ToolCall(name=nome, arguments=args or {}))
        return chamadas
