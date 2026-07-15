"""
Router — roteamento determinístico de RESERVA.

Na v3, quem decide o agente é o Orquestrador (via LLM + tool-calling). Este Router
existe como **rede de segurança**: se o modelo falhar, ignorar as ferramentas ou
ficar offline, o Orquestrador usa este roteamento simples por palavra-chave para
nunca deixar a Cris sem resposta.

As palavras-chave vêm dos **manifests dos agentes** (`"keywords"`), não de um mapa
hardcoded — adicionar/etiquetar um agente não exige mexer aqui (OCP). Itera os
agentes na ordem recebida (registry) e devolve o primeiro cujo keyword casa.
Default seguro: a Secretária.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class Router:
    """Roteamento de reserva por palavra-chave (derivado dos manifests)."""

    def __init__(self, default_agent: str = "secretary", agents=None) -> None:
        self.default_agent = default_agent
        # Mapa ordenado [(agente, keywords)], derivado dos agentes carregados.
        self._mapa: list[tuple[str, list[str]]] = [
            (a.name, [k.lower() for k in getattr(a, "keywords", [])])
            for a in (agents or [])
        ]

    def route(self, message: str) -> str:
        """Retorna o agente provável para a mensagem (fallback)."""
        texto = message.lower()
        for nome, palavras in self._mapa:
            if any(p in texto for p in palavras):
                logger.debug("Fallback roteou para '%s'", nome)
                return nome
        return self.default_agent
