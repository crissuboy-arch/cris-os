"""
Carregador de agentes.

Varre a pasta `agents/` procurando `manifest.json` e monta um BaseAgent para cada
agente habilitado e marcado como delegável. Resultado: adicionar um novo agente
é só criar uma pasta com `manifest.json` + `SYSTEM.md` — nenhum código do núcleo
muda. Isso é baixo acoplamento na prática.

O Orquestrador NÃO é carregado como agente delegável (ele é o gerente). O prompt
dele é lido à parte, em core/runtime.py.
"""

from __future__ import annotations

import logging
from pathlib import Path

from agents.base import BaseAgent
from core.registry import discover_manifests

logger = logging.getLogger(__name__)


def carregar_agentes(agents_dir: Path, llm,
                     tool_executor=None) -> list[BaseAgent]:
    """Monta a lista de agentes delegáveis a partir dos manifests."""
    agentes: list[BaseAgent] = []

    for folder, dados in discover_manifests(agents_dir):
        if dados is None:
            logger.warning("Manifest inválido em %s", folder)
            continue

        # Pula o orquestrador (gerente) e agentes não-delegáveis/desabilitados.
        if not dados.get("delegate", True) or not dados.get("enabled", True):
            continue

        system_file = folder / "SYSTEM.md"
        system_prompt = (
            system_file.read_text(encoding="utf-8").strip()
            if system_file.exists()
            else "Você é um assistente prestativo. Responda em português do Brasil."
        )

        agentes.append(
            BaseAgent(
                name=dados["name"],
                description=dados.get("description", dados["name"]),
                system_prompt=system_prompt,
                llm=llm,
                projects=dados.get("projects", []),
                status=dados.get("status", "draft"),
                domain=dados.get("domain", ""),
                keywords=dados.get("keywords", []),
                tool_executor=tool_executor,
                tools_allowed=dados.get("tools_allowed"),
                tools_forbidden=dados.get("tools_forbidden"),
                tool_timeout=dados.get("tool_timeout", 60.0),
            )
        )

        if tool_executor:
            ferr = dados.get("tools_allowed", "todas")
            proib = dados.get("tools_forbidden", [])
            logger.info("Agente '%s' | ferramentas permitidas=%s proibidas=%s",
                        dados["name"], ferr, proib)

    logger.info("Agentes carregados: %s", ", ".join(a.name for a in agentes) or "(nenhum)")
    return agentes
