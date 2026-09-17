"""
Testes do OpenRouterProvider (Fase 2.5) -- sem rede real, sem gastar custo.

Cobre: chat com sucesso, classificacao de erro (timeout, conexao, rate
limit, saldo insuficiente, modelo indisponivel, erro generico) e que o log
de uso nunca contem a API key nem o conteudo do prompt/resposta.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import logging

import pytest
import requests

from llm.openrouter import OpenRouterError, OpenRouterProvider


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


def _provider():
    return OpenRouterProvider(
        api_key="sk-or-chave-fake-de-teste",
        model="openai/gpt-4o-mini",
        tier="economico",
    )


def test_chat_sucesso_parseia_conteudo_e_uso(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return FakeResponse(200, {
            "choices": [{"message": {"content": "Ola! Tudo bem?"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        })

    monkeypatch.setattr(requests, "post", fake_post)
    resp = _provider().chat([{"role": "user", "content": "Oi"}])
    assert resp.content == "Ola! Tudo bem?"
    assert resp.tool_calls == []


def test_chat_timeout_vira_openroutererror_categoria_timeout(monkeypatch):
    def fake_post(*a, **kw):
        raise requests.Timeout("demorou demais")

    monkeypatch.setattr(requests, "post", fake_post)
    with pytest.raises(OpenRouterError) as exc:
        _provider().chat([{"role": "user", "content": "Oi"}])
    assert exc.value.categoria == "timeout"


def test_chat_connection_error_vira_openroutererror_categoria_conexao(monkeypatch):
    def fake_post(*a, **kw):
        raise requests.ConnectionError("sem rede")

    monkeypatch.setattr(requests, "post", fake_post)
    with pytest.raises(OpenRouterError) as exc:
        _provider().chat([{"role": "user", "content": "Oi"}])
    assert exc.value.categoria == "conexao"


def test_chat_rate_limit_429(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResponse(429))
    with pytest.raises(OpenRouterError) as exc:
        _provider().chat([{"role": "user", "content": "Oi"}])
    assert exc.value.categoria == "rate_limit"


def test_chat_saldo_insuficiente_402(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResponse(402))
    with pytest.raises(OpenRouterError) as exc:
        _provider().chat([{"role": "user", "content": "Oi"}])
    assert exc.value.categoria == "saldo_insuficiente"


def test_chat_modelo_indisponivel_404(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResponse(404))
    with pytest.raises(OpenRouterError) as exc:
        _provider().chat([{"role": "user", "content": "Oi"}])
    assert exc.value.categoria == "modelo_indisponivel"


def test_chat_erro_generico_5xx(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResponse(500, text="boom"))
    with pytest.raises(OpenRouterError) as exc:
        _provider().chat([{"role": "user", "content": "Oi"}])
    assert exc.value.categoria == "erro_api"


def test_log_de_uso_nao_vaza_api_key_nem_prompt(monkeypatch, caplog):
    def fake_post(url, json, headers, timeout):
        return FakeResponse(200, {
            "choices": [{"message": {"content": "SEGREDO_DA_RESPOSTA_NAO_DEVE_APARECER"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        })

    monkeypatch.setattr(requests, "post", fake_post)
    with caplog.at_level(logging.INFO):
        _provider().chat([{"role": "user", "content": "PROMPT_SECRETO_NAO_DEVE_APARECER"}])

    texto_log = "\n".join(r.message for r in caplog.records)
    assert "sk-or-chave-fake-de-teste" not in texto_log
    assert "PROMPT_SECRETO_NAO_DEVE_APARECER" not in texto_log
    assert "SEGREDO_DA_RESPOSTA_NAO_DEVE_APARECER" not in texto_log
    assert "OPENROUTER" in texto_log
    assert "openai/gpt-4o-mini" in texto_log


def test_is_alive_true_quando_200(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResponse(200))
    assert _provider().is_alive() is True


def test_is_alive_false_quando_erro_de_rede(monkeypatch):
    def fake_get(*a, **kw):
        raise requests.ConnectionError("sem rede")

    monkeypatch.setattr(requests, "get", fake_get)
    assert _provider().is_alive() is False
