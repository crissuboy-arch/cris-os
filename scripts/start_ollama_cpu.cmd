@echo off
REM ============================================================
REM  CRIS OS - Inicia o Ollama em modo CPU (GPU desabilitada).
REM
REM  Por que: a GPU desta maquina nao comporta o modelo e gera
REM  "CUDA out of memory". Este script forca CPU 100%%.
REM
REM  Uso: de um duplo-clique OU rode no terminal:
REM       scripts\start_ollama_cpu.cmd
REM  Deixe a janela ABERTA enquanto usar o CRIS OS.
REM ============================================================

echo [CRIS OS] Parando instancias do Ollama (se houver)...
taskkill /IM "ollama app.exe" /F >nul 2>&1
taskkill /IM "ollama.exe" /F >nul 2>&1
timeout /t 2 /nobreak >nul

REM Esconde a GPU do Ollama -> roda 100%% em CPU (sem CUDA).
set CUDA_VISIBLE_DEVICES=-1
set OLLAMA_NUM_GPU=0

echo [CRIS OS] Iniciando Ollama em CPU (CUDA_VISIBLE_DEVICES=-1)...
echo [CRIS OS] Deixe esta janela ABERTA. Pressione Ctrl+C para parar.
echo.
ollama serve
