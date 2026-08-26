"""
Smoke tests do CRIS OS v3 (arquitetura event-driven + memória 4 camadas).

Não precisam de Telegram nem de Ollama: usam um FakeLLM e bancos SQLite
temporários. Validam a fundação da Fase 100.

Rodar:  pytest -q     (ou)     python tests/test_smoke.py
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agents.loader import carregar_agentes  # noqa: E402
from core.application import (  # noqa: E402
    AgentTarget,
    ExecutionDispatcher,
    IntentRouter,
    Orchestrator,
    ResponseComposer,
    TargetRegistry,
    WorkflowEngine,
)
from core.contracts.llm import LLMResponse, ToolCall  # noqa: E402
from core.domain.events import EventType  # noqa: E402
from core.events import InProcessEventBus  # noqa: E402
from core.models import IncomingMessage  # noqa: E402
from core.registry import AgentRegistry  # noqa: E402
from core.router import Router  # noqa: E402
from memory import (  # noqa: E402
    ConversationMemory,
    KnowledgeBaseMemory,
    MemoryFacade,
    PermanentMemory,
    ProjectMemory,
    TemporaryMemory,
)
from memory.seed import seed_if_empty  # noqa: E402
from storage import SQLiteMemory, SQLiteOpsStore  # noqa: E402


class FakeLLM:
    """LLM determinístico (cumpre a porta LLMProvider)."""

    def __init__(self, route_to=None, reply="ok"):
        self.route_to = route_to
        self.reply = reply

    def is_alive(self):
        return True

    def chat(self, messages, tools=None):
        if tools and self.route_to:
            return LLMResponse(
                tool_calls=[ToolCall(name=self.route_to, arguments={"instruction": "faça X"})]
            )
        return LLMResponse(content=self.reply)


def _montar(tmp: Path, llm):
    """Monta o stack completo de memória + orquestração para um teste."""
    mem = SQLiteMemory(tmp / "mem.db")
    ops = SQLiteOpsStore(tmp / "ops.db")
    bus = InProcessEventBus(ops)
    conv = ConversationMemory(mem, 10)
    temp = TemporaryMemory(mem)
    proj = ProjectMemory(mem)
    perm = PermanentMemory(mem)
    kb = KnowledgeBaseMemory(mem)
    seed_if_empty(perm, proj)
    facade = MemoryFacade(conv, temp, proj, perm, kb)

    registry = AgentRegistry()
    for a in carregar_agentes(RAIZ / "agents", llm=llm):
        registry.register(a)

    intent = IntentRouter(llm, registry, Router("secretary", registry.all()), "secretary")
    workflow = WorkflowEngine(registry, ops, bus, facade, "secretary")
    dispatcher = ExecutionDispatcher(TargetRegistry().register(AgentTarget(workflow)))
    composer = ResponseComposer(llm)
    orch = Orchestrator(intent, dispatcher, composer, conv, bus, "gerente")
    return {"orch": orch, "ops": ops, "mem": mem, "kb": kb, "perm": perm,
            "proj": proj, "registry": registry, "bus": bus}


# ----------------------------------------------------------------------
def test_memoria_4_camadas(tmp_path: Path):
    mem = SQLiteMemory(tmp_path / "m.db")
    perm = PermanentMemory(mem)
    proj = ProjectMemory(mem)
    temp = TemporaryMemory(mem)
    kb = KnowledgeBaseMemory(mem)

    seed_if_empty(perm, proj)
    assert not perm.is_empty()
    assert "Zavix.online" in proj.all_projects()

    temp.add("s1", "caminhar 30min")
    assert "caminhar 30min" in temp.today("s1")

    kb.ingest("doc1.md", "O VitrinePro ajuda negócios locais a vender online.")
    achados = kb.search("negócios locais")
    assert achados and "VitrinePro" in achados[0].text


def test_memoria_escopada_por_projeto(tmp_path: Path):
    mem = SQLiteMemory(tmp_path / "m.db")
    perm, proj = PermanentMemory(mem), ProjectMemory(mem)
    conv, temp, kb = ConversationMemory(mem, 10), TemporaryMemory(mem), KnowledgeBaseMemory(mem)
    seed_if_empty(perm, proj)
    facade = MemoryFacade(conv, temp, proj, perm, kb)

    # Agente do Zavix só enxerga a memória do Zavix (não a do VitrinePro).
    ctx = facade.build_context(["Zavix.online"], "s1", "qualquer")
    titulos = {i.title for i in ctx.project_memory}
    assert titulos == {"Zavix.online"}
    assert ctx.permanent  # mas vê a memória permanente


def test_orquestrador_delega_e_rastreia(tmp_path: Path):
    llm = FakeLLM(route_to="financeiro", reply="Resumo financeiro pronto.")
    s = _montar(tmp_path, llm)
    resposta = s["orch"].handle(IncomingMessage("telegram", "1", "como estão minhas vendas?"))
    assert resposta == "Resumo financeiro pronto."
    # A tarefa foi rastreada e concluída.
    feitas = s["ops"].list_by_status("done")
    assert any(t.agent == "financeiro" for t in feitas)


def test_eventos_no_log(tmp_path: Path):
    llm = FakeLLM(route_to="secretary", reply="Organizado!")
    s = _montar(tmp_path, llm)
    s["orch"].handle(IncomingMessage("telegram", "1", "organiza meu dia"))
    eventos = [e.type for _, e in s["ops"].read_since(0, 500)]
    assert EventType.MESSAGE_RECEIVED in eventos
    assert EventType.INTENT_IDENTIFIED in eventos
    assert EventType.AGENT_COMPLETED in eventos
    assert EventType.RESPONSE_COMPOSED in eventos


def test_outbox_alimentado(tmp_path: Path):
    llm = FakeLLM(route_to="secretary", reply="ok")
    s = _montar(tmp_path, llm)
    s["orch"].handle(IncomingMessage("telegram", "1", "oi"))
    pendentes = s["ops"].pending_outbox()
    assert len(pendentes) > 0  # eventos prontos para replicar
    s["ops"].ack_outbox(pendentes[-1][0])
    assert s["ops"].pending_outbox() == []


def test_fallback_sem_toolcalling(tmp_path: Path):
    # route_to=None -> LLM não delega; Router de reserva pega "vídeo" -> mkvideos.
    llm = FakeLLM(route_to=None, reply="Roteiro pronto.")
    s = _montar(tmp_path, llm)
    resposta = s["orch"].handle(IncomingMessage("telegram", "1", "preciso de um vídeo novo"))
    assert resposta == "Roteiro pronto."
    assert any(t.agent == "mkvideos" for t in s["ops"].list_by_status("done"))


def test_lease_eleicao_de_lider(tmp_path: Path):
    ops = SQLiteOpsStore(tmp_path / "ops.db")
    assert ops.acquire("maquina-A", 60) is True
    assert ops.acquire("maquina-B", 60) is False  # A ainda é líder
    assert ops.renew("maquina-A", 60) is True
    assert ops.current().owner == "maquina-A"


def test_loader_12_agentes():
    agentes = carregar_agentes(RAIZ / "agents", llm=FakeLLM())
    nomes = {a.name for a in agentes}
    assert "secretary" in nomes and "orchestrator" not in nomes
    assert len(agentes) == 13


def test_cognicao_dominio_e_eventos():
    """A camada de cognição existe no domínio e nos eventos."""
    from core.domain.events import EventType
    from core.domain.planning import (
        ExecutionReport, Objective, Plan, PlanStep, QualityVerdict, Strategy,
    )

    obj = Objective(text="vender mais no Zavix", session="telegram:1", correlation_id="c1")
    plano = Plan(objective=obj, strategy=Strategy(name="foco-vendas"),
                 steps=[PlanStep(agent="zavix", instruction="revisar produtos")])
    assert plano.steps[0].agent == "zavix"
    assert QualityVerdict(approved=True).approved is True
    assert ExecutionReport(plan_id=plano.id).completed is False

    for ev in ("OBJECTIVE_RECEIVED", "STRATEGY_SELECTED", "PLAN_CREATED",
               "EXECUTION_STARTED", "TASK_TIMEOUT", "EXECUTION_COMPLETED",
               "QUALITY_EVALUATED", "QUALITY_APPROVED", "REEXECUTION_REQUESTED"):
        assert hasattr(EventType, ev)


def test_cognicao_e_esqueleto_nao_implementado():
    """Os 3 componentes existem mas a inteligência ainda NÃO está implementada."""
    from core.cognition import ExecutionManager, QualitySupervisor, StrategicPlanner
    from core.domain.planning import ExecutionReport, Objective, Plan, Strategy

    planner = StrategicPlanner(llm=None, memory_facade=None, intent_router=None, event_bus=None)
    executor = ExecutionManager(workflow_engine=None, event_bus=None)
    supervisor = QualitySupervisor(llm=None, event_bus=None)

    obj = Objective(text="x", session="s", correlation_id="c")
    plano = Plan(objective=obj, strategy=Strategy(name="s"))

    for chamada in (
        lambda: planner.plan(obj),
        lambda: executor.execute(plano),
        lambda: supervisor.review(plano, ExecutionReport(plan_id=plano.id)),
    ):
        try:
            chamada()
            raise AssertionError("deveria levantar NotImplementedError")
        except NotImplementedError:
            pass


if __name__ == "__main__":
    import tempfile

    testes = [
        test_memoria_4_camadas, test_memoria_escopada_por_projeto,
        test_orquestrador_delega_e_rastreia, test_eventos_no_log,
        test_outbox_alimentado, test_fallback_sem_toolcalling,
        test_lease_eleicao_de_lider,
    ]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        base = Path(d)
        for i, t in enumerate(testes):
            sub = base / f"t{i}"
            sub.mkdir()
            t(sub)
        test_loader_11_agentes()
        test_cognicao_dominio_e_eventos()
        test_cognicao_e_esqueleto_nao_implementado()
    print("OK - Todos os smoke tests (v3 + cognicao) passaram!")
