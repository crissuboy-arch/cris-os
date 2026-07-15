"""
BaseAgent — o "funcionário digital" genérico.

Recebe uma Task do Orquestrador e um AgentContext já ESCOPADO (só a memória do
seu domínio + permanente + base de conhecimento relevante + itens do dia). Usa o
LLM para produzir um resultado. NÃO conhece canais, não fala com a Cris e não
enxerga a memória de outros projetos.

Quase todos os 11 especialistas são instâncias desta classe, mudando só o cargo
(`SYSTEM.md`) e o escopo (`projects`). Comportamento próprio? Herde e sobrescreva.

TODO (fase futura): laço de uso de ferramentas (tools/MCP) dentro do handle.
"""

from __future__ import annotations

import json
import logging
import time

from agents._format import render_itens
from core.contracts.agent import AgentContext
from core.models import AgentResult, Task

logger = logging.getLogger(__name__)


class BaseAgent:
    def __init__(self, name: str, description: str, system_prompt: str, llm,
                 projects: list[str] | None = None, tools: list | None = None,
                 status: str = "draft", domain: str = "",
                 keywords: list[str] | None = None) -> None:
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.llm = llm
        self.projects = projects or []  # escopo de memória de projeto (L2); ["*"] = todos
        self.tools = tools or []  # reservado para a Fase de ferramentas
        self.status = status
        self.domain = domain  # domínio p/ roteamento hierárquico (usado a partir do B7)
        self.keywords = keywords or []  # palavras-chave do fallback (core/router.py)

    # ------------------------------------------------------------------
    def _montar_system(self, context: AgentContext) -> str:
        partes = [self.system_prompt]

        if context.permanent:
            partes.append("----- SOBRE A CRIS (memória permanente) -----\n"
                          + render_itens(context.permanent))
        if context.project_memory:
            partes.append("----- MEMÓRIA DO(S) PROJETO(S) -----\n"
                          + render_itens(context.project_memory))
        if context.knowledge:
            kb = "\n".join(f"- ({p.source}) {p.text}" for p in context.knowledge)
            partes.append("----- BASE DE CONHECIMENTO (trechos relevantes) -----\n" + kb)
        if context.temporary:
            partes.append("----- HOJE (itens do dia) -----\n"
                          + "\n".join(f"- {t}" for t in context.temporary))

        return "\n\n".join(partes)

    # ------------------------------------------------------------------
    def _model_name(self) -> str:
        """Nome legível do modelo usado pelo provider deste agente."""
        p = getattr(self.llm, "_provider_name", None) or getattr(self.llm, "model", None) or "desconhecido"
        return p

    def handle(self, task: Task, context: AgentContext) -> AgentResult:
        model_name = self._model_name()
        logger.info("=== [AGENT '%s'] Executando (modelo: %s): '%s' ===",
                    self.name, model_name, task.instruction[:120])

        system = self._montar_system(context)
        mensagens: list[dict] = [{"role": "system", "content": system}]
        mensagens.extend(context.conversation)
        mensagens.append({"role": "user", "content": task.instruction})

        n_historico = len(context.conversation)
        logger.info("=== [AGENT '%s'] Prompt: %d msgs, system=%d chars, historico=%d msgs ===",
                    self.name, len(mensagens), len(system), n_historico)
        logger.debug("=== [AGENT '%s'] CONTEUDO DO PROMPT (DEBUG) ===\n%s",
                     self.name, json.dumps(mensagens, ensure_ascii=False)[:2000])

        try:
            t0 = time.perf_counter()
            saida = self.llm.chat(mensagens).content.strip()
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info("=== [AGENT '%s'] Provider respondeu em %.0fms (%d chars): '%s' ===",
                        self.name, elapsed_ms, len(saida), saida[:200])
        except Exception as exc:  # noqa: BLE001 - reporta a falha ao orquestrador
            logger.exception("=== [AGENT '%s'] Provider FALHOU ===", self.name)
            return AgentResult(agent=self.name,
                               output=f"(o agente {self.name} não conseguiu responder: {exc})",
                               success=False)

        return AgentResult(agent=self.name, output=saida or "(sem resposta)")
