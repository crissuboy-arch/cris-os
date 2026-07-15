# ============================================================
# CRIS OS - Atalho para iniciar (Windows / PowerShell)
# Uso:  .\scripts\run.ps1
# ============================================================

# Vai para a raiz do projeto (pasta acima de "scripts").
Set-Location -Path (Join-Path $PSScriptRoot "..")

# Ativa o ambiente virtual, se existir.
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}

# Inicia o CRIS OS.
python main.py
