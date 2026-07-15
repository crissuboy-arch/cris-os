# 🌊 ONDA1_PLAN — Plano de execução da Onda 1

**Data:** 2026-06-30 · **Tipo:** plano (nenhum código alterado ainda — **aguardando aprovação**).
**Objetivo:** preparar o CRIS OS para escalar a **100 agentes / 300 skills**, sem adicionar funcionalidades.
**Base:** findings da [ARCHITECTURE_NEXT.md](ARCHITECTURE_NEXT.md) (N13, N3, N2, N4, N6, N5, N1-fase1).

---

## 1. Princípios de execução (regras desta Onda)
- ❌ Não criar novas skills/agentes. ❌ Não implementar Browser/WhatsApp/Calendar/MCP.
- ❌ Não mexer em funcionalidades externas (Telegram/Ollama/Memory de runtime continuam iguais).
- ✅ **Refatoração comportamentalmente neutra** — exceto o roteamento (B7), que muda mas com **fallback para o comportamento atual**.
- ✅ **Testes primeiro** (caracterização), depois refatorar.
- ✅ **Passos pequenos**; após cada bloco: rodar `pytest`/smoke e **mostrar o resultado**.
- ✅ Todos os smoke tests **sempre verdes**.

> ⚠️ **Sem controle de versão:** o projeto não é um repositório git. Sugiro (opcional) um `git init` + commit por bloco como rede de segurança. Sem isso, a rede de segurança são os **testes de caracterização** do Bloco 0 (capturam o comportamento atual antes de mexer).

---

## 2. Estratégia de testes
**Caracterização antes de refatorar:** o Bloco 0 escreve testes que fixam o
comportamento **atual** dos componentes que serão tocados. Assim, cada refatoração
seguinte só é considerada pronta se esses testes continuarem verdes (= comportamento
preservado). Cada bloco também adiciona testes específicos da sua mudança.

**Como testar o runtime sem rede:** `build(check_llm=False)` + monkeypatch
(`OllamaProvider.is_alive` → True, `settings.DB_PATH` → tmp, token de teste). O
`TelegramChannel` só conecta no `.run()`, então `build()` roda offline.

---

## 3. Blocos (ordem exata de implementação)

### 🧱 Bloco 0 — Testes de caracterização (N13) — *pré-requisito*
- **O que:** fixar o comportamento atual antes de qualquer mudança.
- **Arquivos criados:** `tests/test_registries.py`, `tests/test_loader.py`,
  `tests/test_skill_registry.py`, `tests/test_router.py`, `tests/test_storage.py`,
  `tests/test_memory_facade.py`, `tests/test_intent_router.py`, `tests/test_runtime_build.py`.
- **Arquivos modificados:** nenhum (só testes).
- **Cobre:** AgentRegistry/ToolRegistry; `carregar_agentes` (11 agentes, pula orchestrator);
  SkillRegistry (descobre 5, valida, enable/disable, version, `load_executor`); Router
  (mapa atual + default); SQLiteMemory/Ops (CRUD básico); MemoryFacade.build_context
  (escopo); IntentRouter com FakeLLM; build() do runtime.
- **Riscos:** baixíssimo (não muda produção). Risco: testes frágeis demais → escrevê-los
  sobre **saídas estáveis** (contagens, nomes, tipos), não sobre detalhes internos.
- **Pronto quando:** todos passam + smoke verde.

### 🧱 Bloco 1 — Limpeza do runtime (N6)
- **O que:** remover o import morto e tirar a **cognição inativa** do caminho quente
  (construir só sob `COGNITION_ENABLED`).
- **Arquivos modificados:** `core/runtime.py`.
- **Mudança:** apagar `from agents.loader import carregar_agentes  # noqa` (vira uso real
  no Bloco 4); mover a construção de `StrategicPlanner/ExecutionManager/QualitySupervisor/
  CognitiveOrchestrator` para dentro de `if settings.COGNITION_ENABLED:`; manter o log/aviso.
- **Testes:** `tests/test_runtime_build.py` — build() retorna `CrisOS` com agentes+skills e
  **não** constrói cognição quando `COGNITION_ENABLED=false`.
- **Riscos:** runtime é I/O-pesado; mitigado pelo monkeypatch do Bloco 0. Risco: quebrar a
  ordem de montagem → manter a sequência idêntica, só condicionar a cognição.
- **Pronto quando:** build test + smoke verdes.

### 🧱 Bloco 2 — Base SQLite comum (N3)
- **O que:** extrair conexão/lock/WAL/close para uma base; `SQLiteMemory` e `SQLiteOpsStore`
  herdam. **Comportamento idêntico.**
- **Arquivos criados:** `storage/_base.py` (`class SQLiteStore`).
- **Arquivos modificados:** `storage/sqlite_memory.py`, `storage/sqlite_ops.py`.
- **Testes:** `tests/test_storage.py` (do Bloco 0) deve continuar verde + 1 teste do `_base`.
- **Riscos:** diferença sutil de PRAGMA/ordem de schema → o `_base` cuida da conexão; cada
  store mantém **seu** `executescript` de schema. Conexões separadas por store (mesmo `.db`)
  preservadas. Mitigação: testes de storage + smoke.
- **Pronto quando:** storage + smoke verdes.

### 🧱 Bloco 3 — Unificar registries + descoberta (N2)
- **O que:** um `Registry[T]` genérico (register/get/all/names) + um `discover_manifests(dir)`
  único, reusados por agentes e skills. **APIs públicas idênticas.**
- **Arquivos modificados:** `core/registry.py` (adiciona base genérica + `discover_manifests`),
  `core/skills/registry.py` (usa a base + o discover), `agents/loader.py` (usa o discover).
- **Testes:** `tests/test_registries.py`, `test_loader.py`, `test_skill_registry.py` (Bloco 0)
  inalterados e verdes (mesmas contagens/validações).
- **Riscos:** mudar sutilmente a descoberta/validação (ex.: ordem, skip de `_template`,
  mensagens de `issues`) → os testes de caracterização travam isso. Manter `REQUIRED_FILES`
  e o skip de `_`/`.` idênticos.
- **Pronto quando:** registries/loader/skill + smoke verdes.

### 🧱 Bloco 4 — Corrigir acoplamentos invertidos (N4)
- **O que:** (a) inverter `plugins → agents`: o **runtime** carrega os agentes e os injeta no
  `PluginManager` (que deixa de importar `agents.loader`); (b) tirar o import `agent → memory`:
  mover `render_itens` para perto de quem usa (camada de agentes), não em `memory`.
- **Arquivos modificados:** `core/plugins/manager.py` (recebe agentes prontos),
  `core/runtime.py` (carrega e injeta), `agents/base.py` (não importa de `memory`),
  `memory/layers.py` (remove `render_itens`); **criado:** `agents/_format.py` (render).
- **Pré-checagem:** `grep render_itens` para confirmar que **só** `base.py` usa (senão, ajustar).
- **Testes:** `test_runtime_build.py` (agentes injetados), `test_loader.py`, + teste de que
  `BaseAgent._montar_system` renderiza igual (caracterização).
- **Riscos:** mover `render_itens` quebrar algum import → grep antes; manter assinatura idêntica.
  Inverter o manager → garantir que `PluginManager.discover_agents` continue existindo (ou
  virar `register_agents(lista)`), atualizando o runtime junto.
- **Pronto quando:** build/loader/agent + smoke verdes.

### 🧱 Bloco 5 — `domain` nos manifests (N5a) — *dado, sem lógica*
- **O que:** adicionar `"domain": "..."` a cada manifest de agente (12) e skill (5); o
  loader/registry passam a **carregar** o campo (default seguro se ausente).
- **Arquivos modificados:** `agents/*/manifest.json` (12), `skills/*/manifest.json` (5),
  `agents/loader.py` + `agents/base.py` (BaseAgent guarda `domain`), `core/skills/skill.py`
  + `core/skills/registry.py` (Skill guarda `domain`).
- **Taxonomia proposta (aprovar na seção 5):** ver tabela abaixo.
- **Testes:** caracterização atualizada para assertar `domain` carregado; ausência → default.
- **Riscos:** taxonomia mal escolhida → **decisão sua** (seção 5); manter `domain` opcional
  (default `geral`) para não quebrar nada.
- **Pronto quando:** registries/loader + smoke verdes.

### 🧱 Bloco 6 — Fallback derivado dos manifests (N5b)
- **O que:** `core/router.py` deixa de ter `MAPA_PALAVRAS` fixo; o mapa de fallback é
  **derivado dos manifests** (cada agente declara `keywords` opcional + `domain`).
- **Arquivos modificados:** `core/router.py` (recebe os agentes/registry e monta o mapa),
  `core/runtime.py` (passa o registry ao Router), `agents/*/manifest.json` (campo `keywords`
  opcional — derivado do que hoje está hardcoded no router).
- **Testes:** `tests/test_router.py` — mesmas rotas que hoje (caracterização), agora vindas
  dos manifests; novo agente (em teste) roteável sem editar o router.
- **Riscos:** perder alguma rota existente → migrar o conteúdo atual de `MAPA_PALAVRAS` para
  os manifests **1:1** e travar com o teste de caracterização.
- **Pronto quando:** router + smoke verdes.

### 🧱 Bloco 7 — N1 fase 1: roteamento hierárquico por domínio (N1)
- **O que:** `IntentRouter` em **2 etapas**: (1) classifica o **domínio** (lista curta);
  (2) escolhe agente(s) **dentro** do domínio (lista curta como tools). **Com fallback** para
  o comportamento atual quando o domínio não resolver (degradação graciosa).
- **Arquivos modificados:** `core/application/intent_router.py` (2 etapas + fallback),
  `core/registry.py` (índice `by_domain`), `core/runtime.py` (catálogo de domínios + prompt),
  `agents/orchestrator/SYSTEM.md` (prompt do classificador de domínio — texto, não código).
- **Testes:** `tests/test_intent_router.py` com **FakeLLM ciente de domínio** (passo 1 devolve
  domínio, passo 2 devolve agente); casos: domínio certo → agente do domínio; classificador
  falha → fallback; mensagem cross-domínio → múltiplos.
- **Compatibilidade com smoke:** o smoke usa `FakeLLM(route_to="financeiro")`. O IntentRouter
  vai **degradar para 1-etapa** quando o nome devolvido já for um **agente** (não um domínio),
  preservando as asserções atuais. Se necessário, o `FakeLLM` do smoke ganha lógica de domínio
  **sem alterar as asserções** (continuam: delega a `financeiro`, etc.).
- **Riscos (o mais alto da Onda):**
  - quebrar smoke pela mudança de roteamento → **fallback** + FakeLLM compatível;
  - latência (2 chamadas) → aceitável; só ativa com domínios presentes;
  - classificação errada de domínio → fallback por keyword (Bloco 6) cobre.
- **Pronto quando:** intent_router + **todos** os smoke verdes.

---

## 4. Arquivos afetados (consolidado)

**Criados:** `storage/_base.py`, `agents/_format.py`, e os `tests/test_*.py` (8 arquivos).
**Modificados (produção):**
- `core/runtime.py` (B1, B4, B6, B7)
- `core/registry.py` (B3, B7)
- `core/skills/registry.py`, `core/skills/skill.py` (B3, B5)
- `agents/loader.py`, `agents/base.py` (B3, B4, B5)
- `core/plugins/manager.py` (B3, B4)
- `storage/sqlite_memory.py`, `storage/sqlite_ops.py` (B2)
- `memory/layers.py` (B4)
- `core/router.py` (B6)
- `core/application/intent_router.py` (B7)
- `agents/*/manifest.json` (12) e `skills/*/manifest.json` (5) (B5, B6) — **dados**
- `agents/orchestrator/SYSTEM.md` (B7) — **texto de prompt**

**Intocados (garantido):** Event Bus (`core/events/bus.py`), Orquestrador
(`core/application/orchestrator.py` — só recebe o IntentRouter já pronto), Memory de runtime
(comportamento), canais, `llm/`, skills existentes (lógica), cognição (só condicionada).

---

## 5. ⚠️ Decisão sua: taxonomia de domínios (aprovar/ajustar)
A hierarquia precisa de uma lista **curta e estável** de domínios. Proposta (1 por agente;
skills herdam o domínio da sua área):

| Domínio | Agentes | Skills |
|---|---|---|
| `pessoal` | secretary | — |
| `atendimento` | atendimento | — |
| `pesquisa` | pesquisador | browser-tool |
| `marketing` | social-media | — |
| `conteudo` | mkvideos | — |
| `financeiro` | financeiro | — |
| `zavix` | zavix | zavix-product |
| `vitrinepro` | vitrinepro | — |
| `scalaflow` | scalaflow | — |
| `pinklogic` | pinklogic | — |
| `curriculo` | curriculo | curriculum-builder |
| `sistema` | — | session-handoff, roast |

Reservados para o futuro (sem agente ainda): `produtos-3d`, `sites`.
> É só a partida — ajustável a qualquer momento (é só dado no manifest).

---

## 6. Riscos globais e mitigação
| Risco | Mitigação |
|---|---|
| Regressão de comportamento numa refatoração | **Bloco 0** (caracterização) trava o comportamento atual |
| Runtime difícil de testar | `build(check_llm=False)` + monkeypatch (offline) |
| Roteamento (B7) quebrar smoke | Fallback para 1-etapa + FakeLLM compatível |
| Sem git para reverter | Passos pequenos + testes; (opcional) `git init` + commit por bloco |
| Taxonomia de domínio inadequada | Aprovação sua (seção 5); `domain` é dado, troca fácil |
| Perder rota do fallback | Migração 1:1 do `MAPA_PALAVRAS` + teste de caracterização |

---

## 7. Ordem exata (resumo)
**B0** testes → **B1** limpeza runtime → **B2** base SQLite → **B3** unificar registries →
**B4** acoplamentos → **B5** `domain` nos manifests → **B6** fallback por manifest →
**B7** roteamento hierárquico.

Após **cada** bloco: rodar `python tests/test_smoke.py` + os unitários do bloco e **mostrar o resultado**. Só avanço ao próximo com tudo verde.

---

## 8. ✋ Aprovação
Antes de eu escrever qualquer linha de código, preciso do seu **OK** em:
1. **A ordem** dos blocos (B0→B7).
2. A **taxonomia de domínios** (seção 5) — ou seus ajustes.
3. (Opcional) Se quer que eu rode `git init` por segurança antes de começar.

Com o "pode começar", eu executo **bloco a bloco**, mostrando os testes verdes a cada passo.
