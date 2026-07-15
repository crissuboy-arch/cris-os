# 🏛️ CRIS OS — Architecture Review

**Data:** 2026-06-30 · **Tipo:** revisão técnica (somente análise; nenhuma alteração de código).

**Escopo analisado:** `core/` (domain, contracts, application, cognition, events, plugins, skills, runtime), `agents/`, `memory/`, `storage/`, `llm/`, `channels/`, `skills/`.
**Estado:** 11 agentes, 5 skills, 4 camadas de memória, event-driven, single-user.
**Saúde geral:** **boa.** A base hexagonal é sólida; os achados são sobre **escala e dívida**, não bugs.

## Legenda de classificação
- 🔴 **Crítico** — resolver **antes** de escalar agentes/skills; bloqueia o objetivo declarado.
- 🟠 **Importante** — dívida real que vai doer ao crescer; planejar em breve.
- 🟡 **Futuro** — só relevante em escala maior; revisitar depois.
- ⚪ **Não vale a pena** — cosmético / baixo ROI.

---

## 🔴 Crítico

### C1 — Seleção/roteamento não escala para 100 agentes / 300 Skills
`IntentRouter._agent_tools()` envia **todos** os agentes como *tools* ao LLM, e
`runtime._planner_prompt()` ([runtime.py:82](core/runtime.py#L82)) concatena **todas**
as descrições de agentes no system prompt. Com 11 funciona; a ~30–50 a qualidade do
roteamento cai e o contexto incha; a **100 quebra** (e a mesma lógica valerá para skills).
**Não está quebrado hoje**, mas é a decisão de design que precisa existir **antes** de
adicionar agentes/skills em massa. → ver **[C1_DESIGN.md](C1_DESIGN.md)**.

---

## 🟠 Importante

- **I1 — Três registries quase idênticos + duas descobertas por manifesto.**
  `AgentRegistry`/`ToolRegistry` ([core/registry.py](core/registry.py)) e `SkillRegistry`
  ([core/skills/registry.py](core/skills/registry.py)) repetem o padrão dict→register/get/all/names;
  a varredura de `*/manifest.json` existe em [agents/loader.py](agents/loader.py) **e** no
  `SkillRegistry.discover`. Vai se multiplicar com tools/channels/mcp.
- **I2 — Violações de direção de dependência (Clean Architecture).**
  `core/plugins/manager.py` (interno) importa `agents.loader` (externo); `agents/base.py`
  importa `memory.layers.render_itens` (agente conhece a apresentação da memória).
- **I3 — Router de fallback hardcoded (viola OCP).** `core/router.py` tem `MAPA_PALAVRAS`
  fixo: adicionar agente exige editar o router. A 100 agentes é insustentável.
- **I4 — Dívida no composition root.** [runtime.py:138-144](core/runtime.py#L138-L144)
  constrói a cognição inativa a cada boot (`noqa F841`); [runtime.py:25](core/runtime.py#L25)
  tem import morto (`carregar_agentes`).
- **I5 — Conhecimento duplicado em 3 lugares (drift):** `brain.md`, `substrate/compendium.md`,
  `memory/seed.py` sincronizados à mão.
- **I6 — Boilerplate de SQLite duplicado** em `storage/sqlite_memory.py` e `storage/sqlite_ops.py`
  (init/lock/WAL/close/__enter__).
- **I7 — Cobertura só de smoke tests** — sem testes unitários por componente; refatorações
  de escala ficam arriscadas.
- **I8 — Event Log sem truncamento/snapshot** — tabela `events` cresce sem limite.

---

## 🟡 Futuro

- **F1 — Implementações "gordas" de port.** `SQLiteMemory` cumpre 5 ports; `SQLiteOpsStore`
  cumpre 3 (EventLog/TaskStore/LeaseStore).
- **F2 — `MemoryFacade.build_context` recupera tudo** (permanente + todos os itens de cada
  projeto + KB) → infla o contexto.
- **F3 — Event Bus síncrono in-process** — tarefas longas/paralelas pedirão assíncrono.
- **F4 — `enable/disable` de skills só em memória** (não persiste).
- **F5 — Domínio dividido** entre `core/domain/` e `core/models.py`.
- **F6 — `_agora`/`_novo_id`/`_now` duplicados em 4 arquivos.**

---

## ⚪ Não vale a pena (agora)

- **N1 — `Settings` é uma classe plana** com muitos campos.
- **N2 — `contracts/__init__` importa todos os contratos.**
- **N3 — PT-BR misturado com nomes técnicos em logs.**
- **N4 — Skills têm `_template`, agentes não.**

---

## ✅ O que está genuinamente bom
- Ports & adapters reais — trocar LLM/canal/banco é plugar adaptador.
- Direção de dependência majoritariamente correta (só os 2 desvios de I2).
- Event Log como espinha dorsal (auditoria + replicação + failover).
- Descoberta plugin-style (agentes e skills por pasta) — OCP de verdade.
- Orquestrador decomposto (IntentRouter/Workflow/Composer) — SRP.
- Memória escopada por agente — "nenhum agente conhece tudo" é estrutural.

---

## 🗺️ Mapa de prioridade

| ID | Achado | Classe |
|---|---|---|
| C1 | Roteamento "tudo como tool" + prompt com todos os agentes | 🔴 Crítico |
| I1 | 3 registries + 2 descobertas duplicadas | 🟠 Importante |
| I2 | plugins→agents e agent→memory (Clean Arch) | 🟠 Importante |
| I3 | Router de palavra-chave hardcoded | 🟠 Importante |
| I4 | Cognição inativa + import morto no runtime | 🟠 Importante |
| I5 | Conhecimento em 3 lugares (drift) | 🟠 Importante |
| I6 | Boilerplate SQLite duplicado | 🟠 Importante |
| I7 | Só smoke tests | 🟠 Importante |
| I8 | Event Log sem snapshot | 🟠 Importante |
| F1–F6 | ports gordos, facade, bus síncrono, etc. | 🟡 Futuro |
| N1–N4 | flat settings, imports, idioma, template | ⚪ Não vale |

---

## 🎯 Recomendação (sem implementar)
1. **C1** — desenhar o roteamento em escala (ver [C1_DESIGN.md](C1_DESIGN.md)).
2. **I1 + I6** — unificar registries + descoberta + base SQLite.
3. **I2 + I3 + I4** — limpar acoplamentos invertidos, router hardcoded e cognição morta.
4. **I7** — testes unitários mínimos para destravar as refatorações com segurança.

Itens **Futuro** esperam o uso real puxar a necessidade; **Não vale a pena** ficam como estão.
