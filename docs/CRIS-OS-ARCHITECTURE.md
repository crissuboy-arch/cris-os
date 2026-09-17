# CRIS OS — Arquitetura (Fase 2)

> Visão de arquitetura da camada inteligente construída na Fase 2 (Project
> Brain + Opportunity Analyst + Decision Engine), em cima do Marco 1
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

## Por que "COST-FIRST"

Ordem de operações em `tools/opportunity_tools.py`:

```
dados (Supabase, já existentes) → filtro determinístico (palavra-chave) →
score/decisão (regras Python puras) → resposta
```

Nunca manda nada para um modelo de IA nesta fase — não há chamada de LLM em
nenhum ponto do fluxo Opportunity Analyst / Decision Engine. Quando termos de
busca não existem (oferta sem `keyword`/nicho/anunciante úteis), o código
**nem faz a chamada de rede** — ver `_extrair_termos_busca` +
`_buscar_sinal_fonte` em `tools/opportunity_tools.py`.

Arquitetura futura de custo (documentada, **não implementada agora**):

```
LOCAL (determinístico, custo zero) → CHEAP (modelo pequeno/barato) → PREMIUM (modelo forte)
```

Hoje só existe o degrau LOCAL.

## Segurança

- Nenhuma ação que envolva dinheiro, campanhas, publicação, e-mails externos,
  contas externas ou compras é executada nesta fase. Toda decisão fica em
  `PENDING_APPROVAL` (`ProjectBrain.decisao.decision_status`).
- Autorização do Telegram (`TELEGRAM_ALLOWED_USER_ID`) inalterada desde o
  Marco 1 — ver `core/gateway.py`.
- Nenhum segredo novo foi introduzido (Opportunity Analyst usa as mesmas
  `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` já configuradas).
- Todo acesso ao Supabase do ScalaFlow nesta fase é **somente leitura**
  (`SELECT` via REST) — nenhuma tabela nova, nenhuma escrita.

## Limitações desta fase

Ver a seção "Limitações" em cada doc específico
([PROJECT-BRAIN.md](PROJECT-BRAIN.md#limitações),
[OPPORTUNITY-ANALYST.md](OPPORTUNITY-ANALYST.md#limitações),
[DECISION-ENGINE.md](DECISION-ENGINE.md#limitações)). Resumo geral:

- Sem Ollama/LLM nesta fase → sem análise qualitativa de copy (público,
  problema, promessa, mecanismo, ângulos, padrões criativos).
- Correlação cross-plataforma é por palavra-chave, não por relação real no
  banco (as tabelas `*_minerados` do ScalaFlow não têm FK para
  `collected_ads`).
- `niche` em `collected_ads` é quase sempre `"Geral"` (274 de 286 registros
  reais na amostra usada) — não é um bom termo de busca; o código já
  prioriza `keyword` e `advertiser` por isso.

## Como restaurar / adicionar novas Skills

Ver [ROADMAP-AGENTS.md](ROADMAP-AGENTS.md#como-adicionar-um-novo-agentetool)
para o passo a passo de como um novo agente/Skill é adicionado, seguindo
exatamente o padrão de `scalaflow_intel`/`opportunity_analyst`.

Para restaurar o estado desta fase: `git log` até o commit do checkpoint
"Fase 2" (ver relatório de entrega) e `git checkout <hash> -- <arquivo>` no
arquivo específico, igual ao processo já documentado no Marco 1.
