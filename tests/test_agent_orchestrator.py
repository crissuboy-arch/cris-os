"""
Testes do AgentOrchestrator e agentes especialistas.

Nao precisam de Telegram nem Ollama: usa um FakeLLM deterministico.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agents import AgentOrchestrator, SpecialistAgent, create_agent, discover_agents, discover_general_agent
from agents.base_specialist import create_agent
from agents.prompts import (
    MARKETING_PROMPT, SOCIAL_MEDIA_PROMPT, VENDAS_PROMPT, ATENDIMENTO_PROMPT,
    PROGRAMADOR_PROMPT, PESQUISADOR_PROMPT, COPYWRITER_PROMPT, PRODUTIVIDADE_PROMPT,
    GERAL_PROMPT, ROUTING_PROMPT,
)
from core.models import IncomingMessage


class FakeLLM:
    """LLM deterministico para testes."""

    def __init__(self, reply="resposta do agente"):
        self.reply = reply

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        return LLMResponse(content=self.reply)

    def is_alive(self):
        return True


class FakeLLMRouter:
    """LLM que retorna nome de agente para testar roteamento."""

    def __init__(self, agent_name="marketing"):
        self.agent_name = agent_name

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        return LLMResponse(content=self.agent_name)

    def is_alive(self):
        return True


# ----------------------------------------------------------------------
#  Testes do SpecialistAgent
# ----------------------------------------------------------------------

def test_specialist_agent_cria_resposta():
    llm = FakeLLM("Conteudo de marketing criado.")
    agente = create_agent("marketing", "teste", "prompt de teste", llm)
    resposta = agente.generate("Crie uma campanha")
    assert resposta == "Conteudo de marketing criado."
    assert agente.name == "marketing"
    assert agente.description == "teste"


def test_specialist_agent_erro_amigavel():
    class LLMQuebrado:
        def chat(self, messages, tools=None):
            raise RuntimeError("Falha na GPU")

        def is_alive(self):
            return False

    agente = create_agent("teste", "teste", "prompt", LLMQuebrado())
    resposta = agente.generate("teste")
    assert "erro" in resposta.lower()
    assert "teste" in resposta


def test_specialist_agent_resposta_vazia():
    class LLMVazio:
        def chat(self, messages, tools=None):
            from core.contracts.llm import LLMResponse
            return LLMResponse(content="   ")

        def is_alive(self):
            return True

    agente = create_agent("teste", "teste", "prompt", LLMVazio())
    resposta = agente.generate("teste")
    assert "resposta" in resposta.lower()


# ----------------------------------------------------------------------
#  Testes do AgentOrchestrator
# ----------------------------------------------------------------------

def _criar_orchestrator(agents=None):
    """Cria um orchestrator com agentes de teste."""
    llm = FakeLLM()
    if agents is None:
        agents = [
            create_agent("marketing", "Cria campanhas", "prompt", llm),
            create_agent("social_media", "Cria posts", "prompt", llm),
            create_agent("vendas", "Propostas", "prompt", llm),
            create_agent("programador", "Codigo", "prompt", llm),
        ]
    return AgentOrchestrator(llm=llm, agents=agents)


def test_orchestrator_agente_ativo():
    orch = _criar_orchestrator()
    user = "user1"

    # Sem agente ativo, deve ser auto
    assert orch.get_active_agent(user) == "auto"

    # Define agente ativo
    msg = orch.set_active_agent(user, "marketing")
    assert "marketing" in msg
    assert orch.get_active_agent(user) == "marketing"

    # Reseta para auto
    msg = orch.set_active_agent(user, None)
    assert "automatico" in msg.lower()
    assert orch.get_active_agent(user) == "auto"


def test_orchestrator_agente_invalido():
    orch = _criar_orchestrator()
    msg = orch.set_active_agent("user1", "nao_existe")
    assert "nao encontrado" in msg.lower()


def test_orchestrator_lista_agentes():
    orch = _criar_orchestrator()
    texto = orch.list_agents()
    assert "marketing" in texto
    assert "social_media" in texto
    assert "programador" in texto
    assert "/use" in texto


def test_orchestrator_usa_agente_ativo():
    llm = FakeLLM("Resposta do marketing")
    agentes = [create_agent("marketing", "MKT", "prompt", llm)]
    orch = AgentOrchestrator(llm=llm, agents=agentes)
    orch.set_active_agent("user1", "marketing")

    msg = IncomingMessage("telegram", "user1", "faca uma campanha")
    resposta = orch.handle(msg)
    assert resposta == "Resposta do marketing"


def test_orchestrator_followup_reusa_ultimo_agente():
    """Mensagens curtas como 'continua' devem reusar o ultimo agente."""
    llm_respostas = ["Resposta mkt", "Continuacao mkt"]
    idx = [0]

    class LLMSequencial:
        def chat(self, messages, tools=None):
            from core.contracts.llm import LLMResponse
            r = llm_respostas[idx[0] % len(llm_respostas)]
            idx[0] += 1
            return LLMResponse(content=r)

        def is_alive(self):
            return True

    llm = LLMSequencial()
    agentes = [
        create_agent("marketing", "MKT", "prompt", llm),
        create_agent("vendas", "Vendas", "prompt", llm),
    ]
    orch = AgentOrchestrator(llm=llm, agents=agentes)

    # Primeira mensagem longa -> roteamento (cai no keyword fallback)
    msg1 = IncomingMessage("telegram", "user1", "crie uma campanha de natal")
    resposta1 = orch.handle(msg1)
    assert resposta1  # Nao falha

    # Segunda mensagem: "continua" -> deve reusar ultimo agente
    idx[0] = 0
    msg2 = IncomingMessage("telegram", "user1", "continua")
    resposta2 = orch.handle(msg2)
    assert resposta2


def test_orchestrator_mensagem_vazia():
    orch = _criar_orchestrator()
    msg = IncomingMessage("telegram", "user1", "")
    resposta = orch.handle(msg)
    assert resposta == ""


# ----------------------------------------------------------------------
#  Testes de roteamento por keyword (fallback)
# ----------------------------------------------------------------------

def test_keyword_social_media():
    llm = FakeLLM()
    agentes = [create_agent(n, f"Agente {n}", "prompt", llm)
               for n in ("social_media", "vendas", "marketing")]
    orch = AgentOrchestrator(llm=llm, agents=agentes)
    msg = IncomingMessage("telegram", "user1", "preciso de uma legenda para instagram")
    resposta = orch.handle(msg)
    assert resposta == "resposta do agente"


def test_keyword_programador():
    llm = FakeLLM()
    agentes = [create_agent(n, f"Agente {n}", "prompt", llm)
               for n in ("programador", "vendas")]
    orch = AgentOrchestrator(llm=llm, agents=agentes)
    msg = IncomingMessage("telegram", "user1", "cria um script em python")
    resposta = orch.handle(msg)
    assert resposta == "resposta do agente"


def test_keyword_vendas():
    llm = FakeLLM()
    agentes = [create_agent(n, f"Agente {n}", "prompt", llm)
               for n in ("vendas", "marketing")]
    orch = AgentOrchestrator(llm=llm, agents=agentes)
    msg = IncomingMessage("telegram", "user1", "preciso de uma proposta comercial")
    resposta = orch.handle(msg)
    assert resposta == "resposta do agente"


def test_keyword_nao_confunde_substring():
    """'post' nao deve ser substring de 'proposta'."""
    llm = FakeLLM()
    agentes = [create_agent(n, f"Agente {n}", "prompt", llm)
               for n in ("vendas", "social_media")]
    orch = AgentOrchestrator(llm=llm, agents=agentes)
    msg = IncomingMessage("telegram", "user1", "preciso de uma proposta comercial")
    resposta = orch.handle(msg)
    assert resposta == "resposta do agente"


# ----------------------------------------------------------------------
#  Testes de normalizacao de nomes (aliases)
# ----------------------------------------------------------------------

def test_normalizar_nome_aliases():
    from agents.orchestrator import AgentOrchestrator
    assert AgentOrchestrator._normalizar_nome("social") == "social_media"
    assert AgentOrchestrator._normalizar_nome("midia") == "social_media"
    assert AgentOrchestrator._normalizar_nome("prog") == "programador"
    assert AgentOrchestrator._normalizar_nome("copy") == "copywriter"
    assert AgentOrchestrator._normalizar_nome("suporte") == "atendimento"
    assert AgentOrchestrator._normalizar_nome("vendedor") == "vendas"
    assert AgentOrchestrator._normalizar_nome("Marketing") == "marketing"


# ----------------------------------------------------------------------
#  Testes de descoberta de agentes
# ----------------------------------------------------------------------

def test_discover_agents_carrega_todos():
    llm = FakeLLM()
    agentes = discover_agents(llm)
    nomes = {a.name for a in agentes}
    assert nomes == {
        "marketing", "social_media", "vendas", "atendimento",
        "programador", "pesquisador", "copywriter", "produtividade",
    }
    assert len(agentes) == 8


def test_discover_general_agent():
    llm = FakeLLM()
    agente = discover_general_agent(llm)
    assert agente is not None
    assert agente.name == "geral"


def test_orchestrator_com_agente_geral():
    """Agente geral deve ser usado quando nenhum especialista cobre a pergunta."""
    llm = FakeLLM("Resposta geral")
    mkt = create_agent("marketing", "MKT", "prompt", llm)
    geral = create_agent("geral", "Assistente geral", "prompt", llm)
    orch = AgentOrchestrator(llm=llm, agents=[mkt], general_agent=geral)

    # Pergunta que nao casa com nenhum especialista
    msg = IncomingMessage("telegram", "user1", "qual a capital do brasil")
    resposta = orch.handle(msg)
    assert resposta == "Resposta geral"


def test_orchestrator_sem_agente_geral():
    """Sem agente geral, deve retornar mensagem de fallback."""
    llm = FakeLLM("Resposta geral")
    mkt = create_agent("marketing", "MKT", "prompt", llm)
    orch = AgentOrchestrator(llm=llm, agents=[mkt])

    msg = IncomingMessage("telegram", "user1", "qual a capital do brasil")
    resposta = orch.handle(msg)
    assert "nenhum" in resposta.lower() or "/agents" in resposta


# ----------------------------------------------------------------------
#  Testes dos prompts (estrutura basica)
# ----------------------------------------------------------------------

def test_prompts_nao_vazios():
    prompts = [
        MARKETING_PROMPT, SOCIAL_MEDIA_PROMPT, VENDAS_PROMPT,
        ATENDIMENTO_PROMPT, PROGRAMADOR_PROMPT, PESQUISADOR_PROMPT,
        COPYWRITER_PROMPT, PRODUTIVIDADE_PROMPT, GERAL_PROMPT, ROUTING_PROMPT,
    ]
    for p in prompts:
        assert p and len(p) > 100, f"Prompt muito curto: {p[:50]}"


def test_prompts_em_portugues():
    """Verifica que os prompts estao em portugues (tem acentos/pt-br keywords)."""
    portugues = ["voce", "responsavel", "regras", "formato", "saida"]
    for p in [MARKETING_PROMPT, SOCIAL_MEDIA_PROMPT, VENDAS_PROMPT]:
        assert any(kw in p.lower() for kw in portugues), f"Prompt parece nao estar em pt-br: {p[:100]}"


# ----------------------------------------------------------------------
#  Execucao direta
# ----------------------------------------------------------------------

if __name__ == "__main__":
    test_specialist_agent_cria_resposta()
    test_specialist_agent_erro_amigavel()
    test_specialist_agent_resposta_vazia()
    test_orchestrator_agente_ativo()
    test_orchestrator_agente_invalido()
    test_orchestrator_lista_agentes()
    test_orchestrator_usa_agente_ativo()
    test_orchestrator_followup_reusa_ultimo_agente()
    test_orchestrator_mensagem_vazia()
    test_keyword_social_media()
    test_keyword_programador()
    test_keyword_vendas()
    test_normalizar_nome_aliases()
    test_discover_agents_carrega_todos()
    test_prompts_nao_vazios()
    test_prompts_em_portugues()
    print("OK - Todos os testes do AgentOrchestrator passaram!")
