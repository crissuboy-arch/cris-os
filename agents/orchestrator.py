"""
AgentOrchestrator — orquestrador inteligente do CRIS OS.

Analisa a mensagem do usuario e roteia para o agente especialista correto.
Mantem estado por usuario (agente ativo e ultimo agente usado).

Fluxo:
  1. Se usuario tem agente definido via /use, usa diretamente
  2. Se a mensagem e curta e o usuario tem ultimo agente, reusa
  3. Senao, usa o LLM para classificar e rotear para o melhor agente
  4. Se nenhum agente foi encontrado, usa o agente geral como fallback
"""

from __future__ import annotations

import logging
import re
import time

from agents.base_specialist import SpecialistAgent
from agents.prompts import ROUTING_PROMPT
from core.models import IncomingMessage

logger = logging.getLogger(__name__)

# Palavras que indicam continuacao (msg curta sem contexto proprio)
_FOLLOWUP_WORDS = {
    "continua", "continue", "sim", "nao", "ok", "isso", "esse",
    "aquilo", "sim,", "nao,", "ok,", "beleza", "pode ser",
    "faz", "faca", "quero", "gostei", "nao gostei",
    "explique", "elabore", "mais", "detalhe",
}

_FOLLOWUP_THRESHOLD = 5


def _model_name(llm: object) -> str:
    """Extrai o nome do modelo do provedor LLM."""
    return (
        getattr(llm, "_provider_name", None)
        or getattr(llm, "model", None)
        or "desconhecido"
    )


class AgentOrchestrator:
    """
    Orquestrador que roteia mensagens para o agente especialista adequado.

    Attributes:
        agents: dict de {nome: SpecialistAgent}
        llm: provedor LLM usado para roteamento
        general_agent: agente generico usado como fallback final
        active_agents: {user_id: agent_name} — definido via /use
        last_agents: {user_id: agent_name} — ultimo usado (auto)
    """

    def __init__(
        self,
        llm: object,
        agents: list[SpecialistAgent],
        general_agent: SpecialistAgent | None = None,
    ) -> None:
        self.llm = llm
        self.agents: dict[str, SpecialistAgent] = {a.name: a for a in agents}
        self.general_agent = general_agent
        self.active_agents: dict[str, str | None] = {}
        self.last_agents: dict[str, str] = {}

    # ------------------------------------------------------------------
    #  API publica
    # ------------------------------------------------------------------

    def handle(self, incoming: IncomingMessage) -> str:
        """Recebe uma mensagem e retorna a resposta do agente escolhido."""
        user_id = incoming.sender_id
        texto = (incoming.text or "").strip()
        t0 = time.perf_counter()
        modelo = _model_name(self.llm)

        if not texto:
            return ""

        agent = self._escolher_agente(user_id, texto)
        elapsed = (time.perf_counter() - t0) * 1000

        if not agent:
            logger.info(
                "=== [ORCHESTRATOR] Mensagem recebida: '%s' | "
                "Agente escolhido: NENHUM | "
                "Tempo: %.0fms | "
                "Modelo: %s ===",
                texto[:120], elapsed, modelo,
            )
            if self.general_agent:
                logger.info(
                    "=== [ORCHESTRATOR] Usando agente geral como fallback ===",
                )
                return self.general_agent.generate(texto)
            return (
                "Nao encontrei um agente adequado para essa tarefa. "
                "Use /agents para ver os agentes disponiveis ou /use <nome> para escolher um."
            )

        self.last_agents[user_id] = agent.name
        resposta = agent.generate(texto)
        elapsed_total = (time.perf_counter() - t0) * 1000

        logger.info(
            "=== [ORCHESTRATOR] Mensagem recebida: '%s' | "
            "Agente escolhido: %s | "
            "Tempo: %.0fms | "
            "Modelo: %s ===",
            texto[:120], agent.name, elapsed_total, modelo,
        )

        return resposta

    def set_active_agent(self, user_id: str, agent_name: str | None) -> str:
        """Define o agente ativo para um usuario. Retorna mensagem de confirmacao."""
        if agent_name is None:
            self.active_agents.pop(user_id, None)
            return "Modo automatico ativado. O orquestrador escolhera o melhor agente para cada mensagem."

        agent_name = self._normalizar_nome(agent_name)
        if agent_name not in self.agents:
            disponiveis = ", ".join(sorted(self.agents))
            return (
                f"Agente '{agent_name}' nao encontrado. "
                f"Disponiveis: {disponiveis}"
            )

        self.active_agents[user_id] = agent_name
        agent = self.agents[agent_name]
        logger.info(
            "=== [ORCHESTRATOR] Usuario '%s' fixou agente '%s' ===",
            user_id, agent_name,
        )
        return (
            f"Agente ativo: {agent.name}\n"
            f"{agent.description}\n\n"
            f"Suas mensagens agora serao enviadas diretamente para este agente. "
            f"Use /use auto para voltar ao modo automatico."
        )

    def get_active_agent(self, user_id: str) -> str:
        """Retorna o nome do agente ativo para o usuario."""
        nome = self.active_agents.get(user_id)
        if nome and nome in self.agents:
            return nome
        return "auto"

    def list_agents(self) -> str:
        """Lista todos os agentes disponiveis como texto formatado."""
        linhas = ["Agentes Especialistas do CRIS OS", "=" * 34, ""]

        for nome in sorted(self.agents):
            agent = self.agents[nome]
            linhas.append(f"  {nome}")
            linhas.append(f"       {agent.description}")

        if self.general_agent:
            linhas.append(f"  geral")
            linhas.append(f"       {self.general_agent.description}")

        linhas.append("")
        linhas.append("-" * 34)
        linhas.append("Use /use <nome> para ativar um agente manualmente.")
        linhas.append("Use /use auto para voltar ao modo automatico.")
        return "\n".join(linhas)

    # ------------------------------------------------------------------
    #  Metodos internos
    # ------------------------------------------------------------------

    def _escolher_agente(self, user_id: str, texto: str) -> SpecialistAgent | None:
        """Escolhe o agente com base no estado do usuario e na mensagem."""
        # 1) Se usuario tem agente fixo definido via /use
        ativo = self.active_agents.get(user_id)
        if ativo and ativo in self.agents:
            return self.agents[ativo]

        # 2) Se a mensagem parece continuacao e ja temos um ultimo agente
        if self._eh_followup(texto):
            ultimo = self.last_agents.get(user_id)
            if ultimo and ultimo in self.agents:
                logger.info(
                    "=== [ORCHESTRATOR] Followup detectado, reusando agente '%s' ===",
                    ultimo,
                )
                return self.agents[ultimo]

        # 3) Roteamento via LLM + keyword fallback
        nome_agente = self._rotear(texto)
        if nome_agente and nome_agente in self.agents:
            return self.agents[nome_agente]

        return None

    @staticmethod
    def _eh_followup(texto: str) -> bool:
        """Detecta se a mensagem parece ser continuacao sem contexto proprio."""
        palavras = texto.strip().lower().split()
        if len(palavras) > _FOLLOWUP_THRESHOLD:
            return False
        if not palavras:
            return False
        return palavras[0] in _FOLLOWUP_WORDS

    def _rotear(self, mensagem: str) -> str | None:
        """Usa o LLM para classificar a mensagem no melhor agente."""
        messages = [{"role": "system", "content": "Classifique a mensagem."},
                    {"role": "user", "content": mensagem}]

        try:
            resposta = self.llm.chat(messages)
            nome = self._extrair_agente(resposta.content or "")
            if nome and nome in self.agents:
                logger.info(
                    "=== [ORCHESTRATOR] Roteamento LLM: '%s' -> '%s' ===",
                    mensagem[:60], nome,
                )
                return nome
            logger.warning(
                "=== [ORCHESTRATOR] Roteamento LLM devolveu '%s' (invalido) ===",
                resposta.content[:60] if resposta.content else "(vazio)",
            )
        except Exception as exc:
            logger.warning("=== [ORCHESTRATOR] Erro no roteamento LLM: %s ===", exc)

        return self._rotear_por_keyword(mensagem)

    @staticmethod
    def _extrair_agente(texto: str) -> str | None:
        """Extrai o nome do agente da resposta do LLM."""
        texto = texto.strip().lower().split("\n")[0].split(",")[0].strip()
        texto = re.sub(r'[^a-z0-9_]', '', texto)
        return texto if texto else None

    @staticmethod
    def _rotear_por_keyword(mensagem: str) -> str | None:
        """Fallback: roteamento por palavra-chave (palavra inteira)."""
        palavras = set(mensagem.lower().split())

        regras: list[tuple[list[str], str]] = [
            (["legenda", "post", "instagram", "facebook", "tiktok", "linkedin",
              "hashtag", "stories", "reels", "feed"], "social_media"),
            (["codigo", "programa", "script", "automacao", "api", "funcao",
              "bug", "erro", "terminal", "bash", "powershell", "backend",
              "frontend", "github", "git"], "programador"),
            (["proposta", "orcamento", "pitch", "negociacao",
              "prospeccao", "comercial", "argumentario"], "vendas"),
            (["atendimento", "suporte", "reclamacao", "cancelamento",
              "troca", "devolucao"], "atendimento"),
            (["analise", "pesquisa", "concorrente", "concorrentes",
              "fornecedor", "mercado", "tendencia",
              "comparar", "comparacao", "preco"], "pesquisador"),
            (["copy", "conversao", "headline", "landing"], "copywriter"),
            (["campanha", "branding", "divulgacao", "midia"], "marketing"),
            (["rotina", "agenda", "planejar", "produtividade",
              "tarefas", "prioridade", "checklist", "pomodoro"], "produtividade"),
        ]

        multi: list[tuple[str, str]] = [
            ("rede social", "social_media"),
            ("pagina de venda", "copywriter"),
            ("landing page", "copywriter"),
            ("email marketing", "copywriter"),
            ("google ads", "marketing"),
            ("facebook ads", "marketing"),
            ("problema com", "atendimento"),
        ]

        for keywords, agent_name in regras:
            for kw in keywords:
                if kw in palavras:
                    logger.info(
                        "=== [ORCHESTRATOR] Keyword fallback: '%s' -> '%s' ===",
                        kw, agent_name,
                    )
                    return agent_name

        for frase, agent_name in multi:
            if frase in mensagem.lower():
                logger.info(
                    "=== [ORCHESTRATOR] Multi-palavra fallback: '%s' -> '%s' ===",
                    frase, agent_name,
                )
                return agent_name

        return None

    @staticmethod
    def _normalizar_nome(nome: str) -> str:
        """Normaliza nome de agente (alias)."""
        aliases = {
            "social": "social_media",
            "midia": "social_media",
            "redes": "social_media",
            "redes sociais": "social_media",
            "prog": "programador",
            "dev": "programador",
            "pesq": "pesquisador",
            "copy": "copywriter",
            "cx": "atendimento",
            "suporte": "atendimento",
            "vendedor": "vendas",
            "comercial": "vendas",
        }
        n = nome.strip().lower().replace("-", "_")
        return aliases.get(n, n)
