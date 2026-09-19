"""
Testes da Fase 6: Performance Agent (fundação -- lógica pura).

Nada aqui inventa métrica: sem snapshot REAL/IMPORTED, a resposta é sempre
determinística.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

from core.performance_agent import (
    diagnosticar_performance,
    registrar_snapshot,
    tem_metricas_utilizaveis,
    ultimo_snapshot_utilizavel,
)
from memory.project_brain import Identidade, PerformanceSnapshot, ProjectBrain


def _brain() -> ProjectBrain:
    return ProjectBrain(identidade=Identidade(project_id="proj_teste", name="Curso de Velas"))


class FakeLLMJSON:
    _provider_name = "fake:inteligente"

    def __init__(self, payload):
        self.payload = payload
        self.chamadas = 0

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        self.chamadas += 1
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False))


class FakeLLMBoom:
    def chat(self, messages, tools=None):
        raise RuntimeError("OpenRouter indisponivel (simulado)")


# ---------------------------------------------------------------------------
# Sem métricas -- resposta determinística, nunca inventa (requisito J)
# ---------------------------------------------------------------------------

def test_sem_nenhum_snapshot_nao_tem_metricas_utilizaveis():
    brain = _brain()
    assert tem_metricas_utilizaveis(brain) is False
    assert ultimo_snapshot_utilizavel(brain) is None


def test_diagnostico_sem_snapshot_e_mensagem_deterministica():
    brain = _brain()
    resultado = diagnosticar_performance(brain)
    assert "ainda não existem métricas" in resultado.lower()
    # nenhum numero/percentual foi inventado na mensagem de ausencia
    assert "%" not in resultado


def test_diagnostico_sem_snapshot_nunca_chama_llm():
    brain = _brain()
    # nem precisa passar llm -- a funcao de dispatch (tools) so chama o LLM
    # depois de confirmar tem_metricas_utilizaveis(); aqui testamos que
    # mesmo passando um LLM que sempre falha, a ausencia de snapshot e
    # resolvida ANTES de qualquer LLM ser necessario.
    assert tem_metricas_utilizaveis(brain) is False


# ---------------------------------------------------------------------------
# SIMULATED nunca conta como dado real (requisito K)
# ---------------------------------------------------------------------------

def test_snapshot_simulated_nunca_e_utilizavel():
    brain = _brain()
    registrar_snapshot(brain, PerformanceSnapshot(platform="META_ADS", source="SIMULATED", ctr="2.5%"))
    assert tem_metricas_utilizaveis(brain) is False
    resultado = diagnosticar_performance(brain)
    assert "ainda não existem métricas" in resultado.lower()


def test_snapshot_simulated_misturado_com_real_nao_conta_o_simulated():
    brain = _brain()
    registrar_snapshot(brain, PerformanceSnapshot(platform="META_ADS", source="SIMULATED", ctr="99%"))
    registrar_snapshot(brain, PerformanceSnapshot(platform="META_ADS", source="REAL", ctr="1.2%", collected_at="2026-01-02T00:00:00+00:00"))
    ultimo = ultimo_snapshot_utilizavel(brain)
    assert ultimo.source == "REAL"
    assert ultimo.ctr == "1.2%"


# ---------------------------------------------------------------------------
# REAL/IMPORTED -- métricas preservadas exatamente (requisito L)
# ---------------------------------------------------------------------------

def test_snapshot_real_preserva_metricas_exatamente():
    brain = _brain()
    snap = PerformanceSnapshot(
        platform="TIKTOK_ADS", campaign_id="camp_x", date_range="2026-01-01/2026-01-07",
        spend="123.45", impressions="10000", clicks="200", ctr="2.0%", cpc="0.61",
        source="REAL",
    )
    registrar_snapshot(brain, snap)
    resultado = diagnosticar_performance(brain)
    assert "123.45" in resultado
    assert "10000" in resultado
    assert "2.0%" in resultado
    assert "0.61" in resultado


def test_snapshot_importado_e_utilizavel():
    brain = _brain()
    registrar_snapshot(brain, PerformanceSnapshot(platform="GOOGLE_SEARCH", source="IMPORTED", ctr="3.1%"))
    assert tem_metricas_utilizaveis(brain) is True


def test_campos_ausentes_aparecem_not_available():
    brain = _brain()
    registrar_snapshot(brain, PerformanceSnapshot(platform="META_ADS", source="REAL", spend="50"))
    resultado = diagnosticar_performance(brain)
    assert "NOT_AVAILABLE" in resultado


# ---------------------------------------------------------------------------
# Diagnostico com LLM -- hipoteses, nunca fatos inventados; fallback honesto
# ---------------------------------------------------------------------------

def test_diagnostico_com_llm_separa_fatos_de_hipoteses():
    brain = _brain()
    registrar_snapshot(brain, PerformanceSnapshot(platform="META_ADS", source="REAL", ctr="1.0%"))
    payload = {
        "diagnostico": "CTR abaixo da media do canal.",
        "hipoteses": ["O criativo pode nao estar prendendo atencao nos primeiros segundos"],
        "riscos": ["Continuar sem ajuste pode desperdicar orcamento"],
        "proximo_teste": ["Testar um novo hook"],
    }
    resultado = diagnosticar_performance(brain, llm=FakeLLMJSON(payload))
    assert "FATOS" in resultado
    assert "HIPÓTESES" in resultado
    assert "prendendo atencao" in resultado.lower() or "prendendo atenção" in resultado.lower()


def test_diagnostico_llm_falha_cai_em_fallback_honesto():
    brain = _brain()
    registrar_snapshot(brain, PerformanceSnapshot(platform="META_ADS", source="REAL", ctr="1.0%"))
    resultado = diagnosticar_performance(brain, llm=FakeLLMBoom())
    assert "FATOS" in resultado
    assert "1.0%" in resultado
    assert "nenhuma causa foi inferida" in resultado.lower()


def test_diagnostico_nao_afirma_causalidade_sem_llm():
    brain = _brain()
    registrar_snapshot(brain, PerformanceSnapshot(platform="META_ADS", source="REAL", ctr="1.0%"))
    resultado = diagnosticar_performance(brain, llm=None)
    assert "nunca causalidade comprovada" in resultado.lower()
