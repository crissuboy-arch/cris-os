# Changelog

All notable changes to CRIS OS will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v1.0.0] - 2026-07-30

### CRIS OS v1.0 — Release Oficial

#### Added
- **Fase 7.1**: Canal Telegram com `ConversationManager`, `NaturalLanguageInterpreter`, `AgentSelector`, `UserContextManager`
- **Fase 7.2**: Plugin oficial CRIS Telegram com 10 capabilities (send, reply, notify, confirm, reject, health, metrics, execute_agent, get_status, get_logs)
- **Fase 7.3**: Conversa natural — interpretacao de linguagem natural, selecao automatica de agente por keywords, followup detection, contexto por utilizador, fallback para agente geral
- **Fase 7.4**: Sistema completo de confirmacao humana — `ConfirmationGateway` com tokens unicos, expiracao (15 min), botoes inline (approve/reject), comandos `/approve`/`/reject`, bloqueio de reuso do mesmo token, isolamento por utilizador, cleanup automatico de expirados
- **Fase 7.5**: Persistencia de conversas (`MemoryManager`), logs de execucao (`ActivityLogger`), metricas (`MetricEntry`), flags de contexto, formato de historico para recuperacao
- **Fase 7.6**: Validacao ponta a ponta — 87 testes end-to-end cobrindo todos os 16 requisitos do fluxo Telegram

#### Fixed
- **PluginLoader**: modulo carregado como `plugins.{name}.plugin` (nao `plugins.{name}`) para evitar conflito com namespace packages
- **plugins/**: adicionados `__init__.py` em todos os diretorios de plugin para resolver erros de importacao
- **test_cris_notes.py**: 32 erros de setup + 1 falha resolvidos (importacao de modulo)

#### Changed
- README atualizado com 656 testes (vs 144 anteriores)
- ARQUITETURA.md sincronizada com a implementacao atual
- Roadmap atualizado com marcos pos-v1.0

#### Technical Details
- **Commits**: studio-phase-7a a studio-phase-7f, phase-8-stabilization
- **Tests**: 656/656 pytest passing (0 failed, 0 errors)
- **TypeScript**: clean (no errors)
- **Build**: successful
- **Tags**: `v1.0.0-rc1`, `v1.0.0`
- **Python**: 3.11+
- **Node.js**: 18+

---

### CRIS OS Studio - Fase 6

#### Added
- **System Prompt Preview** (`PromptPreview.tsx`): preview em tempo real do system prompt montado no editor, espelhando `DynamicAgent._build_system_prompt`
- **Agent Playground** (`AgentPlayground.tsx`): modal completo de teste com input, output, status bar, system prompt toggle, metadata toggle, e botão copiar
- **Agent Templates** (`templates.py`): 5 presets de agente para criação rápida:
  - Assistente Pessoal (organização, tarefas, notas)
  - Atendimento ao Cliente (suporte com aprovação)
  - Marketing / Social Media (conteúdo para redes)
  - Vendas (propostas, follow-up)
  - Programador (revisão, debugging, explicações)
- **Template Selector** (`CreateAgentModal.tsx`): grid de cards com seleção visual de templates

#### Fixed
- **Payload Bugfix**: `formToPayload()` agora envia `instructions`, `memory`, `permissions`, `tools` como top-level (antes ficavam perdidos em `metadata`)
- **StudioAgent model**: adicionados campos `instructions`, `memory`, `permissions`, `tools` ao modelo

#### Changed
- `StudioAgentEditor.tsx`: tabs Prompt e Playground integrados no painel lateral
- `studio.py`: 2 novos endpoints (`GET /studio/templates`, `GET /studio/templates/{id}`)
- `api.ts`: endpoints `studioApi.templates()` e `studioApi.template(id)`

### Technical Details
- **Commits**: f2671f5 (6a), 3f6bd41 (6b), 3e2ec06 (6c), 9be7d75 (6d), dd75d4d (consolidacao)
- **Tests**: 144/144 pytest passing
- **TypeScript**: clean (no errors)
- **Build**: successful (758KB bundle, 212KB gzipped)
- **Tags**: `studio-phase-6a`, `studio-phase-6b`, `studio-phase-6c`, `studio-phase-6d`, `studio-phase-6`

---

## [v0.5.0] - 2026-07-28

### CRIS OS Studio - Fase 5

#### Added
- **JWT Authentication**: login/logout, token management, user CRUD
- **MCP Executor**: MCP server registration, tool discovery, execution via stdio
- **Telegram Notifier**: notifications for confirmations and pending actions
- **Version Diff**: recursive dict diff for agent version comparison
- **Export/Import**: agent export/import with manifest validation
- **Executive Dashboard**: metrics visualization with recharts (line, bar, pie charts)

#### Technical Details
- **Tags**: `studio-phase-5`
- **Tests**: 144/144 passing
- **Commits**: multiple across Fase 5 implementation

---

## [v0.4.0] - 2026-07-27

### CRIS OS Studio - Fase 4

#### Added
- **Runtime Integration**: agent execution via `AgentBuilder.test()`
- **Observability**: execution log, metrics, memory visualization
- **HTTP Executor**: external HTTP tool execution
- **Confirmation Gateway**: pending confirmations management
- **Studio Memory**: session and agent memory visualization

#### Technical Details
- **Tags**: `studio-phase-4`
- **Tests**: 144/144 passing

---

## [v0.3.0] - 2026-07-26

### CRIS OS Studio - Fase 3

#### Added
- **Agent Editor**: visual configuration of instructions, memory, permissions, tools
- **Binding System**: fixed values, input sources, context sources, previous results
- **Permission System**: allow/deny/confirmation_required rules
- **Memory Configuration**: session/agent scope, read/write controls
- **Tool Configuration**: HTTP and MCP tool binding

#### Technical Details
- **Tags**: `studio-phase-3`
- **Tests**: 144/144 passing

---

## [v0.2.0] - 2026-07-25

### CRIS OS Studio - Fase 2

#### Added
- **Agent CRUD**: create, read, update, delete agents
- **Dashboard**: agent list with status, version, metrics
- **Agent Status**: draft/published/inactive states
- **Version Management**: version history and snapshots

#### Technical Details
- **Tags**: `studio-phase-2`
- **Tests**: 144/144 passing

---

## [v0.1.0] - 2026-07-24

### CRIS OS Studio - Fase 1

#### Added
- **Studio Dashboard**: main interface for agent management
- **React Frontend**: Vite + TypeScript + Tailwind CSS
- **FastAPI Backend**: REST API for agent operations
- **Dark Theme**: consistent design system

#### Technical Details
- **Tags**: `studio-phase-1`
- **Tests**: 144/144 passing

---

## [v0.0.1] - 2026-07-15

### Initial Release

#### Added
- Core CRIS OS architecture (Clean Architecture + event-driven)
- Telegram integration with Ollama
- Agent runtime with skill execution
- Capability registry with 3 plugins
- Memory system with 4 layers
- Basic testing suite

#### Technical Details
- **Tests**: 196/196 passing
- **Python**: 3.11+
- **Node.js**: 18+
