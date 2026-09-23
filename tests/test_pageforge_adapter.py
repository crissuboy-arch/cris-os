"""
Testes do PageForgeAdapter (`core/pageforge_adapter.py`) -- conexão real com
o bridge PageForge já validado em produção (POST/GET
/api/integrations/cris-os/work-orders). ZERO chamada de rede real: todo
`requests.post`/`requests.get` é substituído por um fake determinístico.

Cobre explicitamente:
  - sem token configurado -> nunca chama a rede, nunca finge sucesso;
  - 2xx -> DISPATCHED, nunca COMPLETED;
  - 401/403 -> nunca expõe o token, status permanece READY (retry seguro);
  - erro de rede/timeout -> tratado, sem crash, status permanece READY;
  - idempotência: work_order_id no header Idempotency-Key, nunca cria
    segunda WorkOrder (dispatch sempre muta a MESMA instância);
  - mapeamento de estados PageForge -> Cris OS sem perda de informação;
  - COMPLETED só é aceito com output real (reaproveita
    core.production_orders.pode_marcar_completed).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from config.settings import settings
from core.executor_adapter import EXECUTOR_REGISTRY, obter_adapter
from core.pageforge_adapter import PageForgeAdapter
from memory.project_brain import ProductionWorkOrder


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
def _token_configurado(monkeypatch):
    monkeypatch.setattr(settings, "PAGEFORGE_BRIDGE_TOKEN", "token-de-teste-nunca-real")
    monkeypatch.setattr(settings, "PAGEFORGE_API_URL", "https://pageforge.exemplo.test")
    monkeypatch.setattr(settings, "PAGEFORGE_TIMEOUT", 5)


def _work_order(**overrides) -> ProductionWorkOrder:
    base = dict(
        project_id="proj_carla", handoff_id="ho_carla", execution_plan_id="exec_carla",
        source_task_id="task_01e9c7c7", asset_type="LANDING_PAGE", executor_type="PAGEFORGE",
        title="Landing page com prova social", status="READY",
    )
    base.update(overrides)
    return ProductionWorkOrder(**base)


# ---------------------------------------------------------------------------
# Registro / contrato
# ---------------------------------------------------------------------------

def test_pageforge_registrado_no_executor_registry():
    assert isinstance(EXECUTOR_REGISTRY["PAGEFORGE"], PageForgeAdapter)
    assert obter_adapter("PAGEFORGE") is EXECUTOR_REGISTRY["PAGEFORGE"]


def test_can_handle_somente_pageforge():
    adapter = PageForgeAdapter()
    assert adapter.can_handle(_work_order(executor_type="PAGEFORGE")) is True
    assert adapter.can_handle(_work_order(executor_type="PINK_LOGIC")) is False


# ---------------------------------------------------------------------------
# Sem token configurado -- nunca chama a rede, nunca finge sucesso
# ---------------------------------------------------------------------------

def test_sem_token_nunca_chama_rede(monkeypatch):
    monkeypatch.setattr(settings, "PAGEFORGE_BRIDGE_TOKEN", "")

    def _boom(*a, **k):
        raise AssertionError("nao deveria chamar requests sem token configurado")
    monkeypatch.setattr("requests.post", _boom)
    monkeypatch.setattr("requests.get", _boom)

    wo = _work_order()
    resultado = PageForgeAdapter().dispatch(wo)
    assert resultado.status == "READY"
    assert "PAGEFORGE_BRIDGE_TOKEN" in resultado.last_error


def test_sem_token_get_status_nao_chama_rede(monkeypatch):
    monkeypatch.setattr(settings, "PAGEFORGE_BRIDGE_TOKEN", "")

    def _boom(*a, **k):
        raise AssertionError("nao deveria chamar requests sem token configurado")
    monkeypatch.setattr("requests.get", _boom)

    wo = _work_order(status="DISPATCHED")
    assert PageForgeAdapter().get_status(wo) == "DISPATCHED"


# ---------------------------------------------------------------------------
# Dispatch -- 2xx aceito, nunca COMPLETED
# ---------------------------------------------------------------------------

def test_dispatch_sem_status_utilizavel_cai_no_fallback_dispatched(monkeypatch):
    """Compatibilidade defensiva (Seção E): corpo 2xx sem `status`
    reconhecível -- NUNCA finge COMPLETED, cai no mesmo fallback seguro
    pré-existente. Não há `job_id` no contrato real do PageForge (a chave é
    sempre `work_order_id`) -- nunca inventamos um."""
    def _fake_post(url, json, headers, timeout):
        return FakeResponse(202, {})
    monkeypatch.setattr("requests.post", _fake_post)

    wo = _work_order()
    resultado = PageForgeAdapter().dispatch(wo)

    assert resultado.status == "DISPATCHED"
    assert resultado.status != "COMPLETED"
    assert resultado.last_error is None
    assert "pageforge_job_id" not in resultado.metadata
    assert resultado.attempts == 1


def test_dispatch_envia_idempotency_key_e_work_order_id(monkeypatch):
    capturado = {}

    def _fake_post(url, json, headers, timeout):
        capturado["headers"] = headers
        capturado["json"] = json
        return FakeResponse(200, {})
    monkeypatch.setattr("requests.post", _fake_post)

    wo = _work_order()
    PageForgeAdapter().dispatch(wo)

    assert capturado["headers"]["Idempotency-Key"] == wo.work_order_id
    assert capturado["json"]["work_order_id"] == wo.work_order_id


def test_dispatch_nunca_expoe_token_no_payload(monkeypatch):
    capturado = {}

    def _fake_post(url, json, headers, timeout):
        capturado["json"] = json
        return FakeResponse(200, {})
    monkeypatch.setattr("requests.post", _fake_post)

    PageForgeAdapter().dispatch(_work_order())
    bruto = str(capturado["json"])
    assert "token-de-teste-nunca-real" not in bruto


def test_dispatch_autenticacao_do_header_usa_bearer(monkeypatch):
    capturado = {}

    def _fake_post(url, json, headers, timeout):
        capturado["headers"] = headers
        return FakeResponse(200, {})
    monkeypatch.setattr("requests.post", _fake_post)

    PageForgeAdapter().dispatch(_work_order())
    assert capturado["headers"]["Authorization"] == "Bearer token-de-teste-nunca-real"


# ---------------------------------------------------------------------------
# Falhas tratadas -- nunca expõe token, nunca crasha, nunca finge sucesso
# ---------------------------------------------------------------------------

def test_dispatch_401_marca_failed_nunca_expoe_token(monkeypatch):
    """Correção Etapa 18 (política de retry): 401/403 é falha PERMANENTE
    (token inválido nunca se resolve tentando de novo) -- NUNCA fica READY,
    nunca é retryable automaticamente."""
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(401, {}))
    wo = _work_order()
    resultado = PageForgeAdapter().dispatch(wo)
    assert resultado.status == "FAILED"
    assert "token-de-teste-nunca-real" not in (resultado.last_error or "")
    assert resultado.last_error


def test_dispatch_403_tratado_igual_401(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(403, {}))
    resultado = PageForgeAdapter().dispatch(_work_order())
    assert resultado.status == "FAILED"


def test_dispatch_5xx_e_transitorio_mantem_ready(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(503, {}))
    resultado = PageForgeAdapter().dispatch(_work_order())
    assert resultado.status == "READY"
    assert resultado.last_error


def test_dispatch_429_e_transitorio_mantem_ready(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(429, {}))
    resultado = PageForgeAdapter().dispatch(_work_order())
    assert resultado.status == "READY"


def test_dispatch_400_marca_failed(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(400, {"error": "payload inválido"}))
    resultado = PageForgeAdapter().dispatch(_work_order())
    assert resultado.status == "FAILED"
    assert resultado.last_error


def test_dispatch_erro_de_rede_nao_crasha(monkeypatch):
    import requests

    def _fake_post(*a, **k):
        raise requests.exceptions.Timeout("simulado")
    monkeypatch.setattr("requests.post", _fake_post)

    resultado = PageForgeAdapter().dispatch(_work_order())
    assert resultado.status == "READY"
    assert resultado.last_error
    assert resultado.attempts == 1


def test_dispatch_nao_redespacha_ordem_ja_completed(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("nao deveria despachar uma WorkOrder ja COMPLETED")
    monkeypatch.setattr("requests.post", _boom)

    wo = _work_order(status="COMPLETED", output_refs=["preview_url:https://exemplo.test"])
    resultado = PageForgeAdapter().dispatch(wo)
    assert resultado.status == "COMPLETED"  # inalterado


def test_dispatch_nao_redespacha_ordem_cancelada(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("nao deveria despachar uma WorkOrder CANCELLED")
    monkeypatch.setattr("requests.post", _boom)

    wo = _work_order(status="CANCELLED")
    resultado = PageForgeAdapter().dispatch(wo)
    assert resultado.status == "CANCELLED"


def test_dispatch_aceita_status_running_como_ponto_de_partida(monkeypatch):
    """Etapa 18 -- crash-safety: `core/production_runner.py` grava RUNNING
    ANTES de chamar dispatch() (marcador de "em andamento" persistido antes
    da chamada de rede). dispatch() precisa aceitar esse marcador como ponto
    de partida válido, senão o próprio dispatch nunca aconteceria."""
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(200, {"status": "RECEIVED"}))
    wo = _work_order(status="RUNNING")
    resultado = PageForgeAdapter().dispatch(wo)
    assert resultado.status == "DISPATCHED"


# ---------------------------------------------------------------------------
# POST é SÍNCRONO -- o corpo 2xx já traz o resultado real. dispatch() deve
# interpretar status/artifact/error exatamente como collect_result().
# ---------------------------------------------------------------------------

def test_dispatch_post_sincrono_completed_com_artifact_e_reconhecido(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(200, {
        "ok": True, "work_order_id": "wo_d0ad992898fe", "project_id": "proj_carla",
        "executor": "PAGEFORGE", "status": "COMPLETED",
        "received_at": "2026-09-23T00:00:00Z", "updated_at": "2026-09-23T00:00:05Z",
        "completed_at": "2026-09-23T00:00:05Z",
        "artifact": {
            "artifact_id": "artf_cris-wo-d0ad992898fe", "artifact_type": "LANDING_PAGE",
            "page_id": "cris-wo-d0ad992898fe", "version": "1", "checksum": "sha256deadbeef",
            "preview_url": "https://pageforge-ai-woad.vercel.app/demo/cris-wo-d0ad992898fe",
        },
    }))
    wo = _work_order()
    resultado = PageForgeAdapter().dispatch(wo)

    assert resultado.status == "COMPLETED"
    assert resultado.last_error is None
    assert any("artifact_id" in ref for ref in resultado.output_refs)
    assert any("preview_url" in ref for ref in resultado.output_refs)
    assert resultado.metadata["pageforge_status"] == "COMPLETED"


def test_dispatch_post_sincrono_failed_com_error_e_reconhecido(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(200, {
        "ok": True, "status": "FAILED",
        "error": {"code": "GENERATION_FAILED", "message": "O gerador não produziu uma página válida."},
    }))
    wo = _work_order()
    resultado = PageForgeAdapter().dispatch(wo)

    assert resultado.status == "FAILED"
    assert "GENERATION_FAILED" in resultado.last_error
    assert "não produziu uma página válida" in resultado.last_error
    assert resultado.output_refs == []


def test_dispatch_post_sincrono_needs_input_e_reconhecido(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(200, {
        "ok": True, "status": "NEEDS_INPUT",
        "error": {
            "code": "NEEDS_INPUT", "message": "Faltam informações indispensáveis no WorkOrder para gerar a página.",
            "missing": ["offer", "audience"],
        },
    }))
    wo = _work_order()
    resultado = PageForgeAdapter().dispatch(wo)

    assert resultado.status == "WAITING_APPROVAL"
    assert resultado.metadata["pageforge_status"] == "NEEDS_INPUT"
    assert "faltando" in resultado.last_error.lower()
    assert "offer" in resultado.last_error and "audience" in resultado.last_error


def test_dispatch_post_sincrono_completed_sem_artifact_nao_marca_completed(monkeypatch):
    """Gate crítico: mesmo com status=COMPLETED vindo do POST, sem nenhum
    artefato reconhecível a WorkOrder NUNCA é aceita como concluída de
    verdade (mesmo gate usado em collect_result/production_orders)."""
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(200, {"status": "COMPLETED"}))
    wo = _work_order()
    resultado = PageForgeAdapter().dispatch(wo)

    assert resultado.status != "COMPLETED"
    assert resultado.status == "RUNNING"
    assert resultado.last_error


# ---------------------------------------------------------------------------
# collect_result -- mapeamento de estados + gate de COMPLETED
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status_pageforge,status_cris_esperado", [
    ("RECEIVED", "DISPATCHED"),
    ("QUEUED", "DISPATCHED"),
    ("RUNNING", "RUNNING"),
    ("FAILED", "FAILED"),
    ("NEEDS_INPUT", "WAITING_APPROVAL"),
])
def test_collect_result_mapeia_estados_sem_perder_informacao(monkeypatch, status_pageforge, status_cris_esperado):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse(200, {"status": status_pageforge}))
    wo = _work_order(status="DISPATCHED")
    resultado = PageForgeAdapter().collect_result(wo)
    assert resultado.status == status_cris_esperado
    assert resultado.metadata["pageforge_status"] == status_pageforge  # nunca perdido


def test_collect_result_completed_com_output_real_marca_completed(monkeypatch):
    # Formato REAL confirmado no código-fonte do PageForge: os campos do
    # artefato vêm ANINHADOS em "artifact", nunca soltos no corpo.
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse(200, {
        "status": "COMPLETED",
        "artifact": {
            "artifact_id": "artf_cris-wo-carla", "artifact_type": "LANDING_PAGE",
            "page_id": "cris-wo-carla", "version": "1", "checksum": "abc123",
            "preview_url": "https://pageforge.exemplo.test/demo/cris-wo-carla",
            "deployment_url": "https://minha-pagina.vercel.app",
        },
    }))
    wo = _work_order(status="RUNNING")
    resultado = PageForgeAdapter().collect_result(wo)
    assert resultado.status == "COMPLETED"
    assert any("preview_url" in ref for ref in resultado.output_refs)
    assert any("deployment_url" in ref for ref in resultado.output_refs)
    assert any("artifact_id" in ref for ref in resultado.output_refs)
    assert resultado.last_error is None


def test_collect_result_completed_com_apenas_file_ref_ainda_marca_completed(monkeypatch):
    """Correção pós-incidente real: mesmo quando a publicação bonita falha
    (sem preview_url/deployment_url), o backup durável (file_ref) sozinho
    já é output real suficiente para o gate aceitar COMPLETED -- o
    conteúdo nunca mais fica sem nenhuma referência recuperável."""
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse(200, {
        "status": "COMPLETED",
        "artifact": {
            "artifact_id": "artf_cris-wo-carla", "artifact_type": "LANDING_PAGE",
            "page_id": "cris-wo-carla", "version": "1", "checksum": "abc123",
            "file_ref": "https://pageforge-public.blob.vercel-storage.com/cris-os-artifacts/wo_carla.html",
        },
    }))
    wo = _work_order(status="RUNNING")
    resultado = PageForgeAdapter().collect_result(wo)
    assert resultado.status == "COMPLETED"
    assert any("file_ref" in ref for ref in resultado.output_refs)
    assert resultado.last_error is None


def test_collect_result_completed_sem_output_nunca_marca_completed(monkeypatch):
    """Gate crítico -- reaproveita core.production_orders.pode_marcar_completed.
    PageForge dizer 'COMPLETED' sem nenhum artefato reconhecível NUNCA é
    aceito como conclusão real."""
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse(200, {"status": "COMPLETED"}))
    wo = _work_order(status="RUNNING")
    resultado = PageForgeAdapter().collect_result(wo)
    assert resultado.status != "COMPLETED"
    assert resultado.status == "RUNNING"
    assert resultado.last_error


def test_collect_result_failed_registra_last_error(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse(200, {"status": "FAILED", "error": "template inválido"}))
    wo = _work_order(status="RUNNING")
    resultado = PageForgeAdapter().collect_result(wo)
    assert resultado.status == "FAILED"
    assert "template inválido" in resultado.last_error


def test_collect_result_erro_http_nao_crasha(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse(500, {}))
    wo = _work_order(status="DISPATCHED")
    resultado = PageForgeAdapter().collect_result(wo)
    assert resultado.status == "DISPATCHED"  # inalterado
    assert resultado.last_error


def test_collect_result_json_invalido_nao_crasha(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse(200, texto_json_invalido=True))
    wo = _work_order(status="DISPATCHED")
    resultado = PageForgeAdapter().collect_result(wo)
    assert resultado.status == "DISPATCHED"
    assert resultado.last_error


def test_get_status_devolve_status_bruto_do_pageforge(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse(200, {"status": "RUNNING"}))
    wo = _work_order(status="DISPATCHED")
    assert PageForgeAdapter().get_status(wo) == "RUNNING"


def test_get_status_erro_devolve_status_atual_sem_crashar(monkeypatch):
    import requests

    def _fake_get(*a, **k):
        raise requests.exceptions.ConnectionError("simulado")
    monkeypatch.setattr("requests.get", _fake_get)

    wo = _work_order(status="DISPATCHED")
    assert PageForgeAdapter().get_status(wo) == "DISPATCHED"


# ---------------------------------------------------------------------------
# work_order_id nunca muda, nenhuma segunda WorkOrder é criada
# ---------------------------------------------------------------------------

def test_dispatch_preserva_work_order_id_e_muta_a_mesma_instancia(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(200, {}))
    wo = _work_order()
    id_original = wo.work_order_id
    resultado = PageForgeAdapter().dispatch(wo)
    assert resultado is wo  # mesma instância, nunca uma nova
    assert resultado.work_order_id == id_original


def test_nenhuma_chamada_real_e_feita_nestes_testes(monkeypatch):
    """Meta-teste: garante que NENHUM teste deste arquivo bate na internet
    de verdade -- todo requests.post/get está sempre monkeypatchado."""
    import requests

    def _bloqueado(*a, **k):
        raise AssertionError("chamada de rede real bloqueada neste teste")
    monkeypatch.setattr(requests, "post", _bloqueado)
    monkeypatch.setattr(requests, "get", _bloqueado)
    # dispatch/collect_result SEM monkeypatch adicional aqui devem estourar
    # o AssertionError acima se tentarem chamar a rede de verdade.
    with pytest.raises(AssertionError):
        PageForgeAdapter().dispatch(_work_order())
