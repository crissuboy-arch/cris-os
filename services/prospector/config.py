"""
Configuracao do modulo Prospector dentro do CRIS OS.

A Maquina de Leads continua sendo a fonte unica de regras de negocio
(motor/engine). Este pacote apenas a chama como biblioteca. A pasta dela e
configuravel via env PROSPECTOR_ML_DIR, com o caminho padrao desta maquina.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_ML_DIR = r"C:\Users\Evand\Documents\MAQUINA DE LEDES\MAQUINA-DE-LEADS"


def ml_dir() -> Path:
    """Pasta raiz da Maquina de Leads (motor/engine/configs)."""
    return Path(os.getenv("PROSPECTOR_ML_DIR", DEFAULT_ML_DIR)).expanduser()


def ml_db_path() -> Path:
    """Banco SQLite usado pelo motor da Maquina de Leads."""
    return ml_dir() / "prospector.db"
