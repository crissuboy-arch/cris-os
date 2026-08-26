"""
BaseAgent — o "funcionário digital" genérico.

Recebe uma Task do Orquestrador e um AgentContext já ESCOPADO (só a memória do
seu domínio + permanente + base de conhecimento relevante + itens do dia). Usa o
LLM para produzir um resultado. NÃO conhece canais, não fala com a Cris e não
enxerga a memória de outros projetos.

Quase todos os 11 especialistas são instâncias desta classe, mudando só o cargo
(`SYSTEM.md`) e o escopo (`projects`). Comportamento próprio? Herde e sobrescreva.

Tool-calling: se um `tool_executor` for fornecido, o agente faz um loop
LLM -> tool call -> resultado -> LLM ate obter resposta final em texto.
"""

from __future__ import annotations

import json
import logging
import time

from agents._format import render_itens
from core.contracts.agent import AgentContext
from core.models import AgentResult, Task

logger = logging.getLogger(__name__)

_MAX_TOOL_ITERATIONS = 10


class BaseAgent:
    def __init__(self, name: str, description: str, system_prompt: str, llm,
                 projects: list[str] | None = None, tools: list | None = None,
                 status: str = "draft", domain: str = "",
                 keywords: list[str] | None = None,
                 tool_executor=None,
                 tools_allowed: list[str] | None = None,
                 tools_forbidden: list[str] | None = None,
                 tool_timeout: float = 60.0) -> None:
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.llm = llm
        self.projects = projects or []
        self.tools = tools or []
        self.status = status
        self.domain = domain
        self.keywords = keywords or []
        self.tool_executor = tool_executor
        self.tools_allowed = tools_allowed
        self.tools_forbidden = tools_forbidden
        self.tool_timeout = tool_timeout

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

    # ------------------------------------------------------------------
    def _ferramentas_schemas(self):
        """Retorna schemas das ferramentas disponiveis para este agente."""
        if not self.tool_executor:
            return None
        return self.tool_executor.get_schemas_filtered(
            allowed=self.tools_allowed,
            forbidden=self.tools_forbidden,
        )

    def handle(self, task: Task, context: AgentContext) -> AgentResult:
        model_name = self._model_name()
        logger.info("=== [AGENT '%s'] Executando (modelo: %s): '%s' ===",
                    self.name, model_name, task.instruction[:120])

        system = self._montar_system(context)
        mensagens: list[dict] = [{"role": "system", "content": system}]
        mensagens.extend(context.conversation)
        mensagens.append({"role": "user", "content": task.instruction})

        n_historico = len(context.conversation)
        has_tools = self.tool_executor is not None
        ferr_schemas = self._ferramentas_schemas()
        logger.info("=== [AGENT '%s'] Prompt: %d msgs, system=%d chars, historico=%d msgs, tools=%s ===",
                    self.name, len(mensagens), len(system), n_historico,
                    len(ferr_schemas) if ferr_schemas else 0)

        t_total = time.perf_counter()

        try:
            for turno in range(_MAX_TOOL_ITERATIONS):
                t0 = time.perf_counter()
                tools = ferr_schemas if has_tools else None
                resposta = self.llm.chat(mensagens, tools=tools)
                elapsed_ms = (time.perf_counter() - t0) * 1000

                if not resposta.tool_calls:
                    saida = (resposta.content or "").strip()
                    logger.info("=== [AGENT '%s'] Resposta final no turno %d (%.0fms, %d chars): '%s' ===",
                                self.name, turno + 1, elapsed_ms, len(saida), saida[:200])
                    total_ms = (time.perf_counter() - t_total) * 1000
                    logger.info("=== [AGENT '%s'] Tempo total com tools: %.0fms ===", self.name, total_ms)
                    return AgentResult(agent=self.name, output=saida or "(sem resposta)")

                for tc in resposta.tool_calls:
                    logger.info("=== [AGENT '%s'] Tool call turno %d: '%s' args=%s ===",
                                self.name, turno + 1, tc.name, tc.arguments)

                    t_tool = time.perf_counter()
                    resultado = self.tool_executor.execute(tc.name, **(tc.arguments or {}))
                    tool_ms = (time.perf_counter() - t_tool) * 1000

                    logger.info("=== [AGENT '%s'] Tool '%s' concluida em %.0fms ===",
                                self.name, tc.name, tool_ms)

                    mensagens.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{"id": tc.name, "type": "function",
                                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}],
                    })
                    mensagens.append({
                        "role": "tool",
                        "tool_call_id": tc.name,
                        "content": resultado,
                    })

            logger.warning("=== [AGENT '%s'] Limite de %d turnos de ferramentas atingido ===",
                           self.name, _MAX_TOOL_ITERATIONS)
            return AgentResult(
                agent=self.name,
                output="(limite de uso de ferramentas atingido. Tente dividir em partes menores.)",
            )

        except Exception as exc:
            logger.exception("=== [AGENT '%s'] Provider FALHOU ===", self.name)
            return AgentResult(agent=self.name,
                               output=f"(o agente {self.name} nao conseguiu responder: {exc})",
                               success=False)
