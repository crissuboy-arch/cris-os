# CRIS OS v1.0 — Release Notes

**Data:** 2026-07-30  
**Tag:** `v1.0.0`  
**Branch:** `feature/ods-integration`

---

## Visao Geral

CRIS OS e o sistema operacional pessoal da Cris — uma equipe de agentes de IA rodando localmente, coordenada por um gerente (Orquestrador). O usuario conversa pelo Telegram com seu time de especialistas digitais.

---

## Novidades desde v0.6.0

### Telegram Channel (Fase 7)

- **Conversa Natural**: interpretacao de linguagem natural em portugues, deteccao de intencao e keywords, selecao automatica do agente especialista
- **8 Agentes Especialistas**: marketing, social_media, vendas, atendimento, programador, pesquisador, copywriter, produtividade
- **Agente Fixo**: comando `/use <nome>` para fixar um agente; `/use auto` para voltar ao automatico
- **Followup Detection**: mensagens curtas como "continue" reusam o ultimo agente

### Confirmacao Humana

- **Confirmacao por Botao Inline**: botoes "Aprovar" e "Rejeitar" nas mensagens
- **Confirmacao por Comando**: `/approve <id>` e `/reject <id>`
- **Tokens Unicos**: cada confirmacao tem ID unico — bloqueio de reuso apos aprovacao/rejeicao
- **Expiracao**: confirmacoes expiram apos 15 minutos
- **Isolamento por Usuario**: confirmacoes de um usuario nao sao visiveis para outro
- **Historico**: todas as acoes (criacao, aprovacao, rejeicao, expiracao) sao registradas

### Persistencia e Metricas

- **Conversas**: salvas automaticamente via MemoryManager (SQLite)
- **Logs de Execucao**: cada mensagem registrada com usuario, agente, duracao, erro
- **Metricas**: contagem de mensagens por agente, confirmacoes aprovadas/rejeitadas
- **Context Flag**: estado do usuario preservado entre sessoes
- **Recuperacao**: ao reiniciar, o contexto das ultimas conversas e restaurado

### Plugin Telegram

- 10 capabilities registradas: send, reply, notify, confirm, reject, health, metrics, execute_agent, get_status, get_logs
- Comandos `/start`, `/agent`, `/agents`, `/use`, `/status`, `/clear`, `/approve`, `/reject`, `/confirmations`, `/ods`

### Estabilizacao (Fase 8)

- **656 testes** — todos verdes, 0 falhas, 0 erros
- PluginLoader corrigido para evitar conflitos de namespace
- `__init__.py` adicionado em todos os diretorios de plugin
- Build do frontend validado
- Sem segredos ou credenciais no repositorio
- Documentacao completa de instalacao e uso

---

## Como Instalar

```powershell
git clone https://github.com/crissuboy-arch/cris-os.git
cd cris-os
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edite .env com seu TELEGRAM_BOT_TOKEN
python main.py
```

## Como Testar

```powershell
python -m pytest
```

---

## Stack

| Componente | Tecnologia |
|---|---|
| Backend | Python 3.11+ (Clean Architecture + Event-Driven) |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Chat | Telegram Bot API (python-telegram-bot 21.6) |
| IA Local | Ollama (llama3.1, qwen2.5) |
| IA Nuvem | NVIDIA AI (8B/70B), OpenAI, Gemini |
| Banco | SQLite |
| Deploy | ODS (Osmantic Deployment System) |

---

## Links

- **Repositorio**: https://github.com/crissuboy-arch/cris-os
- **Documentacao**: ARQUITETURA.md
- **Changelog**: CHANGELOG.md