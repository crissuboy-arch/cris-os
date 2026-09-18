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

# Comandos do ScalaFlow sao 100% deterministicos (tools/scalaflow_tools.py nao
# usa LLM). Por isso sao interceptados ANTES de tentar o roteador via LLM
# (Ollama) -- evita esperar/errar no Ollama para um comando que nunca
# precisou dele.
_SCALAFLOW_KEYWORDS = frozenset({
    "scalaflow", "vencedor", "vencedores", "minerado", "minerados",
    "oferta", "ofertas", "top", "anuncio", "anuncios", "anúncio",
    "anúncios", "quente", "quentes", "favorito", "favoritos",
    "escalado", "escalados", "escalada", "escaladas",
})

# Opportunity Analyst tambem e 100% deterministico (Fase 2, sem LLM). Checado
# ANTES do scalaflow_intel: frases como "investigue uma das minhas melhores
# ofertas" contem palavras de ambos os agentes ("ofertas" + "investigue"), e a
# intencao de INVESTIGAR uma oferta especifica deve vencer a de LISTAR ofertas.
_OPPORTUNITY_KEYWORDS = frozenset({
    "investigue", "investigar", "investigacao", "analise", "analisar",
    "analisa", "oportunidade", "oportunidades", "sinais", "sinal",
    "caminho", "decisao", "decision",
})

# Continuacao de uma investigacao ja em andamento (ex.: "Cris, isso aparece
# no TikTok?" depois de "investigue minha melhor oferta"). NAO depende da
# frase comecar com uma palavra especifica -- so entra em jogo quando o
# ULTIMO agente da conversa ja foi o opportunity_analyst (ver
# `_eh_continuacao_opportunity`), entao nao risca roteamento de mensagens
# novas/nao relacionadas (ex.: "crie uma legenda pro meu tiktok" continua
# indo pro social_media normalmente, porque o ultimo agente nao era o
# opportunity_analyst).
_CONTINUACAO_OPORTUNIDADE_KEYWORDS = frozenset({
    "tiktok", "meta", "facebook", "instagram", "youtube", "google",
    "trends", "tendencia", "tendencias", "aparece", "evidencia",
    "evidencias", "fonte", "fontes", "esta", "essa", "este", "esse",
    "isso", "aquela", "aquele", "aquilo", "dessa", "desse", "nessa",
    "nesse",
})

# Product Architect (Fase 3) e checado ANTES do opportunity_analyst: frases
# como "pegue uma das minhas melhores oportunidades e me diga que produto
# deveriamos criar" contem palavra de ambos ("oportunidades" + "produto"), e
# a intencao de PROPOR UM PRODUTO deve vencer a de so investigar/listar.
_PRODUCT_ARCHITECT_KEYWORDS = frozenset({
    "produto", "produtos", "blueprint", "formato",
    "arquitet", "alternativas", "alternativa", "opcoes", "opções",
    "aprovacao", "aprovação", "aguardando", "pendentes", "pendente",
})

# Continuacao de uma proposta ja feita (aprovar/rejeitar/explicar). So entra
# em jogo quando o ULTIMO agente da conversa ja foi o product_architect --
# nunca interpreta uma mensagem ambigua de outro contexto como aprovacao.
_PRODUCT_ARCHITECT_CONTINUACAO_KEYWORDS = frozenset({
    "aprovado", "aprovada", "aprovo", "autorizado", "autorizo",
    "confirmado", "confirmo", "rejeitado", "rejeitada", "rejeito",
    "porque", "motivo", "justificativa",
})
_PRODUCT_ARCHITECT_CONTINUACAO_FRASES = (
    "pode criar", "pode seguir", "pode produzir", "pode comecar",
    "pode começar", "bora criar", "nao gostei", "não gostei",
    "quero outra", "outra alternativa", "por que",
)

# Business Builder (Fase 4) e checado ANTES do product_architect: frases como
# "transforme esse produto aprovado em um negocio" contem "produto" (palavra
# do product_architect) mas a intencao e clara e mais especifica (montar
# NEGOCIO em cima do produto ja aprovado) -- mesmo padrao de precedencia ja
# usado para product_architect vs. opportunity_analyst na Fase 3. "oferta" e
# de proposito NAO incluida como palavra solta (colide com _SCALAFLOW_KEYWORDS
# -- "quais sao as ofertas hoje" continua indo pro scalaflow_intel), so como
# parte de frases especificas.
_BUSINESS_BUILDER_KEYWORDS = frozenset({"negocio", "negócio", "monetiz"})
_BUSINESS_BUILDER_FRASES = (
    "modelo de negocio", "modelo de negócio",
    "plano de negocio", "plano de negócio",
    "monte a oferta", "montar a oferta", "estruture a oferta",
    "monte o modelo de negocio", "monte o modelo de negócio",
    "como vamos monetizar", "transforme em negocio", "transforme em negócio",
    "transforme esse produto em um negocio", "transforme esse produto em um negócio",
    "transforme o produto aprovado em um negocio", "transforme o produto aprovado em um negócio",
    "transforme esse produto aprovado em um negocio", "transforme esse produto aprovado em um negócio",
)

# Product Factory (Fase 4) tambem e checado ANTES do product_architect pelo
# mesmo motivo ("o que precisa ser produzido para lancar esse produto" contem
# "produto"). "producao"/"artefatos" nao colidem com nenhum outro agente.
#
# CORRECAO pos-teste real: "manifesto"/"manifest" (leitura determinística do
# GET_CURRENT_PROJECT_MANIFEST, ver `tools/product_factory_tools.py`) faltava
# aqui -- a Tool ja reconhecia a palavra, mas o ORCHESTRATOR nunca chegava a
# escolher o agente `product_factory` pra essa mensagem (caia no roteamento
# via LLM, que mandou pro assistente generico -- "Não tenho acesso ao
# manifesto..."). Mesma classe de bug ja corrigida 3x na Fase 3 (Tool precisa
# ser SUPERSET do orchestrator), mas na direcao oposta desta vez: era o
# ORCHESTRATOR que estava desatualizado em relacao a Tool.
_PRODUCT_FACTORY_KEYWORDS = frozenset({
    "producao", "produção", "artefatos", "entregaveis", "entregáveis",
    "manifesto", "manifest",
})
_PRODUCT_FACTORY_FRASES = (
    "plano de producao", "plano de produção",
    "quais artefatos", "o que precisa ser produzido",
    "manifesto atual", "manifesto deste projeto", "manifesto do projeto",
    "mostre o manifesto", "mostre somente o manifesto",
    "qual o status do projeto", "qual é o status do projeto",
    "mostre a estrutura atual do projeto", "estrutura atual do projeto",
)

# Paid Traffic Architect (Fase 5) e checado ANTES do product_architect (mesmo
# motivo dos dois de cima: "monte uma estrategia de anuncios para este
# PRODUTO" contem "produto") E ANTES do scalaflow_intel ("anúncios" esta em
# `_SCALAFLOW_KEYWORDS` -- "estratégia de anúncios" nao pode virar uma
# listagem de anuncios minerados). "trafego"/"tráfego" e unico o bastante
# pra nao colidir com nada. Pedido explicito da Fase 5: "nao repetir o erro
# da Fase 4 criando apenas listas frageis de palavras exatas" -- por isso
# tambem ha uma checagem de co-ocorrencia ("plano" + nome de plataforma) em
# `_eh_comando_paid_traffic`, cobrindo frases como "quero o plano de Meta,
# Google e TikTok desse projeto" sem depender de uma frase fixa.
_PAID_TRAFFIC_KEYWORDS = frozenset({"trafego", "tráfego"})
_PAID_TRAFFIC_FRASES = (
    "estrategia de anuncios", "estratégia de anúncios",
    "como vamos anunciar", "plano de trafego", "plano de tráfego",
    "plano de campanha", "campanha paga", "anuncios pagos", "anúncios pagos",
    "trafego pago", "tráfego pago", "meta ads", "google ads", "tiktok ads",
    "google display", "youtube ads",
)


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
                return self.general_agent.generate(texto, incoming.session)
            return (
                "Nao encontrei um agente adequado para essa tarefa. "
                "Use /agents para ver os agentes disponiveis ou /use <nome> para escolher um."
            )

        self.last_agents[user_id] = agent.name
        # `incoming.session` (canal+usuario, ex.: "telegram:123") permite a
        # Tools que precisam de contexto POR sessao (ex.: oportunidade em
        # foco do Opportunity Analyst/Product Architect, Fase 3) persistirem
        # isso isolado por usuario/canal, em vez de um global compartilhado.
        resposta = agent.generate(texto, incoming.session)
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

        # 2.2) Interceptacao deterministica do Business Builder (Fase 4),
        #      checada ANTES do product_architect -- "transforme esse produto
        #      aprovado em um negocio" contem "produto" mas a intencao e mais
        #      especifica (montar negocio).
        if "business_builder" in self.agents and self._eh_comando_business_builder(texto):
            logger.info(
                "=== [ORCHESTRATOR] Interceptacao deterministica: 'business_builder' "
                "(sem passar pelo LLM/Ollama) ===",
            )
            return self.agents["business_builder"]

        # 2.3) Interceptacao deterministica do Product Factory (Fase 4),
        #      checada ANTES do product_architect pelo mesmo motivo.
        if "product_factory" in self.agents and self._eh_comando_product_factory(texto):
            logger.info(
                "=== [ORCHESTRATOR] Interceptacao deterministica: 'product_factory' "
                "(sem passar pelo LLM/Ollama) ===",
            )
            return self.agents["product_factory"]

        # 2.4) Interceptacao deterministica do Paid Traffic Architect (Fase 5),
        #      checada ANTES do product_architect ("produto") E ANTES do
        #      scalaflow_intel ("anúncios" colide com _SCALAFLOW_KEYWORDS).
        if "paid_traffic_architect" in self.agents and self._eh_comando_paid_traffic(texto):
            logger.info(
                "=== [ORCHESTRATOR] Interceptacao deterministica: 'paid_traffic_architect' "
                "(sem passar pelo LLM/Ollama) ===",
            )
            return self.agents["paid_traffic_architect"]

        # 2.5) Interceptacao deterministica do Product Architect (Fase 3),
        #      checada ANTES do opportunity_analyst -- "pegue uma das minhas
        #      melhores oportunidades e me diga que produto criar" nao pode
        #      virar uma investigacao pura (a intencao e propor um produto).
        if "product_architect" in self.agents and self._eh_comando_product_architect(texto):
            logger.info(
                "=== [ORCHESTRATOR] Interceptacao deterministica: 'product_architect' "
                "(sem passar pelo LLM/Ollama) ===",
            )
            return self.agents["product_architect"]

        # 3) Interceptacao deterministica do Opportunity Analyst (checada ANTES
        #    do scalaflow_intel -- "investigue essa oferta" nao pode virar uma
        #    listagem de ofertas)
        if "opportunity_analyst" in self.agents and self._eh_comando_opportunity(texto):
            logger.info(
                "=== [ORCHESTRATOR] Interceptacao deterministica: 'opportunity_analyst' "
                "(sem passar pelo LLM/Ollama) ===",
            )
            return self.agents["opportunity_analyst"]

        # 4) Interceptacao deterministica do ScalaFlow (sem chamar o LLM)
        if "scalaflow_intel" in self.agents and self._eh_comando_scalaflow(texto):
            logger.info(
                "=== [ORCHESTRATOR] Interceptacao deterministica: 'scalaflow_intel' "
                "(sem passar pelo LLM/Ollama) ===",
            )
            return self.agents["scalaflow_intel"]

        # 4.5) Continuacao de uma investigacao ja em andamento: so entra em
        #      jogo se o ULTIMO agente desta conversa ja foi o
        #      opportunity_analyst (nao risca roteamento de mensagens novas).
        #      Nao depende de a frase comecar com uma palavra especifica.
        if (
            "opportunity_analyst" in self.agents
            and self.last_agents.get(user_id) == "opportunity_analyst"
            and self._eh_continuacao_opportunity(texto)
        ):
            logger.info(
                "=== [ORCHESTRATOR] Continuacao de investigacao (opportunity_analyst) "
                "(sem passar pelo LLM/Ollama) ===",
            )
            return self.agents["opportunity_analyst"]

        # 4.6) Continuacao de uma proposta de produto ja feita (aprovar/
        #      rejeitar/explicar). So entra em jogo se o ULTIMO agente ja foi
        #      o product_architect -- nunca interpreta mensagem ambigua de
        #      outro contexto como aprovacao.
        if (
            "product_architect" in self.agents
            and self.last_agents.get(user_id) == "product_architect"
            and self._eh_continuacao_product_architect(texto)
        ):
            logger.info(
                "=== [ORCHESTRATOR] Continuacao de proposta (product_architect) "
                "(sem passar pelo LLM/Ollama) ===",
            )
            return self.agents["product_architect"]

        # 5) Roteamento via LLM + keyword fallback
        nome_agente = self._rotear(texto)
        if nome_agente and nome_agente in self.agents:
            return self.agents[nome_agente]

        return None

    @staticmethod
    def _eh_comando_business_builder(texto: str) -> bool:
        """Detecta comandos do Business Builder por palavra-chave/frase (sem
        LLM). Ver `_BUSINESS_BUILDER_KEYWORDS`/`_BUSINESS_BUILDER_FRASES`
        sobre por que "oferta" sozinha nao entra aqui."""
        texto_lower = texto.lower()
        palavras = set(texto_lower.split())
        if palavras & _BUSINESS_BUILDER_KEYWORDS:
            return True
        if any(kw in texto_lower for kw in _BUSINESS_BUILDER_KEYWORDS):
            return True
        return any(f in texto_lower for f in _BUSINESS_BUILDER_FRASES)

    @staticmethod
    def _eh_comando_product_factory(texto: str) -> bool:
        """Detecta comandos do Product Factory por palavra-chave/frase (sem LLM)."""
        texto_lower = texto.lower()
        palavras = set(texto_lower.split())
        if palavras & _PRODUCT_FACTORY_KEYWORDS:
            return True
        if any(kw in texto_lower for kw in _PRODUCT_FACTORY_KEYWORDS):
            return True
        if any(f in texto_lower for f in _PRODUCT_FACTORY_FRASES):
            return True
        # "status"/"estrutura" + "projeto" juntos (qualquer fraseado) -- mais
        # flexivel que uma frase fixa pra pedidos de status do manifesto
        # (ex.: "qual o status DESTE projeto" -- variacao real do teste --
        # nao bate a frase fixa "status DO projeto"), mas ainda exige AMBAS
        # as palavras pra nao capturar mensagens genericas sem relacao
        # nenhuma (ex.: "status da minha entrega dos Correios").
        if ("status" in texto_lower or "estrutura" in texto_lower) and "projeto" in texto_lower:
            return True
        return False

    @staticmethod
    def _eh_comando_paid_traffic(texto: str) -> bool:
        """Detecta comandos do Paid Traffic Architect por palavra-chave/frase
        (sem LLM). Ver comentario de `_PAID_TRAFFIC_KEYWORDS` sobre a
        co-ocorrencia "plano" + plataforma (cobre "quero o plano de Meta,
        Google e TikTok desse projeto" sem depender de frase fixa)."""
        texto_lower = texto.lower()
        palavras = set(texto_lower.split())
        if palavras & _PAID_TRAFFIC_KEYWORDS:
            return True
        if any(kw in texto_lower for kw in _PAID_TRAFFIC_KEYWORDS):
            return True
        if any(f in texto_lower for f in _PAID_TRAFFIC_FRASES):
            return True
        # "meta" de proposito NAO entra aqui (colide com "meta" no sentido
        # de objetivo/goal, ex.: "plano para bater minha meta de vendas") --
        # Meta Ads especificamente so e reconhecido pela frase completa
        # "meta ads" acima.
        if "plano" in texto_lower and any(
            p in texto_lower for p in ("tiktok", "google", "youtube")
        ):
            return True
        return False

    @staticmethod
    def _eh_comando_product_architect(texto: str) -> bool:
        """Detecta comandos do Product Architect por palavra-chave (sem LLM)."""
        palavras = set(texto.lower().split())
        if palavras & _PRODUCT_ARCHITECT_KEYWORDS:
            return True
        texto_lower = texto.lower()
        return any(kw in texto_lower for kw in _PRODUCT_ARCHITECT_KEYWORDS)

    @staticmethod
    def _eh_continuacao_product_architect(texto: str) -> bool:
        """Detecta aprovacao/rejeicao/explicacao de uma proposta ja feita
        (sem LLM). So chamado quando o ultimo agente ja era o
        product_architect -- ver `_escolher_agente`."""
        texto_lower = texto.lower()
        palavras = set(texto_lower.split())
        if palavras & _PRODUCT_ARCHITECT_CONTINUACAO_KEYWORDS:
            return True
        if any(kw in texto_lower for kw in _PRODUCT_ARCHITECT_CONTINUACAO_KEYWORDS):
            return True
        return any(f in texto_lower for f in _PRODUCT_ARCHITECT_CONTINUACAO_FRASES)

    @staticmethod
    def _eh_comando_scalaflow(texto: str) -> bool:
        """Detecta comandos do ScalaFlow por palavra-chave (sem LLM)."""
        palavras = set(texto.lower().split())
        if palavras & _SCALAFLOW_KEYWORDS:
            return True
        texto_lower = texto.lower()
        return any(kw in texto_lower for kw in _SCALAFLOW_KEYWORDS)

    @staticmethod
    def _eh_comando_opportunity(texto: str) -> bool:
        """Detecta comandos do Opportunity Analyst por palavra-chave (sem LLM)
        OU por um link/ID real da Meta Ads Library em qualquer mensagem
        (Fase 3 -- ex.: a pessoa so cola o link, sem nenhuma palavra-chave).
        Um link reconhecido NUNCA deve cair no LLM generico."""
        palavras = set(texto.lower().split())
        if palavras & _OPPORTUNITY_KEYWORDS:
            return True
        texto_lower = texto.lower()
        if any(kw in texto_lower for kw in _OPPORTUNITY_KEYWORDS):
            return True
        from tools.opportunity_tools import detectar_ad_library_id

        return detectar_ad_library_id(texto) is not None

    @staticmethod
    def _eh_continuacao_opportunity(texto: str) -> bool:
        """Detecta continuacao de uma investigacao (sem LLM, sem exigir
        palavra inicial fixa). So e chamado quando o ultimo agente ja era o
        opportunity_analyst -- ver `_escolher_agente`."""
        palavras = set(texto.lower().split())
        if palavras & _CONTINUACAO_OPORTUNIDADE_KEYWORDS:
            return True
        texto_lower = texto.lower()
        return any(kw in texto_lower for kw in _CONTINUACAO_OPORTUNIDADE_KEYWORDS)

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
            (list(_PRODUCT_ARCHITECT_KEYWORDS), "product_architect"),
            (list(_BUSINESS_BUILDER_KEYWORDS), "business_builder"),
            (list(_PRODUCT_FACTORY_KEYWORDS), "product_factory"),
            (list(_PAID_TRAFFIC_KEYWORDS), "paid_traffic_architect"),
            (["proposta", "orcamento", "pitch", "negociacao",
              "prospeccao", "comercial", "argumentario"], "vendas"),
            (["atendimento", "suporte", "reclamacao", "cancelamento",
              "troca", "devolucao"], "atendimento"),
            (list(_OPPORTUNITY_KEYWORDS), "opportunity_analyst"),
            (["pesquisa", "concorrente", "concorrentes",
              "fornecedor", "mercado", "tendencia",
              "comparar", "comparacao", "preco"], "pesquisador"),
            (["copy", "conversao", "headline", "landing"], "copywriter"),
            (["campanha", "branding", "divulgacao", "midia"], "marketing"),
            (["rotina", "agenda", "planejar", "produtividade",
              "tarefas", "prioridade", "checklist", "pomodoro"], "produtividade"),
            (list(_SCALAFLOW_KEYWORDS), "scalaflow_intel"),
        ]

        multi: list[tuple[str, str]] = [
            ("rede social", "social_media"),
            ("pagina de venda", "copywriter"),
            ("landing page", "copywriter"),
            ("email marketing", "copywriter"),
            ("google ads", "marketing"),
            ("facebook ads", "marketing"),
            ("problema com", "atendimento"),
            ("produto quente", "scalaflow_intel"),
            ("produtos quentes", "scalaflow_intel"),
            ("top 10", "scalaflow_intel"),
            ("top produtos", "scalaflow_intel"),
            ("produto vencedor", "scalaflow_intel"),
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
            "scalaflow": "scalaflow_intel",
            "produtos": "scalaflow_intel",
            "investigar": "opportunity_analyst",
            "oportunidade": "opportunity_analyst",
            "analyst": "opportunity_analyst",
            "produto": "product_architect",
            "architect": "product_architect",
            "arquiteto": "product_architect",
            "negocio": "business_builder",
            "negócio": "business_builder",
            "builder": "business_builder",
            "producao": "product_factory",
            "produção": "product_factory",
            "factory": "product_factory",
            "fabrica": "product_factory",
            "trafego": "paid_traffic_architect",
            "tráfego": "paid_traffic_architect",
            "traffic": "paid_traffic_architect",
            "ads": "paid_traffic_architect",
        }
        n = nome.strip().lower().replace("-", "_")
        return aliases.get(n, n)
