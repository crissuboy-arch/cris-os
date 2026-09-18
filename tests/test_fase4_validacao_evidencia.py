"""
Testes da Fase 4: endurecimento de afirmacoes prospectivas sem evidencia
(correcao pos-teste real -- o Product Architect produziu frases como "pode
reduzir churn", "fáceis de escalar com tráfego pago", "pode facilitar
primeiras vendas" como se fossem conclusao, mesmo sem nenhum dado de
trafego/venda real).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.product_architect import _endurecer_afirmacao_prospectiva, _validar_candidato


def test_afirmacao_de_churn_sem_marcador_e_sinalizada():
    texto = "Esse formato pode reduzir churn dos usuários no longo prazo."
    resultado = _endurecer_afirmacao_prospectiva(texto)
    assert "HIPÓTESE/PREMISSA" in resultado
    assert "A VALIDAR" in resultado


def test_afirmacao_de_escala_sem_marcador_e_sinalizada():
    texto = "Mini-apps são fáceis de escalar com tráfego pago."
    resultado = _endurecer_afirmacao_prospectiva(texto)
    assert "HIPÓTESE/PREMISSA" in resultado


def test_afirmacao_de_primeiras_vendas_sem_marcador_e_sinalizada():
    texto = "Pode facilitar as primeiras vendas do produto."
    resultado = _endurecer_afirmacao_prospectiva(texto)
    assert "HIPÓTESE/PREMISSA" in resultado


def test_afirmacao_ja_marcada_explicitamente_nao_e_duplicada():
    texto = "Isso pode reduzir churn -- mas isso é uma HIPÓTESE, ainda a validar."
    resultado = _endurecer_afirmacao_prospectiva(texto)
    assert resultado == texto  # ja tem marcador explicito, nao mexe


def test_afirmacao_sem_risco_nenhum_nao_e_alterada():
    texto = "O público-alvo são iniciantes em velas artesanais."
    resultado = _endurecer_afirmacao_prospectiva(texto)
    assert resultado == texto


def test_nao_bloqueia_nem_descarta_o_candidato_so_anota():
    """Pedido explicito: 'nao transforme isso em bloqueio excessivo' -- o
    candidato continua valido, so o texto ganha o marcador."""
    bruto = {
        "product_type": "mini_app",
        "why_it_fits": "Pode reduzir churn e é fácil de escalar com tráfego pago.",
        "confidence": "MEDIO",
    }
    candidato = _validar_candidato(bruto)
    assert candidato is not None
    assert candidato["product_type"] == "mini_app"
    assert "HIPÓTESE/PREMISSA" in candidato["why_it_fits"]
