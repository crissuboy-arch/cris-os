from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UserContext:
    user_id: str
    active_agent: str | None = None
    last_agent: str | None = None
    conversation_history: list[dict] = field(default_factory=list)
    last_activity: float = 0.0
    topics: list[str] = field(default_factory=list)


@dataclass
class Interpretation:
    intent: str
    confidence: float
    agent_hint: str | None = None
    keywords: list[str] = field(default_factory=list)
    is_command: bool = False
    is_followup: bool = False


_FOLLOWUP_WORDS = {
    "sim", "nao", "ok", "isso", "beleza", "pode ser", "continua",
    "continue", "mais", "detalhe", "explique", "elabore", "quero",
    "gostei", "nao gostei", "faz", "faca", "esse", "aquilo",
}

_FOLLOWUP_THRESHOLD = 5

_AGENT_KEYWORDS: dict[str, list[str]] = {
    "marketing": [
        "campanha", "marketing", "branding", "anuncio", "anuncios",
        "divulgacao", "midia", "google ads", "facebook ads", "tiktok ads",
        "funil", "conversao", "publicidade", "posicionamento",
    ],
    "social_media": [
        "post", "legenda", "instagram", "facebook", "tiktok", "linkedin",
        "hashtag", "stories", "reels", "feed", "rede social", "redes sociais",
        "conteudo", "calendario editorial",
    ],
    "vendas": [
        "proposta", "orcamento", "pitch", "negociacao", "prospeccao",
        "comercial", "argumentario", "venda", "vendas", "fechar",
        "preco", "desconto", "cliente",
    ],
    "atendimento": [
        "atendimento", "suporte", "reclamacao", "cancelamento",
        "troca", "devolucao", "cliente insatisfeito", "problema com",
        "duvida",
    ],
    "programador": [
        "codigo", "programa", "script", "automacao", "api", "funcao",
        "bug", "erro", "terminal", "bash", "powershell", "backend",
        "frontend", "github", "git", "python", "javascript", "html",
        "css", "banco de dados", "sql",
    ],
    "pesquisador": [
        "analise", "pesquisa", "concorrente", "concorrentes",
        "fornecedor", "mercado", "tendencia", "comparar", "comparacao",
        "preco", "relatorio", "dados", "estatistica",
    ],
    "copywriter": [
        "copy", "conversao", "headline", "landing", "pagina de venda",
        "email marketing", "texto persuasivo", "copywriting", "aida",
    ],
    "produtividade": [
        "rotina", "agenda", "planejar", "produtividade", "tarefas",
        "prioridade", "checklist", "pomodoro", "organizar", "prazo",
        "deadline", "reuniao",
    ],
}


class NaturalLanguageInterpreter:
    def interpret(self, text: str, context: UserContext | None = None) -> Interpretation:
        text = text.strip()
        if not text:
            return Interpretation(intent="empty", confidence=0.0)

        if text.startswith("/"):
            return Interpretation(intent="command", confidence=1.0, is_command=True)

        if context and self._is_followup(text, context):
            return Interpretation(
                intent="followup",
                confidence=0.8,
                is_followup=True,
                agent_hint=context.last_agent,
            )

        # Check for agent keywords FIRST
        keywords_found: dict[str, list[str]] = {}
        for agent, kws in _AGENT_KEYWORDS.items():
            found = [kw for kw in kws if re.search(rf"\b{re.escape(kw)}\b", text.lower())]
            if found:
                keywords_found[agent] = found

        if keywords_found:
            best_agent = max(keywords_found, key=lambda a: len(keywords_found[a]))
            all_keywords = []
            for kws in keywords_found.values():
                all_keywords.extend(kws)
            confidence = min(0.95, 0.5 + 0.1 * len(keywords_found[best_agent]))
            return Interpretation(
                intent="agent_request",
                confidence=confidence,
                agent_hint=best_agent,
                keywords=all_keywords,
            )

        # Only check question patterns if NO agent keywords found
        question_patterns = [
            r"^(como|quando|onde|por que|por qual|quantos?|qual)",
            r"(pode|consegue|sabe|ajuda|help)",
            r"(preciso|necessito|quero|gostaria)",
            r"(explique|explica|me diga|conte)",
        ]
        for pattern in question_patterns:
            if re.search(pattern, text.lower()):
                return Interpretation(
                    intent="general_question",
                    confidence=0.4,
                    keywords=[],
                )

        return Interpretation(intent="general", confidence=0.3)

    def _is_followup(self, text: str, context: UserContext) -> bool:
        if not context.last_agent:
            return False
        elapsed = time.time() - context.last_activity
        if elapsed > 300:
            return False
        words = text.strip().lower().split()
        if len(words) > _FOLLOWUP_THRESHOLD:
            return False
        return words[0] in _FOLLOWUP_WORDS if words else False


class AgentSelector:
    def __init__(self, agents: dict[str, Any], general_agent: Any | None = None):
        self._agents = agents
        self._general = general_agent

    def select(
        self,
        interpretation: Interpretation,
        context: UserContext | None = None,
    ) -> Any | None:
        if interpretation.is_followup and context and context.last_agent:
            agent = self._agents.get(context.last_agent)
            if agent:
                return agent

        if interpretation.agent_hint:
            agent = self._agents.get(interpretation.agent_hint)
            if agent:
                return agent

        if context and context.active_agent:
            agent = self._agents.get(context.active_agent)
            if agent:
                return agent

        return self._general

    def list_agents(self) -> list[str]:
        return sorted(self._agents.keys())


class UserContextManager:
    def __init__(self, max_history: int = 50):
        self._contexts: dict[str, UserContext] = {}
        self._max_history = max_history

    def get(self, user_id: str) -> UserContext:
        if user_id not in self._contexts:
            self._contexts[user_id] = UserContext(user_id=user_id)
        return self._contexts[user_id]

    def update_activity(self, user_id: str, agent_name: str | None = None) -> UserContext:
        ctx = self.get(user_id)
        ctx.last_activity = time.time()
        if agent_name:
            ctx.last_agent = agent_name
        return ctx

    def add_to_history(self, user_id: str, role: str, content: str, agent: str = "") -> None:
        ctx = self.get(user_id)
        entry = {
            "role": role,
            "content": content,
            "agent": agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        ctx.conversation_history.append(entry)
        if len(ctx.conversation_history) > self._max_history:
            ctx.conversation_history = ctx.conversation_history[-self._max_history:]

    def get_history(self, user_id: str, limit: int = 10) -> list[dict]:
        ctx = self.get(user_id)
        return ctx.conversation_history[-limit:]

    def set_active_agent(self, user_id: str, agent_name: str | None) -> None:
        ctx = self.get(user_id)
        ctx.active_agent = agent_name

    def get_active_agent(self, user_id: str) -> str | None:
        return self.get(user_id).active_agent

    def clear_history(self, user_id: str) -> None:
        ctx = self.get(user_id)
        ctx.conversation_history.clear()
        ctx.topics.clear()


class ConversationManager:
    def __init__(
        self,
        agents: dict[str, Any],
        general_agent: Any | None = None,
        max_history: int = 50,
    ):
        self.interpreter = NaturalLanguageInterpreter()
        self.selector = AgentSelector(agents, general_agent)
        self.context_manager = UserContextManager(max_history)
        self._agents = agents
        self._general = general_agent

    def handle_message(self, user_id: str, text: str) -> tuple[str, str | None]:
        context = self.context_manager.get(user_id)
        interpretation = self.interpreter.interpret(text, context)

        if interpretation.is_followup and context.last_agent:
            agent = self._agents.get(context.last_agent)
            if agent:
                self.context_manager.update_activity(user_id, agent.name)
                self.context_manager.add_to_history(user_id, "user", text, agent.name)
                response = agent.generate(text)
                self.context_manager.add_to_history(user_id, "assistant", response, agent.name)
                return response, agent.name

        agent = self.selector.select(interpretation, context)
        if not agent:
            return (
                "Nao encontrei um agente adequado para essa tarefa. "
                "Use /agents para ver os agentes disponiveis.",
                None,
            )

        self.context_manager.update_activity(user_id, agent.name)
        self.context_manager.add_to_history(user_id, "user", text, agent.name)
        response = agent.generate(text)
        self.context_manager.add_to_history(user_id, "assistant", response, agent.name)
        return response, agent.name

    def format_response(self, response: str, agent_name: str | None) -> str:
        if not agent_name:
            return response
        agent_display = agent_name.replace("_", " ").title()
        return f"[{agent_display}] {response}"

    def set_active_agent(self, user_id: str, agent_name: str | None) -> str:
        self.context_manager.set_active_agent(user_id, agent_name)
        if agent_name is None:
            return "Modo automatico ativado. Vou escolher o melhor agente para cada mensagem."
        agent = self._agents.get(agent_name)
        if agent:
            return f"Agente fixado: {agent.name}\n{agent.description}"
        return f"Agente '{agent_name}' nao encontrado."

    def get_status(self, user_id: str) -> dict:
        ctx = self.context_manager.get(user_id)
        return {
            "active_agent": ctx.active_agent,
            "last_agent": ctx.last_agent,
            "history_size": len(ctx.conversation_history),
            "available_agents": self.selector.list_agents(),
        }