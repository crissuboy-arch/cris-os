# ✅ ONDA1_COMPLETED — Estabilização do CRIS OS

**Data:** 2026-07-01 · **Status:** **Onda 1 concluída** (8 blocos B0→B7, todos com testes verdes e sem regressão).
**Objetivo da Onda:** preparar a arquitetura para escalar a **100 agentes / 300 skills**, sem novas funcionalidades.
**Governança:** [ARCHITECTURE_FREEZE.md](ARCHITECTURE_FREEZE.md) · [GOVERNANCE.md](GOVERNANCE.md) · plano em [ONDA1_PLAN.md](ONDA1_PLAN.md).

---

## 1. Objetivos alcançados (por bloco)
| Bloco | Objetivo | Status |
|---|---|---|
| B0 | Testes de caracterização antes de refatorar | ✅ |
| B1 | Remover código morto / cognição inativa do caminho quente | ✅ |
| B2 | Base SQLite comum | ✅ |
| B3 | Unificar registries + descoberta de manifests | ✅ |
| B4 | Corrigir acoplamentos invertidos | ✅ |
| B5 | `domain` nos manifests (agentes + skills) | ✅ |
| B6 | Fallback derivado dos manifests (fim do hardcode) | ✅ |
| B7 | N1 fase 1 — roteamento hierárquico por domínio | ✅ |

---

## 2. Arquivos alterados

**Novos (10):**
- `storage/_base.py` (base SQLite comum)
- `agents/_format.py` (render de memória na camada de agentes)
- `tests/`: `test_registries.py`, `test_skill_registry.py`, `test_loader.py`, `test_router.py`,
  `test_storage.py`, `test_memory_facade.py`, `test_intent_router.py`, `test_runtime_build.py`

**Produção modificada (12):**
- `core/runtime.py` (B1, B4, B6)
- `core/registry.py` (B3 — `Registry` base + `discover_manifests`)
- `core/skills/registry.py` (B3, B5), `core/skills/skill.py` (B5)
- `agents/loader.py` (B3, B4, B5, B6), `agents/base.py` (B4, B5, B6)
- `core/plugins/manager.py` (B3, B4)
- `storage/sqlite_memory.py`, `storage/sqlite_ops.py` (B2)
- `memory/layers.py` (B4)
- `core/router.py` (B6 — fim do `MAPA_PALAVRAS`)
- `core/application/intent_router.py` (B7 — 2 etapas)

**Dados (17 manifests):** `domain` em 12 agentes + 5 skills; `keywords` em 10 agentes (1:1 do `MAPA_PALAVRAS`).

**Intocados (garantido):** Event Bus (`core/events/bus.py`), Orquestrador (`core/application/orchestrator.py`),
Memory de runtime (comportamento), canais, skills existentes (lógica), contratos/portas.

---

## 3. Melhorias obtidas
- **Escala de roteamento (C1 fase 1):** seleção **domínio → agente** no lugar de "todos como tools"; fan-out limitado por domínio.
- **OCP restaurado:** adicionar/etiquetar um agente é **só dado** (manifest) — nada de editar o Router (fim do `MAPA_PALAVRAS`).
- **Menos duplicação:** 1 base de registry, 1 descoberta de manifests, 1 base SQLite.
- **Clean Architecture:** removidos os 2 acoplamentos invertidos (plugins→agents, agent→memory).
- **Composition root limpo:** import morto removido; cognição inativa fora do caminho quente.
- **Rede de segurança:** 8 arquivos de teste unitário (caracterização) + smoke + skill — todos verdes.

---

## 4. Métricas

**Duplicação removida:**
- 3 registries (`AgentRegistry`/`ToolRegistry`/`SkillRegistry`) → **1 base** `Registry`.
- 2 varreduras de `manifest.json` (loader + skill registry) → **1** `discover_manifests`.
- 2 boilerplates de conexão SQLite → **1 base** `SQLiteStore`.
- Mapa de roteamento hardcoded (`MAPA_PALAVRAS`) → **dado** nos manifests.

**Acoplamentos corrigidos:** 2/2
- `core/plugins/manager.py` → `agents.loader` (removido; runtime injeta).
- `agents/base.py` → `memory.layers` (removido; render foi p/ `agents/_format.py`).

**Código morto removido:** import morto no runtime + construção da cognição fora do caminho quente.

**Contratos preservados (0 quebras):**
- `AgentRegistry`/`ToolRegistry`/`SkillRegistry` — métodos públicos mantidos (só adição aditiva de `names()` ao ToolRegistry por herança).
- `Router.route()`, `IntentRouter.__init__`/`plan()`, `Orchestrator.handle()` — assinaturas idênticas.
- Todas as portas/DTOs de `core/contracts` e `core/models` — **inalteradas**.
- Evolução **100% aditiva** (novos campos com default: `domain`, `keywords`, `executor`).

**Testes:** 8 suites unitárias novas + smoke (v3+cognição) + session_handoff → **100% verdes**, sem regressão, ao fim de cada bloco.

---

## 5. Itens adiados (para Ondas seguintes — ver [ARCHITECTURE_NEXT.md](ARCHITECTURE_NEXT.md))
- **C1 fase 2 (N1):** embeddings **dentro** do domínio + índice vetorial (Onda 3).
- **Ligar Skills ao Orquestrador** (execução de skills no fluxo) — Onda 2.
- **N7/N8:** cache + validação + sandbox no `load_executor`; `SkillMemory` estreita + `SkillResult`/`skill.failed`.
- **N9:** recuperação de memória com relevância/limite (`build_context`).
- **N10:** snapshot/truncamento do Event Log. **N15:** Event Bus assíncrono.
- **N11:** multiusuário (User/Tenant + memória escopada). **N17:** 2ª máquina real.
- **N18:** tools/Browser/MCP + gate de confirmação + canal de saída proativa. **N19:** L4 vetorial.
- **N12:** unificar conhecimento (brain.md/compendium/seed). **Precedência exata do fallback** (não adicionada, por decisão).

---

## 6. Próximos passos recomendados
1. **Revisar** este fechamento e aprovar a Onda 1.
2. **Antes de escalar agentes/skills em massa**, a Onda 1 já protege — mas para qualidade real do roteamento em 2 etapas, considerar um modelo com **tool-calling** que caiba na máquina (ver [MODELOS.md](MODELOS.md): `llama3.1` exige ajuste de page file).
3. **Onda 2 (execução de Skills + 1ª Tool):** ligar o `SkillRegistry` ao Orquestrador (usar o seam), `SkillResult`/erro padronizado, e a Browser Tool **só leitura** com gate de confirmação.
4. Manter o protocolo: **teste de caracterização antes de refatorar**, bloco pequeno, testes verdes a cada passo (GOVERNANCE §13).

---

> **Nenhuma nova funcionalidade foi adicionada nesta Onda.** Só estabilização: menos duplicação,
> menos acoplamento, roteamento pronto para escalar — com todos os contratos preservados.
