"""
Teste da correcao pos-teste real da Fase 3: respostas longas (ex.: Product
Architect listando hipoteses de produto) nao podem quebrar o envio ao
Telegram (`telegram.error.BadRequest: Message is too long`).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from channels.telegram.bot import _dividir_mensagem, _LIMITE_MENSAGEM_TELEGRAM


def test_mensagem_curta_nao_e_dividida():
    texto = "Resposta curta."
    assert _dividir_mensagem(texto) == [texto]


def test_mensagem_longa_e_dividida_em_pedacos_dentro_do_limite():
    texto = "\n".join(f"Linha {i} com algum conteudo de exemplo repetido." for i in range(500))
    assert len(texto) > _LIMITE_MENSAGEM_TELEGRAM
    partes = _dividir_mensagem(texto)
    assert len(partes) > 1
    for p in partes:
        assert len(p) <= _LIMITE_MENSAGEM_TELEGRAM


def test_divisao_preserva_todo_o_conteudo():
    texto = "\n".join(f"Linha {i}" for i in range(1000))
    partes = _dividir_mensagem(texto)
    reconstruido = "\n".join(partes)
    # todo pedaço original precisa aparecer em algum lugar do reconstruido
    for linha in texto.split("\n"):
        assert linha in reconstruido


def test_linha_unica_maior_que_limite_e_cortada_em_blocos():
    linha_gigante = "x" * (_LIMITE_MENSAGEM_TELEGRAM * 3)
    partes = _dividir_mensagem(linha_gigante)
    assert len(partes) >= 3
    for p in partes:
        assert len(p) <= _LIMITE_MENSAGEM_TELEGRAM
    assert "".join(partes) == linha_gigante
