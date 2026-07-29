"""
Testes do sistema de memoria e gerenciadores do CRIS OS.

Cobre:
  - Criacao de tabelas
  - MemoryManager (conversas, preferencias)
  - ProjectManager (CRUD projetos)
  - ClientManager (CRUD clientes)
  - TaskManager (CRUD tarefas)
  - PromptLibrary (CRUD prompts)
  - ConfigManager (get/set configuracoes)
  - ActivityLogger (registro de atividades)
  - SpecialistAgent com memoria
"""

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from database.schema import criar_tabelas, TABELAS
from database.connection import get_connection, close_connection


# ----------------------------------------------------------------------
#  Setup / Teardown
# ----------------------------------------------------------------------

def setup_module():
    """Garante que as tabelas existem antes de qualquer teste."""
    criar_tabelas()


def teardown_module():
    """Limpa dados de teste apos todos os testes."""
    conn = get_connection()
    for tabela in TABELAS:
        conn.execute(f"DELETE FROM {tabela}")
    conn.commit()


def _limpar():
    """Limpa todas as tabelas entre testes."""
    conn = get_connection()
    for tabela in TABELAS:
        conn.execute(f"DELETE FROM {tabela}")
    conn.commit()


# ----------------------------------------------------------------------
#  Schema
# ----------------------------------------------------------------------

def test_criar_tabelas():
    tabelas = criar_tabelas()
    for t in TABELAS:
        assert t in tabelas, f"Tabela {t} nao encontrada"


def test_tabelas_existem():
    conn = get_connection()
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    existentes = {r["name"] for r in cur.fetchall()}
    for t in TABELAS:
        assert t in existentes, f"Tabela {t} deveria existir"


# ======================================================================
#  MemoryManager
# ======================================================================

def test_memory_salvar_conversa():
    _limpar()
    from services.memory_manager import MemoryManager
    mm = MemoryManager()
    msg_id = mm.salvar_conversa("user1", "user", "Ola", "social_media")
    assert msg_id > 0

    hist = mm.historico("user1")
    assert len(hist) == 1
    assert hist[0]["conteudo"] == "Ola"
    assert hist[0]["agente"] == "social_media"


def test_memory_historico_por_agente():
    _limpar()
    mm = __import__("services.memory_manager", fromlist=["MemoryManager"]).MemoryManager()
    mm.salvar_conversa("user1", "user", "Post", "social_media")
    mm.salvar_conversa("user1", "user", "Codigo", "programador")

    hist = mm.historico_por_agente("user1", "social_media")
    assert len(hist) == 1
    assert hist[0]["conteudo"] == "Post"


def test_memory_contexto_recente():
    _limpar()
    mm = __import__("services.memory_manager", fromlist=["MemoryManager"]).MemoryManager()
    mm.salvar_conversa("user1", "user", "Primeira msg", "geral")
    mm.salvar_conversa("user1", "assistant", "Resposta", "geral")

    ctx = mm.contexto_recente("user1", limite=5)
    assert "Primeira msg" in ctx
    assert "Resposta" in ctx


def test_memory_preferencias():
    _limpar()
    mm = __import__("services.memory_manager", fromlist=["MemoryManager"]).MemoryManager()
    mm.definir_preferencia("user1", "tema", "escuro")
    assert mm.obter_preferencia("user1", "tema") == "escuro"
    assert mm.obter_preferencia("user1", "inexistente", "padrao") == "padrao"

    pref = mm.listar_preferencias("user1")
    assert len(pref) == 1
    assert pref[0]["chave"] == "tema"


def test_memory_limpar_conversas():
    _limpar()
    mm = __import__("services.memory_manager", fromlist=["MemoryManager"]).MemoryManager()
    mm.salvar_conversa("user1", "user", "Msg", "agente")
    assert mm.limpar_conversas("user1") is True
    assert len(mm.historico("user1")) == 0


# ======================================================================
#  ProjectManager
# ======================================================================

def test_project_crud():
    _limpar()
    from services.project_manager import ProjectManager
    pm = ProjectManager()

    # Criar
    proj = pm.criar("user1", "Meu Projeto", "Descricao teste")
    assert proj["nome"] == "Meu Projeto"
    pid = proj["id"]

    # Listar
    lista = pm.listar("user1")
    assert any(p["id"] == pid for p in lista)

    # Abrir
    proj2 = pm.abrir(pid)
    assert proj2 is not None
    assert proj2["nome"] == "Meu Projeto"

    # Atualizar
    assert pm.atualizar(pid, nome="Projeto Atualizado")
    proj3 = pm.abrir(pid)
    assert proj3["nome"] == "Projeto Atualizado"

    # Arquivar
    assert pm.arquivar(pid)
    proj4 = pm.abrir(pid)
    assert proj4["status"] == "arquivado"

    # Excluir
    assert pm.excluir(pid)
    assert pm.abrir(pid) is None


# ======================================================================
#  ClientManager
# ======================================================================

def test_client_crud():
    _limpar()
    from services.client_manager import ClientManager
    cm = ClientManager()

    cliente = cm.criar("user1", "Joao", "Empresa X", "119999", "joao@x.com")
    assert cliente["nome"] == "Joao"
    cid = cliente["id"]

    lista = cm.listar("user1")
    assert any(c["id"] == cid for c in lista)

    cm.atualizar(cid, nome="Joao Silva")
    c2 = cm.abrir(cid)
    assert c2["nome"] == "Joao Silva"

    busca = cm.buscar("user1", "Joao")
    assert len(busca) >= 1

    assert cm.excluir(cid)
    assert cm.abrir(cid) is None


# ======================================================================
#  TaskManager
# ======================================================================

def test_task_crud():
    _limpar()
    from services.task_manager import TaskManager
    tm = TaskManager()

    tarefa = tm.criar("user1", "Fazer relatorio", "Relatorio mensal",
                       "alta", "2026-08-01", "Cris")
    assert tarefa["titulo"] == "Fazer relatorio"
    tid = tarefa["id"]

    pendentes = tm.pendentes("user1")
    assert any(t["id"] == tid for t in pendentes)

    assert tm.concluir(tid)
    t2 = tm.abrir(tid)
    assert t2["status"] == "concluida"

    assert tm.excluir(tid)
    assert tm.abrir(tid) is None


def test_task_por_projeto():
    _limpar()
    from services.project_manager import ProjectManager
    from services.task_manager import TaskManager

    pm = ProjectManager()
    tm = TaskManager()

    proj = pm.criar("user1", "Projeto Tarefas")
    tm.criar("user1", "Task 1", projeto_id=proj["id"])
    tm.criar("user1", "Task 2", projeto_id=proj["id"])

    tasks = tm.por_projeto(proj["id"])
    assert len(tasks) == 2


# ======================================================================
#  PromptLibrary
# ======================================================================

def test_prompt_library():
    _limpar()
    from services.prompt_library import PromptLibrary
    pl = PromptLibrary()

    prompt = pl.adicionar("user1", "Prompt de Vendas", "Conteudo do prompt",
                           "vendas", favorito=True)
    assert prompt["titulo"] == "Prompt de Vendas"
    pid = prompt["id"]

    favs = pl.favoritos("user1")
    assert any(p["id"] == pid for p in favs)

    busca = pl.buscar("user1", "Vendas")
    assert len(busca) >= 1

    pl.alternar_favorito(pid)
    p2 = __import__("repositories.prompt_repo", fromlist=["PromptRepository"]).PromptRepository().get_by_id(pid)
    assert p2["favorito"] == 0

    assert pl.excluir(pid)
    assert pl.buscar("user1", "Vendas") == []


# ======================================================================
#  ConfigManager
# ======================================================================

def test_config_manager():
    _limpar()
    from services.config_manager import ConfigManager, DEFAULT_CONFIG
    cm = ConfigManager()

    configs = cm.listar("user1")
    assert configs["idioma"] == "pt-BR"
    assert configs["temperatura"] == "0.7"

    cm.set("user1", "temperatura", "0.5")
    assert cm.get("user1", "temperatura") == "0.5"

    cm.resetar("user1")
    assert cm.get("user1", "temperatura") == "0.7"


# ======================================================================
#  ActivityLogger
# ======================================================================

def test_activity_logger():
    _limpar()
    from services.activity_logger import ActivityLogger
    al = ActivityLogger()

    al.log("user1", "social_media", "criar_legenda", "llama3.1", 150)
    al.log("user1", "programador", "", "llama3.1", 2000, "timeout")

    ultimos = al.ultimos(5)
    assert len(ultimos) == 2

    por_agente = al.por_agente("social_media")
    assert len(por_agente) == 1

    erros = al.erros()
    assert len(erros) == 1
    assert erros[0]["erro"] == "timeout"


# ======================================================================
#  SpecialistAgent com memoria
# ======================================================================

class _FakeLLMMemoria:
    def __init__(self, reply="resposta"):
        self.reply = reply

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        return LLMResponse(content=self.reply)

    def is_alive(self):
        return True


def test_agent_com_memoria_salva_conversa():
    _limpar()
    from agents.base_specialist import create_agent
    from services.memory_manager import MemoryManager

    mm = MemoryManager()
    agente = create_agent("teste", "Teste", "prompt",
                          _FakeLLMMemoria(), memory=mm, usuario_id="mem_user")

    agente.generate("Ola mundo")

    hist = mm.historico("mem_user")
    # Deve ter: user + assistant
    papeis = [h["papel"] for h in hist]
    assert "user" in papeis
    assert "assistant" in papeis


# ======================================================================
#  Execucao direta
# ======================================================================

if __name__ == "__main__":
    setup_module()

    test_criar_tabelas()
    test_tabelas_existem()
    test_memory_salvar_conversa()
    test_memory_historico_por_agente()
    test_memory_contexto_recente()
    test_memory_preferencias()
    test_memory_limpar_conversas()
    test_project_crud()
    test_client_crud()
    test_task_crud()
    test_task_por_projeto()
    test_prompt_library()
    test_config_manager()
    test_activity_logger()
    test_agent_com_memoria_salva_conversa()

    teardown_module()
    print("OK - Todos os testes de memoria passaram!")
