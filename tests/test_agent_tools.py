"""
Testes do sistema de ferramentas dos agentes especialistas.

Cobre:
  - Tool base (matching, execucao)
  - Todas as ferramentas de cada modulo
  - SpecialistAgent com ferramentas (disparo e fallback)
  - Logs indicando qual ferramenta foi usada
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agents.base_specialist import SpecialistAgent, create_agent
from tools.base import Tool


class FakeLLM:
    """LLM deterministico para testes."""

    def __init__(self, reply="resposta do agente"):
        self.reply = reply

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        return LLMResponse(content=self.reply)

    def is_alive(self):
        return True


# ----------------------------------------------------------------------
#  Tool base
# ----------------------------------------------------------------------

def _minha_funcao(texto: str) -> str:
    return f"EXECUTADO: {texto}"


def test_tool_cria():
    tool = Tool("teste", "descricao", ["abc", "def"], _minha_funcao)
    assert tool.name == "teste"
    assert tool.description == "descricao"
    assert tool.keywords == ["abc", "def"]


def test_tool_executa():
    tool = Tool("teste", "", ["x"], _minha_funcao)
    resultado = tool.execute("hello")
    assert resultado == "EXECUTADO: hello"


def test_tool_match_palavra_exata():
    tool = Tool("teste", "", ["legenda"], _minha_funcao)
    assert tool.matches("preciso de uma legenda")
    assert not tool.matches("nao tem nada a ver")


def test_tool_match_substring():
    tool = Tool("teste", "", ["instagram"], _minha_funcao)
    assert tool.matches("post para instagram")
    assert not tool.matches("vamos programar")


def test_tool_match_case_insensitive():
    tool = Tool("teste", "", ["headline"], _minha_funcao)
    assert tool.matches("crie uma HEADLINE")


# ----------------------------------------------------------------------
#  SpecialistAgent com ferramentas
# ----------------------------------------------------------------------

def _ferramenta_legenda(texto: str) -> str:
    return f"LEGENDA CRIADA: {texto}"


def test_agent_com_ferramenta_dispara():
    tool = Tool("criar_legenda", "Cria legenda", ["legenda"], _ferramenta_legenda)
    agente = create_agent("social_media", "SM", "prompt", FakeLLM(), tools=[tool])
    resposta = agente.generate("preciso de uma legenda para instagram")
    assert "LEGENDA CRIADA:" in resposta
    assert "instagram" in resposta


def test_agent_sem_ferramenta_cai_no_llm():
    tool = Tool("criar_legenda", "Cria legenda", ["legenda"], _ferramenta_legenda)
    agente = create_agent("social_media", "SM", "prompt", FakeLLM(), tools=[tool])
    resposta = agente.generate("qual a capital do brasil")
    assert resposta == "resposta do agente"


def test_agent_sem_tools_usa_llm():
    agente = create_agent("geral", "Geral", "prompt", FakeLLM())
    resposta = agente.generate("qual a capital do brasil")
    assert resposta == "resposta do agente"


def test_agent_log_ferramenta_usada():
    """Verifica que a ferramenta correta foi usada (pelo resultado, nao pelo log)."""
    called = {"vezes": 0, "entrada": ""}

    def _rastreador(texto: str) -> str:
        called["vezes"] += 1
        called["entrada"] = texto
        return f"RESULTADO: {texto}"

    tool = Tool("criar_legenda", "Cria legenda", ["legenda"], _rastreador)
    agente = create_agent("social_media", "SM", "prompt", FakeLLM(), tools=[tool])

    resposta = agente.generate("preciso de uma legenda")
    assert called["vezes"] == 1
    assert "legenda" in called["entrada"]
    assert resposta == "RESULTADO: preciso de uma legenda"


# ----------------------------------------------------------------------
#  Todas as ferramentas (verificacao estrutural)
# ----------------------------------------------------------------------

def test_todas_as_ferramentas_social():
    from tools.social_tools import get_tools
    ferramentas = get_tools()
    assert len(ferramentas) == 7
    nomes = {t.name for t in ferramentas}
    assert nomes == {
        "criar_legenda", "criar_hashtags", "criar_calendario",
        "criar_reels_roteiro", "criar_tiktok_roteiro",
        "criar_meta_ads", "criar_google_ads",
    }
    for t in ferramentas:
        assert t.name
        assert t.description
        assert t.keywords
        assert callable(t.fn)


def test_todas_as_ferramentas_copy():
    from tools.copy_tools import get_tools
    ferramentas = get_tools()
    assert len(ferramentas) == 8
    nomes = {t.name for t in ferramentas}
    assert nomes == {
        "pagina_de_vendas", "vsl", "headline", "oferta",
        "email_marketing", "sequencia_emails",
        "copy_whatsapp", "copy_telegram",
    }
    for t in ferramentas:
        assert callable(t.fn)


def test_todas_as_ferramentas_sales():
    from tools.sales_tools import get_tools
    ferramentas = get_tools()
    assert len(ferramentas) == 6
    nomes = {t.name for t in ferramentas}
    assert nomes == {
        "proposta_comercial", "orcamento", "follow_up",
        "quebra_objecoes", "negociacao", "fechamento",
    }
    for t in ferramentas:
        assert callable(t.fn)


def test_todas_as_ferramentas_service():
    from tools.service_tools import get_tools
    ferramentas = get_tools()
    assert len(ferramentas) == 5
    nomes = {t.name for t in ferramentas}
    assert nomes == {
        "responder_cliente", "responder_reclamacao",
        "responder_duvida", "responder_orcamento",
        "atendimento_humanizado",
    }
    for t in ferramentas:
        assert callable(t.fn)


def test_todas_as_ferramentas_research():
    from tools.research_tools import get_tools
    ferramentas = get_tools()
    assert len(ferramentas) == 6
    nomes = {t.name for t in ferramentas}
    assert nomes == {
        "pesquisar_web", "resumir", "analisar",
        "comparar", "analisar_concorrentes", "tendencias",
    }
    for t in ferramentas:
        assert callable(t.fn)


def test_todas_as_ferramentas_coding():
    from tools.coding_tools import get_tools
    ferramentas = get_tools()
    assert len(ferramentas) == 6
    nomes = {t.name for t in ferramentas}
    assert nomes == {
        "gerar_codigo", "corrigir_bugs", "revisar_codigo",
        "criar_api", "criar_testes", "documentar",
    }
    for t in ferramentas:
        assert callable(t.fn)


def test_todas_as_ferramentas_productivity():
    from tools.productivity_tools import get_tools
    ferramentas = get_tools()
    assert len(ferramentas) == 6
    nomes = {t.name for t in ferramentas}
    assert nomes == {
        "planejamento_diario", "checklist",
        "plano_semanal", "plano_mensal",
        "organizar", "dicas_produtividade",
    }
    for t in ferramentas:
        assert callable(t.fn)


# ----------------------------------------------------------------------
#  Contagem total
# ----------------------------------------------------------------------

def test_total_de_ferramentas():
    from tools.social_tools import get_tools as s1
    from tools.copy_tools import get_tools as s2
    from tools.sales_tools import get_tools as s3
    from tools.service_tools import get_tools as s4
    from tools.research_tools import get_tools as s5
    from tools.coding_tools import get_tools as s6
    from tools.productivity_tools import get_tools as s7

    total = (
        len(s1()) + len(s2()) + len(s3()) + len(s4()) +
        len(s5()) + len(s6()) + len(s7())
    )
    assert total == 44, f"Total {total} ferramentas (esperado 44)"


# ----------------------------------------------------------------------
#  Execucao direta
# ----------------------------------------------------------------------

if __name__ == "__main__":
    test_tool_cria()
    test_tool_executa()
    test_tool_match_palavra_exata()
    test_tool_match_substring()
    test_tool_match_case_insensitive()
    test_agent_com_ferramenta_dispara()
    test_agent_sem_ferramenta_cai_no_llm()
    test_agent_sem_tools_usa_llm()
    test_agent_log_ferramenta_usada()
    test_todas_as_ferramentas_social()
    test_todas_as_ferramentas_copy()
    test_todas_as_ferramentas_sales()
    test_todas_as_ferramentas_service()
    test_todas_as_ferramentas_research()
    test_todas_as_ferramentas_coding()
    test_todas_as_ferramentas_productivity()
    test_total_de_ferramentas()
    print("OK - Todos os testes de ferramentas passaram!")
