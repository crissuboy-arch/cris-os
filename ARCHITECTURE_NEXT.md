# 🧭 ARCHITECTURE_NEXT — Auditoria completa do CRIS OS

**Data:** 2026-06-30 · **Tipo:** auditoria técnica (somente análise; **nenhum código alterado, nenhum arquivo existente modificado**).
**Objetivo:** manter a arquitetura limpa, escalável e preparada para **~100 agentes** e **~300 Skills**.
**Estado auditado:** v3 (hexagonal/event-driven) + camada de Skills (Registry/SDK) + 1ª Skill completa (Session Handoff).

> Complementa e atualiza [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) (inclui agora a camada de Skills e o caminho de execução).

---

## 1. Respostas diretas às 20 perguntas

| # | Pergunta | Resposta | Findings |
|---|---|---|---|
| 1 | Duplicação de código? | **Sim** | N2, N3, N12, N22 |
| 2 | Acoplamento desnecessário? | **Sim** | N4 |
| 3 | Violação de Clean Architecture? | **Sim (pontual)** | N4, N21 |
| 4 | Violação de SOLID? | **Sim** | N5, N7, N8, N14 |
| 5 | Gargalo para escalar? | **Sim (crítico)** | N1, N7, N9, N10 |
| 6 | Responsabilidade misturada? | **Sim** | N6, N14, N20 |
| 7 | Pasta a reorganizar? | **Parcial** | N21 |
| 8 | Código morto? | **Sim** | N6, N22 |
| 9 | Abstração cedo demais? | **Sim** | N6, N17, N22 |
| 10 | Abstração faltando? | **Sim** | N1, N8, N11 |
| 11 | Melhoria de performance? | **Sim** | N7, N9, N15 |
| 12 | Melhoria para memória? | **Sim** | N9, N19, N20 |
| 13 | Melhoria para Event Bus? | **Sim** | N10, N15 |
| 14 | Melhoria para Skills? | **Sim** | N7, N8 |
| 15 | Melhoria para Agents? | **Sim** | N1, N5 |
| 16 | Melhoria para o Orchestrator? | **Sim** | N1, N6 |
| 17 | Melhoria para Cognição? | **Sim** | N6, N16 |
| 18 | Melhoria para 2ª máquina? | **Sim** | N10, N17 |
| 19 | Melhoria para multiusuário? | **Sim** | N11 |
| 20 | Melhoria para Browser/MCP/integrações? | **Sim** | N18 |

**Veredito:** arquitetura **saudável e limpa**; os achados são de **escala e dívida**, não bugs. Há **1 crítico** (roteamento) e um conjunto de **importantes** que vale resolver **antes** de multiplicar agentes/skills.

---

## 2. Findings detalhados

> Cada item: Problema · Impacto · Prioridade · Solução · Complexidade · Arquivos · Ordem.
> Prioridade: 🔴 Crítico · 🟠 Importante · 🟡 Futuro · ⚪ Não vale a pena.

### 🔴 N1 — Roteamento/seleção não escala (agents + skills)
- **Problema:** `IntentRouter._agent_tools()` manda **todos** os agentes como tools e `runtime._planner_prompt()` ([runtime.py:82](core/runtime.py#L82)) concatena **todas** as descrições no system prompt. Skills herdarão o mesmo quando o Orquestrador as acionar.
- **Impacto:** a ~30–50 unidades o roteamento degrada; a 100 agentes/300 skills **quebra** (prompt não cabe, modelo local não decide). Bloqueia o objetivo central.
- **Prioridade:** 🔴 Crítico.
- **Solução:** roteamento **híbrido em fases** (ver [C1_DESIGN.md](C1_DESIGN.md)): 1) hierarquia de **domínio** (adicionar `domain` ao manifest, indexar no registry, IntentRouter 2-etapas); 2) embeddings dentro do domínio quando crescer.
- **Complexidade:** Média (fase 1) → Alta (fase 2).
- **Arquivos:** `core/application/intent_router.py`, `core/runtime.py`, `agents/*/manifest.json`, `core/registry.py`, (fase 2) `memory/`, novo `Embedder`.
- **Ordem:** Onda 1 (fase 1) e Onda 3 (fase 2).

### 🟠 N2 — Três registries + duas descobertas duplicadas
- **Problema:** `AgentRegistry`/`ToolRegistry` ([core/registry.py](core/registry.py)) e `SkillRegistry` ([core/skills/registry.py](core/skills/registry.py)) repetem `register/get/all/names`; a varredura de `*/manifest.json` existe em [agents/loader.py](agents/loader.py) **e** no `SkillRegistry.discover`.
- **Impacto:** manutenção multiplicada quando tools/channels/mcp também forem descobertos; inconsistência (agentes não validam estrutura; skills sim).
- **Prioridade:** 🟠 Importante.
- **Solução:** `Registry[T]` genérico + um `ManifestLoader` único (descoberta/validação/parse) parametrizado por schema.
- **Complexidade:** Média.
- **Arquivos:** `core/registry.py`, `core/skills/registry.py`, `agents/loader.py`, `core/plugins/manager.py`.
- **Ordem:** Onda 1.

### 🟠 N3 — Boilerplate de SQLite duplicado
- **Problema:** `storage/sqlite_memory.py` e `storage/sqlite_ops.py` repetem `__init__`/lock/WAL/`close`/`__enter__`.
- **Impacto:** dívida; risco de divergência (ex.: PRAGMA aplicado num só).
- **Prioridade:** 🟠 Importante.
- **Solução:** base `SQLiteStore` (conexão/lock/WAL/close) herdada pelas duas.
- **Complexidade:** Baixa.
- **Arquivos:** `storage/sqlite_memory.py`, `storage/sqlite_ops.py`, novo `storage/_base.py`.
- **Ordem:** Onda 1.

### 🟠 N4 — Acoplamentos invertidos (Clean Architecture)
- **Problema:** `core/plugins/manager.py` (interno) importa `agents.loader` (externo) ([manager.py:15](core/plugins/manager.py#L15)); `agents/base.py` importa `memory.layers.render_itens` ([base.py:21](agents/base.py#L21)); skills acessam `context.memory.conversation/...` (internos do `MemoryFacade`) — acoplam-se à implementação.
- **Impacto:** mudanças na infra quebram o núcleo/skills; dificulta trocar memória/loader.
- **Prioridade:** 🟠 Importante.
- **Solução:** inverter via portas — o loader injeta agentes no manager (não o contrário); a renderização vira responsabilidade do chamador ou de um helper neutro; skills recebem uma **interface estreita de memória** (ver N8).
- **Complexidade:** Média.
- **Arquivos:** `core/plugins/manager.py`, `agents/base.py`, `core/skills/context.py`.
- **Ordem:** Onda 1.

### 🟠 N5 — Router de fallback hardcoded + agentes sem `domain` (OCP)
- **Problema:** `core/router.py` tem `MAPA_PALAVRAS` fixo (novo agente exige editar o router); agentes não têm `domain`/categoria (skills têm `category`).
- **Impacto:** viola OCP; insustentável a 100 agentes; sem `domain` não há como montar a hierarquia do N1.
- **Prioridade:** 🟠 Importante.
- **Solução:** derivar gatilhos/domínio dos **manifests** (cada agente declara `domain` e palavras-chave); aposentar o mapa fixo.
- **Complexidade:** Baixa–Média.
- **Arquivos:** `core/router.py`, `agents/*/manifest.json`, `agents/loader.py`.
- **Ordem:** Onda 1 (pré-requisito do N1).

### 🟠 N6 — Cognição inativa construída no runtime + import morto (código morto / abstração cedo)
- **Problema:** [runtime.py:138-144](core/runtime.py#L138-L144) constrói `StrategicPlanner/ExecutionManager/QualitySupervisor/CognitiveOrchestrator` a cada boot sem uso (`noqa F841`); [runtime.py:25](core/runtime.py#L25) tem import morto (`carregar_agentes`).
- **Impacto:** ruído no composition root; constrói objetos descartados; abstração antecipada parada há fases.
- **Prioridade:** 🟠 Importante.
- **Solução:** remover o import morto; **adiar** a construção da cognição para trás do flag `COGNITION_ENABLED` (lazy), só quando ativar.
- **Complexidade:** Baixa.
- **Arquivos:** `core/runtime.py`.
- **Ordem:** Onda 1.

### 🟠 N7 — `load_executor` sem cache, sem validação de contrato, sem sandbox
- **Problema:** `SkillRegistry.load_executor` ([core/skills/registry.py](core/skills/registry.py)) **re-importa** o módulo a cada chamada (importlib por caminho), **não valida** que a classe cumpre `SkillExecutor`, e **executa código arbitrário** da pasta da skill.
- **Impacto:** performance (re-import a cada uso) e re-execução de código de topo; risco de runtime quando o Orquestrador acionar skills com frequência; risco de segurança quando houver skills de terceiros (multiusuário/marketplace).
- **Prioridade:** 🟠 Importante.
- **Solução:** **cache** do executor por nome+versão; **validar** o contrato (checar `name`/`version`/`execute`); preparar ponto de **sandbox**/allowlist para skills não confiáveis (futuro).
- **Complexidade:** Baixa (cache+validação) / Alta (sandbox).
- **Arquivos:** `core/skills/registry.py`, `core/contracts/skill.py`.
- **Ordem:** Onda 2 (antes de ligar skills ao Orquestrador).

### 🟠 N8 — Skills acopladas ao `MemoryFacade`; falta interface estreita + resultado tipado
- **Problema:** `SkillContext.memory` é `object` ([core/skills/context.py](core/skills/context.py)) e o handler usa `context.memory.conversation/temporary/permanent` (internos do facade). Falta um `SkillResult` tipado e um padrão de **erro/evento `skill.failed`**.
- **Impacto:** mudanças no facade quebram todas as skills; resultados/erros inconsistentes dificultam o Orquestrador consumir skills uniformemente.
- **Prioridade:** 🟠 Importante.
- **Solução:** porta `SkillMemory` estreita (só o que skills precisam: ler conversa/dia, gravar/recuperar notas) injetada no contexto; `SkillResult` tipado + evento `skill.failed` padronizado.
- **Complexidade:** Média.
- **Arquivos:** `core/skills/context.py`, `core/contracts/skill.py`, `skills/*/handler.py`.
- **Ordem:** Onda 2.

### 🟠 N9 — Memória recupera tudo (sem relevância/limite)
- **Problema:** `MemoryFacade.build_context` ([memory/facade.py](memory/facade.py)) carrega **toda** a permanente + **todos** os itens de cada projeto do escopo + KB; `recall_permanent`/`recall_project` carregam tudo e filtram em Python.
- **Impacto:** com memória grande (e muitos handoffs em L3), o contexto do agente incha e o boot/consulta ficam lentos. Gargalo de escala e custo de tokens.
- **Prioridade:** 🟠 Importante.
- **Solução:** recuperação com **limite + relevância** (ranking/recência), paginação no store, e seleção por domínio (sinergia com N1).
- **Complexidade:** Média.
- **Arquivos:** `memory/facade.py`, `memory/layers.py`, `storage/sqlite_memory.py`.
- **Ordem:** Onda 2.

### 🟠 N10 — Event Log sem truncamento/snapshot
- **Problema:** a tabela `events` ([storage/sqlite_ops.py](storage/sqlite_ops.py)) cresce sem limite; sem snapshot/compactação.
- **Impacto:** `.db` cresce indefinidamente; replicação futura fica cara; consultas lentas com o tempo.
- **Prioridade:** 🟠 Importante.
- **Solução:** política de **snapshot periódico** + truncamento do log antigo (mantendo o necessário p/ auditoria/replicação).
- **Complexidade:** Média.
- **Arquivos:** `storage/sqlite_ops.py`, `replication/`.
- **Ordem:** Onda 3.

### 🟠 N11 — Multiusuário ausente (sem User/Tenant; memória global)
- **Problema:** não há conceito de `User`/`Tenant` no domínio; `session = "channel:sender_id"` é implícito; memória L2/L3/L4 é **global** (não escopada por usuário); `Gateway` autoriza **um** `allowed_sender` ([core/gateway.py](core/gateway.py)).
- **Impacto:** sem isolamento, abrir para mais usuários **vazaria** memória/projetos entre eles. Bloqueia o objetivo "múltiplos usuários".
- **Prioridade:** 🟠 Importante (vira 🔴 quando multiusuário entrar na pauta).
- **Solução:** entidade `Tenant/User` no domínio; **dimensão de tenant** na memória e nas sessões; o corte de domínio do N1 já carrega o tenant; autorização multi-usuário no Gateway.
- **Complexidade:** Alta.
- **Arquivos:** `core/domain/`, `core/gateway.py`, `memory/*`, `storage/sqlite_memory.py`, `core/models.py`.
- **Ordem:** Onda 4.

### 🟠 N12 — Conhecimento duplicado em 3 lugares (drift)
- **Problema:** a mesma ficha/projetos vive em `brain.md`, `substrate/compendium.md` e `memory/seed.py`, sincronizados à mão.
- **Impacto:** divergência silenciosa; a IA pode "saber" coisas diferentes do que está documentado.
- **Prioridade:** 🟠 Importante.
- **Solução:** uma fonte canônica (`compendium.md`) **ingerida** no seed/L4; os demais viram ponteiros.
- **Complexidade:** Baixa–Média.
- **Arquivos:** `memory/seed.py`, `substrate/compendium.md`, `brain.md`, (futuro) ingestão L4.
- **Ordem:** Onda 2.

### 🟠 N13 — Cobertura de testes ainda fina
- **Problema:** smoke (v3) + 1 teste de skill; faltam **unitários por componente** (registry, facade, ops, router, intent).
- **Impacto:** as refatorações de escala (N2/N3/N1) ficam arriscadas sem rede.
- **Prioridade:** 🟠 Importante.
- **Solução:** suíte unitária mínima por módulo + CI local (`pytest`).
- **Complexidade:** Média.
- **Arquivos:** `tests/`.
- **Ordem:** Onda 1 (habilita as demais).

### 🟡 N14 — Implementações "gordas" de port (SRP)
- **Problema:** `SQLiteMemory` cumpre **5** ports; `SQLiteOpsStore` cumpre **3** (EventLog/TaskStore/LeaseStore) + outbox.
- **Impacto:** classes multi-responsabilidade; dificultam trocar parte do backend (ex.: só o EventLog para Postgres).
- **Prioridade:** 🟡 Futuro.
- **Solução:** separar por responsabilidade quando trocar de backend/escala; manter coesão por ora.
- **Complexidade:** Média.
- **Arquivos:** `storage/*`.
- **Ordem:** Onda 4+.

### 🟡 N15 — Event Bus síncrono in-process
- **Problema:** `InProcessEventBus` ([core/events/bus.py](core/events/bus.py)) entrega síncrono; handlers bloqueiam; sem retry/dead-letter; eventos são publicados mas quase ninguém **reage** (subutilizado).
- **Impacto:** tarefas longas (Browser, mkVideos) e paralelismo precisarão de assíncrono; hoje o bus é mais "log" que "reativo".
- **Prioridade:** 🟡 Futuro.
- **Solução:** entrega assíncrona opcional (fila in-process → broker depois), com retry/dead-letter; mover lógica reativa para handlers.
- **Complexidade:** Alta.
- **Arquivos:** `core/events/bus.py`, `core/contracts/events.py`.
- **Ordem:** Onda 3.

### 🟡 N16 — `CognitiveOrchestrator` duplica a forma do `Orchestrator`
- **Problema:** [core/cognition/cognitive_orchestrator.py](core/cognition/cognitive_orchestrator.py) replica o fluxo do `Orchestrator` v3; ao ativar, haverá **dois caminhos** que podem divergir.
- **Impacto:** risco de manutenção dupla quando a cognição for ligada.
- **Prioridade:** 🟡 Futuro.
- **Solução:** ao ativar, o Orquestrador v3 deve **compor** os estágios de cognição (não duplicar) — um único caminho com etapas plugáveis.
- **Complexidade:** Média.
- **Arquivos:** `core/application/orchestrator.py`, `core/cognition/*`.
- **Ordem:** Onda 3.

### 🟡 N17 — 2ª máquina: só fundação (Replicator Noop)
- **Problema:** outbox + lease prontos, mas `Replicator` é `Noop` ([replication/noop.py](replication/noop.py)); falta transporte real, snapshots, **política de conflito** e fencing token robusto (lease usa hostname).
- **Impacto:** failover real ainda não existe; sem política, 2 máquinas poderiam divergir.
- **Prioridade:** 🟡 Futuro.
- **Solução:** transporte (HTTP/arquivo) + loop de replicação + promoção do standby; regra de escrita única (single-writer) ou LWW; fencing token.
- **Complexidade:** Alta.
- **Arquivos:** `replication/`, `storage/sqlite_ops.py`, `core/runtime.py`.
- **Ordem:** Onda 4.

### 🟡 N18 — Tools/Browser/MCP: portas sem adaptador + lacunas de integração
- **Problema:** `Tool`/`MCPClient` definidos sem adapter; `ToolRegistry` instanciado mas **nunca populado** ([manager.py:24](core/plugins/manager.py#L24)); agentes não têm **laço de tools**; falta **gate de confirmação** humana, **ingestão p/ L4** e **canal de saída proativa** (canais só respondem).
- **Impacto:** Browser/MCP/Calendar/WhatsApp não têm como ser ligados de forma uniforme; sem gate, ações externas seriam inseguras.
- **Prioridade:** 🟡 Futuro (🟠 quando a Fase Browser começar).
- **Solução:** laço de tools no `BaseAgent` (tool-calling) + `ToolRegistry` populável por manifest; gate de confirmação; porta `send()` no `Channel`; adapter MCP que expõe tools MCP como `Tool`.
- **Complexidade:** Alta.
- **Arquivos:** `agents/base.py`, `core/registry.py`, `tools/`, `mcp/`, `core/contracts/channel.py`, `channels/*`.
- **Ordem:** Onda 2 (gate + 1ª tool) e Onda 4 (MCP/canais).

### 🟡 N19 — L4 só FTS5 (sem vetorial)
- **Problema:** a Base de Conhecimento usa FTS5/LIKE ([storage/sqlite_memory.py](storage/sqlite_memory.py)); sem embeddings.
- **Impacto:** recuperação semântica fraca; limita o roteamento por embeddings (N1 fase 2) e a qualidade do RAG.
- **Prioridade:** 🟡 Futuro.
- **Solução:** índice vetorial (sqlite-vss/local) + `Embedder`, reaproveitado pelo roteamento e pelo KB.
- **Complexidade:** Alta.
- **Arquivos:** `storage/sqlite_memory.py`, `memory/knowledge_base*`, novo `Embedder`.
- **Ordem:** Onda 3 (junto do N1 fase 2).

### 🟡 N20 — Estado transitório na memória permanente (handoff em L3)
- **Problema:** Session Handoff grava em **L3 permanente** com `type="handoff"` ([skills/session-handoff/handler.py](skills/session-handoff/handler.py)); sem TTL/limpeza; `recall` carrega todos.
- **Impacto:** L3 vira depósito de estado de sessão; cresce; `resume` fica O(n) ao filtrar em Python.
- **Prioridade:** 🟡 Futuro.
- **Solução:** "casa" de memória de **sessão/handoff** (entre L1 e L3) com consulta por sessão + retenção configurável; ou índice por sessão no store.
- **Complexidade:** Média.
- **Arquivos:** `memory/`, `storage/sqlite_memory.py`, `skills/session-handoff/handler.py`.
- **Ordem:** Onda 2–3.

### 🟡 N21 — Reorganização: domínio dividido + abstrações antecipadas
- **Problema:** entidades de domínio divididas entre `core/domain/` e `core/models.py`; `replication`/`mcp` (portas) e `ToolRegistry`/cognição criadas antes do uso.
- **Impacto:** "casa" do domínio ambígua; peças paradas no caminho quente.
- **Prioridade:** 🟡 Futuro / ⚪ em parte.
- **Solução:** mover `core/models.py` → `core/domain/`; manter as portas antecipadas, mas fora do caminho quente até o uso.
- **Complexidade:** Baixa.
- **Arquivos:** `core/models.py`, `core/domain/`.
- **Ordem:** Onda 3.

### ⚪ N22 — Cosméticos / baixo ROI
- **Problema:** `_agora`/`_now`/`_novo_id` duplicados em 4 arquivos; `Settings` plana; PT-BR misturado em logs; `ToolRegistry` ocioso; skills têm `_template`, agentes não.
- **Impacto:** baixo.
- **Prioridade:** ⚪ Não vale a pena (agora).
- **Solução:** `util/time.py` único; deixar o resto como está.
- **Complexidade:** Baixa.
- **Arquivos:** vários (trivial).
- **Ordem:** oportunístico.

---

## 3. Resumo de prioridade e ordem global

| Onda | Tema | Findings |
|---|---|---|
| **1** | Higiene + fundação de escala | N13, N2, N3, N4, N5, N6, **N1 (fase 1)** |
| **2** | Execução de Skills + Tools + memória relevante | N7, N8, N12, N9, N18 (gate + 1ª tool), N20 (parcial) |
| **3** | Escala semântica + Event Bus + snapshots | **N1 (fase 2)**, N19, N10, N15, N16, N21 |
| **4** | Multiusuário + 2ª máquina + integrações | N11, N17, N18 (MCP/canais), N14 |
| **∞** | Cosméticos | N22 |

> Regra: **Onda 1 antes de multiplicar agentes/skills.** É o que protege o objetivo de 100/300.

---

## 4. Roadmap técnico — próximos 12 meses

> Hoje é jun/2026. Cada trimestre fecha com um marco verificável.

### 🗓️ T3 2026 (Jul–Set) — "Fundação de escala e higiene"
- **N13** suíte unitária mínima (rede de segurança).
- **N2/N3** unificar registries + descoberta + base SQLite.
- **N4/N6** corrigir acoplamentos invertidos, remover import morto e cognição inativa do caminho quente.
- **N5** `domain` nos manifests + router derivado do manifest.
- **N1 fase 1** roteamento hierárquico por domínio (IntentRouter 2-etapas).
- **Marco:** adicionar agentes/skills em massa **sem** inchar o prompt; roteamento por domínio funcionando.

### 🗓️ T4 2026 (Out–Dez) — "Skills executáveis de verdade + 1ª Tool"
- **N7/N8** cache + validação de contrato no `load_executor`; `SkillMemory` estreita; `SkillResult` + `skill.failed`.
- Ligar **Skills ao Orquestrador** (usar o seam) — selecionar/rodar skill por domínio.
- **N18 (parcial)** laço de tools no `BaseAgent` + **gate de confirmação** + 1ª Tool real (Browser **leitura/extração**).
- **N9/N12** memória com relevância/limite; conhecimento canônico (compendium → seed/L4).
- **Marco:** um agente aciona uma Skill que usa uma Tool, com aprovação humana e tudo no Event Log.

### 🗓️ T1 2027 (Jan–Mar) — "Escala semântica e robustez"
- **N1 fase 2 + N19** embeddings dentro do domínio + L4 vetorial.
- **N10** snapshots/truncamento do Event Log.
- **N15** Event Bus assíncrono opcional (retry/dead-letter).
- **N16/N21** unificar caminho de cognição; mover `models` → `domain`.
- **Marco:** seleção semântica entre centenas de skills/agentes; log sob controle.

### 🗓️ T2 2027 (Abr–Jun) — "Multiusuário, 2ª máquina e integrações"
- **N11** `Tenant/User` no domínio + memória escopada por tenant + Gateway multi-usuário.
- **N17** replicação real + snapshots + política de conflito + promoção do standby.
- **N18 (resto)** adapter MCP + novos canais (WhatsApp) + **canal de saída proativa** (`send()`).
- **N14** separar ports "gordos" se a escala pedir.
- **Marco:** CRIS OS multiusuário, com 2ª máquina assumindo no failover e integrações externas plugáveis.

---

> **Conclusão:** a base está limpa o suficiente para crescer. O **único bloqueador estrutural** do objetivo 100/300 é o **N1 (roteamento)**; o resto da **Onda 1** é higiene barata que evita que a dívida se multiplique. Recomenda-se **não adicionar mais agentes/skills em massa antes da Onda 1**.
