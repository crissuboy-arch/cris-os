# ARQUITETURA — CRIS OS (v1.0)

Sistema operacional pessoal de agentes: uma **equipe de funcionarios digitais**
coordenada por um **gerente** (Orquestrador). Desenhado com Clean Architecture,
SOLID, baixo acoplamento, alta coesão, **event-driven**, plugins, IA local/remota,
MCP e Tool Calling — para **durar anos**.

---

## 1. 🎯 Princípios

- **Clean Architecture**: domínio puro no centro; infraestrutura na borda.
- **SOLID** (com destaque): SRP (cada peça uma responsabilidade), ISP (portas
  pequenas), OCP (plugins entram sem mudar o núcleo), DIP (núcleo depende de
  portas, não de implementações).
- **Event-Driven**: tudo relevante vira evento no barramento + Event Log.
- **Estado externalizado**: pronto para 2ª máquina e failover.
- **Filosofia dos agentes**: um agente, um domínio. Nenhum agente conhece tudo.
  Toda comunicação passa pelo Orquestrador.

---

## 2. 🧱 Camadas (Clean Architecture)

```
INFRAESTRUTURA  Ollama · Telegram · SQLite · (Postgres/MCP/Google/n8n)   ← trocável
  ADAPTADORES   channels/ · tools/ · llm/ · storage/ · mcp/ · replication/
    APLICAÇÃO   Orchestrator · IntentRouter · WorkflowEngine · ResponseComposer
      DOMÍNIO   Event · entidades · regras (core/domain, core/models)     ← puro
        Regra de dependência: as setas SEMPRE apontam para dentro.
```

| Camada | Pasta | Conhece... |
|---|---|---|
| Domínio | `core/domain`, `core/models` | nada externo |
| Aplicação | `core/application` | só o domínio + portas |
| Portas | `core/contracts` | interfaces (a fronteira) |
| Adaptadores/Infra | `channels` `tools` `llm` `storage` `memory` `mcp` `replication` | o mundo real |

---

## 3. 🔌 Portas (contratos) — `core/contracts/`

| Porta | Implementação atual |
|---|---|
| `LLMProvider` | `llm/ollama.py` + `llm/router.py` (política local/remoto) |
| `Channel` | `channels/telegram/` |
| `Agent` | `agents/base.py` (BaseAgent) |
| `Tool` / `MCPClient` | — (design; `tools/`, `mcp/`) |
| `EventBus` / `EventLog` | `core/events/bus.py` (EM CONSTRUCAO — Modulo 2) + `storage/sqlite_ops.py` |
| `ConversationStore`,`TemporaryStore`,`ProjectMemoryStore`,`PermanentStore`,`KnowledgeBase` | `storage/sqlite_memory.py` |
| `TaskStore` | `storage/sqlite_ops.py` |
| `Replicator` / `LeaseStore` | `replication/noop.py` + `storage/sqlite_ops.py` |
| `Plugin` | descoberto por `core/plugins/manager.py` |

---

## 4. 🔄 Backbone Event-Driven (a espinha dorsal)

Todo acontecimento vira um `Event` publicado no `EventBus`, que (1) **grava no
Event Log** e (2) **notifica assinantes**. O mesmo log resolve **4 requisitos**:

| Uso | Como |
|---|---|
| Event-Driven | assinantes reagem a eventos (hoje síncrono, pronto p/ assíncrono) |
| Auditoria | todo evento gravado, amarrado por `correlation_id` |
| Replicação | `outbox` lista eventos novos para enviar à 2ª máquina |
| Failover | a réplica **reprocessa** eventos e reconstrói o estado |

Eventos: `message.received → intent.identified → task.created → task.assigned →
agent.completed → response.composed`.

---

## 4.1 🧠 Camada de Cognição (autonomia) — arquitetura pronta, inativa

Acima da execução existe um ciclo de raciocínio que transforma o CRIS OS em
**sistema operacional autônomo**. Três componentes (`core/cognition/`), uma
responsabilidade cada:

```
Objetivo da Cris
  → StrategicPlanner   pensa: contexto + memória (4 camadas) + estratégia → Plano
  → ExecutionManager   executa: distribui, monitora, reexecuta, controla timeout
  → QualitySupervisor  avalia: objetivo atingido? aprova OU pede refação
        ↑______________ loop de re-execução (até MAX_REVISIONS) ______________|
  → (aprovado) → ResponseComposer → Cris
```

| Componente | Porta | Reaproveita do v3 |
|---|---|---|
| StrategicPlanner | `contracts/cognition.py` | IntentRouter (escolha de agente por passo) |
| ExecutionManager | `contracts/cognition.py` | WorkflowEngine (despacho + Task) |
| QualitySupervisor | `contracts/cognition.py` | — (novo gate antes da resposta) |
| CognitiveOrchestrator | — | ResponseComposer (entrega) |

Domínio em `core/domain/planning.py` (Objective, Strategy, Plan, PlanStep,
ExecutionReport, StepResult, QualityVerdict). Usa o **Event Bus existente** com
eventos próprios (`objective.received` … `quality.approved`/`reexecution.requested`).

> **Status:** esqueletos. A camada é **construída** no runtime (faz parte da
> arquitetura principal e do Event Bus), mas está **INATIVA** — `plan/execute/
> review` levantam `NotImplementedError`. O atendimento à Cris segue pelo
> Orquestrador v3 até a próxima revisão de arquitetura. Ver
> [core/cognition/README.md](core/cognition/README.md).

---

## 5. 🧭 Orquestrador v3 (decomposto — SRP)

O gerente **nunca executa**. Foi quebrado em 3 responsabilidades únicas:

```
Orchestrator (core/application/orchestrator.py) — amarra e publica eventos
 ├─ IntentRouter ── identifica intenção → plano [(agente, instrução)]  (tool-calling)
 ├─ WorkflowEngine ─ cria/rastreia Tasks (persistidas) + memória escopada + executa
 └─ ResponseComposer ─ entrega UMA resposta (1 agente: repassa; vários: sintetiza)
```

Fallback: se o LLM não delegar (sem suporte a tools), o `Router` por palavra-chave
garante resposta.

---

## 6. 🧠 Memória em 4 camadas (com acesso escopado)

| Camada | Conteúdo | Backend | Quem acessa |
|---|---|---|---|
| **L1 Conversa** | histórico do diálogo | SQLite | a sessão |
| **L1 Temporária** | tarefas/itens do dia | SQLite (por dia) | a sessão |
| **L2 Projetos** | memória própria de cada projeto | SQLite (namespace) | **só o projeto do agente** |
| **L3 Permanente** | quem é a Cris, objetivos, preferências, estratégias | SQLite | todos (leitura) |
| **L4 Base de Conhecimento** | documentos, PDF, markdown, prompts, repos | SQLite **FTS5** (→ vetorial) | recuperação por relevância |

O **`MemoryFacade`** monta o contexto de cada agente respeitando o **escopo**
(`projects` no manifest): `[]` = sem projeto; `["Zavix.online"]` = só esse; `["*"]`
= todos (agentes transversais, ex.: Financeiro). É assim que "**nenhum agente
conhece tudo**" vira garantia de arquitetura.

---

## 7. 👥 Agentes como plugins

Cada agente é uma pasta `agents/<nome>/` com `manifest.json` (nome, descrição,
`projects`, `delegate`, `status`) + `SYSTEM.md` + `README.md`. O `PluginManager`
**descobre e registra** — adicionar agente = criar pasta, **núcleo intocado** (OCP).
Canais, ferramentas, provedores e MCP seguem a mesma mecânica nas próximas fases.

| Agente | Domínio | Escopo L2 | Status |
|---|---|---|---|
| secretary | agenda, rotina, prioridades, saúde, produtividade | — | ✅ produção |
| atendimento | clientes (todos os produtos) | `*` | rascunho |
| pesquisador | concorrentes, preços, fornecedores, tendências | `*` | rascunho |
| social-media | Instagram/TikTok/Facebook/YouTube/Threads/Pinterest | `*` | rascunho |
| mkvideos | roteiro, voz, thumbnail, vídeo, legenda | mkVideos | rascunho |
| scalaflow | mineração, anúncios, nichos, produtos vencedores | ScalaFlow | rascunho |
| pinklogic | SaaS, sistemas, automações, IA | PinkLogic | rascunho |
| zavix | produtos, estoque, links, categorias, pedidos | Zavix.online | rascunho |
| vitrinepro | negócios locais | VitrinePro | rascunho |
| curriculo | ferramenta de currículo | Currículo Gratuito | rascunho |
| financeiro | receitas, despesas, metas, lucro, investimentos | `*` | rascunho |

---

## 8. 💾 Segunda máquina, replicação e backup

- **Estado atrás de portas** (memória, event log, tasks, lease) → trocar o
  mecanismo de replicação não toca no núcleo.
- **Replicação** (aprovada): Event Log + **outbox** + `Replicator`. A réplica
  reprocessa os eventos. (Ver [replication/README.md](replication/README.md).)
- **Lease**: eleição de líder (`acquire/renew`) → só o líder age; standby assume
  no failover.
- **Backup**: Git (código/prompts/manifests) · SQLite/Postgres (estado) ·
  **snapshots** periódicos · job de backup automático.
- **Backends**: SQLite (hoje) → SQLite+Litestream → PostgreSQL (multi-nó).

---

## 9. 🤖 IA local/remota, MCP e Tool Calling

- **LLMRouter** escolhe o modelo por papel (roteamento barato local; síntese
  maior; tarefas específicas em remoto). Hoje: Ollama. Adicionar Claude/remoto =
  registrar outro provedor.
- **Tool Calling**: já usado pelo Orquestrador para delegar; estende-se aos
  agentes (`tools/`) para ações reais.
- **MCP**: porta pronta ([core/contracts/mcp.py](core/contracts/mcp.py)); um
  adaptador transformará ferramentas MCP em `Tool`. (Ver [mcp/README.md](mcp/README.md).)

---

## 10. 🗂️ Mapa de pastas
```
core/
  domain/        # Event + entidades (puro)
  models.py      # IncomingMessage, Task, AgentResult, KnowledgeItem, Passage
  contracts/     # PORTAS (agent, channel, llm, memory, events, task_store, tool, mcp, replication, plugin)
  application/   # Orchestrator, IntentRouter, WorkflowEngine, ResponseComposer
  events/        # InProcessEventBus
  plugins/       # PluginManager
  gateway.py · registry.py · router.py · runtime.py
agents/          # base.py · loader.py · <agente>/(manifest+SYSTEM+README)
memory/          # layers (L1–L4) · facade (escopo) · seed
storage/         # sqlite_memory (4 camadas) · sqlite_ops (event log/outbox/tasks/lease)
llm/             # ollama · router         channels/  tools/  mcp/  replication/
config/  data/(cris_os.db)  logs/  backups/  automations/  docs/  tests/
```

---

## 11. 🛣️ Roadmap (Fase 100)

- **Feito:** Clean Architecture + event-driven (bus + log), memória 4 camadas
  (escopada, FTS5), workflow com tarefas rastreadas, plugins de agentes, LLM
  router, portas de MCP e replicação (outbox + lease), Secretária funcional.
- **Próximo:** ferramentas reais (`tools/`) + Tool Calling nos agentes; ingestão
  de documentos na L4; promover especialistas a produção.
- **Depois:** adaptador MCP; novos canais (WhatsApp/Discord/Instagram/Email);
  replicação real entre máquinas + promoção automática; memória vetorial; n8n e
  automações agendadas; backup automático + snapshots.
