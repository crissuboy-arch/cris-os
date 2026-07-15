"""
Caracterização (Onda 1 / B0, atualizado no B6) — Router (fallback por palavra-chave).
As keywords agora vêm dos manifests; o Router é montado com os agentes carregados.
Mesmas rotas de antes (cada caso casa com um único agente -> ordem irrelevante).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agents.loader import carregar_agentes  # noqa: E402
from core.router import Router  # noqa: E402


class _LLM:
    def is_alive(self):
        return True

    def chat(self, messages, tools=None):
        return None


def _router():
    return Router("secretary", carregar_agentes(RAIZ / "agents", llm=_LLM()))


def test_default_when_no_keyword():
    assert _router().route("oi, tudo bem?") == "secretary"


def test_keyword_routes():
    r = _router()
    casos = {
        "preciso editar um vídeo": "mkvideos",
        "dúvida do cliente": "atendimento",
        "como vão as vendas?": "financeiro",
        "fazer um post no instagram": "social-media",
        "minha loja zavix": "zavix",
        "pesquisar concorrente": "pesquisador",
    }
    for texto, alvo in casos.items():
        assert r.route(texto) == alvo, (texto, r.route(texto))


if __name__ == "__main__":
    test_default_when_no_keyword()
    test_keyword_routes()
    print("OK - test_router")
