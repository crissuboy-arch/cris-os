# CRIS OS — memory.md (estado da construção)

> ⚠️ **Isto NÃO é a memória de runtime do sistema.** A memória que os agentes
> usam vive no banco **SQLite (`data/cris_os.db`)**, em 4 camadas (pacote
> `memory/` + ARQUITETURA.md §6). Este arquivo é o **"onde paramos"** da
> *construção* do CRIS OS — para a Cris e para o Claude Code entre sessões.

**Goal:** Construir o sistema operacional pessoal da Cris (equipe de agentes) que
automatize a vida pessoal e profissional e cresça por anos.
**Owner:** Cris (dona única).
**Updated:** 2026-07-28

## Onde estamos (fases)
- **Arquitetura v3** (Clean Architecture + event-driven + memória 4 camadas + plugins): **pronta**.
- **Camada de cognição** (Planner/Execution Manager/Quality Supervisor): **esqueleto no runtime, INATIVA** (`NotImplementedError`).
- **Fase 1** (Secretária via Telegram + Ollama + Orquestrador): **funcionando em produção**; roda com `OLLAMA_MODEL=qwen2.5-coder:1.5b` (llama3.1 8B não sobe por limite de commit/page-file do Windows).
- **Sistema de Skills:** SDK + Registry + 5 skills descobertas; `session-handoff` completa, habilitada e **executando em produção**.
- **ONDA 1 (estabilização):** ✅ concluída (B0–B7) — ver [ONDA1_COMPLETED.md](ONDA1_COMPLETED.md).
- **ONDA 2 (execução real de skills):** ✅ **CONCLUÍDA e validada no Telegram real** — ver [ONDA2_COMPLETED.md](ONDA2_COMPLETED.md).

## Baseline v1 — Core Module 1 (Capability Registry)
- **Status:** CONCLUÍDO E CONGELADO ✅
- **Checkpoint:** [docs/baseline-v1-capability-registry.md](docs/baseline-v1-capability-registry.md)
- **Testes:** 196/196 passando
- **Exemplo:** `python examples/capability_registry_demo.py`
- **Interfaces públicas congeladas** — breaking changes exigem versionamento major
- **Próximo módulo:** Event Bus (Module 2)

## Próximos passos (após aprovação do checkpoint)
1. Implementar **Event Bus** — backbone event-driven (pub/sub síncrono + assíncrono opcional)
2. Implementar **Event Log** — append-only em SQLite (auditoria, replicação, failover)

## ONDA 2 — todos os blocos concluídos
| Bloco | O quê | Status |
|---|---|---|
| B0 | Freeze + plano ([ONDA2_PLAN.md](ONDA2_PLAN.md)) | ✅ |
| B1 | `SkillResult` (DTO tolerante a dict) + eventos `skill.started/completed/failed` | ✅ |
| B2 | `load_executor` com **cache** (nome@versão) + validação de contrato (`SkillLoadError`) | ✅ |
| B3 | Porta estreita `SkillMemory` + adapter `FacadeSkillMemory` | ✅ |
| B4 | `SkillRunner` (executa skill, rastreia Task, emite `skill.*`) | ✅ |
| B5 | **Kernel de execução** + roteamento de skills (tools do `input_schema` + **fallback por keyword do manifest**) | ✅ |
| B6 | **ConfirmationGate** (read-only passa; `SENSITIVE` exige confirmação) | ✅ |
| B7 | **Browser Tool SOMENTE LEITURA** (Playwright lazy) + `BrowserTarget` (`type=TOOL`) | ✅ |

### Kernel de execução (DTO universal) — resumo
- `core/domain/execution.py` → `ExecutionType` (AGENT/SKILL/TOOL/MCP/PLANNER/WORKFLOW) + `Effect` (READ_ONLY/SENSITIVE).
- `core/models.py` → `ExecutionStep` (entrada; `effect` + reservados) e `ExecutionResult` (saída UNIVERSAL; `of`/`from_agent`/`from_skill`).
- `core/contracts/execution.py` → `ExecutionTarget` (`id` estável + `type` + `run`) + `DispatchContext` (`confirmed`).
- `core/application/` → `dispatcher.py` (`TargetRegistry` + `ExecutionDispatcher`+gate), `targets.py` (`AgentTarget`/`SkillTarget`), `confirmation.py`.
- `tools/browser/` → `BrowserTool` (read-only) + `BrowserTarget`. Runtime registra: `agent.workflow` + `skill.runner` + `tool.browser`.
- Fluxo: `msg → IntentRouter → [ExecutionStep] → Dispatcher(+Gate) → TargetRegistry.get(type).run → ExecutionResult → Composer → Cris`.
- **Adicionar Browser/MCP/Planner/DeepSearch = novo `ExecutionTarget` + `register(...)`** (OCP).

## ✅ Validação em produção (Telegram real) — 2026-07-01
A Cris (`telegram:6460872429`) enviou **"faça o handoff desta sessão"** e o fluxo rodou ponta a ponta (**2×**):
`Gateway → IntentRouter (Fallback por keyword de SKILL → session-handoff) → Dispatcher → SkillTarget → SkillRunner (skill.started/completed) → session-handoff (created) → ExecutionResult → Composer → resposta` + **L3 recebeu `type=handoff`** (tags `handoff, telegram:6460872429`).
Evidências completas (event log corr `046ba49b`/`61c62b2d`, linhas de log, itens L3) em **[ONDA2_COMPLETED.md](ONDA2_COMPLETED.md)**.
> Observação: como o `qwen 1.5b` não faz tool-calling confiável, a skill é alcançada pelo **fallback por keyword do manifest** — não pela etapa 2 do LLM. Arquitetura pronta para o caminho por LLM quando houver modelo capaz.

## Testes (todos verdes) — `python tests/<arquivo>.py`
registries · skill_registry · loader · router · storage · memory_facade · skill_memory ·
intent_router · runtime_build · skill_execution · skill_result · skill_runner ·
execution_types · execution_result · dispatcher · **confirmation_gate** · **browser_tool** ·
smoke · session_handoff  (17 unitários + smoke + integração)

## Protocolo de trabalho (manter)
Por bloco: explicar arquivo-por-arquivo ANTES de editar → menor alteração → rodar TODOS os
testes + smoke → diff resumido → explicar compat com **ARCHITECTURE_FREEZE.md** (aditivo-only) →
**parar e aguardar aprovação**. Só o Orquestrador fala com a Cris; agentes/skills nunca direto.
Nada de segredos no repo (`.env` no `.gitignore`).

## Operacional do bot (importante)
Manter `python main.py` vivo exige rodar **no terminal da Cris** (processos em background lançados
pelo agente não persistem entre turnos). Se der `Conflict 409`: garantir **uma única** instância e
esperar ~1 min (a sessão `getUpdates` anterior expira no lado do Telegram).

## Próximos passos (Onda 3 — a planejar)
1. **Roteamento de skill por LLM** com modelo capaz de tool-calling (ou gatilhos por keyword ampliados).
2. **ConfirmationGate — pause/resume completo** (executar de fato após "confirmar" da Cris).
3. **Browser Tool**: tornar roteável por linguagem natural + `playwright install chromium`.
4. Revisar/ativar a **camada de cognição** (Planner/Execution/Quality).
5. Só então: integrações externas (Calendar, WhatsApp, MCP).

## CRIS OS Studio — Fase 6 CONCLUÍDA ✅
- **Tag:** `studio-phase-6` (sub-tags: 6a, 6b, 6c, 6d)
- **Commits:** f2671f5 (6a), 3f6bd41 (6b), 3e2ec06 (6c), 9be7d75 (6d), dd75d4d (consolidacao)
- **Testes:** 144/144 pytest pass, tsc clean, build OK
- **Resumo das sub-fases:**
  - **6a (Bugfix payload):** `formToPayload()` agora envia `instructions`, `memory`, `permissions`, `tools` como top-level (antes ficavam perdidos em `metadata`)
  - **6b (System Prompt Preview):** componente `PromptPreview.tsx` monta o system prompt em tempo real no editor
  - **6c (Agent Playground):** modal completo com input, output, status bar, system prompt toggle, metadata toggle, copiar
  - **6d (Templates):** 5 presets de agente (Assistente Pessoal, Atendimento, Marketing, Vendas, Programador) + seletor no CreateAgentModal

## audit_log
- **2026-06-29** — 1ª auditoria após adotar o modelo de 6 camadas (ver [OS-AUDIT.md](OS-AUDIT.md)).
- **2026-07-01** — ONDA 2 concluída (B0–B7): kernel de execução, gate de confirmação, Browser read-only.
  **Validada em produção no Telegram real**: `session-handoff` acionada via fallback por keyword,
  `skill.started/completed` emitidos, L3 gravou `type=handoff` (corr `046ba49b`/`61c62b2d`). Ver [ONDA2_COMPLETED.md](ONDA2_COMPLETED.md).
