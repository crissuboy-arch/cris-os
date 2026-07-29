"""
SpecialistAgent — agente especialista do novo sistema de orquestracao.

Cada agente sabe gerar respostas no seu dominio usando o LLM local
ou ferramentas especializadas.

Separacao:
  - PROMPTS em agents/prompts.py
  - FERRAMENTAS em tools/*.py
  - LOGICA aqui (SpecialistAgent)

Memoria:
  Opcionalmente aceita um MemoryManager para consultar historico
  antes de responder e salvar conversas automaticamente.
"""

from __future__ import annotations

import logging
import time

from core.contracts.llm import LLMResponse
from tools.base import Tool

logger = logging.getLogger(__name__)


class SpecialistAgent:
    """
    Agente especialista que gera respostas usando LLM ou ferramentas.

    Fluxo:
      1. Se tem MemoryManager, carrega contexto do historico
      2. Tenta encontrar uma ferramenta que corresponda a mensagem
      3. Se encontra, executa a ferramenta e retorna o resultado
      4. Se nao encontra, usa o LLM como fallback
      5. Se tem MemoryManager, salva a conversa

    Atributos:
        name: identificador unico
        description: descricao curta para o roteador
        system_prompt: prompt especializado
        llm: provedor LLM
        tools: lista de Tool
        memory: MemoryManager opcional
        usuario_id: ID do usuario atual (para memoria)
    """

    def __init__(
        self,
        name: str,
        description: str,
        system_prompt: str,
        llm: object,
        tools: list[Tool] | None = None,
        memory: object | None = None,
        usuario_id: str = "",
    ) -> None:
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.llm = llm
        self.tools = tools or []
        self.memory = memory
        self.usuario_id = usuario_id

    def generate(self, message: str) -> str:
        """
        Gera uma resposta para a mensagem do usuario.

        Tenta ferramentas primeiro; se nenhuma corresponde, usa LLM.
        Se MemoryManager configurado, salva a conversa automaticamente.
        """
        logger.info(
            "=== [SPECIALIST '%s'] Processando: '%s' ===",
            self.name, message[:120],
        )

        # Salva mensagem do usuario na memoria
        if self.memory and self.usuario_id:
            self.memory.salvar_conversa(self.usuario_id, "user", message, self.name)

        # 1) Tentar ferramenta
        ferramenta = self._encontrar_ferramenta(message)
        if ferramenta:
            t0 = time.perf_counter()
            resultado = ferramenta.execute(message)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info(
                "=== [SPECIALIST '%s'] Ferramenta usada: '%s' "
                "(tamanho: %d caracteres, tempo: %.0fms) ===",
                self.name, ferramenta.name, len(resultado), elapsed,
            )
            # Salva resposta na memoria
            if self.memory and self.usuario_id:
                self.memory.salvar_conversa(self.usuario_id, "assistant", resultado, self.name)
            return resultado

        # 2) Fallback: LLM
        logger.info(
            "=== [SPECIALIST '%s'] Nenhuma ferramenta, usando LLM ===",
            self.name,
        )
        resultado = self._gerar_com_llm(message)

        # Salva resposta na memoria
        if self.memory and self.usuario_id:
            self.memory.salvar_conversa(self.usuario_id, "assistant", resultado, self.name)

        return resultado

    def _encontrar_ferramenta(self, message: str) -> Tool | None:
        """Retorna a primeira ferramenta cujas keywords correspondem a mensagem."""
        for tool in self.tools:
            if tool.matches(message):
                logger.info(
                    "=== [SPECIALIST '%s'] Ferramenta encontrada: '%s' ===",
                    self.name, tool.name,
                )
                return tool
        return None

    def _gerar_com_llm(self, message: str) -> str:
        """Gera resposta usando o LLM, com contexto opcional da memoria."""
        mensagens: list[dict] = [
            {"role": "system", "content": self.system_prompt},
        ]

        # Injeta contexto das ultimas conversas se houver memoria
        if self.memory and self.usuario_id:
            contexto = self.memory.contexto_recente(self.usuario_id, limite=5)
            if contexto:
                mensagens.append({
                    "role": "system",
                    "content": f"Contexto recente da conversa:\n{contexto}",
                })

        mensagens.append({"role": "user", "content": message})

        try:
            resposta: LLMResponse = self.llm.chat(mensagens)
            texto = (resposta.content or "").strip()
            if not texto:
                return f"Nao consegui gerar uma resposta como {self.name}."
            return texto
        except Exception as exc:
            logger.exception("=== [SPECIALIST '%s'] ERRO ===", self.name)
            return (
                f"O agente {self.name} encontrou um erro ao processar sua mensagem: "
                f"{exc}. Tente novamente ou escolha outro agente com /use."
            )

    def __repr__(self) -> str:
        return f"<SpecialistAgent '{self.name}' ({len(self.tools)} ferramentas)>"


def create_agent(
    name: str,
    description: str,
    system_prompt: str,
    llm: object,
    tools: list[Tool] | None = None,
    memory: object | None = None,
    usuario_id: str = "",
) -> SpecialistAgent:
    """Cria um agente especialista configurado."""
    return SpecialistAgent(
        name=name,
        description=description,
        system_prompt=system_prompt,
        llm=llm,
        tools=tools,
        memory=memory,
        usuario_id=usuario_id,
    )
