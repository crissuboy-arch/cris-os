# Integração ScalaFlow ↔ CRIS OS (Fase 9)

> Fronteira de integração final entre inteligência de mercado (ScalaFlow) e
> orquestração/decisão (CRIS OS). Documento de fechamento da Fase 9 — a
> última fase da arquitetura planejada.

## Arquitetura final — três responsabilidades, nunca misturadas

```
SCALAFLOW                    CRIS OS                       PINK LOGIC
(inteligência)                (cérebro/orquestração)         (produção)
─────────────                ──────────────────             ───────────
TikTok/Instagram/Facebook/    Project Brain                  ebooks
YouTube/Google Trends         AgentOrchestrator               posts
concorrentes, anúncios,       Business Builder                carrosséis
ofertas, páginas, funis       Execution Engine                criativos
                              Approval Router                 páginas
"O que vale a pena criar/     "Como decidir, estruturar,     materiais digitais
 explorar?"                   aprovar e executar com
                               controle humano?"
```

- **ScalaFlow** nunca aprova, nunca executa, nunca publica, nunca gasta. Ele só fornece inteligência.
- **CRIS OS** mantém autoridade total sobre seu próprio workflow — nada que chegue de fora pula o Approval Router.
- **Pink Logic** (futuro) produz os ativos que o Business Builder/Execution Engine especificam — o CRIS OS nunca gera ebook/post/criativo/página ele mesmo.

## O que já existe vs. o que a Fase 9 constrói

**Já existia (Marco 1+, reaproveitado sem alteração):**
- `tools/opportunity_tools.py` já lê diretamente as tabelas `*_minerados`/`collected_ads` do Supabase do ScalaFlow — integração **pull**, síncrona, já em produção desde a Fase 2. A Fase 9 **não substitui isso**.
- `ProjectBrain`/`ProjectBrainStore` (memória canônica), `PendingApprovalStore` + `core/approval_router.py` (aprovação humana central), `AgentOrchestrator` (roteamento), `Oportunidade`/`Mercado`/`Origem` (seções já lidas por Opportunity Analyst, Product Architect, Business Builder desde a Fase 2).

**Novo nesta fase — um contrato de integração *push*:**
- `memory/project_brain.py`: `MarketIntelligenceHandoff` (contrato canônico), `Evidence` (evidência rastreável), `IntelligenceHandoffStore` (índice global de deduplicação).
- `core/market_intelligence.py`: pipeline de validação → verification-before-trust → deduplicação → resolução de projeto → persistência.
- `tools/market_intelligence_tools.py` + `agents/market_intelligence.py`: consulta somente-leitura pelo Telegram do que já foi recebido.

**Auditoria confirmada (ver commit da Fase 9): nenhum webhook/handoff endereçado ao CRIS OS existe hoje no repositório ScalaFlow/ScalaFlow Insights.** Por isso este contrato foi construído inteiramente do lado CRIS OS, como uma porta desacoplada e mockável — nada do lado ScalaFlow foi inventado ou alterado.

## Por que reaproveitar `Oportunidade`/`Mercado`/`Origem` em vez de um modelo novo

Um `MarketIntelligenceHandoff` aceito **nunca** vira uma segunda fonte de verdade — ele é *distilado* para dentro dos mesmos campos (`brain.mercado.market/niche/target_country`, `brain.oportunidade.score/evidence/signals`, `brain.origem.source_*`) que Opportunity Analyst, Product Architect e Business Builder **já leem** desde as Fases 2–7. Isso significa: **nenhuma integração adicional é necessária** para que os agentes existentes já consigam trabalhar sobre inteligência recebida por este novo caminho — eles não sabem (nem precisam saber) que a origem mudou de "leitura direta do Supabase" para "handoff estruturado".

O próprio `MarketIntelligenceHandoff` (payload bruto + metadados de validação/confiança) fica preservado à parte, em `brain.market_intelligence: list[MarketIntelligenceHandoff]` — histórico completo, nunca sobrescrito, é o que dá provenance total.

## Contrato canônico: `MarketIntelligenceHandoff`

Campos mínimos exigidos: `handoff_id`, `source_system`. Todo o resto é opcional — **ausência nunca vira invenção**: fica `None`/lista vazia.

| Grupo | Campos |
|---|---|
| META | `handoff_id`, `schema_version` (só `"1.0"` suportada hoje), `source_system`, `source_module`, `created_at`, `received_at` |
| PROJECT | `project_id` (opcional), `external_project_ref` (opcional) |
| OPPORTUNITY | `opportunity_id`, `title`, `market`, `niche`, `subniche`, `country`, `language`, `description` |
| SIGNALS | `trend_signals`, `demand_signals`, `competition_signals`, `ad_signals`, `social_signals`, `search_signals` (dicts livres) |
| OFFER | `product_name`, `offer_type`, `price`, `currency`, `commission`, `platform`, `sales_page_url` |
| COMPETITION | `competitors`, `competitor_urls`, `observed_offers` |
| EVIDENCE | lista de `Evidence`: `evidence_id`, `source_type`, `source_name`, `source_url`, `captured_at`, `raw_reference`, `metric_name`, `metric_value`, `metric_unit`, `evidence_type`, `confidence_level` |
| CONFIDENCE | `confidence_score`, `confidence_level`, `confidence_reason` |
| SCORING | `opportunity_score` (0–100), `score_components`, `scoring_version` |
| META extra | `tags`, `notes`, `warnings` |
| CONTROLE | `status` (`RECEIVED\|VALIDATED\|REJECTED\|DUPLICATE\|PERSISTED\|NEEDS_REVIEW`), `rejection_reason` |

## Verification before trust (regra crítica, aplicada — não só documentada)

`core/market_intelligence.py:_classificar_confianca` **rebaixa deterministicamente** `confidence_level`:
- Nenhuma evidência com `evidence_type` `OBSERVED`/`DERIVED` por trás → `confidence_level` cai para `LOW`.
- Nenhuma evidência nenhuma → cai para `UNKNOWN`.
- `opportunity_score >= 70` **e** zero evidência → o handoff inteiro vira `NEEDS_REVIEW` (nunca `PERSISTED` silenciosamente) — fail closed no caso de maior impacto potencial.

Exemplo real testado (`tests/test_market_intelligence.py::test_produto_vencedor_sem_evidencia_nunca_vira_fato`): ScalaFlow envia `title="Produto vencedor"` com `confidence_level="HIGH"` e `evidence=[]` → persistido, mas com `confidence_level` rebaixado para `UNKNOWN` — a afirmação nunca chega como fato confirmado.

## Provenance / rastreabilidade

Cada `Evidence` carrega origem (`source_type`/`source_name`/`source_url`), timestamp (`captured_at`) e classificação (`evidence_type`/`confidence_level`) — nunca uma frase solta. Ao ser aplicada em `brain.oportunidade.evidence`, cada linha preserva `handoff_id` de origem, permitindo responder "de onde veio esse dado?" a qualquer momento: `ScalaFlow → source_module → Evidence → MarketIntelligenceHandoff.handoff_id → project_id → ProjectBrain.oportunidade/mercado → (Product Architect/Business Builder) → BusinessPlan/TrafficPlan → ExecutionPlan`.

## Idempotência / deduplicação

`IntelligenceHandoffStore` é um índice **global** (por `handoff_id`, não por sessão/projeto — mesma infraestrutura `ProjectMemory`/`KnowledgeItem`, nenhum banco paralelo) checado **antes** de qualquer resolução de projeto. O mesmo `handoff_id` enviado duas vezes nunca cria uma segunda `Opportunity`, projeto, evidência ou execução — a segunda chamada devolve `status: "DUPLICATE"` imediatamente. Testado explicitamente, inclusive após restart real do processo.

## Project resolution — nunca adivinha

1. `project_id` informado e existente → usa esse projeto.
2. `external_project_ref` corresponde a exatamente **um** projeto já existente (via `origem.source_offer_id`) → usa esse projeto.
3. `external_project_ref` corresponde a **mais de um** → `NEEDS_REVIEW` (ambíguo, nunca escolhido arbitrariamente).
4. Nenhum dos dois → cria um projeto novo, controladamente (`ProjectBrainStore.create`).
5. `project_id` informado mas inexistente → `NEEDS_REVIEW` (nunca cria por engano nem ignora silenciosamente).

## Validação de payload (fail closed)

Antes de qualquer persistência, `validar_payload` checa: payload é um dict serializável; tamanho ≤ 256 KB; `handoff_id`/`source_system` presentes; `schema_version` suportada; `opportunity_score` em `[0, 100]`; `confidence_level` no vocabulário fechado; timestamps ISO válidos; URLs com esquema `http(s)://`; cada item de `evidence` com `evidence_type`/`confidence_level` válidos. Qualquer falha → `status: "REJECTED"` com lista de erros — **nada é persistido**.

## Segurança do workflow — ScalaFlow não manda no CRIS OS

Testado explicitamente (`tests/test_market_intelligence.py`, seção "ScalaFlow NAO manda no CRIS OS"): um handoff, mesmo tentando "contrabandear" campos como `business_plan`/`approval_status` no payload, **nunca** consegue aprovar BusinessPlan/TrafficPlan, executar CampaignSpec/ExecutionPlan, criar uma `PendingApproval`, ou causar qualquer chamada HTTP/gasto. `_construir_handoff` só aceita campos que existem no dataclass `MarketIntelligenceHandoff` — qualquer campo extra é descartado silenciosamente antes de qualquer escrita.

## Observabilidade

Eventos logados (via `logging` padrão, mesmo padrão de todas as fases anteriores): `intelligence_received` (implícito no log de payload rejeitado), `intelligence_validated`/`intelligence_rejected`/`intelligence_deduplicated`/`intelligence_persisted` (logs em `core/market_intelligence.py`). Nunca logado: tokens, API keys, passwords, segredos — o pipeline não lida com nenhum segredo (não há autenticação HTTP implementada nesta fase, ver limitações).

## Persistência

Tudo no **mesmo** `ProjectBrain`/`data/cris_os.db` — `market_intelligence: list[MarketIntelligenceHandoff]` no brain do projeto resolvido, `IntelligenceHandoffStore` na mesma tabela `project_memory`. Testado: após restart do processo, handoff/evidência/provenance/status continuam intactos, e deduplicação continua funcionando.

## Como conectar o ScalaFlow real (o que falta)

Hoje `receive_intelligence(payload, brain_store, handoff_store)` é uma **função Python direta** — não existe um servidor HTTP escutando por handoffs. Para conectar o ScalaFlow real, falta **um único passo técnico**: expor esta função via algum transporte que o ScalaFlow possa chamar. Duas opções, escolher **depois** de decidir onde o ScalaFlow vai rodar:

1. **Mesmo processo/máquina**: o ScalaFlow (ou um script ponte) importa `core.market_intelligence.receive_intelligence` diretamente e chama com um payload no formato do contrato acima.
2. **Processos/máquinas diferentes**: expor uma rota HTTP fina (ex.: no `web/backend` FastAPI já existente para o CRIS OS Studio, **não** no bot do Telegram) que recebe o payload, chama `receive_intelligence` e devolve o dict de resultado. Isso exigiria: autenticação (token compartilhado via variável de ambiente, nunca hardcoded), validação de tamanho de payload no nível HTTP também, e rate limiting básico contra replay.

**Nenhuma das duas opções foi implementada nesta fase** — nenhum endpoint HTTP, nenhuma URL, nenhuma tabela ou payload do lado ScalaFlow foi inventado, conforme regra explícita da Fase 9.

### Variáveis de ambiente necessárias (quando a opção 2 for implementada)

Nenhuma variável nova foi adicionada nesta fase (não há HTTP ainda). Quando implementado, será necessário no mínimo: um token de autenticação compartilhado (ex.: `SCALAFLOW_INTEGRATION_TOKEN`), nunca commitado, sempre lido via `config/settings.py` como as demais chaves (`OPENROUTER_API_KEY`, `SUPABASE_SERVICE_KEY`).

## Como executar os testes

```powershell
python -m pytest tests/test_market_intelligence.py tests/test_fase9_routing.py tests/test_fase9_end_to_end.py tests/test_fase9_tools.py -v
```

## Como diagnosticar a integração

```python
from tools.opportunity_tools import get_project_brain_store
from memory.project_brain import IntelligenceHandoffStore
from core.market_intelligence import get_intelligence, get_project_intelligence

store = get_project_brain_store()
handoff_store = IntelligenceHandoffStore(store.project_memory)

# ver todos os handoffs de um projeto
get_project_intelligence("proj_xxx", store)

# ver um handoff especifico pelo id (funciona mesmo sem saber o projeto)
get_intelligence("handoff_yyy", store, handoff_store)
```

Pelo Telegram: `"Mostre a inteligência de mercado deste projeto."` (projeto resolvido pelo foco atual da sessão, mesmo mecanismo do `UserFocusStore` usado desde a Fase 3).

## Limitações conhecidas

- Não existe transporte HTTP/webhook real ainda — só a função Python (`receive_intelligence`), ver seção acima.
- `schema_version` só suporta `"1.0"` — versionamento futuro exigirá lógica de migração explícita quando `"2.0"` existir.
- Validação de URL é superficial (checa só o esquema `http(s)://`) — não valida se a URL responde de verdade.
- `_classificar_confianca` usa um limiar fixo (`opportunity_score >= 70` sem evidência → `NEEDS_REVIEW`) — pode precisar de calibração com dados reais.
- Um handoff `NEEDS_REVIEW` fica registrado no índice global (`IntelligenceHandoffStore`) mas **não** persistido em nenhum `ProjectBrain` — não há hoje uma fila/tela de "handoffs aguardando revisão humana" (só o log estruturado). Reenviar o mesmo `handoff_id` depois de resolver a ambiguidade manualmente exigirá lógica adicional (fora de escopo desta fase).
- `resolver_projeto` usa `brain_store.list_all()` para checar `external_project_ref` — aceitável na escala atual (uma pessoa, dezenas/centenas de projetos), mesma limitação já documentada em `docs/PROJECT-BRAIN.md`.

## FUTURE CONSIDERATIONS (não implementar agora)

- LOOP-R, Hermes, Zo Computer — nenhum destes foi avaliado ou implementado nesta fase; ficam como ideias registradas para avaliação futura, fora do escopo da Fase 9.
- Endpoint HTTP real de recebimento de handoffs (com autenticação, rate limiting, proteção contra replay).
- Fila de "handoffs NEEDS_REVIEW" pesquisável/acionável pelo Telegram.
- Mineração real via ScalaFlow (Apify, atores pagos) — **explicitamente fora de escopo desta fase**; o primeiro teste real será conduzido pela usuária após o fechamento, seguindo o checklist abaixo.

## Checklist para a primeira mineração/handoff real

**Antes:**
- [ ] CRIS OS online (bot rodando, `AgentOrchestrator` ativo)
- [ ] ScalaFlow online
- [ ] Project Brain acessível (`data/cris_os.db` presente e gravável)
- [ ] Decisão tomada sobre transporte (chamada direta vs. HTTP) e, se HTTP, integração autenticada
- [ ] Nenhuma chave exposta em código/logs
- [ ] Orçamento/custo conhecido (Apify e afins) antes de rodar qualquer mineração paga
- [ ] Projeto de teste identificado (ou aceitar criação controlada de um novo)

**Durante:**
- [ ] Executar somente UMA mineração/handoff de teste
- [ ] Acompanhar logs (`intelligence_received`/`validated`/`rejected`/`persisted`)
- [ ] Confirmar handoff recebido (`status: PERSISTED` ou `NEEDS_REVIEW` com motivo claro)
- [ ] Confirmar evidência presente e com `evidence_type`/`confidence_level` coerentes
- [ ] Confirmar Opportunity (mercado/nicho/score) populada nos campos canônicos
- [ ] Confirmar projeto correto (não criou um segundo projeto por engano)
- [ ] Verificar ausência de duplicidade (reenviar o mesmo handoff deve dar `DUPLICATE`)

**Depois:**
- [ ] Verificar Project Brain (`get_project_intelligence`)
- [ ] Verificar provenance (cada evidência rastreável até a fonte)
- [ ] Verificar que os agentes existentes (Opportunity Analyst/Product Architect) conseguem ler os dados normalmente
- [ ] Registrar bugs encontrados
- [ ] Registrar custos reais incorridos (se houve mineração paga)
- [ ] NÃO corrigir vários bugs simultaneamente sem reproduzir cada um isoladamente primeiro
