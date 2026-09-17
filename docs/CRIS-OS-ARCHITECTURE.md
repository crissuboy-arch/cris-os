# CRIS OS — Arquitetura (Fase 2 + Fase 2.5)

> Visão de arquitetura da camada inteligente construída na Fase 2 (Project
> Brain + Opportunity Analyst + Decision Engine) e do provedor de IA remota
> adicionado na Fase 2.5 (OpenRouter), em cima do Marco 1
> ([docs/MARCO-01-TELEGRAM-SCALAFLOW.md](MARCO-01-TELEGRAM-SCALAFLOW.md)).

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
