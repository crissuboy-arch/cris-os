# CRIS OS — Arquitetura (Fase 2 + Fase 2.5 + Fase 3 + Fase 4 + Fase 5)

> Visão de arquitetura da camada inteligente construída na Fase 2 (Project
> Brain + Opportunity Analyst + Decision Engine), do provedor de IA remota
> da Fase 2.5 (OpenRouter), do Product Architect + Product Factory
> (fundação) da Fase 3, do Business Builder + Product Factory completada
> (plano de produção por tipo + Artifact Manifest) da Fase 4, e do Paid
> Traffic Architect (plano de tráfego pago estruturado, nunca executado) da
> Fase 5, em cima do Marco 1
> ([docs/MARCO-01-TELEGRAM-SCALAFLOW.md](MARCO-01-TELEGRAM-SCALAFLOW.md)).
> Docs específicos da Fase 3: [PRODUCT-ARCHITECT.md](PRODUCT-ARCHITECT.md),
> [PRODUCT-BLUEPRINT.md](PRODUCT-BLUEPRINT.md),
> [PRODUCT-FACTORY.md](PRODUCT-FACTORY.md),
> [TOOL-REGISTRY.md](TOOL-REGISTRY.md). Docs específicos da Fase 4:
> [BUSINESS-BUILDER.md](BUSINESS-BUILDER.md),
> [PRODUCTION-PLAN.md](PRODUCTION-PLAN.md),
> [ARTIFACT-MANIFEST.md](ARTIFACT-MANIFEST.md). Doc específico da Fase 5:
> [PAID-TRAFFIC-ARCHITECT.md](PAID-TRAFFIC-ARCHITECT.md).

## Princípio central

```
Telegram      = interface   (uma das várias possíveis)
CRIS OS       = orquestrador
ScalaFlow     = inteligência de mercado (dado real, via Supabase)
Supabase      = fonte de verdade (do ScalaFlow — NÃO do CRIS OS)
Skills/agentes = especialistas
```

A lógica de negócio **não pode ficar presa ao Telegram**. Um agente
especialista (`SpecialistAgent`, em `agents/base_specialist.py`) só recebe
texto e devolve texto — nunca importa nada de `channels/telegram`. Isso já
era verdade desde o Marco 1 e continua valendo: o mesmo agente que responde
no Telegram hoje pode ser chamado amanhã por uma API interna, por uma
automação, ou por outro canal, sem mudar uma linha de `agents/` ou `tools/`.

## Onde cada coisa mora

| Camada | Local | Fase |
|---|---|---|
| Canal (Telegram) | `channels/telegram/` | Marco 1 |
| Autorização | `core/gateway.py` | Marco 1 |
| Composition root | `core/runtime.py` | Marco 1 |
| Roteamento (LLM + determinístico) | `agents/orchestrator.py` | Marco 1 (ScalaFlow) + Fase 2 (Opportunity) |
| Agente ScalaFlow Intel (lista/filtra ofertas) | `agents/scalaflow_intel.py` + `tools/scalaflow_tools.py` | Marco 1 |
| Agente Opportunity Analyst (investiga 1 oferta) | `agents/opportunity_analyst.py` + `tools/opportunity_tools.py` | Fase 2 |
| Decision Engine (decide o caminho) | `core/decision_engine.py` | Fase 2 |
| Project Brain (memória estruturada) | `memory/project_brain.py` | Fase 2 |
| Persistência local | `storage/sqlite_memory.py` (`data/cris_os.db`) | já existia — reaproveitado |
| Provedor de IA remota (OpenRouter) | `llm/openrouter.py` | Fase 2.5 |
| Wiring do fallback (Ollama → OpenRouter) | `core/runtime.py:_configurar_openrouter` | Fase 2.5 |
| Agente Product Architect (propõe formato de produto) | `agents/product_architect.py` + `tools/product_architect_tools.py` | Fase 3 |
| Lógica do Product Architect (LLM + fallback) | `core/product_architect.py` | Fase 3 |
| Product Factory (fundação — gate + 1º artefato) | `core/product_factory.py` | Fase 3 |
| Tool Registry (capabilities de produção) | `core/tool_registry.py` | Fase 3 |
| Foco por usuário/chat (persistente) | `memory/project_brain.py:UserFocusStore` | Fase 3 |
| Divisão de mensagens >4000 chars no Telegram | `channels/telegram/bot.py:_dividir_mensagem` | Fase 3 |
| Agente Business Builder (produto aprovado → negócio) | `agents/business_builder.py` + `tools/business_builder_tools.py` | Fase 4 |
| Lógica do Business Builder (LLM tier econômico + fallback) | `core/business_builder.py` | Fase 4 |
| Agente Product Factory (expõe plano de produção sob demanda) | `agents/product_factory.py` + `tools/product_factory_tools.py` | Fase 4 |
| Plano de produção específico por tipo + persistência | `core/product_factory.py` (`_passos_para_tipo`, `persistir_plano`) | Fase 4 |
| Artifact Manifest (estrutura lógica, derivada, sem Drive) | `core/artifact_manifest.py` | Fase 4 |
| Agente Paid Traffic Architect (produto aprovado → plano de tráfego) | `agents/paid_traffic_architect.py` + `tools/paid_traffic_tools.py` | Fase 5 |
| Lógica do Paid Traffic Architect (LLM tier inteligente + fallback) | `core/paid_traffic_architect.py` | Fase 5 |
| Evidence Guard (sanitiza claims herdadas/inventadas) | `core/evidence_guard.py` | Fase 4, estendido na Fase 5 |

## Fluxo completo (Fase 2)

```
Telegram (ou futuro canal/API)
  → core/gateway.py (autorização)
  → agents/orchestrator.py._escolher_agente
       1. agente fixo (/use)
       2. followup
       3. INTERCEPTAÇÃO: opportunity_analyst (palavra-chave, sem LLM)
       4. INTERCEPTAÇÃO: scalaflow_intel (palavra-chave, sem LLM)
       5. LLM (Ollama) + keyword fallback (qualquer outro agente)
  → agents/opportunity_analyst.py (SpecialistAgent)
  → tools/opportunity_tools.py:investigar_oportunidade()
       a. resolve a oferta (URL/ID explícito, ou "salvei"/"favorito"/
          "escalada"/melhor score — reaproveita tools/scalaflow_tools.py)
       b. cruza sinais reais em tiktok_minerados / instagram_minerados /
          youtube_minerados / google_trends_minerados (Supabase do
          ScalaFlow, SOMENTE LEITURA, correlação por palavra-chave)
       c. core/decision_engine.py:decidir() -> caminho + motivo
       d. memory/project_brain.py -> salva tudo em `data/cris_os.db` (local)
  → resposta resumida formatada -> volta pelo mesmo caminho -> Telegram
```

A etapa 5 (LLM) é a única que pode custar dinheiro — e só é alcançada
quando **nenhuma** interceptação determinística (passos 3 e 4) bateu. Ver
"Roteamento por custo" abaixo para o que acontece dentro dela desde a
Fase 2.5.

## Fluxo completo (Fase 3 — Product Architect)

```
... (Opportunity Analyst + Decision Engine, como acima) ...
  → agents/product_architect.py (SpecialistAgent)
  → tools/product_architect_tools.py:gerenciar_produto(entrada, session)
       a. resolve o projeto (foco persistido POR SESSAO -- UserFocusStore --
          ou dispara investigacao nova; um link/ID novo na mensagem sempre
          tem prioridade sobre um foco antigo)
       b. core/product_architect.py:propor_produto() -- OpenRouter tier
          INTELIGENTE gera 3-5 candidatos (hipoteses); so promove um a
          `recommended_product_type` se o proprio LLM sinalizar confianca
          real (`ready_for_approval`)
       c. persiste no MESMO ProjectBrain (`blueprint`), atualiza o foco
  → resposta (hipoteses OU recomendacao, nunca aprovada automaticamente)
  → aprovacao humana explicita ("Aprovado"/"Aprovo o formato X")
  → core/product_factory.py:criar_plano_inicial() -- SO com blueprint
    APPROVED -- monta plano + gera 1 artefato textual real (COPY_GENERATOR)
  → resposta -> Telegram (dividida automaticamente se > 4000 caracteres)
```

**Persistência do contexto** (correção pós-teste real): "qual oportunidade
está em foco" não é mais uma variável Python — é persistido via
`UserFocusStore` na mesma tabela do Project Brain, chaveado por `session`
(`IncomingMessage.session`, ex. `"telegram:6460872429"`). Sobrevive a
restart do processo **e** a reboot do computador (testado com ambos), e é
isolado por sessão (nunca um único "foco atual" global compartilhado). Ver
detalhes em [PRODUCT-ARCHITECT.md](PRODUCT-ARCHITECT.md#persistência-por-usuáriochat).

## Fluxo completo (Fase 4 — Business Builder + Product Factory)

```
... (Product Architect + aprovação humana do PRODUTO, como acima) ...
  → agents/business_builder.py (SpecialistAgent)
  → tools/business_builder_tools.py:gerenciar_negocio(entrada, session)
       a. resolve o MESMO projeto em foco (reaproveita get_foco_atual --
          nenhum "projeto atual" novo)
       b. GATE: bloqueia se blueprint.decision_status != "APPROVED"
          ("Esse produto ainda não foi aprovado [...]")
       c. core/business_builder.py:construir_plano_negocio() -- OpenRouter
          tier ECONOMICO (nao o INTELIGENTE do Product Architect -- tarefa
          mais simples) gera o BusinessPlan inteiro numa unica chamada
       d. persiste no MESMO ProjectBrain (`business_plan`)
  → resposta (plano de negocio, com preco sempre marcado como hipotese
    quando sem benchmark real)

  → agents/product_factory.py (SpecialistAgent) -- sob demanda, ou
    automaticamente logo apos a aprovacao do PRODUTO (mesmo helper)
  → tools/product_factory_tools.py:gerenciar_producao(entrada, session)
       a. mesmo GATE (blueprint APPROVED)
       b. core/product_factory.py:criar_plano_inicial() -- passos
          ESPECIFICOS por `product_type` (mini-app/ebook/afiliado/comercio
          tem listas diferentes -- nunca presume ebook)
       c. persistir_plano() -- guarda em `ProjectBrain.production_plan`
       d. core/artifact_manifest.py:gerar_manifest() -- guarda em
          `ProjectBrain.artifact_manifest` (derivado, nao e 2a fonte de verdade)
  → resposta (plano de produção + artefato textual real, se ainda não gerado)
  → NENHUMA publicação/compra/gasto/deploy acontece aqui -- fora de escopo
    ate uma fase futura com aprovação humana explicita separada
```

## Fluxo completo (Fase 5 — Paid Traffic Architect)

```
... (Product Architect + aprovação humana do PRODUTO, como acima) ...
  → agents/paid_traffic_architect.py (SpecialistAgent)
  → tools/paid_traffic_tools.py:gerenciar_trafego(entrada, session)
       a. resolve o MESMO projeto em foco (nenhum "projeto atual" novo)
       b. core/paid_traffic_architect.py:avaliar_prontidao() -- gate: produto
          aprovado, publico/pais/posicionamento definidos, evidencia real
          registrada (fonte CANONICA: ProjectBrain.coletar_evidencias_pesquisa(),
          a MESMA que o Artifact Manifest usa -- corrige bug real onde os
          dois discordavam sobre o mesmo projeto)
       c. sem lacuna -> core/paid_traffic_architect.py:criar_plano_trafego()
          via Tool Registry (`registry.executar(PAID_TRAFFIC_ARCHITECT, ...)`)
          -- OpenRouter tier INTELIGENTE gera o TrafficPlan inteiro (canais,
          angulos, criativos-a-produzir, teste, medicao, orcamento)
       d. Evidence Guard sanitiza todo campo textual livre do plano (nunca
          herda claim do concorrente como fato do produto novo)
       e. exatamente 1 canal PRIMARY_TEST e imposto deterministicamente
          (_impor_um_unico_primary_test) -- zero canais qualificados ->
          plano volta para NEEDS_INFORMATION em vez de fingir prontidao
       f. persiste no MESMO ProjectBrain (`traffic_plan`)
  → resposta (plano com canais tratados como HIPOTESE de teste, nunca fato;
    nenhuma metrica/orcamento/resultado inventado)
  → aprovacao humana explicita separada ("Aprovado" -> status APPROVED)
  → NENHUMA acao externa acontece aqui -- sem login/API de Ads, sem
    campanha criada/publicada, sem gasto real, mesmo depois de aprovado
```

**Cost-first no Paid Traffic Architect**: leitura/status/manifesto (10-Trafego-Pago/)
tem zero chamadas de LLM e zero escrita no Project Brain -- só a
criação/revisão real do plano usa o tier INTELIGENTE (mesma classe de
problema do Product Architect: escolher entre canais exige julgamento, não
é estruturação simples). Um resultado `NEEDS_INFORMATION` nunca é tratado
como cache final -- sempre reavaliado de graça na proxima tentativa.

**Cost-first no Business Builder**: diferente do Product Architect (tier
INTELIGENTE, precisa escolher entre 22+ formatos), o Business Builder usa o
tier ECONÔMICO -- estruturar uma oferta em cima de um formato **já
aprovado** é uma tarefa mais simples. Ver
[BUSINESS-BUILDER.md](BUSINESS-BUILDER.md#por-que-usa-o-tier-econômico-não-o-inteligente).

**Sem duplicação da Product Factory**: `core/product_factory.py` continua
sendo a única lógica de decisão de passos/execução desde a Fase 3. A Fase 4
só trocou a lista fixa de passos por uma lista específica por tipo
(`_passos_para_tipo`) e adicionou persistência real (antes só existia na
resposta do Telegram) -- ver
[PRODUCTION-PLAN.md](PRODUCTION-PLAN.md#o-que-mudou-desde-a-fase-3).

## Roteamento por custo (Fase 2.5)

Quatro camadas, da mais barata para a mais cara:

| Camada | Quando é usada | Custo | Onde |
|---|---|---|---|
| **DETERMINÍSTICO** | Consultas simples ScalaFlow/Supabase (`scalaflow_intel`, `opportunity_analyst`) | Zero — nenhuma chamada de LLM | Interceptação por palavra-chave em `agents/orchestrator.py`, **antes** de qualquer LLM |
| **ECONÔMICO** | Classificação, resumo, extração, tarefas simples | Baixo (`openai/gpt-4o-mini`, ~$0,15 / $0,60 por 1M tokens) | `llm/openrouter.py` (tier `"economico"`) — implementado, ainda não plugado em nenhum papel específico (ver "Limitações") |
| **INTELIGENTE** | Conversa geral, Opportunity Analyst, Decision Engine e raciocínio mais complexo | Moderado (`openai/gpt-5-mini`, ~$0,25 / $2,00 por 1M tokens) | Usado hoje pelo `AgentOrchestrator` como alternativa ao Ollama quando ele está offline (`core/runtime.py:_configurar_openrouter`) |
| **PREMIUM** | Só quando uma tarefa realmente justificar, com autorização/limites apropriados | Alto (`anthropic/claude-opus-4.5`, ~$5,00 / $25,00 por 1M tokens) | Implementado em `llm/openrouter.py`, **não é usado automaticamente em lugar nenhum ainda** |

Os IDs de modelo foram conferidos no catálogo público real do OpenRouter
(`GET https://openrouter.ai/api/v1/models`, sem autenticação) em 2026-09-17
— nunca fixados de memória. Trocar de modelo é só mudar
`OPENROUTER_MODEL_ECONOMICO`/`_INTELIGENTE`/`_PREMIUM` no `.env`, sem tocar
em código.

**Como o fallback Ollama → OpenRouter funciona** (`core/runtime.py`, dentro
do bloco `DEFAULT_AGENT == "auto"`):

```
Ollama respondendo?
  SIM  -> usa Ollama (comportamento local-first de sempre, sem custo)
  NAO  -> OPENROUTER_API_KEY configurada e o healthcheck passa?
            SIM -> usa OpenRouter (tier INTELIGENTE) para os agentes
            NAO -> mantem Ollama mesmo offline (comandos deterministicos
                   continuam funcionando; geracao livre fica sem resposta
                   real -- comportamento identico ao de antes da Fase 2.5)
```

Nunca deixa o processo cair: qualquer falha ao configurar o OpenRouter
(chave ausente/placeholder, API fora do ar, timeout no healthcheck) é
capturada em `_configurar_openrouter` e vira só um `WARNING` no log.

## Controle de erro e custo (Fase 2.5)

`llm/openrouter.py` nunca deixa uma exceção "crua" escapar — toda falha vira
`OpenRouterError` com uma `categoria` classificada:

| Categoria | Causa | O que quem chama vê |
|---|---|---|
| `timeout` | Modelo não respondeu a tempo | Mensagem clara, sem detalhe técnico exposto ao usuário |
| `conexao` | Falha de rede/DNS | Idem |
| `rate_limit` | HTTP 429 (muitas requisições) | Idem |
| `saldo_insuficiente` | HTTP 402 (sem crédito na conta) | Idem |
| `modelo_indisponivel` | HTTP 404 (modelo não existe/foi descontinuado) | Idem |
| `erro_api` | Qualquer outro `4xx`/`5xx` | Idem |

Essas exceções sobem para `AgentOrchestrator._rotear` e
`SpecialistAgent._gerar_com_llm`, que **já** capturavam `Exception` de forma
genérica desde o Marco 1 — nenhuma mudança foi necessária ali. Uma falha do
OpenRouter no meio de uma conversa vira, no pior caso, uma mensagem de erro
amigável ou uma resposta via keyword fallback — nunca derruba o processo.

**Log de uso seguro**: cada chamada registra `tier`, `modelo`, tipo de
tarefa, `tokens_in`/`tokens_out` (quando a API informa), custo estimado
(calculado localmente a partir de uma tabela de preços conhecidos — não é a
fatura oficial), duração e sucesso/erro. **Nunca** loga o conteúdo do
prompt/resposta nem a API key (testado em
`tests/test_openrouter.py::test_log_de_uso_nao_vaza_api_key_nem_prompt`).

## Por que "COST-FIRST"

Ordem de operações em `tools/opportunity_tools.py`:

```
dados (Supabase, já existentes) → filtro determinístico (palavra-chave) →
score/decisão (regras Python puras) → resposta
```

O fluxo Opportunity Analyst / Decision Engine continua **sem nenhuma
chamada de LLM** — isso não mudou na Fase 2.5. Quando termos de busca não
existem (oferta sem `keyword`/nicho/anunciante úteis), o código **nem faz a
chamada de rede** — ver `_extrair_termos_busca` + `_buscar_sinal_fonte` em
`tools/opportunity_tools.py`.

A arquitetura de custo que a Fase 2 deixou como visão futura
(`LOCAL → CHEAP → PREMIUM`) agora tem 3 dos 4 degraus implementados
(DETERMINÍSTICO, ECONÔMICO, INTELIGENTE, PREMIUM — ver "Roteamento por
custo" acima). O que falta é usar o degrau ECONÔMICO em algum papel
concreto (ver "Limitações").

## Segurança

- Nenhuma ação que envolva dinheiro, campanhas, publicação, e-mails externos,
  contas externas ou compras é executada nesta fase. Toda decisão fica em
  `PENDING_APPROVAL` (`ProjectBrain.decisao.decision_status`).
- Autorização do Telegram (`TELEGRAM_ALLOWED_USER_ID`) inalterada desde o
  Marco 1 — ver `core/gateway.py`.
- Nenhum segredo novo foi introduzido no fluxo do ScalaFlow (Opportunity
  Analyst usa as mesmas `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` já
  configuradas). A Fase 2.5 adiciona `OPENROUTER_API_KEY`, com a mesma
  disciplina: nunca no código, nunca commitada, nunca logada — só no `.env`
  local (fora do Git) e lida via `config/settings.py`.
- Todo acesso ao Supabase do ScalaFlow nesta fase é **somente leitura**
  (`SELECT` via REST) — nenhuma tabela nova, nenhuma escrita.

## Limitações desta fase

Ver a seção "Limitações" em cada doc específico
([PROJECT-BRAIN.md](PROJECT-BRAIN.md#limitações),
[OPPORTUNITY-ANALYST.md](OPPORTUNITY-ANALYST.md#limitações),
[DECISION-ENGINE.md](DECISION-ENGINE.md#limitações)). Resumo geral:

- Sem Ollama nesta máquina → sem análise qualitativa de copy no Opportunity
  Analyst (público, problema, promessa, mecanismo, ângulos, padrões
  criativos) — isso continua **não** implementado mesmo com o OpenRouter
  disponível; o fluxo Opportunity Analyst / Decision Engine deliberadamente
  não chama nenhum LLM (ver "Por que COST-FIRST").
- Correlação cross-plataforma é por palavra-chave, não por relação real no
  banco (as tabelas `*_minerados` do ScalaFlow não têm FK para
  `collected_ads`).
- `niche` em `collected_ads` é quase sempre `"Geral"` (274 de 286 registros
  reais na amostra usada) — não é um bom termo de busca; o código já
  prioriza `keyword` e `advertiser` por isso.
- **Classificador de roteamento não usa o tier ECONÔMICO ainda**: o
  `AgentOrchestrator` usa um único LLM tanto para classificar qual agente
  deve responder (`_rotear`) quanto para gerar a resposta do agente geral
  (`_gerar_com_llm`) — os dois papéis não são separados como no
  `Orchestrator` clássico (`llm.for_role("routing")` vs.
  `llm.for_role("generation")`). Na prática, quando o OpenRouter está ativo,
  a chamada de classificação usa o tier INTELIGENTE (mais caro) em vez do
  ECONÔMICO, e o modelo às vezes devolve uma resposta longa em vez de só o
  nome do agente (observado no teste real: 764 tokens de saída só para
  classificar). Não corrigido nesta fase — exigiria separar os dois papéis
  dentro do `AgentOrchestrator`, uma mudança de escopo maior. Fica
  registrado como otimização de custo para uma fase futura.

Limitações específicas da Fase 3 (Product Architect/Factory) estão em
[PRODUCT-ARCHITECT.md](PRODUCT-ARCHITECT.md#limitações-conhecidas) e
[PRODUCT-FACTORY.md](PRODUCT-FACTORY.md#limitações-conhecidas). Resumo:

- `user_id`/`tenant_id` do `ProductBlueprint` continuam vazios — o que foi
  resolvido é o isolamento de *contexto de conversa* por sessão, não uma
  autenticação multiusuário completa.
- Paráfrases não previstas de "quais alternativas" podem disparar uma nova
  chamada ao LLM em vez de reaproveitar candidatos já calculados.
- A maioria das capabilities do Tool Registry seguem indisponíveis de
  propósito (fundação, não construção) — `MINI_APP_BUILDER` em especial
  aguarda uma interface/API do criador de mini-apps que a Cris já tem, ainda
  não integrada (marcado `AVAILABLE_MANUAL` desde a Fase 4).

Limitações específicas da Fase 4 (Business Builder/Production Plan/Artifact
Manifest) estão em
[BUSINESS-BUILDER.md](BUSINESS-BUILDER.md#limitações-conhecidas) e
[PRODUCTION-PLAN.md](PRODUCTION-PLAN.md). Resumo:

- Sem dado de tráfego pago real, todo o plano de negócio (funil, conteúdo,
  lançamento) é planejamento, não validação de mercado.
- `SALES_PAGE_PLANNER`/`FUNNEL_PLANNER`/`EMAIL_SEQUENCE_PLANNER`/
  `CONTENT_PLANNER`/`LAUNCH_PLANNER` existem hoje como campos calculados
  numa única chamada do Business Builder, não como capabilities executáveis
  separadamente no Tool Registry.
- O Artifact Manifest é só a estrutura lógica — não há sincronização real
  com Google Drive ou qualquer outro storage nesta fase.
- Produção completa dos ativos (imagem, vídeo, mini-app funcional, landing
  page publicada) continua fora de escopo — só o brief textual (e, para
  tipos técnicos, a especificação planejada) é gerado de verdade.
- O Evidence Guard (`core/evidence_guard.py`) é baseado em padrões
  conhecidos (regex/categorias), não em compreensão semântica plena.

**Correções pós-teste real (5 rounds de teste via Telegram, resumo)**:
1. Expansão de hipóteses tinha cache incorreto — corrigido com detecção de
   intenção dedicada (`_eh_pedido_expansao`), sempre reconsulta o LLM.
2. Aprovação não era reconhecida pelo Business Builder/Product Factory logo
   após aprovar — corrigido com `ProductBlueprint.esta_aprovado()` (aceita
   `APPROVED`/`IN_PRODUCTION`/`COMPLETED`, nunca só `== "APPROVED"`).
3. Artefatos genéricos (campos do candidato vencedor nunca promovidos pro
   blueprint) — corrigido com `promover_candidato_para_blueprint`.
4. Evidência do concorrente herdada como fato do produto novo — corrigido
   com `core/evidence_guard.py` (4 categorias: fato inventado removido,
   urgência/garantia sem oferta real removida, promessa de resultado
   removida, funcionalidade não construída reescrita como hipótese).
5. Manifesto servia snapshot congelado (Business Plan não sincronizado) e
   caía no assistente genérico por falta de roteamento determinístico —
   corrigido com `get_current_project_manifest` (leitura pura, zero LLM,
   zero escrita) e adição de "manifesto"/"status do projeto" às
   interceptações do `AgentOrchestrator`.

Ver [PRODUCT-ARCHITECT.md](PRODUCT-ARCHITECT.md), [BUSINESS-BUILDER.md](BUSINESS-BUILDER.md)
e [ARTIFACT-MANIFEST.md](ARTIFACT-MANIFEST.md) para o detalhamento completo
de cada correção.

Limitações específicas da Fase 5 (Paid Traffic Architect) estão em
[PAID-TRAFFIC-ARCHITECT.md](PAID-TRAFFIC-ARCHITECT.md#limitações-conhecidas).
Resumo:

- Nenhuma execução real de tráfego (login/API de Ads, criação/publicação de
  campanha, gasto real) existe nesta fase — só planejamento.
- Google Search sempre cai em `REQUIRES_KEYWORD_DATA` — sem fonte real de
  volume de busca/CPC integrada ainda.
- Evidence Guard continua baseado em padrões conhecidos (regex/categorias),
  não em compreensão semântica plena — vale para a 5ª categoria adicionada
  nesta fase (métricas de tráfego pago inventadas) também.
- Resposta do Telegram pode ficar extensa para planos com vários canais —
  já dividida automaticamente, mas sem resumo/paginação (melhoria de UX
  registrada para fase futura, deliberadamente fora de escopo agora).

**Correções pós-teste real da Fase 5 (4 rounds, resumo)**:
1. Paid Traffic Architect não enxergava evidência que o Artifact Manifest já
   mostrava para o mesmo projeto — corrigido com a fonte canônica única
   `ProjectBrain.coletar_evidencias_pesquisa()`, usada por ambos.
2. Resultado `NEEDS_INFORMATION` ficava congelado (cache indevido de um
   resultado que não custou LLM nenhum) — corrigido: só resultados que
   custaram uma chamada real ou representam decisão humana
   (`READY_FOR_APPROVAL`/`APPROVED`/`REJECTED`) são reaproveitados.
3. Auditoria de qualidade (mercado ausente exibido como "?", campos sem
   Evidence Guard, sem guarda formal de prova social/orçamento, mais de um
   canal podendo aparecer como prioritário ao mesmo tempo) — corrigida com
   `REQUIRES_MARKET_DATA`/resolução por fallback, `_lista_limpa()` em todos
   os campos livres, `social_proof_status`/`budget_status` explícitos, e o
   vocabulário `PRIMARY_TEST`/`SECONDARY_TEST`/`LATER`/`NOT_RECOMMENDED_NOW`
   com exatamente um `PRIMARY_TEST` imposto deterministicamente.
4. Regex da categoria 5 do Evidence Guard (métrica de tráfego inventada)
   não capturava frases como "ROAS esperado de 3x" com uma única
   alternação — corrigido com dois grupos opcionais independentes.

Ver [PAID-TRAFFIC-ARCHITECT.md](PAID-TRAFFIC-ARCHITECT.md) para o
detalhamento completo.

## Como restaurar / adicionar novas Skills

Ver [ROADMAP-AGENTS.md](ROADMAP-AGENTS.md#como-adicionar-um-novo-agentetool)
para o passo a passo de como um novo agente/Skill é adicionado, seguindo
exatamente o padrão de `scalaflow_intel`/`opportunity_analyst`.

Para restaurar o estado desta fase: `git log` até o commit do checkpoint
"Fase 2" ou "Fase 2.5" (ver relatórios de entrega) e
`git checkout <hash> -- <arquivo>` no arquivo específico, igual ao processo
já documentado no Marco 1. Ver também
[docs/CHECKPOINT-GIT.md](CHECKPOINT-GIT.md) para o processo de checkpoint em
si.
