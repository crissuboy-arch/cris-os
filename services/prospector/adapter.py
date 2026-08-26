"""
Adapter — carrega a Maquina de Leads como biblioteca dentro do CRIS OS.

Nenhuma regra de negocio e copiada: os modulos `motor`, `engine`, `seguranca`,
`locale_pt` e `market_context` da Maquina de Leads sao importados de onde vivem
e usados como estao. O CRIS OS chama as funcoes existentes via ProspectorService.

O carregamento e LAZY (so no primeiro uso) para nao atrapalhar o startup do
CRIS OS nem os testes que nao precisam do motor.
"""

from __future__ import annotations

import importlib
import logging
import sys

from services.prospector.config import ml_dir, ml_db_path

logger = logging.getLogger(__name__)

_state: dict = {
    "carregado": False,
    "motor": None,
    "engine": None,
    "seguranca": None,
    "locale_pt": None,
    "market_context": None,
}


def carregar() -> tuple:
    """Importa os modulos da Maquina de Leads. Idempotente. Levanta se nao existir."""
    if _state["carregado"]:
        return (_state["motor"], _state["engine"], _state["seguranca"])

    base = ml_dir()
    if not base.exists():
        raise RuntimeError(
            "Pasta da Maquina de Leads nao encontrada em %s. Defina PROSPECTOR_ML_DIR." % base
        )

    caminho = str(base)
    if caminho not in sys.path:
        sys.path.insert(0, caminho)

    try:
        motor = importlib.import_module("motor")
        engine = importlib.import_module("engine")
        seguranca = importlib.import_module("seguranca")
        locale_pt = importlib.import_module("locale_pt")
        market_context = importlib.import_module("market_context")
    except Exception as exc:
        raise RuntimeError("Falha ao importar a Maquina de Leads como biblioteca: %s" % exc)

    _state.update({
        "carregado": True,
        "motor": motor,
        "engine": engine,
        "seguranca": seguranca,
        "locale_pt": locale_pt,
        "market_context": market_context,
    })
    logger.info("Maquina de Leads carregada como biblioteca: %s", base)
    return motor, engine, seguranca


def seguranca():
    """Retorna apenas o modulo seguranca (util para chave/log sem puxar o motor)."""
    _, _, seg = carregar()
    return seg


def engine_db() -> str:
    """Caminho do prospector.db usado pelo motor (fonte de verdade dos leads)."""
    return str(ml_db_path())
