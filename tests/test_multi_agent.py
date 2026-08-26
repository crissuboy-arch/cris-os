"""
Teste Multi-Agent — tarefas compostas que exigem varios especialistas.
Valida que o IntentRouter monta planos multi-passo e que o pipeline
(Dispatcher + Composer) os executa e consolida.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agents.loader import carregar_agentes
from core.application import IntentRouter, ResponseComposer
from core.application.dispatcher import ExecutionDispatcher, TargetRegistry
from core.application.targets import AgentTarget
from core.contracts.execution import DispatchContext
from core.contracts.llm import LLMResponse, ToolCall
from core.domain.execution import ExecutionType
from core.models import ExecutionResult, ExecutionStep
from core.registry import AgentRegistry
from core.router import Router

LOG = []


def _log(msg):
    LOG.append(msg)
    print(f"  {msg}")


class CompoundLLM:
    """LLM fake que devolve tool_calls especificos para cada cenario composto."""

    def __init__(self):
        self.call_count = 0

    def is_alive(self):
        return True

    def chat(self, messages, tools=None):
        self.call_count += 1
        user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")
        user_lower = user_msg.lower()

        # Cenario 1: vender chaveiros em Portugal
        if "chaveiro" in user_lower and "portugal" in user_lower:
            return LLMResponse(tool_calls=[
                ToolCall(name="pesquisador", arguments={"instruction": "analise o mercado de chaveiros personalizados em Portugal"}),
                ToolCall(name="social-media", arguments={"instruction": "crie estrategia de marketing para chaveiros"}),
                ToolCall(name="financeiro", arguments={"instruction": "calcule viabilidade financeira"}),
                ToolCall(name="atendimento", arguments={"instruction": "crie abordagem comercial"}),
            ])

        # Cenario 2: SaaS para imobiliarias
        if "saas" in user_lower and "imobili" in user_lower:
            return LLMResponse(tool_calls=[
                ToolCall(name="pesquisador", arguments={"instruction": "pesquise o mercado de SaaS para imobiliarias"}),
                ToolCall(name="programador", arguments={"instruction": "desenvolva o SaaS para imobiliarias"}),
                ToolCall(name="mkvideos", arguments={"instruction": "crie video de apresentacao do SaaS"}),
                ToolCall(name="social-media", arguments={"instruction": "crie estrategia de divulgacao"}),
            ])

        # Cenario 3: lancar ScalaFlow
        if "scalaflow" in user_lower:
            return LLMResponse(tool_calls=[
                ToolCall(name="scalaflow", arguments={"instruction": "prepare o plano de lancamento do ScalaFlow"}),
                ToolCall(name="programador", arguments={"instruction": "finalize os ajustes tecnicos"}),
                ToolCall(name="social-media", arguments={"instruction": "crie campanha de divulgacao"}),
                ToolCall(name="financeiro", arguments={"instruction": "analise a viabilidade financeira"}),
            ])

        return LLMResponse(content="Nao sei o que fazer.")


class FakeWorkflow:
    """Simula o WorkflowEngine — executa um agente e devolve resposta."""

    def __init__(self, registry):
        self.registry = registry

    def run(self, steps, session, query, correlation_id):
        from core.contracts.agent import AgentContext
        from core.models import AgentResult
        resultados = []
        for nome, instrucao in steps:
            agente_raw = self.registry.get(nome)
            if agente_raw is None:
                resultados.append(AgentResult(agent=nome, output="", success=False))
                continue
            saida = f"Resposta de {nome} sobre: {instrucao[:60]}"
            resultados.append(AgentResult(agent=nome, output=saida, success=True))
        return resultados


class FakeLLM:
    """LLM generico para o ResponseComposer sintetizar."""

    def is_alive(self):
        return True

    def chat(self, messages, tools=None):
        return LLMResponse(
            content="RESUMO UNIFICADO: Aqui esta o plano completo com todas as analises."
        )


def _router(llm):
    agentes = carregar_agentes(RAIZ / "agents", llm=llm)
    reg = AgentRegistry()
    for a in agentes:
        reg.register(a)
    return IntentRouter(llm, reg, Router("secretary", agentes), "secretary")


# ---------------------------------------------------------------------------
# Testes de roteamento
# ---------------------------------------------------------------------------

def test_compound_chaveiros_portugal():
    """Cenario 1: vender chaveiros em Portugal -> 4 especialistas."""
    global LOG
    LOG = []

    llm = CompoundLLM()
    router = _router(llm)
    plano = router.plan("Quero vender chaveiros personalizados em Portugal.", [], "pedido")

    _log(f"Agentes escolhidos ({len(plano)}): {[p.name for p in plano]}")
    nomes = [p.name for p in plano]

    assert len(plano) >= 3, f"Esperado >=3 especialistas, obtido {len(plano)}"
    assert "pesquisador" in nomes, "pesquisador deveria estar no plano"
    assert "social-media" in nomes, "social-media deveria estar no plano"
    assert "financeiro" in nomes, "financeiro deveria estar no plano"
    for p in plano:
        assert p.type == ExecutionType.AGENT
        assert p.instruction, f"Instrucao vazia para {p.name}"

    _log("Ordem de execucao: " + " -> ".join(nomes))
    _log(f"OK - {len(plano)} especialistas selecionados")


def test_compound_saas_imobiliarias():
    """Cenario 2: SaaS para imobiliarias -> 4 especialistas."""
    global LOG
    LOG = []

    llm = CompoundLLM()
    router = _router(llm)
    plano = router.plan("Crie um SaaS para imobiliarias.", [], "pedido")

    _log(f"Agentes escolhidos ({len(plano)}): {[p.name for p in plano]}")
    nomes = [p.name for p in plano]

    assert len(plano) >= 3
    assert "pesquisador" in nomes, "pesquisador deveria estar no plano"
    assert "programador" in nomes, "programador deveria estar no plano"
    assert "social-media" in nomes, "social-media deveria estar no plano"
    for p in plano:
        assert p.type == ExecutionType.AGENT

    _log("Ordem de execucao: " + " -> ".join(nomes))


def test_compound_scalaflow():
    """Cenario 3: lancar ScalaFlow -> 4 especialistas."""
    global LOG
    LOG = []

    llm = CompoundLLM()
    router = _router(llm)
    plano = router.plan("Ajude-me a lancar o ScalaFlow.", [], "pedido")

    _log(f"Agentes escolhidos ({len(plano)}): {[p.name for p in plano]}")
    nomes = [p.name for p in plano]

    assert len(plano) >= 3
    assert "scalaflow" in nomes, "scalaflow deveria estar no plano"
    assert "programador" in nomes, "programador deveria estar no plano"
    assert "social-media" in nomes, "social-media deveria estar no plano"
    assert "financeiro" in nomes, "financeiro deveria estar no plano"
    for p in plano:
        assert p.type == ExecutionType.AGENT

    _log("Ordem de execucao: " + " -> ".join(nomes))


# ---------------------------------------------------------------------------
# Teste de pipeline completo (IntentRouter + Dispatcher + Composer)
# ---------------------------------------------------------------------------

def test_pipeline_completo_multi_agente():
    """Pipeline completo: roteia, executa, consolida."""
    global LOG
    LOG = []

    llm_router = CompoundLLM()
    agentes = carregar_agentes(RAIZ / "agents", llm=llm_router)
    reg = AgentRegistry()
    for a in agentes:
        reg.register(a)
    router = IntentRouter(llm_router, reg, Router("secretary", agentes), "secretary")

    workflow = FakeWorkflow(reg)
    target_reg = TargetRegistry().register(AgentTarget(workflow, id="agent.workflow"))
    dispatcher = ExecutionDispatcher(target_reg)

    llm_composer = FakeLLM()
    composer = ResponseComposer(llm_composer)

    # --- Executar cenario 1 ---
    _log("--- Cenario 1: Chaveiros em Portugal ---")
    texto = "Quero vender chaveiros personalizados em Portugal."
    plano = router.plan(texto, [], "pedido")
    _log(f"Plano: {len(plano)} passos -> {[p.name for p in plano]}")

    import time
    t0 = time.perf_counter()
    ctx = DispatchContext(session="test:1", query=texto, correlation_id="test-1")
    resultados = dispatcher.run(plano, ctx)
    t_total = (time.perf_counter() - t0) * 1000

    for r in resultados:
        _log(f"  [{r.source}] {r.output[:80]}... ({(time.perf_counter() - t0) * 1000:.0f}ms)")

    resposta = composer.compose(texto, resultados)
    _log(f"Tempo total: {t_total:.0f}ms")
    _log(f"Resumo do Orchestrator: {resposta[:100]}")
    _log(f"OK - Pipeline completo executou {len(resultados)} especialistas")

    assert len(resultados) >= 3, "Deveria ter multiplos resultados"
    assert all(r.success for r in resultados), "Todos deveriam ter sucesso"
    assert resposta, "Deveria haver resposta final"


if __name__ == "__main__":
    print("=" * 60)
    print("Teste Multi-Agent — 3 cenarios + pipeline")
    print("=" * 60)

    test_compound_chaveiros_portugal()
    print()
    test_compound_saas_imobiliarias()
    print()
    test_compound_scalaflow()
    print()
    test_pipeline_completo_multi_agente()

    print("=" * 60)
    print("OK - Todos os 4 testes multi-agent passaram")
