#!/usr/bin/env bash
# ============================================================
# CRIS OS - Atalho para iniciar (Linux / macOS / Git Bash)
# Uso:  bash scripts/run.sh
# ============================================================
set -e

# Vai para a raiz do projeto (pasta acima de "scripts").
cd "$(dirname "$0")/.."

# Ativa o ambiente virtual, se existir.
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Inicia o CRIS OS.
python main.py
