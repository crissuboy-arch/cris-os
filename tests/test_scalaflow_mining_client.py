"""
Testes do ScalaFlow Mining Client (`core/scalaflow_mining_client.py`, Etapa
23) -- cliente HTTP server-to-server para o endpoint de mineração já em
produção no ScalaFlow. ZERO chamada de rede real: todo `requests.post` é
substituído por um fake determinístico.

Cobre explicitamente:
  - fonte inválida / termo vazio -> INVALID_REQUEST, nunca chama a rede;
  - sem configuração (URL/secret ausente) -> NOT_CONFIGURED, nunca chama a
    rede, nunca finge sucesso;
  - 2xx -> SUCCESS;
  - 400 -> INVALID_REQUEST, nunca retryable;
  - 401/403 -> AUTH_ERROR, nunca expõe o secret, nunca retryable;
  - 429 -> RATE_LIMITED, nunca retryable (nunca tenta contornar);
  - 5xx -> TRANSIENT_ERROR, retryable=True;
  - erro de rede/timeout -> TRANSIENT_ERROR, retryable=True, sem crash;
  - nenhum retry/loop automático acontece dentro do próprio cliente (uma
    chamada = uma requisição HTTP, no máximo).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from config.settings import settings
from core.scalaflow_mining_client import FONTES_MINERACAO_VALIDAS, solicitar_mineracao


class FakeResponse:
    def __init__(self, status_code: int, corpo: dict | None = None, texto_json_invalido: bool = False):
        self.status_code = status_code
        self._corpo = corpo or {}
        self._invalido = texto_json_invalido

    def json(self):
        if self._invalido:
            raise ValueError("corpo não é JSON")
        return self._corpo


@pytest.fixture(autouse=True)
def _configurado(monkeypatch):
    monkeypatch.setattr(settings, "SCALAFLOW_MINING_URL", "https://scalaflow.exemplo.test/api/integrations/mining/run")
    monkeypatch.setattr(settings, "CRIS_OS_MINING_SECRET", "secret-de-teste-nunca-real")
    monkeypatch.setattr(settings, "SCALAFLOW_MINING_TIMEOUT", 5)


def test_fontes_validas_sao_exatamente_as_quatro_esperadas():
    assert FONTES_MINERACAO_VALIDAS == {"tiktok", "instagram", "youtube", "google_trends"}


def test_fonte_invalida_nunca_chama_a_rede(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("nao deveria chamar a rede com fonte invalida")
    monkeypatch.setattr("requests.post", _boom)

    resultado = solicitar_mineracao("pinterest", "automação")
    assert resultado.ok is False
    assert resultado.status == "INVALID_REQUEST"
    assert resultado.retryable is False


def test_termo_vazio_nunca_chama_a_rede(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("nao deveria chamar a rede com termo vazio")
    monkeypatch.setattr("requests.post", _boom)

    resultado = solicitar_mineracao("tiktok", "   ")
    assert resultado.ok is False
    assert resultado.status == "INVALID_REQUEST"


def test_sem_configuracao_nunca_chama_a_rede_nunca_finge_sucesso(monkeypatch):
    monkeypatch.setattr(settings, "CRIS_OS_MINING_SECRET", "")

    def _boom(*a, **k):
        raise AssertionError("nao deveria chamar a rede sem CRIS_OS_MINING_SECRET configurado")
    monkeypatch.setattr("requests.post", _boom)

    resultado = solicitar_mineracao("tiktok", "automação")
    assert resultado.ok is False
    assert resultado.status == "NOT_CONFIGURED"
    assert resultado.retryable is False


def test_sucesso_2xx(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(200, {"inserted": 5, "source": "tiktok"}))
    resultado = solicitar_mineracao("tiktok", "automação")
    assert resultado.ok is True
    assert resultado.status == "SUCCESS"
    assert resultado.retryable is False
    assert resultado.dados == {"inserted": 5, "source": "tiktok"}


def test_400_marca_invalid_request_nunca_retryable(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(400, {}))
    resultado = solicitar_mineracao("tiktok", "automação")
    assert resultado.status == "INVALID_REQUEST"
    assert resultado.retryable is False


@pytest.mark.parametrize("status_code", [401, 403])
def test_401_403_marca_auth_error_nunca_expoe_secret_nunca_retryable(monkeypatch, status_code):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(status_code, {}))
    resultado = solicitar_mineracao("instagram", "N8N")
    assert resultado.status == "AUTH_ERROR"
    assert resultado.retryable is False
    assert "secret-de-teste-nunca-real" not in (resultado.erro or "")


def test_429_marca_rate_limited_nunca_retryable_nunca_contorna(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(429, {}))
    resultado = solicitar_mineracao("youtube", "automação")
    assert resultado.status == "RATE_LIMITED"
    assert resultado.retryable is False


@pytest.mark.parametrize("status_code", [500, 502, 503, 504])
def test_5xx_marca_transient_error_retryable(monkeypatch, status_code):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(status_code, {}))
    resultado = solicitar_mineracao("google_trends", "automação")
    assert resultado.status == "TRANSIENT_ERROR"
    assert resultado.retryable is True


def test_erro_de_rede_nao_crasha_marca_transient_retryable(monkeypatch):
    import requests

    def _boom(*a, **k):
        raise requests.exceptions.ConnectionError("falha simulada de rede")
    monkeypatch.setattr("requests.post", _boom)

    resultado = solicitar_mineracao("tiktok", "automação")
    assert resultado.status == "TRANSIENT_ERROR"
    assert resultado.retryable is True


def test_timeout_nao_crasha_marca_transient_retryable(monkeypatch):
    import requests

    def _boom(*a, **k):
        raise requests.exceptions.Timeout("timeout simulado")
    monkeypatch.setattr("requests.post", _boom)

    resultado = solicitar_mineracao("tiktok", "automação")
    assert resultado.status == "TRANSIENT_ERROR"
    assert resultado.retryable is True


def test_json_invalido_na_resposta_de_sucesso_nao_crasha(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(200, texto_json_invalido=True))
    resultado = solicitar_mineracao("tiktok", "automação")
    assert resultado.ok is True
    assert resultado.dados == {}


def test_uma_chamada_solicitar_mineracao_faz_no_maximo_uma_requisicao_http(monkeypatch):
    """Nunca faz retry/loop dentro do proprio cliente -- uma solicitacao,
    uma chamada de rede, no maximo."""
    chamadas = []

    def _contar(*a, **k):
        chamadas.append(1)
        return FakeResponse(503, {})
    monkeypatch.setattr("requests.post", _contar)

    solicitar_mineracao("tiktok", "automação")
    assert len(chamadas) == 1


def test_envia_source_term_limit_no_payload(monkeypatch):
    capturado = {}

    def _capturar(url, json=None, headers=None, timeout=None):
        capturado["url"] = url
        capturado["json"] = json
        capturado["headers"] = headers
        return FakeResponse(200, {})
    monkeypatch.setattr("requests.post", _capturar)

    solicitar_mineracao("google_trends", "N8N", limit=15)

    assert capturado["json"] == {"source": "google_trends", "term": "N8N", "limit": 15}
    assert capturado["headers"]["Authorization"] == "Bearer secret-de-teste-nunca-real"
    assert capturado["url"] == settings.SCALAFLOW_MINING_URL


def test_nenhuma_chamada_http_real_neste_arquivo(monkeypatch):
    import requests

    def _boom(*a, **k):
        raise AssertionError("teste nunca deveria fazer chamada HTTP real")
    monkeypatch.setattr(requests, "post", _boom)
    monkeypatch.setattr(settings, "CRIS_OS_MINING_SECRET", "")

    solicitar_mineracao("tiktok", "automação")
