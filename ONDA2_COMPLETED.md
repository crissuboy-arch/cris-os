# ONDA 2 — CONCLUÍDA ✅ (execução real de Skills + kernel de execução)

> **Status:** CONCLUÍDA e **validada em produção no Telegram real**.
> **Data:** 2026-07-01 · **Owner:** Cris · Plano: [ONDA2_PLAN.md](ONDA2_PLAN.md) · Congelamento: [ARCHITECTURE_FREEZE.md](ARCHITECTURE_FREEZE.md)

A Onda 2 transformou a camada de Skills de *fundação inerte* em **execução real**, ligada
ao Orquestrador por um **kernel de execução genérico** (ExecutionType/Step/Result/Target),
com **gate de confirmação humana** e uma **Browser Tool somente-leitura**. Tudo aditivo,
com testes, zero regressão — e agora **comprovado ponta a ponta em ambiente real**.

## Blocos entregues (protocolo bloco-a-bloco, aprovação a cada bloco)
| Bloco | Entrega | Status |
|---|---|---|
| B0 | Freeze + plano | ✅ |
| B1 | `SkillResult` (DTO tolerante a `dict`) + eventos `skill.started/completed/failed` | ✅ |
| B2 | `load_executor` com **cache** (nome@versão) + validação de contrato (`SkillLoadError`) | ✅ |
| B3 | Porta estreita `SkillMemory` + adapter `FacadeSkillMemory` (skill não conhece SQLite/Facade) | ✅ |
| B4 | `SkillRunner` (executa skill, rastreia `Task`, emite `skill.*`) | ✅ |
| B5 | **Kernel de execução** (`ExecutionType`/`ExecutionStep`/`ExecutionResult`/`ExecutionTarget`/`ExecutionDispatcher`/`TargetRegistry` + `AgentTarget`/`SkillTarget`) + roteamento de skills no `IntentRouter` (tools do `input_schema` + **fallback por keyword de skill** do manifest) | ✅ |
| B6 | **ConfirmationGate** — read-only passa; `SENSITIVE` (write/delete/publish/buy/send) exige confirmação | ✅ |
| B7 | **Browser Tool SOMENTE LEITURA** (Playwright, import lazy) + `BrowserTarget` (`type=TOOL`) | ✅ |

## Arquitetura final do fluxo
```
Telegram → Gateway → Orchestrator
  → IntentRouter  (tool-calling; se falhar: keyword de SKILL → keyword de AGENTE → default)
  → [ExecutionStep(type, effect)]
  → ExecutionDispatcher  → ConfirmationGate (bloqueia SENSITIVE não confirmado)
  → TargetRegistry.get(type).run(step, ctx)   { agent.workflow | skill.runner | tool.browser }
  → ExecutionResult (DTO universal)
  → ResponseComposer → Cris
```

---

## 🧪 VALIDAÇÃO EM PRODUÇÃO (Telegram real) — 2026-07-01

O bot rodou com `qwen2.5-coder:1.5b` e a Cris (`telegram:6460872429`) enviou
**"faça o handoff desta sessão"**. Como o modelo pequeno não faz tool-calling de skills,
o roteamento caiu no **fallback determinístico por keyword de skill** (entregue no B5) —
que acionou a `session-handoff` corretamente. Executado **com sucesso 2×**.

### Evidência — cadeia ponta a ponta (correlation_id `046ba49b`)
Fonte: `logs/cris_os.log` (hora local) + Event Log `data/cris_os.db` (UTC).

| Etapa | Evidência | Fonte |
|---|---|---|
| **Telegram → Gateway** | `[telegram:6460872429] faça o handoff desta sessão` | log `18:07:38` |
| **IntentRouter → session-handoff** | `Fallback por keyword de SKILL -> 'session-handoff'` · `intent.identified {"target":"session-handoff","type":"skill"}` | log `18:08:49` · evt seq 51 |
| **Dispatcher → SkillTarget → SkillRunner** | `skill.started` `src=skill_runner` | evt seq 52 |
| **session-handoff executou** | `skill.session_handoff.created` `src=skill:session-handoff` | evt seq 53 |
| **skill concluída** | `skill.completed` `src=skill_runner` | evt seq 54 |
| **ExecutionResult → Composer → resposta** | `response.composed` `src=orchestrator` | evt seq 55 |
| **L3 recebeu o handoff** | `permanent_memory` `type=handoff` tags `["handoff","telegram:6460872429"]` @ `2026-07-01T17:08:49Z` | tabela `permanent_memory` |

### Os 7 pontos — confirmados em produção
1. ✅ IntentRouter escolheu `session-handoff` (`type=skill`) — via fallback por keyword.
2. ✅ ExecutionDispatcher executou o `SkillTarget` (`skill.*` com `src=skill_runner`).
3. ✅ `skill.started` emitido.
4. ✅ `skill.completed` emitido.
5. ✅ `ExecutionResult` chegou ao `ResponseComposer` (`response.composed`).
6. ✅ Resposta composta e enviada ao Telegram.
7. ✅ L3 recebeu `type=handoff` (2 itens: `17:08:49Z` corr `046ba49b` e `17:09:56Z` corr `61c62b2d`).

> **Nota (por que via fallback, não LLM):** o `qwen2.5-coder:1.5b` não emite `tool_call`
> confiável no roteamento em 2 etapas; por isso a skill é alcançada pelo **fallback por
> keyword do manifest** (`keywords: ["handoff", ...]`). Com um modelo capaz de tool-calling,
> o mesmo caminho é alcançado pela etapa 2 do `IntentRouter` — sem mudar arquitetura.

---

## Testes (todos verdes) — `python tests/<arquivo>.py`
`registries · skill_registry · loader · router · storage · memory_facade · skill_memory ·`
`intent_router · runtime_build · skill_execution · skill_result · skill_runner ·`
`execution_types · execution_result · dispatcher · confirmation_gate · browser_tool ·`
**smoke** · **session_handoff** — 17 unitários + 2 de integração.

## Arquivos criados/alterados na Onda 2 (visão geral)
- **Domínio:** `core/domain/execution.py` (`ExecutionType`, `Effect`).
- **DTOs:** `core/models.py` (`SkillResult`, `ExecutionStep`, `ExecutionResult`).
- **Portas:** `core/contracts/skill.py` (`SkillExecutor`, `SkillMemory`), `core/contracts/execution.py` (`ExecutionTarget`, `DispatchContext`).
- **Skills:** `core/skills/registry.py` (cache/validação, `input_schema`, `keywords`), `core/skills/skill.py`, `skills/session-handoff/*`.
- **Aplicação:** `intent_router.py` (skills + fallback por keyword), `dispatcher.py`, `targets.py`, `skill_runner.py`, `confirmation.py`, `composer.py` (universal), `orchestrator.py`.
- **Memória:** `memory/skill_memory.py` (`FacadeSkillMemory`).
- **Ferramentas:** `tools/browser/*` (`BrowserTool`, `BrowserTarget`).
- **Runtime:** `core/runtime.py` (monta targets `agent.workflow` + `skill.runner` + `tool.browser`).
- **Deps:** `requirements.txt` (+`playwright`, lazy).

## Compatibilidade com o FREEZE
100% aditivo: DTOs/portas novos com defaults seguros; motores (`WorkflowEngine`,
`SkillRunner`) intocados; `ResponseComposer` universalizado sem quebrar contratos;
`ExecutionDispatcher` ganhou `gate` opcional. Nenhuma porta/DTO congelado removido ou renomeado.

## Limitações conhecidas / dívidas (para a Onda 3)
- **Roteamento de skill por LLM** depende de modelo com tool-calling; hoje via **fallback por keyword**.
- **ConfirmationGate**: bloqueia + pede confirmação; o **pause/resume completo** (executar após "confirmar") ainda não está fiado.
- **Browser Tool**: só leitura; requer `python -m playwright install chromium` para uso real; ainda **não roteável** por linguagem natural.
- **Operacional do bot**: manter `python main.py` vivo exige rodar no terminal da Cris (processos em background do agente não persistem).

---

## ✅ ONDA 2 OFICIALMENTE CONCLUÍDA
Validada em código (testes + smoke) **e em produção no Telegram real** (evidências acima).
Próximo: planejar a **Onda 3** (ver [memory.md](memory.md)).
