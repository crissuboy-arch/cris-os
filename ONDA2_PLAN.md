# 🌊 ONDA2_PLAN — Execução real de Skills + primeira Tool útil

**Data:** 2026-07-01 · **Tipo:** plano (nenhum código — **aguardando aprovação**).
**Objetivo:** fazer as Skills **executarem de verdade** pelo Orquestrador e entregar a **primeira Tool útil** (Browser em modo leitura), com **gate de confirmação** para qualquer ação externa.
**Base:** findings N7, N8, N18 de [ARCHITECTURE_NEXT.md](ARCHITECTURE_NEXT.md); constituição em [ARCHITECTURE_FREEZE.md](ARCHITECTURE_FREEZE.md) + [GOVERNANCE.md](GOVERNANCE.md).

---

## 1. Princípios (regras desta Onda)
- ✅ **Aditivo, nunca quebrador** (FREEZE §0). `Orchestrator.handle()`, portas e DTOs existentes mantêm assinatura.
- ✅ **Nada externo sem confirmação** (FREEZE §9 / GOVERNANCE §15). Tools read-only por padrão.
- ✅ **Teste de caracterização antes de mexer**; blocos pequenos; testes verdes a cada passo; smoke sempre verde.
- ❌ Não criar novos agentes. ❌ Não criar skills além das existentes (a Browser é **Tool**, não skill nova).
- ❌ Sem embeddings (C1 fase 2 fica para a Onda 3).

---

## 2. Estratégia de testes
Mesmo padrão da Onda 1: **caracterizar** o comportamento atual (session-handoff via `load_executor`, roteamento) antes de estender. Cada bloco adiciona testes próprios. O smoke e o `test_session_handoff` devem permanecer verdes.

---

## 3. Decisões que preciso da sua aprovação (antes de começar)

| # | Decisão | Recomendação |
|---|---|---|
| D1 | **Como a Skill é acionada?** (a) o Orquestrador roteia para skills como unidades (reuso da hierarquia de domínio da Onda 1); (b) o Agente invoca a skill; (c) gatilho explícito | **(a)** — na etapa 2 do IntentRouter, incluir as **skills habilitadas do domínio** como opções; o Orquestrador despacha agente→Workflow, skill→SkillRunner. Reusa o que a Onda 1 construiu. |
| D2 | **Retorno da Skill** | `SkillExecutor.execute -> SkillResult` **tolerando `dict`** (o SkillRunner normaliza; migra a session-handoff). Aditivo. |
| D3 | **Escopo da Browser Tool** | Playwright **read-only** (abrir, ler, extrair links, screenshot). Confirmar a **dependência `playwright`** (+ `playwright install`). Alternativa mais leve: um `fetch/scrape` sem browser primeiro. |
| D4 | **Profundidade do gate de confirmação** | **Design + implementação mínima** agora (a Browser é read-only, então o gate é definido mas não disparado); pause/resume completo quando surgir a 1ª ação de escrita. |

---

## 4. Blocos (ordem de execução)

### 🧱 Bloco 0 — Caracterização da execução atual
- **O que:** fixar o comportamento atual antes de estender.
- **Arquivos criados:** `tests/test_skill_execution.py` (session-handoff via `SkillRegistry.load_executor`, save/resume, eventos atuais).
- **Riscos:** baixíssimo. **Pronto:** testes + smoke verdes.

### 🧱 Bloco 1 — `SkillResult` + eventos `skill.*` (item 2 e 3)
- **O que:** DTO `SkillResult` padronizado + eventos `SKILL_STARTED/COMPLETED/FAILED`.
- **Arquivos:** `core/models.py` (➕ `SkillResult`), `core/domain/events.py` (➕ 3 constantes), `core/contracts/skill.py` (doc: `execute -> SkillResult | dict`, tolerante).
- **Testes:** `tests/test_skill_result.py` (constrói/serializa; compat com dict).
- **Riscos:** mudar o retorno da porta → **tolerância a dict** no runner (D2); nada quebra. **Pronto:** testes + smoke verdes.

### 🧱 Bloco 2 — `load_executor`: cache + validação (item 4 / N7)
- **O que:** cache do executor por `nome@versão`; validar que a classe cumpre `SkillExecutor` (`name`, `version`, `execute` chamável); None se inválido.
- **Arquivos:** `core/skills/registry.py`.
- **Testes:** `tests/test_skill_registry.py` (➕ cache devolve mesma instância; classe inválida → None).
- **Riscos:** cache assume **executor stateless** → documentar na GOVERNANCE/SDK; sandbox fica para Onda futura (N7 completo). **Pronto:** testes verdes.

### 🧱 Bloco 3 — `SkillMemory` (interface estreita) (item 5 / N8)
- **O que:** porta estreita `SkillMemory` (só o que skills precisam: ler conversa/dia, gravar/recuperar nota, buscar KB) + adapter sobre o `MemoryFacade`; `SkillContext.memory` passa a ser `SkillMemory`; migrar a session-handoff para usá-la.
- **Arquivos:** `core/contracts/skill.py` (➕ `SkillMemory`), `core/skills/context.py` (tipa `memory`), `memory/skill_memory.py` (novo adapter `FacadeSkillMemory`), `skills/session-handoff/handler.py` (usa a interface estreita).
- **Testes:** `tests/test_skill_memory.py` + `test_session_handoff.py` continua verde (mesmo comportamento).
- **Riscos:** desacoplar a skill do facade sem mudar comportamento → caracterização da session-handoff trava. **Pronto:** testes verdes.

### 🧱 Bloco 4 — `SkillRunner` (execução no fluxo) (item 1, parte A)
- **O que:** componente de aplicação que executa uma skill por nome: monta `SkillContext` (SkillMemory + publish + session + caller), `load_executor`, roda, **normaliza** para `SkillResult`, emite `skill.started/completed/failed`, persiste a Task (rastreio).
- **Arquivos:** `core/application/skill_runner.py` (novo), `core/runtime.py` (constrói o SkillRunner com registry + facade + event_bus + task_store).
- **Testes:** `tests/test_skill_runner.py` (roda session-handoff via runner; sucesso emite `skill.completed`; erro emite `skill.failed`).
- **Riscos:** duplicar lógica do WorkflowEngine → manter o runner focado só em skills. **Pronto:** testes + smoke verdes.

### 🧱 Bloco 5 — Ligar ao Orquestrador (item 1, parte B)
- **O que:** o `IntentRouter` (etapa 2) passa a incluir as **skills habilitadas do domínio** como opções; o Orquestrador/Workflow **despacha** por nome: skill (no registry, habilitada) → `SkillRunner`; senão → agente (Workflow atual). `Orchestrator.handle()` **sem mudança de assinatura**.
- **Arquivos:** `core/application/intent_router.py` (etapa 2 inclui skills do domínio), `core/application/workflow.py` **ou** `orchestrator.py` (dispatcher agente vs skill), `core/runtime.py` (injeta skill registry + runner).
- **Testes:** `tests/test_intent_router.py` (skill do domínio roteável) + `test_smoke.py` (agentes continuam roteando igual — **fallback/degradação preservados**).
- **Riscos (o mais alto da Onda):** regressão no roteamento de agentes → caracterização + degradação (a etapa 2 só adiciona skills **habilitadas**; hoje só a session-handoff). **Pronto:** **todos** os smoke verdes.

### 🧱 Bloco 6 — Gate de confirmação humana (item 7)
- **O que:** contrato `ConfirmationGate` + resultado `ConfirmationRequired`; política: **read-only passa; ação externa/destrutiva exige aprovação**. Implementação **mínima** (a Browser é read-only → gate definido, não disparado); desenho do fluxo pause/resume (estado de ação pendente + resposta "confirmar/cancelar") documentado para a 1ª ação de escrita.
- **Arquivos:** `core/contracts/tool.py` (➕ `requires_confirmation`/metadados) ou novo `core/contracts/confirmation.py`; `core/application/` (checagem antes de ação externa); (design) `channels/` para surfar a confirmação.
- **Testes:** `tests/test_confirmation_gate.py` (ação read-only passa; ação de escrita → `ConfirmationRequired`).
- **Riscos:** pause/resume é complexo (round-trip com o canal) → **manter mínimo** nesta Onda; só definir e cobrir read-only. **Pronto:** testes verdes.

### 🧱 Bloco 7 — Browser Tool (somente leitura) (item 6 / N18)
- **O que:** primeira Tool concreta cumprindo a porta `Tool`: `open`, ler texto, extrair links, screenshot em `logs/screenshots/`. **Read-only** (sem clicar/enviar/comprar); qualquer ação não-leitura passaria pelo gate (Bloco 6). Registrada no `ToolRegistry`; declarada no manifesto de quem a usa (`browser-tool` skill / `pesquisador`).
- **Arquivos:** `tools/browser/` (novo, impl Playwright), `requirements.txt` (➕ `playwright`), `core/runtime.py` (popular `ToolRegistry`), `logs/screenshots/` (gerado).
- **Testes:** `tests/test_browser_tool.py` (com mock do Playwright — sem rede/instalação no CI local).
- **Riscos:** **dependência pesada** (Playwright + `playwright install`); disco (screenshots); segurança (não logar dados sensíveis) → read-only + gate. **Pronto:** testes (mockados) verdes; leitura funciona.

---

## 5. Arquivos afetados (consolidado)
**Criados:** `core/application/skill_runner.py`, `memory/skill_memory.py`, `tools/browser/*`,
`core/contracts/confirmation.py` (ou extensão de `tool.py`), e `tests/test_*` (skill_execution, skill_result, skill_memory, skill_runner, confirmation_gate, browser_tool).
**Modificados (produção):** `core/models.py`, `core/domain/events.py`, `core/contracts/skill.py`,
`core/skills/registry.py`, `core/skills/context.py`, `core/application/intent_router.py`,
`core/application/workflow.py` (ou `orchestrator.py`), `core/runtime.py`, `skills/session-handoff/handler.py`, `requirements.txt`.
**Intocados (garantido):** `core/events/bus.py` (mecanismo), assinatura de `Orchestrator.handle()`, portas/DTOs existentes (só adição), skills scaffold (roast/curriculum/zavix-product/browser-tool ficam como estão).

---

## 6. Riscos globais e mitigação
| Risco | Mitigação |
|---|---|
| Regressão no roteamento de agentes (B5) | Caracterização + só skills **habilitadas** entram; degradação/fallback da Onda 1 |
| Quebrar a session-handoff (B3) | `test_session_handoff` como caracterização; interface estreita mapeia 1:1 |
| Retorno dict vs SkillResult (B1/B4) | SkillRunner **normaliza**; porta tolerante |
| Cache de executor com estado (B2) | Exigir executor **stateless** (doc na GOVERNANCE/SDK) |
| Gate pause/resume complexo (B6) | Escopo **mínimo** (read-only não dispara); design documentado |
| Playwright (B7) | Testes **mockados**; dependência isolada; read-only; `playwright install` como passo à parte |
| Tudo Core é sensível | Mudanças **aditivas** (FREEZE §0); assinaturas públicas preservadas |

---

## 7. Ordem exata
**B0** caracterização → **B1** SkillResult+eventos → **B2** load_executor(cache/validação) →
**B3** SkillMemory → **B4** SkillRunner → **B5** ligar ao Orquestrador → **B6** gate de confirmação →
**B7** Browser Tool (read-only).

Após **cada** bloco: rodar todos os unitários + smoke e **mostrar o resultado**; só avanço com tudo verde; **paro e aguardo aprovação** entre blocos.

---

## 8. ✋ Aprovação
Antes de escrever qualquer código, preciso do seu **OK** em:
1. A **ordem** dos blocos (B0→B7).
2. As **4 decisões** da seção 3 (D1 acionamento de skill, D2 SkillResult, D3 escopo/dep da Browser, D4 profundidade do gate).

Com o "pode começar", executo **bloco a bloco**, no mesmo protocolo da Onda 1.
