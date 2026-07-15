"""
Provedores de LLM (implementações da porta LLMProvider).

Fase 1: Ollama (modelos locais).
Fase 2: NVIDIA AI (provedor remoto, OpenAI-compatível).
Futuro: Claude Code / outros — basta criar outra classe que cumpra o contrato.
"""

from .nvidia import NVIDIAProvider  # noqa: F401
from .ollama import OllamaProvider  # noqa: F401
