"""
LLMRouter — política de modelos (local + remoto).

Implementa a porta LLMProvider, então pode ser injetado em qualquer lugar que
espere um provedor. Por dentro, escolhe QUAL modelo usar por "papel" (role):
  - roteamento/planejamento pode usar um modelo local barato;
  - síntese/redação pode usar um modelo maior (local ou remoto);
  - tarefas específicas podem ir para um provedor remoto (Claude, etc.).

Cada provedor expõe `_provider_name` para logging de latência.
"""

from __future__ import annotations

import logging
import time

from core.contracts.llm import LLMResponse

logger = logging.getLogger(__name__)


class LLMRouter:
    def __init__(self, default, providers: dict | None = None, policy: dict | None = None) -> None:
        self.default = default
        self.providers = providers or {}
        self.policy = policy or {}  # role -> nome do provedor

    def for_role(self, role: str):
        """Devolve o provedor adequado ao papel (ou o padrão)."""
        nome = self.policy.get(role)
        p = self.providers.get(nome, self.default)
        return p

    # --- Porta LLMProvider (usa o provedor padrão) ---
    def is_alive(self) -> bool:
        return self.default.is_alive()

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        nome = getattr(self.default, "_provider_name", None) or type(self.default).__name__
        modelo = getattr(self.default, "model", "?")
        logger.debug("=== [LLM_ROUTER] Usando provider '%s' (modelo: %s) ===", nome, modelo)
        t0 = time.perf_counter()
        try:
            resp = self.default.chat(messages, tools=tools)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info("=== [TIMING] Provider '%s/%s': %.0fms (tool_calls=%d, content=%d chars) ===",
                        nome, modelo, elapsed_ms, len(resp.tool_calls), len(resp.content))
            return resp
        except Exception:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.warning("=== [TIMING] Provider '%s/%s' FALHOU em %.0fms ===",
                           nome, modelo, elapsed_ms)
            raise
