"""
Teste de Roteamento — 5 prompts reais que a Cris pode enviar.
Valida que cada prompt chega ao agente correto via keyword ou LLM.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agents.loader import carregar_agentes
from core.application import IntentRouter
from core.contracts.llm import LLMResponse, ToolCall
from core.domain.execution import ExecutionType
from core.registry import AgentRegistry
from core.router import Router


def _step(plano):
    assert len(plano) == 1
    return plano[0]


class AgentSelectingLLM:
    """LLM fake que roteia para o agente correto com base no dominio do prompt."""

    def __init__(self):
        self.routing_map = {
            "video": "mkvideos",
            "instagram": "social-media",
            "vendas": "financeiro",
            "receita": "financeiro",
            "despesa": "financeiro",
            "lembrete": "secretary",
            "pesquisa": "pesquisador",
            "concorrente": "pesquisador",
            "cliente": "atendimento",
            "suporte": "atendimento",
        }

    def is_alive(self):
        return True

    def chat(self, messages, tools=None):
        if not tools:
            return LLMResponse(content="Nada a fazer.")
        user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")
        user_lower = user_msg.lower()
        for palavra, agente in self.routing_map.items():
            if palavra in user_lower:
                # Verifica se o agente esta nas tools
                nomes = {t["function"]["name"] for t in tools}
                if agente in nomes:
                    return LLMResponse(
                        tool_calls=[ToolCall(name=agente, arguments={"instruction": user_msg})]
                    )
        # Fallback: secretary ou qualquer agente disponível
        nomes = {t["function"]["name"] for t in tools}
        if "secretary" in nomes:
            return LLMResponse(
                tool_calls=[ToolCall(name="secretary", arguments={"instruction": user_msg})]
            )
        return LLMResponse(content="Nao sei o que fazer.")


def _router(llm):
    agentes = carregar_agentes(RAIZ / "agents", llm=llm)
    reg = AgentRegistry()
    for a in agentes:
        reg.register(a)
    return IntentRouter(llm, reg, Router("secretary", agentes), "secretary")


# ---------------------------------------------------------------------------
# 5 prompts de roteamento
# ---------------------------------------------------------------------------

def test_routing_marketing():
    """Prompt 1: Conteudo/Video -> mkvideos (keyword 'video')"""
    prompt = "preciso de um video novo para o instagram"
    router = _router(AgentSelectingLLM())
    plano = router.plan(prompt, [], "gerente")
    passo = _step(plano)
    assert passo.name == "mkvideos", f"Esperado mkvideos, obtido {passo.name}"
    assert passo.type == ExecutionType.AGENT
    print(f"  [OK] '{prompt}' -> {passo.name}")


def test_routing_vendas():
    """Prompt 2: Vendas/Financeiro -> financeiro (keyword 'vendas')"""
    prompt = "qual foi o total de vendas do mes passado"
    router = _router(AgentSelectingLLM())
    plano = router.plan(prompt, [], "gerente")
    passo = _step(plano)
    assert passo.name == "financeiro", f"Esperado financeiro, obtido {passo.name}"
    assert passo.type == ExecutionType.AGENT
    print(f"  [OK] '{prompt}' -> {passo.name}")


def test_routing_faturamento():
    """Prompt extra: Faturamento -> financeiro (keyword 'faturamento')"""
    prompt = "calcule meu faturamento deste mes"
    router = _router(AgentSelectingLLM())
    plano = router.plan(prompt, [], "gerente")
    passo = _step(plano)
    assert passo.name == "financeiro", f"Esperado financeiro, obtido {passo.name}"
    assert passo.type == ExecutionType.AGENT
    print(f"  [OK] '{prompt}' -> {passo.name}")


def test_routing_pessoal():
    """Prompt 3: Tarefa pessoal -> secretary (fallback, sem keyword)"""
    prompt = "me lembre de comprar leite hoje"
    router = _router(AgentSelectingLLM())
    plano = router.plan(prompt, [], "gerente")
    passo = _step(plano)
    assert passo.name == "secretary", f"Esperado secretary, obtido {passo.name}"
    assert passo.type == ExecutionType.AGENT
    print(f"  [OK] '{prompt}' -> {passo.name}")


def test_routing_tecnico():
    """Prompt 4: Duvida tecnica -> programador (keyword 'servidor')"""
    prompt = "como configurar o servidor de producao"
    router = _router(AgentSelectingLLM())
    plano = router.plan(prompt, [], "gerente")
    passo = _step(plano)
    assert passo.name == "programador", f"Esperado programador, obtido {passo.name}"
    assert passo.type == ExecutionType.AGENT
    print(f"  [OK] '{prompt}' -> {passo.name}")


def test_routing_saudacao():
    """Prompt 5: Saudacao -> secretary (fast path sem LLM)"""
    prompt = "bom dia"
    router = _router(AgentSelectingLLM())
    plano = router.plan(prompt, [], "gerente")
    passo = _step(plano)
    assert passo.name == "secretary", f"Esperado secretary, obtido {passo.name}"
    assert passo.type == ExecutionType.AGENT
    print(f"  [OK] '{prompt}' (fast path) -> {passo.name}")


def test_routing_confirmation():
    """Prompt extra: Sim/confirmacao com contexto -> secretary (fast path)"""
    prompt = "pode ser"
    ctx = [{"role": "assistant", "content": "Quer que eu crie o relatorio?"}]
    router = _router(AgentSelectingLLM())
    plano = router.plan(prompt, ctx, "gerente")
    passo = _step(plano)
    assert passo.name == "secretary", f"Esperado secretary, obtido {passo.name}"
    assert passo.type == ExecutionType.AGENT
    print(f"  [OK] '{prompt}' (com ctx) -> {passo.name}")


def test_routing_erro_python():
    """Prompt extra: Erro Python -> programador (keyword 'codigo'/'bug')"""
    prompt = "analise este erro Python"
    router = _router(AgentSelectingLLM())
    plano = router.plan(prompt, [], "gerente")
    passo = _step(plano)
    assert passo.name == "programador", f"Esperado programador, obtido {passo.name}"
    assert passo.type == ExecutionType.AGENT
    print(f"  [OK] '{prompt}' -> {passo.name}")


if __name__ == "__main__":
    print("=" * 60)
    print("Teste de Roteamento — 5 prompts")
    print("=" * 60)
    test_routing_marketing()
    test_routing_vendas()
    test_routing_faturamento()
    test_routing_pessoal()
    test_routing_tecnico()
    test_routing_erro_python()
    test_routing_saudacao()
    test_routing_confirmation()
    print("=" * 60)
    print("OK - Todos os 8 testes passaram")
