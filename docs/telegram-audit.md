# Auditoria da Integração Telegram — CRIS OS

**Data:** 2026-07-29
**Versão:** v0.6.0 (Fase 6 completa)
**Status:** Diagnóstico completo

---

## 1. Arquivos Envolvidos

| Arquivo | Linhas | Função |
|---------|--------|--------|
| `channels/telegram/bot.py` | 172 | Adapter Telegram (comandos + handler de texto) |
| `channels/telegram/__init__.py` | 1 | Re-export |
| `channels/__init__.py` | 6 | Package docstring |
| `core/gateway.py` | 61 | Ponto de entrada único dos canais no Core |
| `core/runtime.py` | 379 | Composition root — Wiring de tudo |
| `core/models.py` | 194 | `IncomingMessage`, `OutgoingMessage`, `Task`, `AgentResult` |
| `core/contracts/channel.py` | 28 | Protocolo `Channel` |
| `agent_builder/notifier.py` | 178 | Notificações Telegram via HTTP raw |
| `agent_builder/confirmation_gateway.py` | 146 | Fila de confirmações (Studio only) |
| `core/application/confirmation.py` | — | `ConfirmationGate` (bloqueia steps sensíveis) |
| `main.py` | — | Entry point, suprime logs do Telegram |

---

## 2. Fluxo Atual de Mensagens

```
┌─────────────────────────────────────────────────────────────────┐
│  Cris (App Telegram)                                            │
└────────────────────────┬────────────────────────────────────────┘
                         │ Update (texto/comando)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  TelegramChannel (bot.py)                                       │
│  ├── python-telegram-bot (long-polling, async)                  │
│  ├── CommandHandler: /start, /agent, /agents, /use, /ods        │
│  ├── MessageHandler: texto livre → _on_message()                │
│  └── asyncio.to_thread(gateway.handle, incoming)                │
└────────────────────────┬────────────────────────────────────────┘
                         │ IncomingMessage(channel="telegram", sender_id, text)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Gateway (core/gateway.py)                                      │
│  ├── allowed_senders check (TELEGRAM_ALLOWED_USER_ID)           │
│  └── orchestrator.handle(incoming) → str                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌─────────────────────┐    ┌─────────────────────────────┐
│ Classic Orchestrator │    │ AgentOrchestrator (auto)    │
│ IntentRouter →       │    │ LLM/keyword → escolhe       │
│ Dispatcher →         │    │ SpecialistAgent.generate()  │
│ Composer             │    │                             │
└──────────┬──────────┘    └──────────────┬──────────────┘
           │                              │
           └──────────────┬───────────────┘
                          ▼
                 resposta (str)
                          │
                          ▼
              TelegramChannel._on_message()
              reply_text(resposta)
```

---

## 3. Comandos Registrados

| Comando | Handler | Requer | Estado |
|---------|---------|--------|--------|
| `/start` | `_on_start` | — | ✅ Funciona |
| `/agent` | `_on_agent` | `agent_orchestrator` | ✅ Funciona |
| `/agents` | `_on_agents` | `agent_orchestrator` | ✅ Funciona |
| `/use <nome>` | `_on_use` | `agent_orchestrator` | ✅ Funciona |
| `/ods` | `_on_ods` | `ods_client` | ✅ Funciona |
| Texto livre | `_on_message` | — | ✅ Funciona |
| `/help` | — | — | ❌ Não existe |
| `/status` | — | — | ❌ Não existe |
| `/run` | — | — | ❌ Não existe |
| `/notes` | — | — | ❌ Não existe |
| `/tasks` | — | — | ❌ Não existe |
| `/logs` | — | — | ❌ Não existe |
| `/approve` | — | — | ❌ Não existe |
| `/reject` | — | — | ❌ Não existe |

---

## 4. Acoplamentos Encontrados

### 🔴 Acoplamentos Diretos (quebram contratos)

| Local | Problema | Risco |
|-------|----------|-------|
| `core/agent/runtime.py:168-173` | Acessa `plugin_loader._registry`, `._event_bus`, `._config_store`, `._permission_checker` (atributos privados) | Alto |
| `agent_builder/builder.py:309` | Faz `self._registry._items.pop()` diretamente | Médio |
| `web/backend/routes/studio.py:392` | Acessa `builder._registry` | Médio |
| `web/backend/routes/studio.py:496,526` | Acessa `builder._unregister_agent()` | Médio |
| `agent_builder/notifier.py:20-21` | Lê `os.environ` diretamente em vez de `config.settings` | Baixo |

### 🟡 Integrações Incompletas

| Componente | Problema |
|------------|----------|
| `StudioNotifier` → Telegram | Envia notificações com texto sugerindo `/confirm_*` e `/reject_*`, mas **não existem handlers** no bot |
| `ConfirmationGate` → Telegram | Bloqueia steps sensíveis, mas **não há como o utilizador confirmar via Telegram** |
| `StudioConfirmationGateway` → Telegram | Fila de confirmações isolada, sem conexão com o bot |
| `Channel.send()` | Protocolo **não tem método `send()`** — mensagens proativas impossíveis |

### 🟠 Dois Clients Telegram Independentes

| Client | Uso | Biblioteca |
|--------|-----|------------|
| `TelegramChannel` (bot.py) | Bot (recebe mensagens) | `python-telegram-bot` (async) |
| `StudioNotifier` (notifier.py) | Notificações (envia mensagens) | `urllib.request` (sync, raw HTTP) |

---

## 5. O que Funciona vs. o que Precisa Migrar

### ✅ FUNCIONA (manter)

- Bot startup (long-polling)
- `/start`, `/agent`, `/agents`, `/use`, `/ods`
- Texto livre → Gateway → Orchestrator/AgentOrchestrator
- Authorization (allowed_senders)
- Typing indicator
- Conversation memory (L1)
- Event publishing
- Skill execution

### ⚠️ FUNCIONA PARCIALMENTE (corrigir)

- StudioNotifier envia notificações, mas o bot não tem handlers para responder
- ConfirmationGate bloqueia, mas não há fluxo de confirmação no Telegram

### ❌ NÃO EXISTE (criar)

- `/help`, `/status`, `/run`, `/notes`, `/tasks`, `/logs`, `/approve`, `/reject`
- Botões inline (Aprovar/Rejeitar)
- Callback handler para botões
- Expiração de confirmações
- Contexto por utilizador (multi-user)
- Notificações proativas (tarefa concluída, erro, etc.)
- Plugin Telegram via CoreAPI/CapabilityRegistry
- Observabilidade (logs, métricas, latência)
- `send()` no Channel protocol

---

## 6. Dependências

### Bibliotecas Externas

| Biblioteca | Uso | Onde |
|------------|-----|------|
| `python-telegram-bot` | Bot (async, long-polling) | `channels/telegram/bot.py` |
| `urllib.request` | Notificações (sync, HTTP) | `agent_builder/notifier.py` |

### Dependências Internas

| Módulo | Depende de |
|--------|------------|
| `TelegramChannel` | `core.contracts.channel.Handler`, `core.models.IncomingMessage` |
| `Gateway` | `core.models.IncomingMessage` |
| `AgentRuntime` | `core.contracts.agent.Agent`, `core.models.AgentResult`, `core.models.Task` |
| `AgentBuilder` | `agent_builder.agent.DynamicAgent`, `agent_builder.models.*`, `agent_builder.store.AgentStore` |
| `StudioNotifier` | `os.environ` (direto) |

---

## 7. Recomendações para Migração

### 7.1 Correções Imediatas (Baixo Risco)

1. **Adicionar `/confirm` e `/reject` handlers** ao `bot.py`
2. **Adicionar `TELEGRAM_CHAT_ID` ao `Settings`**
3. **Corrigir acoplamentos** em `AgentRuntime`, `AgentBuilder`, `Studio routes`
4. **Usar `config.settings`** no `notifier.py`

### 7.2 Melhorias Arquiteturais (Médio Risco)

5. **Unificar clients Telegram** — extrair `TelegramClient` compartilhado
6. **Adicionar `send()` ao protocolo `Channel`** — mensagens proativas
7. **Persistir estado de confirmações** — SQLite em vez de in-memory
8. **Conectar ConfirmationGateway ao Telegram** — botões inline

### 7.3 Migração Estrutural (Maior Risco)

9. **Extrair handler registry** — comandos como plugins
10. **Conectar Studio agents ao fluxo Telegram** — DynamicAgent registry
11. **Multi-channel threading** — `CrisOS.run()` com múltiplos canais

---

## 8. Conclusão

A integração Telegram atual é **funcional para o caso de uso básico** (receber mensagem, rotear, responder). Porém, apresenta:

- **5 acoplamentos** a atributos privados
- **2 sistemas de notificação** independentes
- **Fluxo de confirmação** incompleto
- **Protocolo Channel** sem suporte a mensagens proativas
- **10 comandos** planejados mas não implementados

A Etapa 7.1 corrige os acoplamentos e prepara a base. As Etapas 7.2–7.6 implementam as funcionalidades faltantes.
