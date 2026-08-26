"""
IA do modulo Prospector — AIsa como provedor principal, fallback no CRIS OS.

Regra do CRIS OS: "Manter AIsa como provedor principal do modulo Prospector.
Quando indisponivel: usar automaticamente o roteador de LLM do CRIS OS. Nao
duplicar provedores."

Por isso nenhum provedor novo e criado aqui: o fallback usa o LLMRouter do CRIS
OS (llm.router) montado com os provedores que ja existem no projeto (Ollama,
NVIDIA, OpenAI-compativel) — apenas uma composicao a partir das settings.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


class ProspectorLLM:
    """Adapter de chat do Prospector com fallback automatico.

    Interface compativel com `motor.chat(chave, sistema, usuario, ...)` para
    poder ser injetada no lugar do motor sem copiar regras de negocio.
    """

    def __init__(self, motor_chat=None, cris_router=None, chave_fn=None) -> None:
        self._motor_chat = motor_chat  # funcao motor.chat (AIsa)
        self._cris_router = cris_router  # roteador LLM do CRIS OS (porta LLMProvider)
        self._chave_fn = chave_fn  # retorna a chave AIsa (str | "")

    def chave_aisa(self) -> str:
        if self._chave_fn:
            try:
                return self._chave_fn() or ""
            except Exception:
                return ""
        return ""

    def chat(self, chave, sistema, usuario, json_mode=True, max_tokens=None):
        """Tenta AIsa; se falhar (ou sem chave), cai no roteador do CRIS OS."""
        chave = chave or self.chave_aisa()

        if chave and self._motor_chat is not None:
            try:
                return self._motor_chat(
                    chave, sistema, usuario,
                    json_mode=json_mode, max_tokens=max_tokens,
                )
            except Exception as exc:
                logger.warning("AIsa indisponivel (%s) — usando fallback do CRIS OS.", exc)

        if self._cris_router is not None:
            mensagens = [
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ]
            resp = self._cris_router.chat(mensagens)
            texto = (getattr(resp, "content", "") or "").strip()
            if json_mode:
                m = re.search(r"\{.*\}", texto, re.S)
                if m:
                    try:
                        return json.loads(m.group(0))
                    except json.JSONDecodeError:
                        return {}
            return texto

        raise RuntimeError(
            "Prospector sem provedor de IA disponivel (AIsa e roteador do CRIS OS indisponiveis)."
        )


def build_cris_router():
    """Monta o LLMRouter do CRIS OS a partir das settings (sem duplicar provedores).

    Compoe os provedores ja existentes (Ollama local + NVIDIA/OpenAI de fallback)
    usando as mesmas classes do pacote `llm`. Retorna None se nada estiver viavel.
    """
    from config.settings import settings
    from llm.router import LLMRouter

    providers: dict = {}
    default = None

    try:
        from llm.ollama import OllamaProvider
        ollama = OllamaProvider(
            settings.OLLAMA_HOST, settings.OLLAMA_MODEL,
            settings.OLLAMA_TIMEOUT, num_gpu=settings.OLLAMA_NUM_GPU,
        )
        providers["ollama"] = ollama
        default = ollama
    except Exception as exc:  # pragma: no cover
        logger.warning("Ollama indisponivel para o fallback do Prospector: %s", exc)

    if settings.NVIDIA_API_KEY and settings.NVIDIA_API_KEY != "COLE_SUA_CHAVE_AQUI":
        try:
            from llm.nvidia import NVIDIAProvider
            nv = NVIDIAProvider(
                settings.NVIDIA_API_KEY, settings.NVIDIA_GENERATION_MODEL,
                settings.NVIDIA_BASE_URL, role="generation",
            )
            providers["nvidia_gen"] = nv
            default = nv
        except Exception as exc:  # pragma: no cover
            logger.warning("NVIDIA indisponivel para o fallback do Prospector: %s", exc)

    if default is None:
        return None
    return LLMRouter(default=default, providers=providers)
