# 📜 GOVERNANCE — Constituição Operacional do CRIS OS

**Data:** 2026-06-30 · **Tipo:** governança (regras de operação; nenhum código alterado).
**Relação com os outros documentos:**
[ARCHITECTURE_FREEZE.md](ARCHITECTURE_FREEZE.md) define **o que é permanente** (contratos,
fronteiras, princípios). Este documento define **como operar** dentro disso (criar, evoluir,
revisar, promover). **Precedência:** FREEZE › GOVERNANCE › decisões de implementação.

> Toda criação/mudança deve, antes de tudo, passar pela pergunta do FREEZE: *muda
> implementação (ok) ou contrato/fronteira/princípio (exige processo aditivo)?*

---

## 1. Como criar um **Agente** novo
Agente = papel com julgamento; **uma responsabilidade**; um **domínio**.

**Passos:**
1. Definir o **domínio** (ver §5) e a responsabilidade única (sem sobreposição com outro agente).
2. Criar `agents/<nome>/` com:
   - `manifest.json` — `name`, `title`, `description` (específica — o Orquestrador roteia por ela),
     `domain`, `projects` (escopo de memória), `status: "draft"`, `enabled`, `delegate: true`, `tools: []`.
   - `SYSTEM.md` — o "cargo" (comportamento/prompt).
   - `README.md` — visão humana.
3. **Não** alterar o Core: o `loader`/`PluginManager` descobre o agente (OCP).
4. Escopar a memória via `projects` (`[]`, `["Projeto"]` ou `["*"]`).
5. Garantir as regras: o agente **nunca** fala com a Cris nem com outro agente — só responde ao Orquestrador.

**Proibido:** importar canais, storage, event bus ou outro agente; rotear via edição do Core.

---

## 2. Como criar uma **Skill** nova
Skill = job empacotado, versionado. **Sempre** seguir o SDK.

**Passos:**
1. Scaffold: `python scripts/new_skill.py <nome> --title "..." --description "..." --category <cat> [--agents ...] [--tools ...]`.
2. Preencher os **8 arquivos** (SKILL.md, manifest.json, README.md, rules.md, examples.md, tools.md, tests.md, version.json).
3. Implementar `handler.py` cumprindo `SkillExecutor`: `execute(payload: dict, context: SkillContext) -> dict`.
4. No `manifest.json`: `domain`/`category`, `executor: "handler:Classe"`, `agents` (ou `["*"]`), `tools`, `status: "scaffold"`.
5. Acessar Memory/Event Log/Tools **apenas pelo `SkillContext`** (nunca importar storage/bus).
6. Escrever testes em `tests/test_<skill>.py` (Memory + Event Log + Registry + "qualquer agente").
7. Atualizar [SKILLS_INDEX.md](SKILLS_INDEX.md).

**Proibido:** ação externa (enviar/publicar/comprar/apagar) **sem confirmação da Cris**;
falar com canais/Cris; chamar outra skill direto.

---

## 3. Como criar uma **Ferramenta (Tool)**
Tool = ação atômica no mundo. **Read-only por padrão.**

**Passos:**
1. Implementar a porta `Tool` (`core/contracts/tool.py`): `name`, `description`, `schema() -> dict`, `run(**kwargs) -> str`.
2. Criar `tools/<nome>/` (código + README + schema).
3. Registrar no `ToolRegistry` (por manifesto/descoberta, quando habilitado) — **sem alterar o Core**.
4. Declarar a tool no `manifest.json` da skill/agente que a usa (`"tools": [...]`).
5. **Segredos só no `.env`** (nunca no repo).
6. Ação **destrutiva/externa** exige **gate de confirmação** explícito da Cris.
7. Testes do `run()` (com mocks das chamadas externas).

**Proibido:** acessar memória/Cris diretamente; write/ação externa sem gate.

---

## 4. Como adicionar um **Canal** (WhatsApp, Discord, Slack, Web, API…)
Canal = adaptador de I/O. **Não conhece** agentes/LLM/memória.

**Passos:**
1. Implementar a porta `Channel` (`core/contracts/channel.py`): `name`, `run()`.
2. Criar `channels/<nome>/`; traduzir plataforma **⇄ `IncomingMessage`** e chamar o `Handler` (Gateway).
3. Registrar o canal no `core/runtime.py` (composition root).
4. Autorização/multiusuário ficam no **Gateway**, não no canal.
5. (Futuro) saída proativa via porta `send(OutgoingMessage)` — aditiva.

**Proibido:** o canal conhecer agentes/skills/LLM/memória; responder à Cris fora do fluxo do Orquestrador.

---

## 5. Como criar um **Domínio** novo
Domínio = bucket **curto, coarse e estável** para o roteamento hierárquico.

**Regras:**
- A lista de domínios é **curada** e mantida pequena (≈ projetos + áreas pessoais).
- Catálogo atual: `pessoal, atendimento, pesquisa, marketing, conteudo, financeiro, zavix,
  vitrinepro, scalaflow, pinklogic, curriculo, sistema`. Reservados: `produtos-3d, sites`.
- Adicionar um domínio exige **aprovação** (decisão deliberada) e:
  1. registrar o domínio no **catálogo único** de domínios;
  2. atribuir agentes/skills via o campo `domain` no manifest;
  3. confirmar que o roteador hierárquico passa a considerá-lo.
- Domínio é **dado** (manifest/catálogo), nunca lógica hardcoded no Core.

---

## 6. Como um **Plugin** evolui sem quebrar o Core
- Depender **apenas** da **API pública interna** (FREEZE §6): ports, DTOs, eventos, contextos, catálogos.
- **Nunca** importar internos de outra camada (storage, bus, runtime, internos do orquestrador).
- Mudanças de manifest são **aditivas** (campo novo com default).
- Subir a **versão** (semver) a cada mudança relevante.
- Se o plugin precisar de algo que o Core não expõe → **estender o Core de forma aditiva**
  (processo do Apêndice do FREEZE), nunca alcançar implementação interna.

---

## 7. ✅ Checklist obrigatório de **Pull Request / Mudança**
> Vale para qualquer alteração (mesmo sem git formal).

- [ ] Respeita o **FREEZE** (não quebra contrato/fronteira/princípio).
- [ ] Toca **apenas** as camadas permitidas para o tipo de mudança.
- [ ] **Nenhuma** quebra de contrato (só evolução **aditiva**).
- [ ] **Direção de dependência** preservada (para dentro); sem agent↔agent, agent→channel, →storage direto.
- [ ] **Testes** adicionados/atualizados **e verdes**; **smoke verde**.
- [ ] **Docs** atualizadas (SYSTEM/README/8-files/índice conforme o caso).
- [ ] Manifests **válidos** (skills: os 8 arquivos; campos obrigatórios presentes).
- [ ] **Sem segredos** no diff; `.env` intocado.
- [ ] Mudança **pequena e focada** (um propósito).
- [ ] Versão bumpada quando aplicável; changelog atualizado.

---

## 8. ✅ Checklist obrigatório **antes de Produção**
- [ ] `status: "production"` **só** após cumprir os critérios (§9/§10).
- [ ] Todos os testes (unit + smoke) **verdes**.
- [ ] Documentação **completa** (nada de stub de template).
- [ ] `rules.md`/regras globais respeitadas; **nenhuma ação externa sem confirmação**.
- [ ] Custo/performance considerados (contexto, latência, memória).
- [ ] **Observável** via Event Log (emite eventos significativos).
- [ ] Plano de **rollback** (reverter `enabled`/`status`).
- [ ] `enabled: true` no manifest.

---

## 9. Critérios: **Skill** Draft → Production
- [ ] `handler.py` implementado e **conforme** `SkillExecutor`.
- [ ] Os **8 arquivos** preenchidos de verdade (sem placeholders).
- [ ] Testes unitários **verdes** cobrindo **Memory + Event Log + Registry + "qualquer agente"**.
- [ ] `examples.md` bate com o comportamento real.
- [ ] `rules.md` respeitada (sem ação externa sem confirmação).
- [ ] Versão **≥ 1.0.0**; changelog no `version.json`.
- [ ] Revisada contra este GOVERNANCE e o FREEZE.
- [ ] `status: "production"`, `enabled: true`.

---

## 10. Critérios: **Agente** Experimental → Production
- [ ] `SYSTEM.md` específico e **testado** (responde no domínio).
- [ ] `domain` e `projects` (escopo) corretos.
- [ ] **Pelo menos uma** tarefa real executada ponta a ponta.
- [ ] O Orquestrador **roteia corretamente** para ele.
- [ ] **Não** acessa canal/Cris/outro agente direto.
- [ ] Revisado; `status: "production"`.

---

## 11. Política de **Versionamento**
- **SemVer** `MAJOR.MINOR.PATCH` em `version.json` **e** `manifest.json`.
- **PATCH:** correção sem mudança de comportamento.
- **MINOR:** adição **retrocompatível** (novo campo/opção/ação).
- **MAJOR:** mudança incompatível — **proibida em contratos** sem coexistência (ver §12).
- Todo bump relevante registra entrada no **changelog**.
- Contratos do Core evoluem **somente aditivamente** (FREEZE §0).

---

## 12. Política de **Depreciação**
- **Nunca** remoção abrupta. Marcar `deprecated`, manter funcionando por uma **janela** definida.
- Documentar o **substituto** e o caminho de migração.
- Contratos: criar **vN+1** convivendo com **vN**; remover **vN** só após a janela e zero uso.
- Skills/Agentes aposentados → `enabled: false` + nota no changelog antes de remover a pasta.

---

## 13. Política de **Testes mínimos**
- **Toda** mudança de comportamento/refator tem **teste unitário**.
- **Smoke sempre verde** (gate de merge).
- **Skill em produção** exige os testes de integração (Registry + Memory/Event Log + "qualquer agente").
- **Mudança em contrato do Core** exige teste do contrato.
- **Refator** → escrever **teste de caracterização antes** (princípio da Onda 1).
- Sem teste = não vai para produção.

---

## 14. Política de **Documentação obrigatória**
- **Agente:** `SYSTEM.md` + `README.md` + `manifest.json` exatos.
- **Skill:** os **8 arquivos** preenchidos (produção não aceita stub) + entrada no [SKILLS_INDEX.md](SKILLS_INDEX.md).
- **Tool:** README + `schema()` documentado.
- **Canal:** README + nota no [channels/README.md](channels/README.md).
- **Mudança arquitetural:** registrar em ARCHITECTURE_NEXT/REVIEW; manifests sempre fiéis ao real.
- Sem documentação = não vai para produção.

---

## 15. O que **nunca** pode ser aceito numa revisão de arquitetura
> 🚫 Reprovação automática.

- 🚫 Quebra **não-aditiva** de contrato/DTO/port (remoção/renomeação/repropósito).
- 🚫 Comunicação direta proibida: **agent↔agent**, **skill↔skill**, agent/skill → **canal/Cris**.
- 🚫 Acesso direto a **storage**, **Event Bus**, **segredos** ou **memória de outro tenant**.
- 🚫 **Alterar o Core para adicionar um plugin** (viola OCP) — incl. roteamento hardcoded por agente.
- 🚫 **Nova camada/abstração sem necessidade** (abstração cedo demais).
- 🚫 **Burlar o Orquestrador** (qualquer caminho de fala com a Cris fora dele).
- 🚫 **Ação externa/destrutiva sem gate de confirmação**.
- 🚫 **Segredos no repositório**.
- 🚫 Ir para **produção sem testes e sem documentação**.
- 🚫 Violar qualquer **princípio do FREEZE §8** ou a **Lei da Comunicação §9**.

---

> Esta é a **Constituição Operacional**. Toda contribuição ao CRIS OS — humana ou automática —
> deve passar por ela. Em conflito, vence o **ARCHITECTURE_FREEZE.md**.
