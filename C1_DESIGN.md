# 🧭 C1_DESIGN — Roteamento em escala (100 agentes / 300 Skills)

**Data:** 2026-06-30 · **Tipo:** documento de design (comparação de arquiteturas; **nenhuma implementação**).
**Resolve:** o achado **C1** de [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md).

---

## 1. O problema (C1)

Hoje o `IntentRouter` envia **todos** os agentes como *tools* ao LLM e o
`_planner_prompt` injeta **todas** as descrições no system prompt. Isso não escala:

| Nº de unidades | Efeito |
|---|---|
| ~11 (hoje) | funciona bem |
| ~30–50 | qualidade do roteamento cai; prompt grande; lento em modelo local |
| ~100 agentes + 300 skills | **inviável**: o prompt não cabe, o modelo local não decide bem, e o tool-calling com 400 funções não funciona |

**Objetivo:** uma arquitetura de **seleção** (qual domínio → qual skill → qual agente)
que escale para o CRIS OS projetado:
- **~100 agentes**, **~300 Skills**, **dezenas de Tools**;
- múltiplos canais (Telegram, WhatsApp, Discord, Web, API);
- múltiplos projetos (Zavix, VitrinePro, ScalaFlow, PinkLogic, Produtos 3D, mkVideos, futuros);
- execução **local com Ollama** (modelos pequenos), com **modelos remotos** possíveis no futuro;
- **múltiplos usuários** no futuro (isolamento por tenant).

> Premissa-chave: o roteamento **precisa funcionar com modelo local pequeno**.
> Qualquer solução que dependa de "jogar tudo num modelo grande" é descartada.

---

## 2. Critérios de avaliação
Cada opção é analisada em: **funcionamento · vantagens · desvantagens · complexidade ·
consumo de contexto · escalabilidade · performance · compatibilidade com a arquitetura
atual · impacto no Event Bus · impacto na Memory · impacto no Orquestrador · impacto nas
Skills · facilidade de manutenção.**

---

## 3. Opção A — Roteamento Hierárquico
**Usuário → Domínio → Skill → Agente**

### Funcionamento
Uma **árvore de decisões**, cada nível com um conjunto **pequeno e fechado** de opções.
1. Classifica a mensagem num **Domínio** (~10–15: Zavix, VitrinePro, Financeiro, Social, Pessoal…).
2. Dentro do domínio, escolhe a **Skill** (job) — cada domínio tem ~10–30 skills.
3. A skill/contexto define o **Agente** que executa.
Cada passo é uma classificação (LLM pequeno ou regra) sobre **poucas** opções. Os
manifests declaram `domain`/`category`; o registry **indexa por domínio**.

### Vantagens
- Cada decisão vê **poucas opções** (~10–20) → cabe em modelo local pequeno.
- **Determinístico e explicável** ("por que foi pro Zavix?" = nó de domínio).
- Sem infraestrutura nova (nada de embeddings/vetor).
- Mapeia 1:1 com **projetos** e prepara **multi-usuário** (o 1º corte pode ser tenant/projeto).
- Adicionar agente/skill = **declarar o domínio** no manifest.

### Desvantagens
- Exige uma **taxonomia limpa**; pedidos ambíguos ou **cross-domínio** ("post do Zavix e do VitrinePro") ficam difíceis.
- **Múltiplos saltos de LLM** (2–3) → mais latência.
- Erro num nó **alto** cascateia (domínio errado → tudo errado).
- Não captura **semântica** (skill descrita diferente da forma como a Cris fala).
- A taxonomia precisa de **curadoria** contínua (risco de "apodrecer").

### Complexidade
**Baixa–Média.** É o `IntentRouter` virando multi-etapas sobre registries indexados por domínio. Sem novos subsistemas.

### Consumo de contexto
**Baixo por chamada** (só as opções do nível atual), porém **várias chamadas**. Total moderado; cada chamada cabe num modelo local.

### Escalabilidade
**Boa** se a árvore ficar **balanceada** (100 agentes ÷ 15 domínios ≈ 7/domínio). Degrada se um domínio incha (aí aquele nível precisa de sub-roteamento).

### Performance
**2–3 chamadas sequenciais** de LLM → latência maior, mas cada uma é rápida (contexto pequeno). Em CPU/Ollama é aceitável; em remoto, ótimo.

### Compatibilidade com a arquitetura atual
**Alta.** O `IntentRouter` já é o ponto de extensão; basta torná-lo multi-etapas. Skills já têm `category`; agentes ganhariam `domain` no manifest. Registry indexa por domínio.

### Impacto no Event Bus
**Aditivo:** novos eventos (`domain.classified`, `skill.selected`, `agent.selected`). Sem mudança no barramento. Auditoria fica mais rica.

### Impacto na Memory
**Positivo:** o domínio escolhido **escopa a memória** (carrega só a L2 daquele projeto). Sinergia natural com o `MemoryFacade`.

### Impacto no Orquestrador
**Baixo:** muda o **interior** do planejamento (IntentRouter multi-etapas); a interface do Orquestrador e o WorkflowEngine não mudam.

### Impacto nas Skills
Skills marcadas por `domain`/`category`; seleção fica **limitada** ao domínio. Encaixa no modelo de manifest.

### Facilidade de manutenção
**Boa** com taxonomia curada — mas a **taxonomia vira um artefato a manter**. Adicionar unidades = etiquetar.

---

## 4. Opção B — Roteamento por Embeddings / RAG

### Funcionamento
No carregamento, cada agente/skill/tool tem sua **descrição + exemplos** convertidos em
**vetores** (embeddings) e indexados. No pedido: gera o embedding da mensagem, faz **busca
por similaridade** (top-K, ex.: 5–8 candidatos) e ou (a) pega o top-1, ou (b) entrega os
top-K a um LLM para a escolha final. É **roteamento aumentado por recuperação**.

### Vantagens
- Escala para **milhares** de unidades (busca vetorial ANN é sub-linear).
- Captura **semântica** ("meu currículo tá fraco" → `curriculum-builder`, mesmo sem citar).
- **Sem taxonomia rígida**; adicionar unidade = indexar (automático).
- **Uma** chamada de LLM (sobre o top-K) → menos saltos.
- Robusto a linguagem/variação com embeddings multilíngues.

### Desvantagens
- Precisa de **modelo de embedding + índice vetorial** (infra/dependência nova).
- **Qualidade do embedding** manda no resultado; descrições pobres → recuperação ruim.
- **Cold-start / reindexação** quando unidades mudam.
- Modelo de embedding **local consome memória** — crítico nesta máquina (já estoura com 8B). Um embed pequeno (ex.: `nomic-embed-text` ~270 MB) é viável, mas é +1 modelo.
- Menos **explicável** ("por que X?" = score de similaridade).
- **Multi-usuário/multi-projeto** exige **filtro de metadados** no índice (não recuperar de outro tenant) — não vem de graça.

### Complexidade
**Média–Alta.** Pipeline de embedding + índice + ingestão em mudanças + filtros.

### Consumo de contexto
**Baixo** — só o top-K (5–8) vai ao LLM. **Melhor eficiência de contexto** em escala. O embedding em si é barato.

### Escalabilidade
**A melhor para números puros** (300 skills + 100 agentes + tools num só índice). Busca sub-linear; inserção automática.

### Performance
Uma chamada de **embedding** (rápida) + uma de **LLM** sobre top-K → menos latência que a hierárquica. **Porém** o embed local adiciona pressão de RAM. A busca vetorial é rápida.

### Compatibilidade com a arquitetura atual
**Média.** Introduz um subsistema novo, mas encaixa no modelo de ports (um `IndexedRouter` + um port `Embedder`). A `KnowledgeBase` já tem FTS5 (recuperação primitiva); embeddings seriam o próximo passo (a L4 vai para vetorial de qualquer forma).

### Impacto no Event Bus
**Aditivo:** evento `router.retrieved` (candidatos + scores). Sem mudança.

### Impacto na Memory
**Médio–Alto (sinergia):** o índice vetorial do roteamento pode **compartilhar infra** com a L4 (Base de Conhecimento), que já vai virar vetorial. Mas soma um modelo de embedding na memória.

### Impacto no Orquestrador
**Baixo:** o IntentRouter vira "recupera top-K → LLM seleciona". Interface intacta.

### Impacto nas Skills
Encaixe **natural**: `examples.md` de cada skill é ótima fonte de embedding. Seleção de skill vira recuperação.

### Facilidade de manutenção
**Baixa manutenção de taxonomia** (não há), **mas** exige manter o pipeline de embedding/índice e reindexar em mudanças. Menos explicável ao depurar.

---

## 5. Opção C — Roteamento Híbrido
**Domínio + Embeddings + Skill + Agente**

### Funcionamento
Combina as duas. Um **1º corte barato e determinístico** escolhe o **Domínio/projeto**
(também resolve isolamento multi-usuário/multi-projeto); **dentro** do domínio, usa
**embeddings/recuperação** para achar o top-K de skills/agentes (semântico, escalável);
uma seleção final (LLM sobre poucos, ou top-1 direto). Hierarquia para o **grosso**
(determinístico, seguro); embeddings para o **fino** (semântico, escalável).

### Vantagens
- **Melhor dos dois:** domínio dá explicabilidade, isolamento de tenant/projeto e escopo;
  embeddings dão semântica e escala **dentro** do domínio.
- **Busca vetorial menor** (filtrada por domínio) → mais rápida e mais precisa.
- **Degrada com elegância:** sem embedding disponível, cai para LLM sobre o conjunto pequeno do domínio (= modo hierárquico).
- O filtro de domínio resolve **multi-usuário** (nunca recupera entre tenants).
- Compatível com **local-first** (classificar domínio é barato; busca num domínio pequeno é barata).

### Desvantagens
- **Mais peças** (taxonomia + embeddings + seleção) → mais design inicial.
- **Dois subsistemas** a manter.
- Mais difícil de raciocinar ponta a ponta.

### Complexidade
**Alta** — porém cada parte é **bounded** (a taxonomia é coarse/estável; o índice é por domínio).

### Consumo de contexto
**Baixo:** classificação de domínio minúscula; recuperação devolve top-K; LLM final vê poucos.

### Escalabilidade
**A melhor no geral:** o domínio **particiona** o espaço (sharding) e os embeddings escalam dentro. Suporta 100 agentes / 300 skills / dezenas de tools / multi-projeto / multi-usuário.

### Performance
Domínio (barato) + busca **filtrada** (rápida) + seleção final. Um passo a mais que o B puro, mas cada um barato; busca filtrada é mais rápida que global.

### Compatibilidade com a arquitetura atual
**Média.** Combina os dois adaptadores; encaixa no modelo de ports. Reaproveita o `IntentRouter` como **pipeline de estágios**.

### Impacto no Event Bus
**Aditivo:** eventos em cada estágio (`domain.classified` → `candidates.retrieved` → `agent.selected`).

### Impacto na Memory
**Forte sinergia:** o passo de domínio **escopa a memória** (carrega só o projeto); o índice vetorial é **compartilhado** com a L4.

### Impacto no Orquestrador
**Baixo:** IntentRouter vira pipeline (filtra → recupera → seleciona). Interface do Orquestrador intacta.

### Impacto nas Skills
**Melhor encaixe:** skills indexadas **por domínio**; seleção semântica dentro do escopo certo.

### Facilidade de manutenção
**Média:** taxonomia **coarse e estável** (poucos domínios) + pipeline de índice. Mais partes, porém **isoladas**.

---

## 6. Matriz comparativa

| Dimensão | A) Hierárquico | B) Embeddings/RAG | C) Híbrido |
|---|---|---|---|
| Complexidade | 🟢 Baixa–Média | 🟠 Média–Alta | 🔴 Alta |
| Consumo de contexto | 🟢 Baixo (n/ chamadas) | 🟢 Baixo | 🟢 Baixo |
| Escalabilidade (nº unidades) | 🟠 Boa (se balanceada) | 🟢 Excelente | 🟢 Excelente |
| Performance (latência) | 🟠 2–3 saltos LLM | 🟢 1 embed + 1 LLM | 🟢 cheap + busca filtrada |
| Semântica / ambiguidade | 🔴 Fraca | 🟢 Forte | 🟢 Forte |
| Explicabilidade / debug | 🟢 Alta | 🔴 Baixa | 🟢 Alta (no corte) |
| Infra nova | 🟢 Nenhuma | 🔴 Embed + vetor | 🟠 Embed + vetor (menor) |
| Pressão de RAM (local) | 🟢 Mínima | 🔴 +modelo embed | 🟠 +modelo embed |
| Multi-usuário / isolamento | 🟢 Natural | 🟠 Exige filtro | 🟢 Natural |
| Multi-projeto | 🟢 Direto (= domínio) | 🟠 via metadados | 🟢 Direto |
| Compat. arquitetura atual | 🟢 Alta | 🟠 Média | 🟠 Média |
| Impacto Event Bus | 🟢 Aditivo | 🟢 Aditivo | 🟢 Aditivo |
| Impacto Memory | 🟢 Escopa memória | 🟠 Compartilha índice | 🟢 Escopa + compartilha |
| Impacto Orquestrador | 🟢 Baixo | 🟢 Baixo | 🟢 Baixo |
| Manutenção | 🟠 Taxonomia | 🟠 Pipeline índice | 🟠 Taxonomia coarse + índice |

---

## 7. Leitura para o cenário de crescimento declarado

- **Local-first + Ollama + RAM apertada (esta máquina):** pesa **contra** depender de
  embeddings desde já (é +1 modelo na memória que já estoura). Favorece começar **sem**
  infra de vetor.
- **Multi-projeto (Zavix, VitrinePro, …):** mapeia direto para **Domínio** → favorece A/C.
- **Multi-usuário futuro:** o corte determinístico de **tenant/domínio** é praticamente
  obrigatório para isolamento → favorece A/C (em B é filtro extra).
- **300 Skills:** dentro de um domínio podem caber ~20–30 skills; acima disso, a seleção
  por LLM sobre lista perde qualidade → **dentro do domínio, embeddings ajudam** (C).
- **Modelos remotos no futuro:** um modelo grande remoto aguenta listas maiores, mas
  **não se pode depender dele** (local-first). O design tem que funcionar **local** → favorece
  contexto pequeno por passo (A/C).
- **Dezenas de Tools / múltiplos canais:** canais convergem todos para `IncomingMessage` →
  **não muda o roteamento**. Tools entram no mesmo índice/recuperação das skills.

---

## 8. Recomendação técnica

**Adotar o Híbrido (C) — porém construído em fases, começando pela hierarquia.**

Justificativa: o cenário declarado (local-first, multi-projeto, multi-usuário futuro,
100/300 unidades, RAM apertada) é **exatamente** onde o híbrido brilha: o **corte de
domínio** dá isolamento, explicabilidade, escopo de memória e custo baixo **sem infra
nova**; os **embeddings dentro do domínio** dão semântica e escala **quando** um domínio
crescer além do que um modelo local decide bem.

### Caminho recomendado (sem implementar agora)
- **Fase 1 — Hierarquia de Domínio (resolve o C1 com runway longo, custo baixo, zero infra nova):**
  - adicionar `domain` ao manifest de agentes (skills já têm `category`);
  - o registry **indexa por domínio**;
  - o `IntentRouter` vira **2 etapas**: (1) classifica o domínio (lista curta de ~15);
    (2) escolhe skill/agente **dentro** do domínio (lista curta);
  - o domínio **escopa a memória** (sinergia com o `MemoryFacade`);
  - novos eventos de roteamento no Event Bus (aditivo).
  - Isso sozinho tira o sistema do "todos como tool" e sustenta **dezenas** de agentes/skills.
- **Fase 2 — Embeddings dentro do domínio (quando um domínio passar de ~20–30 unidades, ou exigir match semântico):**
  - port `Embedder` (local pequeno ou remoto) + índice vetorial (pode reusar a L4);
  - a 2ª etapa vira **recuperação top-K filtrada por domínio** + seleção final;
  - mantém **degradação graciosa**: sem embedding, cai para o modo hierárquico da Fase 1.

### Princípios de design a fixar (independente da fase)
1. O **corte determinístico** (domínio/tenant) é **sempre** o primeiro passo — segurança/isolamento.
2. Embeddings são **opcionais e plugáveis** (atrás de um port) — o sistema funciona sem eles.
3. O roteamento mora **dentro do `IntentRouter`** (atrás do seam atual) — **Orquestrador,
   Event Bus, Memory e Workflow não mudam de interface**.
4. Manifests declaram `domain` (e já têm `category`/`agents`/`tools`) — a unidade de
   roteamento é dado, não código (OCP).

### O que NÃO recomendo
- **B puro agora:** adiciona modelo de embedding (RAM) e índice antes de ser necessário,
  com isolamento multi-usuário mais frágil.
- **A puro como destino final:** resolve a curto/médio prazo, mas a 300 skills a taxonomia
  fina vira gargalo e a falta de semântica incomoda — por isso convergir para o híbrido.

### Riscos a observar
- **Taxonomia de domínios** mal desenhada vira gargalo → manter **coarse e estável** (≈ projetos + áreas pessoais).
- **Pedidos cross-domínio** → permitir o domínio devolver **mais de um** e o Orquestrador compor (já suporta múltiplos agentes).
- **Embedding local x RAM** → só na Fase 2, com modelo pequeno; ou usar remoto quando houver.

---

> **Próximo passo:** analisar este documento juntos e, só então, decidir o escopo da
> Fase 1 (hierarquia de domínio) antes de escrever qualquer código.
