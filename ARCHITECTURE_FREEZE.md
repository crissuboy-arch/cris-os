# 🧊 ARCHITECTURE_FREEZE — Constituição do CRIS OS

**Data:** 2026-06-30 · **Status:** decisões arquitetônicas **permanentes** (documento; nenhum código alterado).
**Autoridade:** este documento prevalece sobre decisões pontuais de implementação.

---

## 0. Preâmbulo — o que este freeze congela (e o que não congela)

Congelamos **3 coisas, para sempre**:
1. **Os contratos (ports) e os modelos que cruzam fronteiras** — a *forma* como as peças se falam.
2. **As fronteiras entre as camadas** — quem conhece quem.
3. **Os princípios arquitetônicos** — as leis do sistema.

**NÃO congelamos as implementações.** O *como* cada peça faz seu trabalho pode (e deve)
evoluir. Exemplos do que segue evolutivo: backends de storage, provedores de LLM, internos
dos registries/router/intent_router, agentes, skills, tools e canais concretos.

> ✅ **Compatível com a Onda 1.** A Onda 1 muda **implementações** atrás de contratos
> estáveis e estende manifests de forma **aditiva** (`domain`). Isso é explicitamente
> permitido por este freeze.
>
> ✅ **Compatível com as Ondas 2 e 3.** A Onda 2 adicionou contratos/DTOs **aditivos**
> (`SkillMemory`, `ExecutionType`/`Effect`, `ExecutionStep`/`ExecutionResult`,
> `ExecutionTarget`/`DispatchContext`). A Onda 3 adiciona os contratos de **roteamento**
> (`RouteScorer`/`RouteCandidate`/`ScoredRoute`) e mantém o **papel público** do
> `IntentRouter` — muda só o *como* ele escolhe (internos evolutivos, §2/§3).

**Política de evolução (a única forma de mexer no que é congelado):** **aditiva, nunca
quebradora.** Um contrato/modelo pode ganhar campos/métodos opcionais; **nunca** pode
remover, renomear ou repropor o significado de algo existente. Quebra de contrato exige
uma nova versão do contrato convivendo com a antiga (depreciação, nunca remoção abrupta).

---

## 1. Invariantes — partes que **nunca mais** deverão mudar

> 🧊 = congelado para sempre.

- 🧊 **A regra de dependência:** as dependências apontam **para dentro**. O domínio não
  depende de nada externo.
- 🧊 **Só o Orquestrador fala com a Cris.** Agentes, Skills e Tools **nunca** falam direto com a Cris.
- 🧊 **Agentes/Skills/Tools não falam entre si.** Toda coordenação passa pelo **Orquestrador**
  e/ou pelo **Event Bus**.
- 🧊 **O Event Log é a fonte da verdade** (auditoria + replicação + failover). Tudo relevante vira Evento.
- 🧊 **Ports & Adapters:** o núcleo depende de **contratos**, jamais de implementações concretas.
- 🧊 **Nenhum agente conhece tudo:** memória **escopada** por domínio/projeto.
- 🧊 **Local-first** e **sem segredos no repositório**.
- 🧊 **Tools read-only por padrão;** ação que sai para fora exige **confirmação da Cris**.
- 🧊 **Plugin por descoberta (OCP):** nova unidade = nova pasta + manifesto, **sem mudar o Core**.
- 🧊 **Composition root único:** só o `runtime` conhece implementações concretas.
- 🧊 **Evolução de contrato é aditiva** (cláusula do §0).

---

## 2. Core definitivo (módulos que são o coração)

Estes módulos formam o **Core**. Seus **contratos e papéis** são congelados; os **internos**
podem evoluir conforme a política aditiva.

| Módulo | Papel (congelado) | Internos (evolutivos?) |
|---|---|---|
| `core/domain/` | Entidades e Eventos de domínio (`Event`, `EventType`, planning) | Aditivo |
| `core/models.py` | DTOs que cruzam fronteiras (`IncomingMessage`, `OutgoingMessage`, `Task`, `AgentResult`, `KnowledgeItem`, `Passage`) | Aditivo |
| `core/contracts/` | **Todas as portas** (Agent, Channel, LLMProvider, Tool, EventBus/EventLog, Memory*, TaskStore, SkillExecutor, Replicator/Lease, MCPClient, Plugin) | Aditivo |
| `core/application/` | **Forma** do pipeline de orquestração (Orchestrator → IntentRouter → WorkflowEngine → ResponseComposer) | Internos evoluem |
| `core/events/` | Mecanismo do Event Bus | Internos evoluem (ex.: async) |
| `core/gateway.py` | Fronteira canais↔núcleo + autorização | Internos evoluem |
| `core/skills/` | **SDK de Skills** (contrato do Registry + `SkillContext`) | Internos evoluem |
| `core/registry.py` | Contrato dos catálogos (Agent/Tool/Skill) | Internos evoluem |
| `core/runtime.py` | **Composition root** (papel congelado; conteúdo muda sempre) | Conteúdo evolui |

---

## 3. Módulos que podem evoluir sem quebrar o Core (Adapters / Plugins)

Trocar/adicionar qualquer um destes **não pode** exigir mudança no Core.

- `agents/` — agentes concretos (plugins por manifesto).
- `skills/` — skills concretas (plugins por manifesto).
- `tools/` — ferramentas concretas (futuro).
- `channels/` — Telegram e futuros (WhatsApp, Discord, Web, API).
- `llm/` — provedores (Ollama hoje; remotos depois) + LLMRouter.
- `storage/` — backends (SQLite hoje; Postgres depois).
- `memory/` — wrappers + facade (implementam os ports de memória).
- `mcp/`, `replication/` — adaptadores (MCP, 2ª máquina).
- `core/cognition/` — camada de cognição (esqueleto; evolui/ativa atrás de flag).

> Os **internos** de `core/registry.py`, `core/router.py`, `core/application/intent_router.py`
> e `storage/*` também são evolutivos (é o que a Onda 1 refatora) — desde que o **contrato público** se mantenha.

---

## 4. Fronteiras entre as camadas (responsabilidade · conhece · NÃO conhece)

| Camada | Responsabilidade | Conhece | **NUNCA** conhece |
|---|---|---|---|
| **Runtime** | Montar o sistema (composition root) | Tudo (concretos) | — (ninguém depende dele) |
| **Channels** | I/O com a Cris; traduzir plataforma ↔ `IncomingMessage` | Gateway (via `Handler`) | Agentes, Skills, LLM, Memory, Tools |
| **Gateway** | Fronteira canais↔núcleo; autorização | Orquestrador | Implementações de canal |
| **Orquestrador** | Decidir e delegar; entregar **uma** resposta | Agentes, Skills (via registries), Memory, Event Bus | Canais concretos; lógica de domínio |
| **Event Bus / Log** | Publicar/persistir eventos | Event Log | Quem produz/consome (desacoplado) |
| **Memory** | Estado (conversa/conhecimento) atrás de ports | Storage (via ports) | Agentes/Skills/Canais |
| **Skills** | Jobs empacotados, versionados | `SkillContext` (Memory/Event/Tools injetados) | Canais, Cris, outros agentes/skills |
| **Agents** | Papéis com julgamento; orquestram skills/tools | `AgentContext` (escopado), Tools/Skills via registry | Canais, Cris, outros agentes |
| **Tools** | Ações atômicas no mundo | Recursos externos (via port) | Cris, canais, memória direta |

---

## 5. Core vs Plugins (a regra)

- **Core** = `core/domain` + `core/models` + `core/contracts` + a **forma** de
  `core/application` + `core/events` + `core/gateway` + `core/skills` (SDK) +
  `core/registry` (contrato) + o **papel** do `core/runtime` + os princípios do §8.
- **Plugins/Adapters** = `agents/`, `skills/`, `tools/`, `channels/`, `llm/`, `storage/`,
  `memory/` (impl), `mcp/`, `replication/`, `core/cognition/` (impl).

> 🧊 **Lei do OCP:** adicionar um plugin **nunca** altera o Core. O Core só muda por
> **evolução aditiva de contrato** (§0).

---

## 6. API pública interna do sistema (superfície estável)

É **somente** isto que plugins/adapters podem importar e depender. Tudo fora desta lista é
**implementação interna** e pode mudar sem aviso.

1. **Portas** — `core/contracts/*`: `Agent`/`AgentContext`, `Channel`/`Handler`,
   `LLMProvider`/`LLMResponse`/`ToolCall`, `Tool`, `EventBus`/`EventLog`/`Subscriber`,
   `ConversationStore`/`TemporaryStore`/`ProjectMemoryStore`/`PermanentStore`/`KnowledgeBase`,
   `TaskStore`, `SkillExecutor`/`SkillMemory`, `ExecutionTarget`/`DispatchContext`,
   `RouteScorer`/`RouteCandidate`/`ScoredRoute`, `Replicator`/`LeaseStore`/`Lease`,
   `MCPClient`, `Plugin`.
2. **DTOs** — `core/models.py`: `IncomingMessage`, `OutgoingMessage`, `Task`, `AgentResult`,
   `KnowledgeItem`, `Passage`.
3. **Domínio** — `core/domain/events.py`: `Event`, `EventType`; `core/domain/planning.py`.
4. **Contextos** — `AgentContext`, `SkillContext`.
5. **Catálogos** — métodos públicos de `AgentRegistry`, `SkillRegistry`, `ToolRegistry`.

**Versionamento:** aditivo (§0). Campos novos têm default; nada é removido/renomeado sem
um contrato novo coexistindo com o antigo.

---

## 7. O que **nunca** poderá ser acessado diretamente por agentes ou skills

> 🚫 = proibição permanente. Acesso só pelo caminho indicado.

- 🚫 **Storage** (`storage/SQLiteMemory`, `SQLiteOpsStore`) → só via **ports de Memory** /
  `AgentContext` / `SkillContext`.
- 🚫 **Event Bus** direto → skills/agents **só publicam** via `context.publish`; nunca importam o bus.
- 🚫 **Canais / Gateway / a Cris** → nenhuma saída direta ao usuário (a resposta sobe pelo Orquestrador).
- 🚫 **Outros agentes/skills** → sem chamada direta (sem agent↔agent, sem skill↔skill); só via Orquestrador/Event Bus.
- 🚫 **Runtime / composition root**.
- 🚫 **`.env` / segredos**.
- 🚫 **Memória de outro projeto/tenant** fora do escopo concedido.
- 🚫 **Internos do Orquestrador** (são orquestrados, não orquestram).

---

## 8. Princípios arquitetônicos congelados para sempre

1. 🧊 **Clean Architecture** + regra de dependência (para dentro).
2. 🧊 **Ports & Adapters** (hexagonal).
3. 🧊 **SOLID** — com ênfase em SRP, OCP, DIP, ISP.
4. 🧊 **Event-Driven** — Event Log como fonte da verdade.
5. 🧊 **Só o Orquestrador fala com a Cris.**
6. 🧊 **Agentes/Skills só se coordenam via Orquestrador/Event Bus.**
7. 🧊 **Memória escopada** ("nenhum agente conhece tudo").
8. 🧊 **Local-first; segredos fora do repo; tools read-only por padrão; confirmação humana para ações externas.**
9. 🧊 **Plugin por descoberta (OCP).**
10. 🧊 **Composition root único.**
11. 🧊 **Evolução de contrato aditiva (nunca quebradora).**

---

## 9. Contratos definitivos (Agente · Skill · Ferramenta · Orquestrador)

> 🧊 Assinaturas e **direção** congeladas (extensão só aditiva).

| De → Para | Contrato (congelado) | Regra de direção |
|---|---|---|
| **Cris → Orquestrador** | via Gateway: `Orchestrator.handle(incoming: IncomingMessage) -> str` | Único ponto de fala com a Cris |
| **Orquestrador → Agente** | `Agent.handle(task: Task, context: AgentContext) -> AgentResult` | O Orquestrador monta o contexto **escopado** |
| **Orquestrador/Agente → Skill** | `SkillExecutor.execute(payload: dict, context: SkillContext) -> dict`; obtida via `SkillRegistry.load_executor` | Skill usa Memory/Event/Tools **só** pelo contexto |
| **Agente/Skill → Ferramenta** | `Tool.run(**kwargs) -> str` (+ `Tool.schema() -> dict`), via `ToolRegistry` | Read-only por padrão; externa/destrutiva exige confirmação |
| **Qualquer → Event Bus** | `EventBus.publish(Event)` | Nunca burlar; tudo relevante vira evento |
| **Núcleo → Memory** | ports de `core/contracts/memory.py` | Agentes/Skills só via contexto escopado |

**A Lei da Comunicação (congelada):**
> A Cris fala **apenas** com o Orquestrador. O Orquestrador delega a Agentes e Skills.
> Agentes e Skills usam Tools e Memory **através do contexto recebido** e registram tudo no
> Event Log. **Nada** sobe de volta para a Cris a não ser pelo Orquestrador. Agentes, Skills
> e Tools **não se conhecem nem se chamam** diretamente.

---

## 10. Diagrama textual da arquitetura completa

```
                                     A CRIS
                                       │  (fala SÓ com o Orquestrador)
                                       ▼
        ┌───────────────────────── CHANNELS (adapters de entrada/saída) ───────────────────────┐
        │  Telegram · (futuro) WhatsApp · Discord · Web · API                                   │
        │      └── traduz plataforma ⇄ IncomingMessage ── chama ──► Handler                     │
        └───────────────────────────────────────────────┬──────────────────────────────────────┘
                                                         ▼
                                                 ┌──────────────┐
                                                 │   GATEWAY    │  autorização (fronteira)
                                                 └──────┬───────┘
                                                        ▼  Orchestrator.handle(IncomingMessage)->str
        ┌──────────────────────────── APPLICATION (Core) ──────────────────────────────────────┐
        │                            ORQUESTRADOR  (único que fala com a Cris)                  │
        │     IntentRouter ──► WorkflowEngine ──► ResponseComposer                              │
        │           │ delega                          ▲ compõe UMA resposta                     │
        │           ▼                                 │                                          │
        │     ┌──────────────┐  Agent.handle(Task,AgentContext)->AgentResult                    │
        │     │   AGENTS     │ ◄── papéis com julgamento (plugins por manifesto)                │
        │     └──────┬───────┘                                                                  │
        │            │ orquestram                                                               │
        │            ▼  SkillExecutor.execute(payload, SkillContext)->dict                      │
        │     ┌──────────────┐   (resolvidas por SkillRegistry.load_executor)                   │
        │     │    SKILLS    │ ── jobs empacotados (plugins por manifesto)                       │
        │     └──────┬───────┘                                                                  │
        │            │ usam   Tool.run(**kwargs)->str   (read-only default; confirmação p/ externo)
        │            ▼                                                                           │
        │     ┌──────────────┐                                                                   │
        │     │    TOOLS     │ ── ações no mundo (futuro: Browser, Calendar, GitHub, n8n, MCP)   │
        │     └──────────────┘                                                                   │
        └───────┬───────────────────────────────────────────────────────────┬──────────────────┘
                │ usa (ports)                                                │ publica (sempre)
                ▼                                                            ▼
        ┌──────────────┐                                          ┌────────────────────┐
        │   MEMORY     │  ports: Conversation/Temporary/          │   EVENT BUS / LOG   │ ← fonte da verdade
        │  (4 camadas) │  Project/Permanent/KnowledgeBase         │  publish(Event)     │   (auditoria/replicação/failover)
        └──────┬───────┘                                          └─────────┬──────────┘
               ▼ (ports)                                                    ▼ (ports)
        ┌─────────────────────────────── STORAGE / INFRA (adapters) ───────────────────────────┐
        │  SQLiteMemory · SQLiteOpsStore (EventLog/Tasks/Lease/Outbox) · (futuro) Postgres      │
        │  llm/ (Ollama, remoto) · replication/ (2ª máquina) · mcp/                              │
        └───────────────────────────────────────────────────────────────────────────────────────┘

        RUNTIME (composition root): monta TUDO acima; único que conhece os concretos.
        COGNIÇÃO (Planner→Executor→Supervisor): camada plugável, inativa, atrás de flag.

        DIREÇÃO DAS DEPENDÊNCIAS: sempre para DENTRO (Channels/Storage → Application → Domain).
        PROIBIDO: Agent↔Agent, Skill↔Skill, Agent/Skill→Channel, Agent/Skill→Cris, →Storage direto.
```

---

## Apêndice — Como mudar algo "congelado" (processo)
1. Mudança em **contrato/modelo/ports** → **somente aditiva** (campo/método opcional com default).
2. Quebra inevitável → criar contrato **vN+1** convivendo com **vN** (depreciação documentada).
3. **Princípios (§8) e a Lei da Comunicação (§9)** → **imutáveis**; não há processo de exceção.
4. **Implementações** (storage/llm/registries/router/agents/skills/channels/...) → livres para
   evoluir, desde que respeitem os contratos e as fronteiras.

> Este freeze é a régua. Antes de qualquer refatoração futura (incl. Onda 1), confira: *muda
> implementação (ok) ou contrato/fronteira/princípio (exige o processo acima)?*
