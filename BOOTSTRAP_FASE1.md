# 🚀 BOOTSTRAP — Fase 1 do CRIS OS

Objetivo: colocar o CRIS OS **rodando de ponta a ponta hoje**.

**Escopo desta fase:** Secretária IA · Telegram · Ollama local · Orquestrador ·
SQLite/memória. **Sem** WhatsApp, **sem** Google Calendar, **sem** novas
integrações, **sem** refatoração. Só ligar o que já existe.

> Comandos no **PowerShell** (Windows). No fim há um **checklist** e o **primeiro
> teste** que você deve fazer no Telegram.

---

## ✅ Pré-requisitos
- **Python 3.10+** (você tem 3.12 — ok).
- **Ollama** instalado e rodando — https://ollama.com
- Conta no **Telegram**.

---

## Passo a passo

### Passo 1 — Criar o `.env`
```powershell
Copy-Item .env.example .env
notepad .env
```
Você só precisa mexer em **duas seções**: Telegram e Ollama. O resto já tem
padrão bom.

### Passo 2 — Configurar o Telegram
1. No Telegram, fale com **@BotFather** → `/newbot` → siga as instruções → copie o
   **token**.
2. (Recomendado) Fale com **@userinfobot** para descobrir seu **ID numérico**.
3. No `.env`, preencha:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC-seu-token-aqui
   TELEGRAM_ALLOWED_USER_ID=seu_id_numerico
   ```
   > `TELEGRAM_ALLOWED_USER_ID` faz o bot responder **só a você**. Deixar vazio
   > libera para qualquer pessoa (não recomendado).

### Passo 3 — Configurar o modelo do Ollama
**Modelo funcional atual:** `qwen2.5-coder:1.5b` (cabe na memória desta máquina). No `.env`:
```
OLLAMA_MODEL=qwen2.5-coder:1.5b
OLLAMA_NUM_GPU=0
```

> 📌 **Sobre o llama3.1 (status real):** ele **foi baixado** (`ollama pull llama3.1`,
> 4.9 GB), mas **não carrega nesta máquina** — falha ao alocar a memória de carga
> (~3,4 GB) porque o **limite de memória comprometida (commit / page file) do
> Windows** está quase no teto (sobra ~1,4 GB; o modelo 8B precisa ~8 GB). **Não é
> GPU nem falta de RAM física** — é o page file. Detalhes, modelo recomendado
> futuro e como resolver: ver **[MODELOS.md](MODELOS.md)**.
>
> Enquanto o page file não for ajustado, o `qwen2.5-coder:1.5b` é o modelo em uso
> (sem tool-calling real — o roteamento cai no fallback por palavra-chave).
>
> `OLLAMA_NUM_GPU=0` força CPU por requisição (ver Passo 5 sobre o porquê).

### Passo 4 — Instalar as dependências
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
> Se o PowerShell bloquear o `Activate.ps1`, rode antes:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

### Passo 5 — Iniciar o Ollama em **CPU** (importante nesta máquina)
> ⚠️ **A GPU desta máquina não comporta o modelo** (dá `CUDA out of memory`). Por
> isso o CRIS OS roda o Ollama **em CPU**. Há duas proteções: o `.env` já vem com
> `OLLAMA_NUM_GPU=0`, e existe um script que sobe o Ollama **sem GPU**.

Use **sempre** o script (mantenha a janela aberta) em vez do app de bandeja do Ollama:
```powershell
scripts\start_ollama_cpu.cmd
```
Ele para qualquer Ollama com GPU, define `CUDA_VISIBLE_DEVICES=-1` e roda
`ollama serve` em CPU. Para conferir o que está baixado: `ollama list`.

### Passo 6 — Verificar tudo de uma vez (preflight)
```powershell
python scripts/preflight.py
```
Corrija os itens marcados com `[--]`. Os `[!!]` são só avisos (ex.: banco ainda
não criado — normal antes do primeiro boot).

### Passo 7 — Testar o núcleo sem subir o bot
```powershell
python tests/test_smoke.py
```
Esperado: `OK - Todos os smoke tests (v3 + cognicao) passaram!`

### Passo 8 — Rodar o CRIS OS
```powershell
python main.py
```
Esperado no terminal:
```
... | INFO | cris-os | Iniciando o CRIS OS...
... | INFO | core.runtime | CRIS OS montado. Modelo: llama3.1 | Agentes: secretary, ... | Cognição: registrada (inativa)
... | INFO | cris-os | Tudo pronto! Abra o Telegram e fale com o seu bot. (Ctrl+C para parar)
```
Deixe essa janela aberta (é o bot rodando). Para parar: **Ctrl+C**.

### Passo 9 — Testar no Telegram
Abra a conversa com o seu bot → `/start` → mande uma mensagem (ver exemplo no fim).

---

## 🧾 Checklist final
Rode `python scripts/preflight.py` (com o `main.py` já tendo rodado ao menos uma vez)
para confirmar quase tudo automaticamente:

| # | Item | Como confirmar |
|---|---|---|
| 1 | **Ollama ativo** | preflight: `[OK] Ollama ativo` (ou `ollama serve`) |
| 2 | **Modelo instalado** | preflight: `[OK] modelo '...' instalado` (ou `ollama list`) |
| 3 | **Token Telegram configurado** | preflight: `[OK] TELEGRAM_BOT_TOKEN configurado` |
| 4 | **Banco SQLite criado** | preflight: `[OK] banco cris_os.db criado` (após 1º `main.py`) |
| 5 | **Bot respondeu no Telegram** | você recebeu a resposta da Secretária |
| 6 | **Evento registrado no Event Log** | preflight: `[OK] Event Log: N eventos` (N > 0) |
| 7 | **Memória funcionando** | preflight: `[OK] memoria permanente (L3): N itens` e `conversas (L1): N` |

---

## 💬 Primeiro teste no Telegram
Depois do `/start`, mande **uma mensagem bagunçada de propósito**, por exemplo:

> **"tenho que gravar um reels do vitrinepro, responder um cliente do zavix, beber água e marcar o dentista"**

O que esperar da **Secretária**:
- um **resumo** do que ela entendeu;
- tarefas **priorizadas** e **separadas** em pessoal × negócio;
- uma **próxima ação** concreta.

Depois, confirme a persistência:
```powershell
python scripts/preflight.py
```
Você deve ver `Event Log: N eventos` e `conversas (L1)` aumentando — prova de que
o pipeline (Orquestrador → agente → memória → event log) rodou de ponta a ponta.

---

## 🛟 Problemas comuns
- **"O Ollama não respondeu"** → `ollama serve`; confira `OLLAMA_HOST` no `.env`.
- **"modelo NAO encontrado"** → `ollama pull <modelo>` com o mesmo nome do `.env`.
- **Bot não responde** → confira `TELEGRAM_BOT_TOKEN`; se setou `TELEGRAM_ALLOWED_USER_ID`,
  garanta que é o **seu** ID.
- **Respostas fracas / sempre na Secretária** → modelo pequeno sem tool-calling;
  use `llama3.1`. (O sistema cai no fallback de propósito para nunca te deixar sem resposta.)
- **`Activate.ps1` bloqueado** → `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
