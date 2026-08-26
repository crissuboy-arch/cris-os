"""
Testes obrigatorios — gestao de tarefas, planejamento, lembretes, memoria,
Telegram e acoes sensiveis com confirmacao.

Cenarios cobertos:
  1. Criar tarefa
  2. Editar tarefa
  3. Concluir tarefa
  4. Cancelar tarefa
  5. Tarefa atrasada
  6. Prioridade
  7. Isolamento entre usuarios
  8. Tarefa por projeto
  9. Delegacao para agente
 10. Planejamento diario
 11. Revisao semanal
 12. Recuperacao de contexto
 13. Lembrete
 14. Recorrencia
 15. Cancelamento de lembrete
 16. Memoria
 17. Telegram
 18. Acao sensivel com confirmacao
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from database.schema import criar_tabelas, TABELAS
from database.connection import get_connection, close_connection


def setup_module():
    criar_tabelas()


def teardown_module():
    conn = get_connection()
    for tabela in TABELAS:
        conn.execute(f"DELETE FROM {tabela}")
    conn.commit()


def _limpar():
    conn = get_connection()
    for tabela in TABELAS:
        conn.execute(f"DELETE FROM {tabela}")
    conn.commit()


# ======================================================================
#  1. Criar tarefa
# ======================================================================

def test_1_criar_tarefa():
    _limpar()
    from services.task_manager import TaskManager
    tm = TaskManager()
    tarefa = tm.criar("u1", "Escrever relatorio", "Relatorio mensal",
                      "alta", "2026-08-05", "Cris")
    assert tarefa["titulo"] == "Escrever relatorio"
    assert tarefa["status"] == "pendente"
    assert tarefa["prioridade"] == "alta"
    assert tm.abrir(tarefa["id"]) is not None


# ======================================================================
#  2. Editar tarefa
# ======================================================================

def test_2_editar_tarefa():
    _limpar()
    from services.task_manager import TaskManager
    tm = TaskManager()
    tarefa = tm.criar("u1", "Titulo antigo", prioridade="baixa")
    assert tm.atualizar(tarefa["id"], titulo="Titulo novo", prioridade="alta")
    t = tm.abrir(tarefa["id"])
    assert t["titulo"] == "Titulo novo"
    assert t["prioridade"] == "alta"


# ======================================================================
#  3. Concluir tarefa
# ======================================================================

def test_3_concluir_tarefa():
    _limpar()
    from services.task_manager import TaskManager
    tm = TaskManager()
    tarefa = tm.criar("u1", "Entregar projeto")
    assert tm.concluir(tarefa["id"])
    assert tm.abrir(tarefa["id"])["status"] == "concluida"


# ======================================================================
#  4. Cancelar tarefa
# ======================================================================

def test_4_cancelar_tarefa():
    _limpar()
    from services.task_manager import TaskManager
    tm = TaskManager()
    tarefa = tm.criar("u1", "Tarefa desnecessaria")
    assert tm.cancelar(tarefa["id"])
    assert tm.abrir(tarefa["id"])["status"] == "cancelada"


# ======================================================================
#  5. Tarefa atrasada
# ======================================================================

def test_5_tarefa_atrasada():
    _limpar()
    from datetime import datetime, timedelta
    from services.task_manager import TaskManager
    tm = TaskManager()
    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    tm.criar("u1", "Vencida ontem", prazo=ontem)
    tm.criar("u1", "Para amanha", prazo=amanha)
    tm.criar("u1", "Sem prazo")
    atrasadas = tm.atrasadas("u1")
    titulos = [t["titulo"] for t in atrasadas]
    assert "Vencida ontem" in titulos
    assert "Para amanha" not in titulos
    assert "Sem prazo" not in titulos


# ======================================================================
#  6. Prioridade
# ======================================================================

def test_6_prioridade_ordena_pendentes():
    _limpar()
    from services.task_manager import TaskManager
    tm = TaskManager()
    tm.criar("u1", "Baixa", prioridade="baixa")
    tm.criar("u1", "Alta", prioridade="alta")
    tm.criar("u1", "Media", prioridade="media")
    pendentes = tm.pendentes("u1")
    assert [t["titulo"] for t in pendentes[:3]] == ["Alta", "Media", "Baixa"]


# ======================================================================
#  7. Isolamento entre usuarios
# ======================================================================

def test_7_isolamento_entre_usuarios():
    _limpar()
    from services.task_manager import TaskManager
    tm = TaskManager()
    tm.criar("u1", "Tarefa da Cris")
    tm.criar("u2", "Tarefa de outro")
    assert len(tm.listar("u1")) == 1
    assert len(tm.listar("u2")) == 1
    assert tm.listar("u1")[0]["titulo"] == "Tarefa da Cris"


# ======================================================================
#  8. Tarefa por projeto
# ======================================================================

def test_8_tarefa_por_projeto():
    _limpar()
    from services.project_manager import ProjectManager
    from services.task_manager import TaskManager
    pm = ProjectManager()
    tm = TaskManager()
    proj = pm.criar("u1", "Projeto AP Obras")
    tm.criar("u1", "Task A", projeto_id=proj["id"])
    tm.criar("u1", "Task B", projeto_id=proj["id"])
    tm.criar("u1", "Task solta")
    tasks = tm.por_projeto(proj["id"])
    assert len(tasks) == 2


# ======================================================================
#  9. Delegacao para agente
# ======================================================================

def test_9_delegacao_para_agente():
    _limpar()
    from services.task_manager import TaskManager
    tm = TaskManager()
    tarefa = tm.criar("u1", "Criar anuncios da Objetiva Metal")
    delegada = tm.delegar(tarefa["id"], responsavel="social_media",
                          agente="social_media")
    assert delegada["agente"] == "social_media"
    assert delegada["responsavel"] == "social_media"


# ======================================================================
#  10. Planejamento diario
# ======================================================================

def test_10_planejamento_diario():
    _limpar()
    from services.project_manager import ProjectManager
    from services.task_manager import TaskManager
    pm = ProjectManager()
    tm = TaskManager()
    proj = pm.criar("u1", "AP Obras")
    tm.criar("u1", "Terminar site AP Obras", prioridade="alta",
             prazo="2026-08-01", projeto_id=proj["id"])
    tm.criar("u1", "Responder cliente", prioridade="media")

    # Ordena por prioridade e prazo, como o endpoint /planejamento/diario
    pendentes = tm.pendentes("u1")
    assert pendentes[0]["prioridade"] == "alta"
    assert len(pendentes) == 2
    assert pendentes[0]["projeto_id"] == proj["id"]


# ======================================================================
#  11. Revisao semanal
# ======================================================================

def test_11_revisao_semanal():
    _limpar()
    from services.task_manager import TaskManager
    tm = TaskManager()
    tm.criar("u1", "Tarefa 1", prioridade="alta")
    tm.criar("u1", "Tarefa 2", prioridade="media")
    tarefa = tm.criar("u1", "Tarefa 3", prioridade="baixa")
    tm.concluir(tarefa["id"])
    rev = tm.revisao_semanal("u1")
    assert rev["total_tarefas"] == 3
    assert rev["pendentes"] == 2
    assert rev["concluidas_semana"] >= 1
    assert rev["por_prioridade"].get("alta") == 1


# ======================================================================
#  12. Recuperacao de contexto
# ======================================================================

def test_12_recuperacao_de_contexto():
    _limpar()
    from channels.telegram.persistence import TelegramPersistenceService
    from channels.telegram.conversation import ConversationManager

    persistence = TelegramPersistenceService()
    cm = ConversationManager({}, persistence_service=persistence)
    cm._persist_exchange("user-telegram", "ola", "tudo bem?", "geral")
    restaurado = cm.restore_context("user-telegram", limit=10)
    assert restaurado >= 1
    history = cm.context_manager.get_history("user-telegram", 10)
    assert any(m["content"] == "ola" for m in history)


# ======================================================================
#  13. Lembrete
# ======================================================================

def test_13_lembrete():
    _limpar()
    from services.reminder_manager import ReminderManager
    rm = ReminderManager()
    lembrete = rm.criar("u1", "Reuniao com cliente",
                        "2026-08-02T09:00:00")
    assert lembrete["titulo"] == "Reuniao com cliente"
    assert lembrete["status"] == "ativo"
    assert len(rm.listar("u1")) == 1


# ======================================================================
#  14. Recorrencia
# ======================================================================

def test_14_recorrencia():
    _limpar()
    from datetime import datetime, timedelta
    from services.reminder_manager import ReminderManager
    rm = ReminderManager()
    data = (datetime.now() - timedelta(minutes=5)).isoformat()
    rm.criar("u1", "Malhar", data, recorrencia="diaria")
    devidos = rm.devidos("u1")
    assert len(devidos) == 1
    processados = rm.processar_devidos("u1")
    assert len(processados) == 1
    # A recorrencia reagenda para o dia seguinte (mesmo horario)
    reagendados = rm.listar("u1")
    assert reagendados[0]["status"] == "ativo"
    assert reagendados[0]["data_hora"] != data


# ======================================================================
#  15. Cancelamento de lembrete
# ======================================================================

def test_15_cancelar_lembrete():
    _limpar()
    from services.reminder_manager import ReminderManager
    rm = ReminderManager()
    lembrete = rm.criar("u1", "Lembrete temporario",
                        "2026-08-03T10:00:00")
    assert rm.cancelar(lembrete["id"])
    assert rm.listar("u1") == []


# ======================================================================
#  16. Memoria
# ======================================================================

def test_16_memoria():
    _limpar()
    from core.models import MemoryItem
    from storage.sqlite_memory_store import SQLiteMemoryStore
    from memory.memory_system import MemorySystem

    db_path = str(RAIZ / "data" / "test_memory_tarefas.db")
    import os
    if os.path.exists(db_path):
        os.unlink(db_path)
    store = SQLiteMemoryStore(db_path)
    ms = MemorySystem(store)
    ms.remember("o preco do chaveiro e 4,90 EUR",
                user_id="mem_user", workspace="default")
    results = ms.query("qual o preco do chaveiro", user_id="mem_user")
    assert any("4,90" in r.content for r in results)
    store.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


# ======================================================================
#  17. Telegram
# ======================================================================

def test_17_telegram_seleciona_agente():
    _limpar()
    from channels.telegram.conversation import (
        NaturalLanguageInterpreter, UserContext,
    )
    interp = NaturalLanguageInterpreter()

    i = interp.interpret(
        "crie uma legenda para o instagram da Objetiva Metal",
        UserContext(user_id="u1"),
    )
    assert i.agent_hint == "social_media"

    i2 = interp.interpret(
        "responder uma cliente sobre o orcamento",
        UserContext(user_id="u1"),
    )
    assert i2.agent_hint in ("vendas", "atendimento")

    # Delegacao para marketing (anuncio)
    i4 = interp.interpret(
        "criar anuncios para a Objetiva Metal",
        UserContext(user_id="u1"),
    )
    assert i4.agent_hint == "marketing"


# ======================================================================
#  18. Acao sensivel com confirmacao
# ======================================================================

def test_18_acao_sensivel_com_confirmacao():
    from channels.telegram.utils import ConfirmationUtils
    from channels.telegram.conversation import ConfirmationGateway

    gw = ConfirmationGateway()
    entry = gw.create_confirmation(
        user_id="u1",
        step_name="enviar_fatura",
        effect="sensitive",
        summary="Enviar fatura de R$ 5.000 para o cliente",
        data={"valor": 5000},
    )
    # Sem confirmacao -> pendente
    pendentes = gw.get_user_pending_confirmations("u1")
    assert len(pendentes) == 1

    # Aprovacao
    ok, status, approved = gw.approve_confirmation(entry.confirmation_id, "u1")
    assert ok and status == "approved"

    # Rejeicao de outra acao sensivel
    entry2 = gw.create_confirmation(
        user_id="u1",
        step_name="excluir_projeto",
        effect="sensitive",
        summary="Excluir projeto AP Obras",
    )
    ok2, status2, _ = gw.reject_confirmation(entry2.confirmation_id, "u1")
    assert ok2 and status2 == "rejected"

    # needs_confirmation bloqueia nova acao sensivel pendente do mesmo passo
    assert gw.needs_confirmation("u1", "enviar_fatura", "sensitive") is False
    gw.create_confirmation(
        user_id="u1",
        step_name="cancelar_conta",
        effect="sensitive",
        summary="Cancelar conta do fornecedor",
    )
    assert gw.needs_confirmation("u1", "cancelar_conta", "sensitive") is True
