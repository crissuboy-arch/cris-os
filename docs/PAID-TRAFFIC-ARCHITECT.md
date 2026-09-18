# Paid Traffic Architect (Fase 5)

Especialista isolado que transforma um produto/oferta **já aprovado** no
Project Brain num **plano de tráfego pago estruturado** (Meta Ads, Google
Search/Display, YouTube Ads, TikTok Ads) — sem executar nenhuma campanha.
Implementado em `core/paid_traffic_architect.py` +
`tools/paid_traffic_tools.py` + `agents/paid_traffic_architect.py`.

## Princípio de Skill (isolamento)

`core/paid_traffic_architect.py` não conhece Telegram nem o orchestrator —
recebe um `ProjectBrain` (e opcionalmente um LLM e um orçamento informado) e
devolve um `TrafficPlan`. A mesma função pode ser chamada por qualquer canal
futuro (API, automação, interface web) sem mudar uma linha do módulo.

## Fluxo

```
Telegram → AgentOrchestrator (reconhece intenção, recupera projeto em foco)
  → agents/paid_traffic_architect.py (SpecialistAgent)
  → tools/paid_traffic_tools.py:gerenciar_trafego(entrada, session)
       a. resolve o MESMO projeto em foco (UserFocusStore -- sem estado novo)
       b. core/paid_traffic_architect.py:avaliar_prontidao() -- verifica
          produto aprovado, público, país, posicionamento, evidência
          (fonte CANONICA: `ProjectBrain.coletar_evidencias_pesquisa()`,
          a mesma que o Artifact Manifest usa)
       c. core/paid_traffic_architect.py:criar_plano_trafego() -- via
          Tool Registry (`PAID_TRAFFIC_ARCHITECT`), OpenRouter tier
          INTELIGENTE (escolha de canal exige julgamento, mesmo tier do
          Product Architect)
       d. persiste no MESMO ProjectBrain (`brain.traffic_plan`)
  → resposta formatada -> Telegram (dividida automaticamente se > 4000 caracteres)
```

O Orchestrator **não contém inteligência de tráfego** — só reconhece a
intenção (palavras-chave/frases determinísticas) e delega inteiramente pro
agente. Toda a lógica de canais/orçamento/criativos/evidência vive isolada
em `core/paid_traffic_architect.py`.

## `TrafficPlan` (persistido no Project Brain)

Novo campo `ProjectBrain.traffic_plan: TrafficPlan | None` — mesmo
`project_id`, mesma infraestrutura SQLite (`ProjectBrainStore`/
`data/cris_os.db`) já usada por `blueprint`/`business_plan`/
`production_plan`. Nenhum banco/JSON paralelo, nenhuma segunda fonte de
verdade.

Campos principais: `version`, `status`, `objective`, `market`/`country`
(nunca `None` silencioso — ver Market Context Guard abaixo),
`audience_summary`, `channels[]` (cada um com `role`, `rationale`,
`campaign_objective`, `campaign_structure`, `targeting_strategy`,
`keyword_strategy`, `creative_requirements`, `conversion_event`,
`test_hypothesis`, `evidence_used`, `assumptions`, `risks`), `angles`,
`hooks`, `creative_matrix[]` (cada item sempre `asset_required: true`),
`testing_plan`, `measurement_plan` (só nomes de métrica, nunca valores),
`stop_conditions`, `scale_conditions`, `budget_scenarios[]` +
`budget_status` + `budget_informado_pelo_usuario`, `social_proof_status`,
`evidence_summary`, `assumptions`, `unknowns`, `risks`,
`missing_information`, `approval_required_actions`.

### Estados

```
DRAFT → NEEDS_INFORMATION | READY_FOR_APPROVAL → APPROVED
                                                → REJECTED
```

- **NEEDS_INFORMATION**: faltou algo essencial (produto não aprovado,
  público/país/posicionamento/evidência ausente, ou nenhum canal pôde ser
  classificado `PRIMARY_TEST` com confiança) — lista objetiva das lacunas,
  nunca fabrica um plano como se o projeto estivesse pronto. Um
  `NEEDS_INFORMATION` **nunca fica congelado**: o comando de criar sempre
  reavalia (barato, sem LLM) em vez de reexibir esse resultado como
  definitivo.
- **READY_FOR_APPROVAL**: evidência suficiente, plano gerado de verdade.
- **APPROVED**: `TrafficPlan.esta_aprovado()` só retorna `True` aqui — texto
  de consulta ("está bom?", "qual o plano?", "mostre o plano", "o que
  acha?", "pronto?") **nunca** aprova. Só um conjunto fechado de
  frases/palavras de aprovação explícita conta.

## Priorização operacional — exatamente um `PRIMARY_TEST`

Canais são classificados como `PRIMARY_TEST` (o único canal prioritário
para começar o teste), `SECONDARY_TEST` (candidato sólido, não o primeiro),
`LATER` (candidato sem evidência suficiente ainda) ou
`NOT_RECOMMENDED_NOW`. `core/paid_traffic_architect.py:_impor_um_unico_primary_test`
nunca confia no LLM sozinho: se ele marcar mais de um canal como
`PRIMARY_TEST`, só o primeiro fica, os demais são rebaixados
deterministicamente. Se **nenhum** canal for classificado `PRIMARY_TEST`
(evidência insuficiente pra escolher um principal), o plano inteiro volta
para `NEEDS_INFORMATION` — preservando a análise já feita, mas nunca
apresentando como pronto pra aprovar.

## Market Context Guard

**Correção pós-teste real**: o plano chegou a mostrar "Mercado: ?" porque só
olhava `blueprint.market` (raramente preenchido — o Opportunity Analyst
normalmente só seta `mercado.niche`/`mercado.target_country`). Agora
`_resolver_mercado`/`_resolver_pais` tentam, nesta ordem: `blueprint.market`
→ `mercado.market` → `blueprint.niche` → `mercado.niche` (e, pro país,
`blueprint.country` → `mercado.target_country` → `origem.source_country`).
Só quando **nenhuma** dessas fontes tem dado, o campo vira o literal
`"REQUIRES_MARKET_DATA"` — nunca `None`/`"?"` silencioso.

## Evidence Guard (reaproveitado da Fase 4, estendido)

`core/evidence_guard.py` ganhou uma **5ª categoria** específica de tráfego
pago (métricas/resultados inventados: CTR/CPC/CPM/CPA/ROAS/CVR esperados,
"vai converter", "alta demanda", "produto comprovado", "oferta vencedora")
e novos padrões genéricos de "funcionalidade não construída" ("acesso a
fornecedor(es)", "parceria com fornecedor(es)", "rede de fornecedores") —
nenhum específico de nicho, válidos pra qualquer projeto.

Aplicado em **todos** os campos textuais livres do `TrafficPlan`
(`rationale`, `campaign_objective`, `targeting_strategy`, `test_hypothesis`,
`evidence_used`, `assumptions`, `risks`, `unknowns`,
`approval_required_actions`, `angles`, `hooks`, itens do `creative_matrix`)
— fatos inventados são removidos; ideias de funcionalidade ainda não
construída são **reescritas** como `[HIPÓTESE DE FUNCIONALIDADE: ... —
ainda não aprovada/construída]`, preservando a ideia em vez de apagá-la.

## Social Proof Guard

`TrafficPlan.social_proof_status` é sempre `"NOT_AVAILABLE"` nesta fase — o
Project Brain não tem (ainda) nenhum campo de prova social real
(depoimento/avaliação/número de clientes verificado). Depoimentos/
avaliações/números de cliente inventados já eram removidos pela categoria
de "fato inventado" do Evidence Guard desde a Fase 4.

## Asset Guard

`creative_matrix[].asset_required` é **forçado `True`** na validação
(`core/paid_traffic_architect.py:_validar_creative_matrix_item`),
independente do que o LLM mandar — nenhum ativo (imagem/vídeo/testimonial)
pode ser declarado como já existente. `core/paid_traffic_architect.py` nunca
gera o asset em si, só especifica o que precisa ser produzido.

## Budget Guard

Orçamento informado pelo usuário (extraído deterministicamente da própria
mensagem por `tools/paid_traffic_tools.py:_extrair_orcamento_informado`) é
preservado **sem alteração** em `budget_informado_pelo_usuario`, e
`budget_status = "PROVIDED"`. Sem orçamento informado,
`budget_status = "REQUIRES_USER_INPUT"` e o plano pode sugerir cenários
ilustrativos LOW/STANDARD/EXPANDED, cada um marcado explicitamente
`"PLANNING_ASSUMPTION"` — nunca uma afirmação de "orçamento ideal" ou
garantia de resultado.

## Google Search — Keyword Data Guard

Sem dado real de volume de busca/CPC/competição, `keyword_strategy` fica
marcado `"REQUIRES_KEYWORD_DATA"` — nunca inventa métrica de keyword.

## Metrics Guard

Nenhum campo do `TrafficPlan` permite CTR/CPC/CPM/CPA/ROAS/CVR/vendas/
receita/conversões/demanda como fato (garantia de schema, testada
explicitamente). `measurement_plan` é sempre uma lista de **nomes** de
métrica a observar (ex.: "CTR", "CPC") — nunca um valor esperado.

## Tool Registry

`PAID_TRAFFIC_ARCHITECT` é registrada em `core/tool_registry.py` com
executor **real** (`criar_plano_trafego`) — diferente de `BUSINESS_BUILDER`/
`PRODUCT_FACTORY` (agentes completos, deliberadamente fora do registry),
esta capability é genuinamente invocada via `registry.executar(...)` por
`tools/paid_traffic_tools.py`. Ver [TOOL-REGISTRY.md](TOOL-REGISTRY.md).

## Cost-first / AI Router

Segue a mesma disciplina da Fase 2.5/3/4: DETERMINÍSTICO primeiro (leitura
de projeto em foco, GET/STATUS do plano já persistido, manifesto) → CACHE
(plano já gerado é reexibido sem custo, exceto quando está em
`NEEDS_INFORMATION`, que é sempre reavaliado de graça) → tier INTELIGENTE
somente quando a criação/revisão do plano realmente precisa de raciocínio.
`GET_TRAFFIC_PLAN`, `GET_TRAFFIC_STATUS` e a leitura do manifesto (10-Trafego-Pago/)
fazem **zero chamadas de LLM e zero escrita no Project Brain** (testado
explicitamente).

## Aprovação humana (gate absoluto)

- `CREATE_TRAFFIC_PLAN` sempre termina em `NEEDS_INFORMATION` ou
  `READY_FOR_APPROVAL` — nunca `APPROVED` automaticamente.
- Só um conjunto fechado de palavras/frases conta como aprovação (mesmo
  vocabulário do Product Architect: "aprovado"/"aprovo"/"autorizado"/"pode
  criar"/"pode seguir"...). Frases de consulta nunca aprovam.
- Mesmo após `APPROVED`, **nenhuma ação externa existe nesta fase** — não
  há login em Meta/Google/TikTok Ads, não há criação/publicação de
  campanha, não há gasto real, não há upload de criativo, pixel, CAPI ou
  qualquer API de Ads. Isso pertence a uma fase futura, com aprovação
  humana explícita separada.

## Integração com o Artifact Manifest

A pasta lógica `10-Trafego-Pago/` (ver [ARTIFACT-MANIFEST.md](ARTIFACT-MANIFEST.md))
reflete `brain.traffic_plan.status` em tempo real: `EMPTY / NOT_STARTED`
antes de qualquer plano, `NEEDS_INFORMATION`/`READY_FOR_APPROVAL`/`APPROVED`
depois — sempre **derivado** do Project Brain, nunca uma segunda fonte de
verdade. `MASTER-PROJECT` ganhou o campo `status_trafego_pago`.

## Roteamento pelo Telegram

`agents/orchestrator.py` reconhece deterministicamente "tráfego"/"trafego",
frases como "estratégia de anúncios", "como vamos anunciar", "plano de
tráfego", nomes de plataforma ("meta ads", "google ads", "tiktok ads") e uma
checagem de co-ocorrência "plano" + plataforma (cobre "quero o plano de
Meta, Google e TikTok desse projeto" sem depender de frase fixa) —
checado **antes** do Product Architect (evita a colisão com a palavra
"produto") e do ScalaFlow Intel (evita a colisão com "anúncios", que está
em `_SCALAFLOW_KEYWORDS`). "meta" sozinha (sentido de "objetivo/goal")
**não** dispara o agente — só a frase completa "meta ads".

## Testado (real, pelo Telegram)

- "Cris, crie o plano de tráfego deste projeto." → roteamento determinístico
  correto, `TrafficPlan` gerado, `status: READY_FOR_APPROVAL`, mercado
  ausente marcado `REQUIRES_MARKET_DATA` quando aplicável, canais tratados
  como hipóteses de teste (nunca fato), nenhuma métrica inventada, nenhuma
  campanha publicada, nenhum gasto.
- Projeto real `proj_cb094b4ef6a4` (velas artesanais).

## Limitações conhecidas

- O Evidence Guard é baseado em padrões conhecidos (regex/categorias), não
  em compreensão semântica plena — uma alegação inventada com fraseado
  totalmente novo, fora dos padrões cobertos, pode não ser detectada.
- Extração determinística de orçamento (`_extrair_orcamento_informado`)
  cobre só padrões simples de moeda+valor (ex.: "R$50/dia"); frases de
  orçamento mais elaboradas podem não ser reconhecidas.
- `keyword_strategy` de Google Search sempre cai em
  `"REQUIRES_KEYWORD_DATA"` por não haver fonte real de dados de busca
  integrada ainda.
- Um `TrafficPlan` gerado antes desta fase de correção final pode ter
  `role` de canal no vocabulário antigo (`PRIORITY_TEST`/`CANDIDATE`) até
  ser recriado/revisado — puramente cosmético na exibição, nunca alterado
  diretamente no banco.
- Resposta do Telegram pode ficar extensa para planos com vários canais —
  já protegida pelo splitter (`channels/telegram/bot.py`), mas sem
  resumo/paginação (melhoria de UX registrada para fase futura, fora de
  escopo desta correção).
- Nenhuma execução real de tráfego (login, campanha, gasto, pixel/CAPI,
  APIs de Ads) existe nesta fase — deliberadamente fora de escopo.
