"""
Testes do CEO Mode — Diretor de Operacoes pessoal.

Cobre as 10 capacidades:
  1. Entender o objetivo
  2. Quebrar em fases
  3. Criar tarefas automaticamente
  4. Identificar dependencias
  5. Escolher os agentes ideais
  6. Delegar automaticamente
  7. Acompanhar progresso
  8. Atualizar memoria
  9. Gerar relatorios
 10. Pedir confirmacao apenas para acoes sensiveis

E os 3 exemplos obrigatorios:
  - Quero lancar o ScalaFlow.
  - Quero vender 500 chaveiros em Portugal.
  - Quero criar um SaaS para imobiliarias.
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from database.schema import criar_tabelas, TABELAS
from database.connection import get_connection

_TEMP_DB = str(RAIZ / "data" / "test_ceo_mem.db")


def setup_module():
    criar_tabelas()


def teardown_module():
    conn = get_connection()
    for tabela in TABELAS:
        conn.execute(f"DELETE FROM {tabela}")
    conn.commit()
    if os.path.exists(_TEMP_DB):
        try:
            os.unlink(_TEMP_DB)
        except OSError:
            pass


def _limpar():
    conn = get_connection()
    for tabela in TABELAS:
        conn.execute(f"DELETE FROM {tabela}")
    conn.commit()


def _ceo_com_memoria():
    from memory.memory_system import MemorySystem
    from storage.sqlite_memory_store import SQLiteMemoryStore
    from services.ceo_mode import CeoMode
    if os.path.exists(_TEMP_DB):
        try:
            os.unlink(_TEMP_DB)
        except OSError:
            pass
    ms = MemorySystem(SQLiteMemoryStore(_TEMP_DB))
    return CeoMode(memory=ms), ms


# ======================================================================
#  1. Entender o objetivo
# ======================================================================

def test_1_entender_objetivo():
    from services.ceo_mode import CeoMode
    ceo = CeoMode()

    e = ceo.entender("Quero vender 500 chaveiros em Portugal.")
    assert e["tipo"] == "vendas"
    assert e["numero"] == 500.0
    assert e["unidade"] == "chaveiros"
    assert e["mercado"] == "portugal"

    e2 = ceo.entender("Quero lancar o ScalaFlow.")
    assert e2["tipo"] == "lancamento"
    assert e2["projeto"] == "ScalaFlow"

    e3 = ceo.entender("Quero criar um SaaS para imobiliarias.")
    assert e3["tipo"] == "saas"


# ======================================================================
#  2. Quebrar em fases
# ======================================================================

def test_2_fases():
    from services.ceo_mode import CeoMode
    ceo = CeoMode()
    plano = ceo.planejar("Quero lancar o ScalaFlow.")
    assert len(plano["fases"]) >= 3
    assert plano["fases"][0]["nome"].startswith("1.")


# ======================================================================
#  3. Criar tarefas automaticamente
# ======================================================================

def test_3_criar_tarefas():
    _limpar()
    from services.ceo_mode import CeoMode
    from services.task_manager import TaskManager
    ceo = CeoMode()
    plano = ceo.executar("Quero lancar o ScalaFlow.", "ceo_user",
                         confirmado=True)
    assert len(plano["tarefas"]) >= 5
    tm = TaskManager()
    ids = [t["tarefa_id"] for t in plano["tarefas"] if t.get("tarefa_id")]
    assert len(ids) >= 5
    for tid in ids:
        assert tm.abrir(tid) is not None


# ======================================================================
#  4. Identificar dependencias
# ======================================================================

def test_4_dependencias():
    _limpar()
    from services.ceo_mode import CeoMode
    from repositories.dependencia_repo import DependenciaRepository
    ceo = CeoMode()
    plano = ceo.executar("Quero lancar o ScalaFlow.", "ceo_user",
                         confirmado=True)
    deps = DependenciaRepository().por_usuario("ceo_user")
    assert len(deps) >= 3
    # A primeira tarefa nao depende de ninguem
    t1 = next(t for t in plano["tarefas"] if t["num"] == 1)
    assert t1["depende_de"] == []


# ======================================================================
#  5. Escolher os agentes ideais
# ======================================================================

def test_5_agentes_ideais():
    _limpar()
    from services.ceo_mode import CeoMode
    ceo = CeoMode()
    plano = ceo.planejar("Quero criar um SaaS para imobiliarias.")
    agentes = {t["agente"] for t in plano["tarefas"]}
    # SaaS exige programador, pesquisador, copywriter, vendas, marketing
    assert "programador" in agentes
    assert "pesquisador" in agentes
    assert "vendas" in agentes
    # Pesquisa vem antes do desenvolvimento (agente correto por fase)
    fases = plano["tarefas"]
    pesquisa = next(t for t in fases if t["agente"] == "pesquisador")
    dev = next(t for t in fases if t["agente"] == "programador")
    assert pesquisa["fase"] < dev["fase"]


# ======================================================================
#  6. Delegar automaticamente
# ======================================================================

def test_6_delegar():
    _limpar()
    from services.ceo_mode import CeoMode
    from services.task_manager import TaskManager
    ceo = CeoMode()
    plano = ceo.executar("Quero vender 500 chaveiros em Portugal.",
                         "ceo_user", confirmado=True)
    tm = TaskManager()
    anuncios = next(t for t in plano["tarefas"] if t["agente"] == "marketing")
    real = tm.abrir(anuncios["tarefa_id"])
    assert real["agente"] == "marketing"


# ======================================================================
#  7. Acompanhar progresso
# ======================================================================

def test_7_progresso():
    _limpar()
    from services.ceo_mode import CeoMode
    from services.task_manager import TaskManager
    ceo = CeoMode()
    plano = ceo.executar("Quero lancar o ScalaFlow.", "ceo_user",
                         confirmado=True)
    oid = plano["objetivo_id"]
    prog = ceo.progresso(oid)
    assert prog["progresso_pct"] == 0
    assert prog["total_tarefas"] >= 5

    tm = TaskManager()
    t1 = next(t for t in plano["tarefas"] if t["num"] == 1)
    tm.concluir(t1["tarefa_id"])
    prog2 = ceo.progresso(oid)
    assert prog2["concluidas"] == 1
    assert prog2["progresso_pct"] > 0


# ======================================================================
#  8. Atualizar memoria
# ======================================================================

def test_8_memoria():
    _limpar()
    ceo, ms = _ceo_com_memoria()
    ceo.executar("Quero vender 500 chaveiros em Portugal.", "ceo_user",
                 confirmado=True)
    itens = ms.list_by_user("ceo_user")
    assert len(itens) >= 1
    assert any("chaveiros" in i.content for i in itens)


# ======================================================================
#  9. Gerar relatorios
# ======================================================================

def test_9_relatorio():
    _limpar()
    from services.ceo_mode import CeoMode
    ceo = CeoMode()
    plano = ceo.executar("Quero criar um SaaS para imobiliarias.",
                         "ceo_user", confirmado=True)
    rel = ceo.relatorio(plano["objetivo_id"])
    for campo in ("objetivo", "plano", "fases", "tarefas",
                  "cronograma", "riscos", "proxima_acao", "progresso",
                  "status"):
        assert campo in rel, f"Falta campo {campo}"
    assert rel["proxima_acao"] != ""
    assert rel["status"] in ("planejado", "em_andamento", "concluido")


# ======================================================================
#  10. Pedir confirmacao apenas para acoes sensiveis
# ======================================================================

def test_10_confirmacao_sensivel():
    _limpar()
    from services.ceo_mode import CeoMode
    from services.task_manager import TaskManager

    ceo = CeoMode()
    tm = TaskManager()

    # Sem confirmacao: tarefa sensivel NAO e criada
    plano = ceo.executar("Quero criar um SaaS para imobiliarias.",
                         "ceo_user", confirmado=False)
    sens = [t for t in plano["tarefas"] if t["sensivel"]]
    assert len(sens) >= 1
    for s in sens:
        assert s.get("tarefa_id") is None
    pend = ceo.confirmacoes_pendentes(plano["objetivo_id"])
    assert len(pend) >= 1

    # Nao-sensiveis foram criadas
    nao_sens = [t for t in plano["tarefas"] if not t["sensivel"] and t.get("tarefa_id")]
    assert len(nao_sens) >= 1

    # Com confirmacao: sensiveis entram no plano
    plano2 = ceo.executar("Quero criar um SaaS para imobiliarias.",
                          "ceo_user", confirmado=True)
    sens2 = [t for t in plano2["tarefas"] if t["sensivel"] and t.get("tarefa_id")]
    assert len(sens2) >= 1
    for s in sens2:
        assert tm.abrir(s["tarefa_id"]) is not None


# ======================================================================
#  Exemplos obrigatorios
# ======================================================================

def test_exemplo_scalaflow():
    _limpar()
    from services.ceo_mode import CeoMode
    ceo = CeoMode()
    plano = ceo.executar("Quero lancar o ScalaFlow.", "ceo_user",
                         confirmado=True)
    assert plano["projeto"] == "ScalaFlow"
    assert plano["tipo"] == "lancamento"
    assert plano["objetivo_id"] > 0
    assert any("ScalaFlow" in t["titulo"] for t in plano["tarefas"])
    rel = ceo.relatorio(plano["objetivo_id"])
    assert rel["proxima_acao"] != ""


def test_exemplo_chaveiros_portugal():
    _limpar()
    from services.ceo_mode import CeoMode
    ceo = CeoMode()
    plano = ceo.executar("Quero vender 500 chaveiros em Portugal.",
                         "ceo_user", confirmado=True)
    assert plano["tipo"] == "vendas"
    assert plano["meta"]["numero"] == 500.0
    assert plano["meta"]["mercado"] == "portugal"
    # Campanha de anuncios e sensivel e deve exigir confirmacao
    sens = [t for t in plano["tarefas"] if t["sensivel"]]
    assert len(sens) >= 1


def test_exemplo_saas_imobiliarias():
    _limpar()
    from services.ceo_mode import CeoMode
    ceo = CeoMode()
    plano = ceo.executar("Quero criar um SaaS para imobiliarias.",
                         "ceo_user", confirmado=True)
    assert plano["tipo"] == "saas"
    agentes = {t["agente"] for t in plano["tarefas"]}
    assert "programador" in agentes
    assert "vendas" in agentes


# ======================================================================
#  Integracao com ProjectManager / TaskManager
# ======================================================================

def test_integracao_projeto_tarefas():
    _limpar()
    from services.ceo_mode import CeoMode
    from services.project_manager import ProjectManager
    from services.task_manager import TaskManager
    ceo = CeoMode()
    plano = ceo.executar("Quero vender 500 chaveiros em Portugal.",
                         "ceo_user", confirmado=True)

    pm = ProjectManager()
    tm = TaskManager()

    projeto = pm.abrir(plano["projeto_id"])
    assert projeto is not None
    assert projeto["nome"] == "Chaveiros"

    tarefas_projeto = tm.por_projeto(projeto["id"])
    assert len(tarefas_projeto) >= 1

    # Proxima acao respeita dependencias
    assert ceo.proxima_acao(plano["objetivo_id"]) != ""
