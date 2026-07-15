# ONDA 3 — PLANO (roteamento inteligente: escolher melhor Skills, Tools e Agentes)

> **Status:** PROPOSTA — aguardando aprovação. **Nenhum código nesta fase.**
> **Data:** 2026-07-01 · **Owner:** Cris · Base: [ONDA2_COMPLETED.md](ONDA2_COMPLETED.md) · Congelamento: [ARCHITECTURE_FREEZE.md](ARCHITECTURE_FREEZE.md)

## 🎯 Objetivo geral
A Onda 2 fez o CRIS OS **executar** Skills/Tools/Agentes (kernel de execução). A Onda 3 faz o
CRIS OS **escolher melhor** o que executar — roteamento mais inteligente e menos frágil — **sem
depender de tool-calling de um modelo grande** e **sem embeddings globais**. Resultado esperado:
a Cris fala naturalmente e o Orquestrador acerta a Skill/Tool/Agente certos, mesmo com `qwen 1.5b`.

## 🧭 Princípios-guia (restrições desta onda)
1. **Funciona com modelo pequeno:** o roteamento não pode depender de `tool_call` confiável (o `qwen 1.5b` não faz). Precisa de um caminho **determinístico e local**.
2. **Aditivo / FREEZE:** nada de quebrar portas/DTOs; tudo com default seguro; motores (`WorkflowEngine`, `SkillRunner`, `BrowserTool`) intocados.
3. **Local-first, sem embeddings globais:** semântica **escopada ao domínio** (poucos candidatos, sob demanda) — não um índice vetorial global.
4. **Protocolo bloco-a-bloco:** explicar → menor alteração → testes + smoke → diff → FREEZE → parar e aguardar aprovação.
5. **Read-only por padrão:** o `ConfirmationGate` continua protegendo qualquer ação sensível.

## 🗺️ Escopo → blocos
| Escopo pedido | Bloco |
|---|---|
| 1. Melhorar roteamento de Skills além de keyword | **B1** (abstração de roteamento) + **B2** (scorer semântico) |
| 2. Roteamento semântico **dentro do domínio** | **B2** + **B3** (metadados no manifest) |
| 3. Como o Browser Tool será chamado pelo Orquestrador | **B4** |
| 4. Como a Secretária IA usará Skills e Tools | **B5** |
| 5. Quando ativar a Cognição (Planner/Executor/Reviewer/Supervisor) | **B6** |
| 6. Fora da Onda 3 | seção **"O que será adiado"** |

---

## 🧱 Blocos

### B0 — Governança + contratos de roteamento (design)
- **Objetivo:** revisar o FREEZE para a onda, definir as **portas de roteamento** (sem implementar scorers) e travar a caracterização atual do `IntentRouter` como rede de segurança.
- **Arquivos possivelmente afetados:** `ARCHITECTURE_FREEZE.md` (nota de escopo), `core/contracts/routing.py` (novo — só as interfaces), `tests/test_intent_router.py` (caracterização reforçada).
- **Riscos:** desenhar a porta larga demais. → manter mínima (rankear candidatos).
- **Critério de pronto:** contratos definidos; testes atuais verdes; nada de comportamento mudado.
- **Testes esperados:** os atuais continuam passando (baseline).

### B1 — Abstração de roteamento (`RouteScorer` + `RouteCandidate`)
- **Objetivo:** refatorar o `IntentRouter` para (a) montar **candidatos** (domínios, agentes, skills, tools) com seus metadados de roteamento e (b) delegar a escolha a **scorers plugáveis**. O scorer de **keyword** atual vira o primeiro plugin — **comportamento idêntico** ao de hoje.
- **Como:** `RouteCandidate(name, type, description, keywords, examples)` + porta `RouteScorer.score(message, candidates) -> [(candidate, score)]`. O `IntentRouter` passa a: LLM tool-calling → scorers (ordenados) → default. Cadeia de fallback preservada.
- **Arquivos:** `core/contracts/routing.py`, `core/application/intent_router.py`, `core/application/routing/__init__.py` + `keyword_scorer.py` (novos), `tests/test_routing.py` (novo), `tests/test_intent_router.py`.
- **Riscos (ALTO):** regressão no roteamento de agentes. → refator neutro, caracterização trava, `skills=None` ainda ≡ hoje.
- **Critério de pronto:** todos os testes + smoke verdes; roteamento idêntico ao atual quando só o keyword_scorer está ativo.
- **Testes esperados:** `test_routing` (scorer keyword rankeia candidatos), `test_intent_router` (mesmos resultados de antes), smoke.

### B2 — Scorer semântico **dentro do domínio** (léxico, local, sem embeddings globais)
- **Objetivo:** escolher a melhor Skill/Tool/Agente entre os candidatos **de um domínio** por similaridade de linguagem — não só substring de keyword.
- **Como:** `LexicalScorer` pontua cada candidato pela sobreposição entre a mensagem e (`description` + `examples` + `keywords`) do candidato (ex.: TF-IDF / n-gramas / tokens normalizados). Escopo = só os poucos candidatos do domínio (sob demanda). **Threshold**: acima dele, vence; abaixo, cai para keyword → default. **Opcional (decisão aberta):** um `EmbeddingScorer` local via Ollama (ex.: `nomic-embed-text`) **escopado aos candidatos** — NÃO é índice global.
- **Arquivos:** `core/application/routing/lexical_scorer.py` (novo), `intent_router.py` (encaixe na cadeia), `config/settings.py` (threshold), (opcional) `llm/embeddings.py` + `core/application/routing/embedding_scorer.py`, `tests/test_lexical_scorer.py`.
- **Riscos:** falsos positivos (rotear para skill errada) → threshold conservador + precedência agente em empate + testes com frases reais. Latência do embedding (se usado) → opcional e sob demanda.
- **Critério de pronto:** "faça o handoff", "resuma esse link", etc. roteiam certo **sem** depender de keyword exata; agentes não regridem; testes + smoke verdes.
- **Testes esperados:** `test_lexical_scorer` (frases variadas → candidato certo), `test_intent_router` (fallback semântico antes do keyword), smoke.

### B3 — Metadados de roteamento no manifest (Skills, Tools, Agentes)
- **Objetivo:** alimentar o scorer com dados declarativos e **nada hardcoded**: `examples` (frases de gatilho), `description` rica, e (se preciso) `routing_hints`.
- **Como:** estender `Skill`/agente/`Tool` para ler `examples` do manifest; o `IntentRouter` usa esses campos ao montar `RouteCandidate`.
- **Arquivos:** `core/skills/skill.py` + `registry.py`, `skills/*/manifest.json`, `agents/*/manifest.json`, `core/contracts/tool.py` (metadados da tool), `agents/loader.py`, `tests/test_skill_registry.py`, `tests/test_loader.py`.
- **Riscos:** manifests inconsistentes → validação leve + defaults (campo ausente ⇒ scorer usa o que tiver).
- **Critério de pronto:** manifests com `examples`; scorer melhora com eles; descoberta/validação verdes.
- **Testes esperados:** `test_skill_registry`/`test_loader` (lê `examples`), `test_lexical_scorer` (usa `examples`).

### B4 — Browser Tool chamado pelo Orquestrador (linguagem natural → `type=TOOL`)
- **Objetivo:** a Cris pedir "abre/lê/resume esse link" e o Orquestrador acionar o `tool.browser` (já registrado), com **extração de URL** e **read-only** garantido pelo gate.
- **Como (decisão aberta):**
  - **(a) Skill-fachada `web-browse`** (recomendado): uma Skill com `examples`/`keywords` (leia, abra, resuma a página, extraia links) que, ao rodar, **emite/chama** um passo `ExecutionStep(type=TOOL, name="browser", payload={url, action})`. Mantém o padrão "Skill usa Tool" e reusa o scorer do B2/B3.
  - **(b) Detector no IntentRouter:** se a mensagem contém URL + verbo de leitura, emite direto o passo `TOOL`. Mais acoplado.
- **Extração de URL:** util simples (regex http/https) para preencher `payload.url`.
- **Arquivos:** `skills/web-browse/*` (novo, se (a)) **ou** `intent_router.py` (se (b)); `tools/browser/*` (helper de URL, se preciso); `core/runtime.py`; `tests/test_browser_routing.py`.
- **Riscos:** SSRF/host interno → mitigado por ser read-only + (futuro) allowlist de host; passo sensível jamais criado (browser é `READ_ONLY`).
- **Critério de pronto:** "resuma https://exemplo.com" → `tool.browser` roda read-only, passa no gate, devolve título/texto/links; testes + smoke verdes.
- **Testes esperados:** `test_browser_routing` (mensagem com URL → passo TOOL read-only via fake fetcher), `test_confirmation_gate` (browser não pede confirmação).

### B5 — Secretária usa Skills e Tools ("Agentes orquestram Skills; Skills usam Tools")
- **Objetivo:** a Secretária (e, no futuro, outros agentes) poder **acionar** Skills/Tools ao atender, sem falar direto com a Cris (só o Orquestrador fala).
- **Como (decisão aberta):**
  - **(a) Tool-belt declarado + roteamento (recomendado):** o agente declara no manifest as Skills/Tools que pode usar; ao rotear para o domínio do agente, o `IntentRouter`/scorer também considera as Skills/Tools do tool-belt. Simples, sem recursão.
  - **(b) Delegação pós-execução:** o `AgentResult` pode conter "follow-ups" (pedidos de Skill/Tool) que o Orquestrador despacha. Mais poderoso, porém exige **limite de profundidade** para evitar loops.
- **Arquivos:** `agents/*/manifest.json` (tool-belt), `agents/base.py`/`agents/loader.py`, `core/contracts/agent.py` (se (b): follow-ups em `AgentResult`), `core/application/workflow.py`/`orchestrator.py`, `tests/test_secretary_tools.py`.
- **Riscos:** loops/recursão (se (b)) → limite de profundidade + gate ainda protege escrita. Escopo de memória do agente preservado (SkillMemory).
- **Critério de pronto:** a Secretária consegue acionar a `session-handoff` (e o browser) dentro de um pedido; sem loops; só o Orquestrador responde; testes + smoke verdes.
- **Testes esperados:** `test_secretary_tools` (pedido → agente aciona skill/tool → 1 resposta), caracterização de agentes intacta.

### B6 — Quando ativar a Cognição (Planner → Executor → Reviewer → Supervisor)
- **Objetivo:** **definir os critérios de ativação** e destravar a cognição de forma **faseada e segura** (hoje é esqueleto com `NotImplementedError`).
- **Critérios de ativação propostos (gatilho por complexidade):**
  - **Planner** (1º a ativar): quando o pedido é **multi-passo/objetivo** (ex.: "planeje minha semana e prepare os posts") — decompõe em `Plan`/`ExecutionStep`s. Atrás de flag `COGNITION_ENABLED` + classificador de complexidade.
  - **Executor:** encapsula o `ExecutionDispatcher` para rodar o plano com rastreio/retentativa/timeout (reusa `ExecutionStep.timeout/priority/depends_on`).
  - **Reviewer/Supervisor** (últimos): só quando houver **critério de qualidade mensurável**; começam **definidos e inativos** (ativação em onda futura).
- **Escopo desta onda (decisão aberta):** **(a)** só DEFINIR os critérios (nenhum código de cognição) — mais conservador; ou **(b)** DEFINIR + implementar um **Planner mínimo** atrás de flag, com Executor reusando o dispatcher; Reviewer/Supervisor ficam definidos-inativos.
- **Arquivos:** `core/cognition/*` (planner/executor), `core/domain/planning.py`, `config/settings.py` (flags + limiares), `core/runtime.py` (fiação condicional), `core/application/` (classificador de complexidade), `tests/test_cognition_*`.
- **Riscos (ALTO):** cognição no caminho quente → tudo atrás de flag, default OFF; classificador conservador (dúvida ⇒ fluxo v3 atual). Latência (planejar chama o LLM).
- **Critério de pronto:** critérios documentados; se (b): Planner mínimo verde em teste, **desligado por padrão**, sem afetar o atendimento atual (smoke intacto).
- **Testes esperados:** `test_cognition_*` (Planner decompõe objetivo simples), `test_smoke`/`test_runtime_build` (v3 inalterado com flag OFF).

---

## 🔢 Ordem recomendada
`B0 → B1 → B2 → B3 → B4 → B5 → B6`

**Racional:** primeiro a **fundação** (abstração de roteamento, B1) e o **cérebro determinístico** (scorer, B2); depois os **dados** que o alimentam (manifests, B3); então os **novos alvos de uso** (Browser B4, Secretária B5); e por último a **cognição** (B6), que é a mais especulativa e a de maior risco — só depois que o roteamento estiver sólido.

## 🚫 O que será adiado (fora da Onda 3)
- **WhatsApp** e outros canais novos.
- **Multiusuário** (o CRIS OS serve só a Cris).
- **Segunda máquina / replicação ativa** (o backbone de eventos/outbox existe, mas ativar failover fica para depois).
- **MCP avançado** (conectar servidores MCP externos como tools).
- **Embeddings globais / índice vetorial global** (a semântica da Onda 3 é **escopada ao domínio**, sob demanda).
- **Reviewer/Supervisor ativos** (ficam definidos-inativos; ativação em onda futura).
- **Pause/resume completo do ConfirmationGate** (só quando existirem ações de escrita reais; o Browser é read-only).
- **Escrita no Browser** (clicar/preencher/login/comprar/publicar/enviar continua proibido).

## ❓ Decisões abertas (para você resolver na aprovação)
1. **Scorer semântico (B2):** léxico-only (determinístico, zero deps) **ou** léxico + `EmbeddingScorer` local via Ollama (escopado, opcional)?
2. **Browser (B4):** Skill-fachada `web-browse` **(recomendado)** ou detector de URL no IntentRouter?
3. **Secretária (B5):** tool-belt declarado + roteamento **(recomendado)** ou follow-ups no `AgentResult` (com limite de profundidade)?
4. **Cognição (B6):** só DEFINIR critérios **ou** DEFINIR + Planner mínimo atrás de flag?

---

## Critérios de pronto (onda inteira)
- Todos os testes unitários + smoke **verdes** ao fim de cada bloco.
- **Aditivo/FREEZE-compat** em cada bloco; nenhuma porta/DTO congelado quebrado.
- **Roteamento melhor comprovado**: frases sem keyword exata acertam a Skill/Tool/Agente certos.
- **Validação em produção** (Telegram real) dos fluxos-chave: roteamento semântico de skill e leitura de página pelo Browser.
- Cognição (se implementada) **desligada por padrão**, sem afetar o atendimento v3.

**Não implementar nada.** Aguardando sua aprovação e as 4 decisões abertas para iniciar pelo **B0**.
