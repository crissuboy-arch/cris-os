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

## Como conectar o ScalaFlow real

**Implementado**: `POST /api/integrations/scalaflow/intelligence` — rota HTTP em `web/backend/routes/market_intelligence.py`, incluída no FastAPI já existente para o CRIS OS Studio (`web/backend/app.py`) — **nunca** no bot do Telegram. A rota é só transporte: autentica, faz validações de tamanho/JSON no nível HTTP e delega toda a lógica de negócio para `core.market_intelligence.receive_intelligence` (a mesma função já testada em `tests/test_market_intelligence.py`).

**Contrato HTTP:**
- `POST /api/integrations/scalaflow/intelligence`
- Header obrigatório: `Authorization: Bearer <CRIS_OS_INTEGRATION_TOKEN>` (aceita também o token sem o prefixo `Bearer `)
- Corpo: JSON no formato `MarketIntelligenceHandoff` (ver contrato acima)
- Respostas:
  - `200` — `PERSISTED` ou `DUPLICATE`
  - `202` — `NEEDS_REVIEW` (aceito, mas precisa de revisão humana)
  - `400` — `REJECTED` (payload inválido — **não repetir sem corrigir**)
  - `401` — token inválido/ausente (**não repetir sem corrigir o token**)
  - `413` — corpo excede o tamanho máximo permitido (~260 KB)
  - `503` — integração não configurada neste ambiente (`CRIS_OS_INTEGRATION_TOKEN` vazio)

Isso corresponde exatamente à "opção 2" (processos/máquinas diferentes) do transporte previsto originalmente nesta fase — a "opção 1" (chamada Python direta, mesmo processo) continua disponível para quem preferir, chamando `core.market_intelligence.receive_intelligence` diretamente.

### Variáveis de ambiente necessárias

- `CRIS_OS_INTEGRATION_TOKEN` (`.env`, raiz do repositório, compartilhado entre bot e `web/backend`) — token estático, gerado por exemplo com `openssl rand -hex 32`. Configure o **mesmo** valor no lado ScalaFlow. Vazio = endpoint responde `503` (nunca abre sem token).

### Segurança implementada

- Comparação de token em tempo constante (`hmac.compare_digest`), mesmo princípio já usado em `agent_builder/auth.py` para verificação de assinatura JWT.
- Nunca loga o token recebido nem o esperado — só o fato de a tentativa ter falhado.
- Nunca expõe stack trace ao chamador — qualquer exceção inesperada vira `500` genérico; o detalhe real fica só no log do servidor.
- Verificação de tamanho do corpo bruto **antes** de tentar decodificar/parsear JSON (defesa em profundidade, além do limite de 256 KB já aplicado dentro de `validar_payload`).
- Autenticação é **service-to-service** (token estático) — deliberadamente separada do JWT de usuário da Studio (`agent_builder/auth.py`), nunca reaproveitada para esse fim.

### Dependências

Este endpoint faz parte do subsistema **CRIS OS Studio** (`web/backend`), que tem dependências próprias (`web/backend/requirements.txt`: `fastapi`, `uvicorn`) — deliberadamente separadas do `requirements.txt` da raiz (usado só pelo bot do Telegram). Para rodar/testar este endpoint: `pip install -r web/backend/requirements.txt`. O teste correspondente (`tests/test_market_intelligence_api.py`) usa `pytest.importorskip("fastapi")` e é pulado automaticamente em ambientes que só instalaram o `requirements.txt` da raiz.

## Como executar os testes

```powershell
python -m pytest tests/test_market_intelligence.py tests/test_fase9_routing.py tests/test_fase9_end_to_end.py tests/test_fase9_tools.py -v

# receptor HTTP -- exige `pip install -r web/backend/requirements.txt` primeiro
# (pulado automaticamente se so o requirements.txt da raiz estiver instalado)
python -m pytest tests/test_market_intelligence_api.py -v
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

Via HTTP (com o `web/backend` rodando -- `python -m uvicorn web.backend.app:app --reload --port 8000`):

```bash
curl -X POST http://localhost:8000/api/integrations/scalaflow/intelligence \
  -H "Authorization: Bearer $CRIS_OS_INTEGRATION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"handoff_id": "teste-manual-1", "source_system": "SCALAFLOW", "title": "Teste manual"}'
```

## Orquestração pós-recebimento: `core/scalaflow_bridge.py`

O receptor HTTP (`web/backend/routes/market_intelligence.py` +
`core/market_intelligence.py:receive_intelligence`) permanece **inalterado**
e continua fazendo só validação/dedup/persistência — nenhuma lógica de
negócio nova foi adicionada a ele (nem ao `receive_intelligence`). A
orquestração que fecha o caminho até uma decisão humana real vive num
módulo separado, `core/scalaflow_bridge.py`, reaproveitando os componentes
já existentes das Fases 3/4/6/8 sem reimplementar nenhum deles:

```
MarketIntelligenceHandoff (persistido, sem alteração)
        │
        ▼
core.scalaflow_bridge.avancar_projeto / avancar_a_partir_do_handoff
        │
        ├─ core.product_architect.propor_produto  (Fase 3, reaproveitado)
        │     → blueprint consolidado (decision_status="APPROVED" pela ponte
        │       — ver decisão arquitetural no docstring do módulo: um único
        │       gate humano nesta integração, não três)
        │
        ├─ core.business_builder.construir_plano_negocio  (Fase 4/7, reaproveitado)
        │     → BusinessPlan (READY_FOR_APPROVAL)
        │
        ├─ memory.project_brain.PendingApprovalStore.set_pending  (Fase 6, reaproveitado)
        │     → pendência com project_id + handoff_id explícitos
        │
        ├─ memory.project_brain.UserFocusStore.set_focus  (Fase 3, reaproveitado)
        │     → foco da sessão passa a apontar para ESTE projeto (correção de
        │       bug real: sem isso, comandos genéricos como "execute o plano"
        │       continuavam resolvendo o último projeto do fluxo orgânico
        │       antigo -- "Aprovado"/"Rejeito" nunca foram afetados, pois o
        │       Approval Router resolve por PendingApprovalStore, não por foco)
        │
        └─ channels.telegram.bot.enviar_mensagem_proativa  (novo, mas reaproveita
              TELEGRAM_BOT_TOKEN/TELEGRAM_ALLOWED_USER_ID já existentes)
              → notifica a Cris

core.approval_router.resolver_aprovacao_contextual  (Fase 6, ESTENDIDO)
        │  ("Aprovado"/"Rejeito" na mesma sessão Telegram)
        ▼
  BUSINESS_PLAN aprovado → core.execution_engine.criar_execution_plan
        (Fase 8, reaproveitado, sem executar nada) → ExecutionPlan + Tasks
        → nova pendência EXECUTION_PLAN (a execução real de tasks continua
          exigindo aprovação explícita por task, inalterado)
```

**Ativação**: hoje esta orquestração é sempre **explícita** (nunca automática
dentro do request HTTP do receptor) — invocada via o comando de chat "avance
o handoff `<id>`"/"retome o projeto" (`tools/market_intelligence_tools.py`)
ou diretamente em Python (`avancar_a_partir_do_handoff`). Isso é deliberado:
o receptor HTTP precisa continuar rápido e sem side effects (ele é testado
explicitamente para nunca fazer chamada externa — `test_endpoint_nunca_faz_chamada_http_externa`),
e gerar um BusinessPlan pode envolver uma chamada real a um LLM.

**Ponto de extensão futuro — "Decision Gate" (Jev, não instalado)**: as duas
funções públicas de `core/scalaflow_bridge.py` (`avancar_projeto`,
`avancar_a_partir_do_handoff`) foram desenhadas para que um futuro
"Decision Gate" (usando `Jev yes/pick/score/run` para decisões rápidas
estruturadas) possa interceptar a chamada ANTES de `propor_produto` — por
exemplo, para decidir automaticamente "avançar" vs. "aguardar mais
evidência" sem intervenção manual a cada handoff. Isso é só um ponto de
extensão documentado — nenhuma dependência de Jev existe no código hoje.

**Consulta de status** (somente leitura, mesma API de integração):
`GET /api/integrations/scalaflow/intelligence/{handoff_id}/status`, mesma
autenticação `Authorization: Bearer <CRIS_OS_INTEGRATION_TOKEN>` do POST.
Devolve o snapshot de `core.scalaflow_bridge.montar_status` (project_id,
status do BusinessPlan/aprovação pendente/ExecutionPlan/contagem de tasks,
contagem de `production` (WorkOrders), último erro) — nunca inclui segredo
algum.

## Cris OS → executores especializados (`ProductionWorkOrder`)

A Task 3 do Execution Engine ("Preparar handoff de ativos necessários",
`core/execution_engine.py`, SEM alteração) já especifica `required_assets`
(ex.: "Landing page com prova social") — mas até esta fase nada transformava
essa especificação em algo endereçável a um executor real. Esta camada fecha
esse gap, mantendo o Cris OS como ORQUESTRADOR (nunca um construtor de
landing pages/gerador de criativos/CRM):

```
ScalaFlow → Cris OS → BusinessPlan → ExecutionPlan → Task 3 (COMPLETED)
        │
        ▼
core.production_orders.gerar_work_orders_da_task  (novo)
        │  para cada item de task.evidence (= required_assets):
        ├─ core.production_router.normalizar_asset_type  (novo, determinístico)
        │     texto livre -> asset_type (vocabulário fechado)
        ├─ core.production_router.resolver_executor  (novo, tabela fixa)
        │     asset_type -> executor_type
        └─ memory.project_brain.ProductionWorkOrder  (novo, persistido no
              MESMO ProjectBrain -- `brain.production_work_orders`)
              status inicial: READY (ou NEEDS_ROUTING se o asset_type não
              mapear para nenhum executor conhecido)
        ▼
core.executor_adapter.ExecutorAdapter  (novo -- CONTRATO, protocol)
        │  can_handle / dispatch / get_status / collect_result
        ▼
  EXECUTOR_REGISTRY  (novo -- hoje, todo executor_type aponta para o MESMO
                       stub `AdapterNaoConectado`, que NUNCA marca
                       DISPATCHED nem finge produção concluída)
```

**Mapeamento inicial de executores** (Seção 3 da missão):

| asset_type | executor_type | Executor real (futuro) |
|---|---|---|
| `APP` | `APP_BUILDER` | Criador-de-App |
| `LANDING_PAGE` | `PAGEFORGE` | PageForge |
| `EBOOK` / `CAROUSEL` / `MARKETING_MATERIAL` | `PINK_LOGIC` | Pink Logic |
| `DISTRIBUTION` | `FORGEHUB` | ForgeHub |
| `CRM` | `NEXORA` | NEXORA |
| `UNKNOWN` | `NEEDS_ROUTING` | (nenhum -- precisa de classificação manual) |

**Nesta fase, NENHUM executor real é chamado.** `AdapterNaoConectado.dispatch()`
devolve a WorkOrder inalterada — nenhuma chamada HTTP, nenhuma integração.
Conectar um executor real (fase futura, fora desta missão) significa:
implementar `ExecutorAdapter` para aquele executor e substituir sua entrada
em `core.executor_adapter.EXECUTOR_REGISTRY` — nenhuma mudança de contrato
em `ProductionWorkOrder`/`production_router`/`production_orders` necessária.

**Identidade preservada**: toda `ProductionWorkOrder` carrega
`handoff_id`/`project_id`/`execution_plan_id`/`source_task_id` explícitos —
nunca um ID solto. `global_project_id` existe como campo reservado (sempre
`None` hoje) para uma futura identidade cross-sistema, sem quebrar
`project_id` como identidade canônica atual.

**Idempotência**: a chave lógica `(execution_plan_id, source_task_id,
asset_type normalizado)` nunca gera uma segunda WorkOrder para o mesmo
requisito — reprocessar a Task 3, reiniciar o processo ou repetir "execute o
plano" sempre reaproveita as WorkOrders já existentes.

**Consulta pelo Telegram**: frases como "o que falta produzir?"/"quais
ativos faltam?"/"status da produção" (`tools/market_intelligence_tools.py`)
mostram as WorkOrders e seus executores — nunca despacham nada, mesmo que a
pergunta pareça pedir isso.

**Ponto de extensão futuro — Decision Gate/Jev (não implementado)**: o mesmo
ponto de extensão documentado acima (interceptar antes de `propor_produto`)
também poderia, no futuro, decidir automaticamente QUANDO despachar uma
WorkOrder `READY` para seu executor — hoje isso nunca acontece sozinho.

## Limitações conhecidas

- O endpoint HTTP não tem rate limiting nem proteção explícita contra replay além da idempotência natural do `handoff_id` (um replay do mesmo handoff é inofensivo — vira `DUPLICATE` — mas nada impede múltiplas tentativas de adivinhar o token, além do próprio custo de cada tentativa falhar com 401).
- Não há rotação de token automatizada — trocar `CRIS_OS_INTEGRATION_TOKEN` exige atualizar `.env` (CRIS OS) e a configuração equivalente no ScalaFlow manualmente, ao mesmo tempo.
- `schema_version` só suporta `"1.0"` — versionamento futuro exigirá lógica de migração explícita quando `"2.0"` existir.
- Validação de URL é superficial (checa só o esquema `http(s)://`) — não valida se a URL responde de verdade.
- `_classificar_confianca` usa um limiar fixo (`opportunity_score >= 70` sem evidência → `NEEDS_REVIEW`) — pode precisar de calibração com dados reais.
- Um handoff `NEEDS_REVIEW` fica registrado no índice global (`IntelligenceHandoffStore`) mas **não** persistido em nenhum `ProjectBrain` — não há hoje uma fila/tela de "handoffs aguardando revisão humana" (só o log estruturado). Reenviar o mesmo `handoff_id` depois de resolver a ambiguidade manualmente exigirá lógica adicional (fora de escopo desta fase).
- `resolver_projeto` usa `brain_store.list_all()` para checar `external_project_ref` — aceitável na escala atual (uma pessoa, dezenas/centenas de projetos), mesma limitação já documentada em `docs/PROJECT-BRAIN.md`.

## FUTURE CONSIDERATIONS (não implementar agora)

- LOOP-R, Hermes, Zo Computer — nenhum destes foi avaliado ou implementado nesta fase; ficam como ideias registradas para avaliação futura, fora do escopo da Fase 9.
- Rate limiting e proteção explícita contra replay no endpoint HTTP (hoje só a idempotência natural do `handoff_id`).
- Fila de "handoffs NEEDS_REVIEW" pesquisável/acionável pelo Telegram.
- Mineração real via ScalaFlow (Apify, atores pagos) — **explicitamente fora de escopo desta fase**; o primeiro teste real será conduzido pela usuária após o fechamento, seguindo o checklist abaixo.

## Checklist para a primeira mineração/handoff real

**Antes:**
- [ ] CRIS OS online (bot rodando, `AgentOrchestrator` ativo)
- [ ] ScalaFlow online
- [ ] Project Brain acessível (`data/cris_os.db` presente e gravável)
- [ ] `web/backend` (CRIS OS Studio) rodando e acessível pelo ScalaFlow, com `CRIS_OS_INTEGRATION_TOKEN` configurado nos dois lados
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
