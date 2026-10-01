"""
Testes do AthenaAdapter (`core/athena_adapter.py`) -- executor ATHENA via ponte
HTTP local da Athena (POST/GET /v1/ordens). ZERO chamada de rede real: todo
`requests.post`/`requests.get` é substituído por um fake determinístico.

Cobre: sem token nunca chama a rede; registro e vocabulário (aditivos);
roteamento fixo inalterado (nenhum asset vai para ATHENA sozinho); payload com
handoff_id + Idempotency-Key = work_order_id; mapeamento de estados;
COMPLETED só com output real; 401/403/409/422 permanentes; rede/429/5xx
transitórios; marcador RUNNING do runner aceito; token nunca exposto.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest
import requests

from config.settings import settings
from core import production_router
from core.athena_adapter import AthenaAdapter
from core.executor_adapter import EXECUTOR_REGISTRY, AdapterNaoConectado, obter_adapter
from memory.project_brain import PRODUCTION_EXECUTOR_TYPES_VALIDOS, ProductionWorkOrder

TOKEN = "token-de-teste-athena-nunca-real"


class FakeResponse:
    def __init__(self, status_code, corpo=None, json_invalido=False):
        self.status_code = status_code
        self._corpo = corpo or {}
        self._invalido = json_invalido

    def json(self):
        if self._invalido:
            raise ValueError("corpo não é JSON")
        return self._corpo


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setattr(settings, "ATHENA_BRIDGE_TOKEN", TOKEN)
    monkeypatch.setattr(settings, "ATHENA_BRIDGE_URL", "http://127.0.0.1:8765")
    monkeypatch.setattr(settings, "ATHENA_TIMEOUT", 5)


def _wo(**overrides) -> ProductionWorkOrder:
    base = dict(project_id="proj_fluxozap", handoff_id="ho_fluxo", execution_plan_id="exec_1", source_task_id="task_1",
                asset_type="LANDING_PAGE", executor_type="ATHENA", title="Landing FluxoZap",
                objective="Landing de demonstração", status="READY")
    base.update(overrides)
    return ProductionWorkOrder(**base)


def _visao(**kw):
    v = {"work_order_id": "x", "mission_id": "x", "handoff_id": "ho_fluxo", "athena_status": "EXECUTANDO",
         "cris_os_status": "RUNNING", "output_refs": [], "summary": "Em andamento", "requires_human_approval": False,
         "last_error": None}
    v.update(kw)
    return v


def _post_fixo(monkeypatch, resposta, capturado=None):
    def _fake(url, json, headers, timeout):
        if capturado is not None:
            capturado.update(url=url, json=json, headers=headers, timeout=timeout)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta
    monkeypatch.setattr("requests.post", _fake)


# ── registro, vocabulário e roteamento (mudança aditiva) ─────────────────────

def test_registro_e_vocabulario():
    assert "ATHENA" in PRODUCTION_EXECUTOR_TYPES_VALIDOS
    assert isinstance(EXECUTOR_REGISTRY["ATHENA"], AthenaAdapter)
    assert obter_adapter("ATHENA") is EXECUTOR_REGISTRY["ATHENA"]
    assert not isinstance(obter_adapter("ATHENA"), AdapterNaoConectado)


def test_roteamento_fixo_nao_envia_nada_para_athena_sozinho():
    assert "ATHENA" not in production_router._EXECUTOR_POR_ASSET_TYPE.values()


# ── sem token / estados ──────────────────────────────────────────────────────

def test_sem_token_nunca_chama_a_rede(monkeypatch):
    monkeypatch.setattr(settings, "ATHENA_BRIDGE_TOKEN", "")

    def _boom(*a, **k):
        raise AssertionError("não deveria chamar a rede")
    monkeypatch.setattr("requests.post", _boom)
    monkeypatch.setattr("requests.get", _boom)
    wo = _wo()
    out = AthenaAdapter().dispatch(wo)
    assert out is wo and wo.status == "READY" and wo.attempts == 0
    assert "ATHENA_BRIDGE_TOKEN não configurado" in wo.last_error
    assert AthenaAdapter().get_status(wo) == "READY"
    assert AthenaAdapter().collect_result(wo) is wo


def test_outro_executor_nao_e_processado(monkeypatch):
    _post_fixo(monkeypatch, AssertionError("não deveria chamar"))
    wo = _wo(executor_type="PAGEFORGE")
    AthenaAdapter().dispatch(wo)
    assert wo.status == "READY" and "não processa" in wo.last_error


@pytest.mark.parametrize("estado", ["COMPLETED", "FAILED", "CANCELLED", "WAITING_APPROVAL", "NEEDS_ROUTING", "CREATED"])
def test_estados_nao_despachaveis(monkeypatch, estado):
    _post_fixo(monkeypatch, AssertionError("não deveria chamar"))
    wo = _wo(status=estado)
    AthenaAdapter().dispatch(wo)
    assert wo.status == estado and wo.attempts == 0


# ── dispatch 2xx ─────────────────────────────────────────────────────────────

def test_dispatch_payload_headers_e_handoff(monkeypatch):
    cap = {}
    _post_fixo(monkeypatch, FakeResponse(202, _visao(work_order_id="w", mission_id="w")), cap)
    wo = _wo()
    out = AthenaAdapter().dispatch(wo)
    assert out is wo
    assert cap["url"] == "http://127.0.0.1:8765/v1/ordens"
    assert cap["headers"]["Idempotency-Key"] == wo.work_order_id
    assert cap["headers"]["Authorization"] == f"Bearer {TOKEN}"
    assert cap["json"]["work_order"]["work_order_id"] == wo.work_order_id
    assert cap["json"]["work_order"]["handoff_id"] == "ho_fluxo"
    assert wo.status == "RUNNING" and wo.attempts == 1 and wo.last_error is None
    assert wo.metadata["athena_status"] == "EXECUTANDO" and wo.metadata["athena_mission_id"] == "w"


def test_marcador_running_do_runner_e_aceito(monkeypatch):
    _post_fixo(monkeypatch, FakeResponse(202, _visao()))
    wo = _wo(status="RUNNING")
    AthenaAdapter().dispatch(wo)
    assert wo.attempts == 1 and wo.status == "RUNNING"


def test_dispatch_sem_status_reconhecido_cai_em_dispatched(monkeypatch):
    _post_fixo(monkeypatch, FakeResponse(202, {"cris_os_status": "QUALQUER"}))
    wo = _wo()
    AthenaAdapter().dispatch(wo)
    assert wo.status == "DISPATCHED"


def test_waiting_approval(monkeypatch):
    _post_fixo(monkeypatch, FakeResponse(202, _visao(cris_os_status="WAITING_APPROVAL", requires_human_approval=True)))
    wo = _wo()
    AthenaAdapter().dispatch(wo)
    assert wo.status == "WAITING_APPROVAL"


def test_completed_so_com_output(monkeypatch):
    _post_fixo(monkeypatch, FakeResponse(202, _visao(cris_os_status="COMPLETED", output_refs=[])))
    wo = _wo()
    AthenaAdapter().dispatch(wo)
    assert wo.status == "RUNNING" and "sem nenhum artefato" in wo.last_error
    _post_fixo(monkeypatch, FakeResponse(202, _visao(cris_os_status="COMPLETED", output_refs=["projects/X/code/index.html"])))
    wo2 = _wo()
    AthenaAdapter().dispatch(wo2)
    assert wo2.status == "COMPLETED" and wo2.output_refs == ["athena:projects/X/code/index.html"]


# ── erros ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("codigo", [401, 403])
def test_autenticacao_rejeitada_e_permanente_sem_vazar_token(monkeypatch, codigo):
    _post_fixo(monkeypatch, FakeResponse(codigo, {"erro": "NAO_AUTORIZADO"}))
    wo = _wo()
    AthenaAdapter().dispatch(wo)
    assert wo.status == "FAILED" and TOKEN not in (wo.last_error or "") and TOKEN not in str(wo.metadata)


def test_conflito_409_e_permanente(monkeypatch):
    _post_fixo(monkeypatch, FakeResponse(409, {"erro": "CONFLITO_IDEMPOTENCIA", "detalhes": "conteúdo diferente"}))
    wo = _wo()
    AthenaAdapter().dispatch(wo)
    assert wo.status == "FAILED" and "409" in wo.last_error


def test_recusa_422_traz_motivo(monkeypatch):
    _post_fixo(monkeypatch, FakeResponse(422, {"erro": "ORDEM_RECUSADA", "motivo": "asset_type 'APP' não aceito"}))
    wo = _wo(asset_type="APP")
    AthenaAdapter().dispatch(wo)
    assert wo.status == "FAILED" and "ORDEM_RECUSADA" in wo.last_error and "APP" in wo.last_error


@pytest.mark.parametrize("resposta", [FakeResponse(429), FakeResponse(500), FakeResponse(503),
                                      requests.exceptions.ConnectionError("recusado"), requests.exceptions.Timeout("lento")])
def test_transitorios_mantem_status(monkeypatch, resposta):
    _post_fixo(monkeypatch, resposta)
    wo = _wo()
    AthenaAdapter().dispatch(wo)
    assert wo.status == "READY" and wo.attempts == 1 and wo.last_error


# ── consulta e coleta ────────────────────────────────────────────────────────

def test_get_status_e_collect_result(monkeypatch):
    cap = {}

    def _fake_get(url, headers, timeout):
        cap["url"] = url
        return FakeResponse(200, _visao(cris_os_status="COMPLETED", athena_status="CONCLUIDA",
                                        output_refs=["projects/X/copy/landing.md"]))
    monkeypatch.setattr("requests.get", _fake_get)
    wo = _wo(status="RUNNING")
    assert AthenaAdapter().get_status(wo) == "COMPLETED" and wo.status == "RUNNING"   # get_status não modifica
    AthenaAdapter().collect_result(wo)
    assert cap["url"].endswith(f"/v1/ordens/{wo.work_order_id}")
    assert wo.status == "COMPLETED" and wo.metadata["athena_status"] == "CONCLUIDA"


def test_collect_result_erros(monkeypatch):
    monkeypatch.setattr("requests.get", lambda url, headers, timeout: FakeResponse(404, {"erro": "ORDEM_NAO_ENCONTRADA"}))
    wo = _wo(status="DISPATCHED")
    AthenaAdapter().collect_result(wo)
    assert wo.status == "DISPATCHED" and "404" in wo.last_error
    monkeypatch.setattr("requests.get", lambda url, headers, timeout: FakeResponse(200, json_invalido=True))
    AthenaAdapter().collect_result(wo)
    assert "não é JSON" in wo.last_error


def test_failed_da_athena_traz_erro(monkeypatch):
    monkeypatch.setattr("requests.get", lambda url, headers, timeout: FakeResponse(
        200, _visao(cris_os_status="FAILED", athena_status="FALHOU", last_error="Rejeitada pelo revisor")))
    wo = _wo(status="RUNNING")
    AthenaAdapter().collect_result(wo)
    assert wo.status == "FAILED" and wo.last_error == "Rejeitada pelo revisor"
