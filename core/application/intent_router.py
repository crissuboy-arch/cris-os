"""
IntentRouter — identifica a intenção e decide quem trabalha (roteamento hierárquico).

Responsabilidade única: dado o pedido da Cris, produzir um PLANO = lista de
`ExecutionStep` (name + type + instrução/payload).

Fast paths (sem chamar o LLM):
  - Saudações simples → secretária
  - Respostas sim/não/continuação → mantém tarefa atual
  - Comandos explícitos com agente/skill nos keywords → roteia direto
  - Etapa única combina domínios + agentes + skills: se o modelo escolher um
    agente direto, a 2ª chamada é pulada.

Degradação graciosa: fallback por keyword de skill → keyword de agente → default.
"""

from __future__ import annotations

import logging
import re

from core.application.timer import StageTimer
from core.domain.execution import ExecutionType
from core.models import ExecutionStep

logger = logging.getLogger(__name__)

_DEFAULT_SKILL_SCHEMA = {
    "type": "object",
    "properties": {
        "instruction": {"type": "string", "description": "Instrução clara e acionável."}
    },
    "required": ["instruction"],
}

_SAUDACOES = re.compile(
    r"^(oi|ol[áa]|bom dia|boa tarde|boa noite|tudo bem|opa|e a[íi]|"
    r"hey|h[ei]|hello|bem[ -]vindo|fala[ a]|iae|beleza|show|"
    r"teste?|testando?|funcionou|s[óo] teste)$",
    re.IGNORECASE,
)

_SIM = re.compile(r"^(sim|pode[ ](ser|fazer)|ok|beleza|pode ir|manda|"
                  r"vai em frente|confirmo|confirmado|claro|com certeza)$", re.IGNORECASE)

_NAO = re.compile(r"^(n[ãa]o|nada|nao|par[aá]|cancela|cancele|"
                  r"deixa|deixa quieto|depois|hora|n[ãa]o quero)$", re.IGNORECASE)

# Compostos: tarefas que mencionam lancamento/venda/criacao de produto + mercado
# Disparam o modo multi-agente (vários especialistas em paralelo).
_COMPOSTO = re.compile(
    r"(quero vender|vender|lancar|lançar|criar|desenvolver|"
    r"preciso de ajuda para|ajuda com o lancamento|"
    r"crie um|monte um|prepare um|faca um plano|faca uma estrategia|"
    r"quero comecar|vou comecar|abrir um negocio|"
    r"me ajude a lancar|me ajuda a lancar)",
    re.IGNORECASE,
)

_MULTI_AGENT_PROMPT = (
    "Voce e o coordenador de equipe do CRIS OS. A Cris fez um pedido que exige "
    "a colaboracao de VARIOS especialistas.\n\n"
    "Selecione OS ESPECIALISTAS necessarios, UM POR tool_call. Para cada um, "
    "especifique uma instrucao clara e acionavel sobre o que ele deve fazer.\n\n"
    "Boas praticas:\n"
    "- pesquisador: pesquisa de mercado, concorrentes, tendencias\n"
    "- social-media: estrategia de marketing, conteudo, redes sociais\n"
    "- financeiro: viabilidade financeira, precificacao, custos\n"
    "- atendimento: abordagem comercial, atendimento ao cliente\n"
    "- programador: desenvolvimento de software, scripts, automacao\n"
    "- mkvideos: producao de video, roteiro, thumbnail\n"
    "- scalaflow: estrategia de produto, validacao de nicho\n"
    "- curriculo: criacao de curriculo e carta de apresentacao\n"
    "- pesquisador: pesquisa de mercado e concorrentes\n"
    "- pinklogic: estrategia para produtos SaaS\n"
    "- vitrinepro: divulgacao de negocio local\n"
    "- zavix: produtos zavix\n\n"
    "IMPORTANTE: selecione APENAS os especialistas realmente necessarios. "
    "Nao invente agentes. Use no minimo 2, no maximo 5."
)


class IntentRouter:
    def __init__(self, llm, registry, fallback_router=None, fallback_agent: str = "secretary",
                 skills=None, routing_ctx: int = 3) -> None:
        self.llm = llm
        self.registry = registry
        self.fallback_router = fallback_router
        self.fallback_agent = fallback_agent
        self.skills = skills
        self.routing_ctx = routing_ctx

    # ------------------------------------------------------------------
    # Fast paths
    # ------------------------------------------------------------------
    def _is_saudacao(self, text: str) -> bool:
        return bool(_SAUDACOES.match(text.strip().lower()))

    def _is_sim(self, text: str) -> bool:
        return bool(_SIM.match(text.strip().lower()))

    def _is_nao(self, text: str) -> bool:
        return bool(_NAO.match(text.strip().lower()))

    def _agent_keyword_match(self, text: str):
        """Busca agente cujo keyword casa exatamente com o texto (fallback determinístico)."""
        t = (text or "").lower()
        for a in self.registry.all():
            for k in (getattr(a, "keywords", None) or []):
                if k.lower() in t:
                    logger.info("=== [INTENT_ROUTER] KEYWORD AGENTE '%s' c/ keyword '%s' (dominio='%s') ===",
                                a.name, k, a.domain)
                    return a
        return None

    def _skill_keyword_match(self, text: str):
        t = (text or "").lower()
        for s in self._enabled_skills():
            for k in (getattr(s, "keywords", None) or []):
                if k.lower() in t:
                    logger.info("=== [INTENT_ROUTER] KEYWORD SKILL '%s' c/ keyword '%s' (dominio='%s') ===",
                                s.name, k, getattr(s, "domain", ""))
                    return s
        return None

    # ------------------------------------------------------------------
    # Catálogo
    # ------------------------------------------------------------------
    def _domains(self) -> dict[str, list]:
        dom: dict[str, list] = {}
        for a in self.registry.all():
            d = getattr(a, "domain", "")
            if d:
                dom.setdefault(d, []).append(a)
        return dom

    def _skill_domains(self) -> dict[str, list]:
        dom: dict[str, list] = {}
        for s in self._enabled_skills():
            d = getattr(s, "domain", "")
            if d:
                dom.setdefault(d, []).append(s)
        return dom

    def _enabled_skills(self) -> list:
        return self.skills.enabled() if self.skills else []

    def _skill_by_name(self, nome: str):
        return next((s for s in self._enabled_skills() if s.name == nome), None)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------
    def _domain_tools(self, dominios) -> list[dict]:
        return [
            {"type": "function",
             "function": {"name": d, "description": f"Domínio: {d}",
                          "parameters": {"type": "object", "properties": {}, "required": []}}}
            for d in dominios
        ]

    def _agent_tools(self, agentes) -> list[dict]:
        return [
            {"type": "function",
             "function": {"name": a.name, "description": a.description,
                          "parameters": {"type": "object",
                                         "properties": {"instruction": {
                                             "type": "string",
                                             "description": "Instrução clara, específica e acionável."}},
                                         "required": ["instruction"]}}}
            for a in agentes
        ]

    def _skill_tools(self, skills) -> list[dict]:
        return [
            {"type": "function",
             "function": {"name": s.name, "description": s.description,
                          "parameters": getattr(s, "input_schema", None) or _DEFAULT_SKILL_SCHEMA}}
            for s in skills
        ]

    def _all_tools(self, dominios, agentes, skills) -> list[dict]:
        return self._domain_tools(dominios) + self._agent_tools(agentes) + self._skill_tools(skills)

    # ------------------------------------------------------------------
    # Multi-agente (tarefas compostas)
    # ------------------------------------------------------------------
    def _is_compound(self, text: str) -> bool:
        """Detecta se o pedido exige múltiplos especialistas."""
        return bool(_COMPOSTO.search(text.strip().lower()))

    def _plan_compound(self, text: str, conversation: list[dict]) -> list[ExecutionStep]:
        """Planeia tarefa composta: LLM escolhe vários agentes."""
        logger.info("=== [INTENT_ROUTER] Tarefa composta detectada: '%s' ===", text[:100])

        todos_agentes = self.registry.all()
        tools = self._agent_tools(todos_agentes)

        ctx_limit = min(len(conversation), self.routing_ctx)
        base = [{"role": "system", "content": _MULTI_AGENT_PROMPT}]
        base.extend(conversation[-ctx_limit:] if ctx_limit > 0 else [])
        base.append({"role": "user", "content": text})

        tool_calls = self._lista(base, tools)
        if not tool_calls:
            logger.info("=== [INTENT_ROUTER] COMPOUND: LLM nao selecionou agentes, fallback ===")
            return self._fallback(text)

        nomes_validos = {a.name for a in todos_agentes}
        plano: list[ExecutionStep] = []
        for tc in tool_calls:
            if tc.name in nomes_validos:
                instrucao = (tc.arguments or {}).get("instruction") or text
                plano.append(ExecutionStep(
                    name=tc.name, type=ExecutionType.AGENT, instruction=instrucao,
                ))
                logger.info("=== [INTENT_ROUTER] COMPOUND: agente '%s' incluido no plano ===", tc.name)
            else:
                logger.warning("=== [INTENT_ROUTER] COMPOUND: agente '%s' nao encontrado, ignorado ===", tc.name)

        if not plano:
            logger.info("=== [INTENT_ROUTER] COMPOUND: nenhum agente valido, fallback ===")
            return self._fallback(text)

        passos_str = "; ".join(f"{p.name}({p.type.value})" for p in plano)
        logger.info("=== [INTENT_ROUTER] COMPOUND: plano com %d passo(s): %s ===",
                    len(plano), passos_str)
        return plano

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------
    def _agent_step(self, nome: str, args: dict | None, text: str) -> ExecutionStep:
        instrucao = (args or {}).get("instruction") or text
        return ExecutionStep(name=nome, type=ExecutionType.AGENT, instruction=instrucao)

    def _skill_step(self, nome: str, args: dict | None) -> ExecutionStep:
        return ExecutionStep(name=nome, type=ExecutionType.SKILL, payload=dict(args or {}))

    # ------------------------------------------------------------------
    def plan(self, text: str, conversation: list[dict], planner_prompt: str) -> list[ExecutionStep]:
        t = StageTimer()

        # --- Fast path 1: saudações → secretary sem LLM.
        t.begin("fast_path")
        if self._is_saudacao(text):
            logger.info("=== [INTENT_ROUTER] FAST PATH: saudacao -> secretary ===")
            t.end("fast_path")
            return [ExecutionStep(
                name=self.fallback_agent, type=ExecutionType.AGENT,
                instruction="Continue a conversa naturalmente com a Cris.",
            )]

        # --- Fast path 2: sim/não com contexto → continua tarefa atual.
        if self._is_sim(text) and len(conversation) > 1:
            logger.info("=== [INTENT_ROUTER] FAST PATH: sim/confirmacao -> secretary ===")
            t.end("fast_path")
            return [ExecutionStep(
                name=self.fallback_agent, type=ExecutionType.AGENT,
                instruction=f"A Cris respondeu: '{text}'. Continue a tarefa em andamento.",
            )]

        if self._is_nao(text) and len(conversation) > 1:
            logger.info("=== [INTENT_ROUTER] FAST PATH: nao/cancelamento -> secretary ===")
            t.end("fast_path")
            return [ExecutionStep(
                name=self.fallback_agent, type=ExecutionType.AGENT,
                instruction=f"A Cris respondeu: '{text}'. Reconheca e pergunte o que ela quer fazer agora.",
            )]
        t.end("fast_path")

        # --- Multi-agente: pedido composto que precisa de varios especialistas.
        #     Antes do keyword match para que frases como "lancar o ScalaFlow"
        #     ou "crie um SaaS para imobiliarias" nao sejam capturadas por
        #     keyword unico.
        if self._is_compound(text):
            return self._plan_compound(text, conversation)

        # --- Fast path 3: comando com keyword de skill ou agente → roteia direto.
        skill = self._skill_keyword_match(text)
        if skill is not None:
            logger.info("=== [INTENT_ROUTER] KEYWORD SKILL -> '%s' ===", skill.name)
            return [self._skill_step(skill.name, {})]

        agente = self._agent_keyword_match(text)
        if agente is not None:
            logger.info("=== [INTENT_ROUTER] KEYWORD AGENTE -> '%s' ===", agente.name)
            return [self._agent_step(agente.name, None, text)]

        # --- Roteamento via LLM com histórico reduzido.
        ctx_limit = min(len(conversation), self.routing_ctx)
        base = [{"role": "system", "content": planner_prompt}]
        base.extend(conversation[-ctx_limit:] if ctx_limit > 0 else [])
        base.append({"role": "user", "content": text})

        dom_agentes = self._domains()
        dom_skills = self._skill_domains()
        dominios = set(dom_agentes) | set(dom_skills)
        todos_agentes = self.registry.all()
        todas_skills = self._enabled_skills()

        # Etapa única: se o modelo escolher agente/skill direto → 1 chamada apenas.
        t.begin("1.provider_call")
        escolha = self._primeiro(base, self._all_tools(dominios, todos_agentes, todas_skills))
        t.end("1.provider_call")
        if escolha is None:
            logger.info("=== [INTENT_ROUTER] Nenhuma tool_call -> fallback ===")
            return self._fallback(text)

        nome = escolha.name

        if self.registry.get(nome) is not None:
            ag_info = self.registry.get(nome)
            logger.info("=== [INTENT_ROUTER] Agente na 1ª chamada: '%s' (dominio='%s', status='%s') ===",
                        nome, ag_info.domain, ag_info.status)
            return [self._agent_step(nome, escolha.arguments, text)]

        if self._skill_by_name(nome) is not None:
            logger.info("=== [INTENT_ROUTER] Skill na 1ª chamada: '%s' ===", nome)
            return [self._skill_step(nome, escolha.arguments)]

        # Escolheu um domínio → 2ª chamada para escolher dentro dele.
        if nome in dominios:
            candidatos_agentes = dom_agentes.get(nome, [])
            candidatos_skills = dom_skills.get(nome, [])
            nomes_agente = {a.name for a in candidatos_agentes}
            nomes_skill = {s.name for s in candidatos_skills}
            tools = self._agent_tools(candidatos_agentes) + self._skill_tools(candidatos_skills)

            plano: list[ExecutionStep] = []
            t.begin("2.provider_call")
            for tc in self._lista(base, tools):
                if tc.name in nomes_skill:
                    plano.append(self._skill_step(tc.name, tc.arguments))
                elif tc.name in nomes_agente:
                    plano.append(self._agent_step(tc.name, tc.arguments, text))
            t.end("2.provider_call")

            if plano:
                passos_str = "; ".join(
                    f"{p.name}({p.type.value})" for p in plano
                )
                logger.info("=== [INTENT_ROUTER] Dominio '%s' -> %d passo(s): %s ===",
                            nome, len(plano), passos_str)
                return plano

        return self._fallback(text)

    # ------------------------------------------------------------------
    def _primeiro(self, mensagens, tools):
        chamadas = self._lista(mensagens, tools)
        logger.info("=== [INTENT_ROUTER] LLM retornou %d tool_calls ===", len(chamadas))
        return chamadas[0] if chamadas else None

    def _lista(self, mensagens, tools):
        n_ctx = max(0, len(mensagens) - 2)
        logger.info("=== [INTENT_ROUTER] Enviando ao provider (hist=%d, tools=%d) ===",
                    n_ctx, len(tools) if tools else 0)
        try:
            resp = self.llm.chat(mensagens, tools=tools)
            logger.info("=== [INTENT_ROUTER] Provider: content='%s', tool_calls=%d ===",
                        (resp.content or "")[:120], len(resp.tool_calls))
            return resp.tool_calls
        except Exception as exc:
            logger.warning("=== [INTENT_ROUTER] Chamada ao provider falhou: %s ===", exc)
            return []

    def _fallback(self, text: str) -> list[ExecutionStep]:
        skill = self._skill_keyword_match(text)
        if skill is not None:
            logger.info("=== [INTENT_ROUTER] FALLBACK (skill_keyword): skill='%s' (dominio='%s') ===",
                        skill.name, getattr(skill, "domain", ""))
            return [self._skill_step(skill.name, {})]
        alvo = self.fallback_router.route(text) if self.fallback_router else self.fallback_agent
        alvo_info = self.registry.get(alvo)
        dom = alvo_info.domain if alvo_info else "?"
        logger.info("=== [INTENT_ROUTER] FALLBACK (sem match): agente='%s' (dominio='%s') ===", alvo, dom)
        return [ExecutionStep(name=alvo, type=ExecutionType.AGENT, instruction=text)]
