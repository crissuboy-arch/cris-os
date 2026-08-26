"""
Testes do fallback de IA do modulo Prospector (ProspectorLLM).

Regra: AIsa e o provedor principal; se indisponivel, usa o roteador do CRIS OS;
nao duplica provedores (compoe os existentes).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from services.prospector.llm import ProspectorLLM  # noqa: E402


class _MotorChat:
    """Motor simulado que responde JSON (AIsa)."""

    def __call__(self, chave, sistema, usuario, json_mode=True, max_tokens=None):
        return {"slug": "x", "resumo": "ok"}


class _MotorChatQuebrado:
    def __call__(self, chave, sistema, usuario, json_mode=True, max_tokens=None):
        raise RuntimeError("AIsa fora do ar")


class _RouterFake:
    """Router do CRIS OS (porta LLMProvider) que responde texto."""

    def chat(self, messages):
        class _R:
            content = '{"fallback": true}'
        return _R()


def test_aisa_primario():
    llm = ProspectorLLM(motor_chat=_MotorChat(), cris_router=_RouterFake(),
                        chave_fn=lambda: "sk-teste")
    out = llm.chat("", "sys", "usr")
    assert out == {"slug": "x", "resumo": "ok"}


def test_fallback_quando_aisa_falha():
    llm = ProspectorLLM(motor_chat=_MotorChatQuebrado(), cris_router=_RouterFake(),
                        chave_fn=lambda: "sk-teste")
    out = llm.chat("", "sys", "usr")
    assert out == {"fallback": True}


def test_fallback_sem_chave():
    llm = ProspectorLLM(motor_chat=_MotorChat(), cris_router=_RouterFake(),
                        chave_fn=lambda: "")
    out = llm.chat("", "sys", "usr")
    assert out == {"fallback": True}


def test_aisa_injetada_por_parametro_tem_prioridade():
    """O chave passada explicitamente no chat tem prioridade sobre a chave_fn."""
    llm = ProspectorLLM(motor_chat=_MotorChat(), cris_router=_RouterFake(),
                        chave_fn=lambda: "outra-chave")
    out = llm.chat("chave-explicita", "sys", "usr")
    assert out == {"slug": "x", "resumo": "ok"}


def test_sem_aisa_e_sem_router_levanta():
    llm = ProspectorLLM(motor_chat=None, cris_router=None, chave_fn=lambda: "")
    try:
        llm.chat("", "sys", "usr")
    except RuntimeError as exc:
        assert "sem provedor" in str(exc)
    else:
        raise AssertionError("Deveria levantar RuntimeError")


def test_fallback_texto_sem_json():
    class _RTexto:
        def chat(self, messages):
            class _R:
                content = "resposta livre sem json"
            return _R()

    llm = ProspectorLLM(motor_chat=None, cris_router=_RTexto(), chave_fn=lambda: "")
    out = llm.chat("", "sys", "usr", json_mode=True)
    assert out == {}  # nao achou {..}, devolve {} em json_mode
    out2 = llm.chat("", "sys", "usr", json_mode=False)
    assert out2 == "resposta livre sem json"
