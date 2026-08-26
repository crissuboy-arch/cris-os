"""
Testes dos comandos Telegram do modulo Prospector.

Verifica que o TelegramChannel registra os CommandHandlers dos comandos
/prospectar, /proposta, /redesenhar, /publicar, /contrato e /followup.
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

telegram = pytest.importorskip("telegram")

from channels.telegram.bot import TelegramChannel  # noqa: E402


class _FakeApp:
    def __init__(self):
        self.handlers = []

    def add_handler(self, h):
        self.handlers.append(h)

    def run_polling(self, allowed_updates=None):
        pass


class _FakeBuilder:
    def __init__(self):
        self._app = _FakeApp()

    def token(self, token):
        return self

    def build(self):
        return self._app


COMANDOS_ESPERADOS = {"prospectar", "proposta", "redesenhar", "publicar",
                      "contrato", "followup"}


def test_comandos_prospector_registrados(monkeypatch):
    builder = _FakeBuilder()
    monkeypatch.setattr(telegram.ext.Application, "builder",
                        staticmethod(lambda: builder))
    chan = TelegramChannel(token="fake-token", handler=None)
    chan.run()

    registrados = {
        h.command
        for h in builder._app.handlers
        if getattr(h, "command", None)
    }
    assert COMANDOS_ESPERADOS.issubset(registrados)


def test_handlers_existem_no_canal():
    chan = TelegramChannel(token="fake-token", handler=None)
    assert callable(chan._on_prospector_prospectar)
    assert callable(chan._on_prospector_slug)
    assert callable(chan._on_prospector_followup)
