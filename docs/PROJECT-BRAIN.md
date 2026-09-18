# Project Brain

Memória estruturada por projeto/oportunidade. Implementado em
`memory/project_brain.py`.

## Por que não é uma tabela nova no Supabase

O Supabase é a fonte de verdade **do ScalaFlow**, não do CRIS OS. Para não
mexer no schema do ScalaFlow (regra explícita desta fase), o Project Brain
guarda tudo **localmente**, reaproveitando uma estrutura que já existia no
CRIS OS: a camada L2 de memória (`memory.layers.ProjectMemory`), que já sabia
guardar um `KnowledgeItem` por projeto na tabela `project_memory` de
`data/cris_os.db` (SQLite local, `storage/sqlite_memory.py`).

`ProjectBrainStore` é uma camada fina em cima disso:
- Serializa o `ProjectBrain` inteiro (todas as seções) como JSON dentro do
  campo `content` do `KnowledgeItem`.
- Usa um `id` determinístico (`brain:<project_id>`), então salvar de novo faz
  **upsert** (`INSERT OR REPLACE`, já existente no backend) em vez de
  acumular histórico duplicado.

Nenhuma tabela nova. Nenhuma migration. Nenhuma mudança em
`storage/sqlite_memory.py`.

## Estrutura (todas as seções do pedido original)

```python
ProjectBrain
├── identidade       (project_id, name, type, status, created_at, updated_at)
├── origem           (source_offer_id, source_platform, source_url, source_country, source_language, source_headline, source_copy)
├── mercado          (niche, market, target_country, target_language, target_audience)
├── oportunidade     (score, signals, evidence, risks, competition, trend_signals)
├── decisao          (recommended_path, reasoning_summary, evidence_level, decision_status, user_approved)
├── produto          (product_type, product_name, positioning, offer, price, business_model)
├── blueprint        (ProductBlueprint | None -- Fase 3, ver PRODUCT-BLUEPRINT.md)
├── business_plan    (BusinessPlan | None -- Fase 4, ver BUSINESS-BUILDER.md)
├── production_plan  (ProductionPlan | None -- Fase 4, ver PRODUCTION-PLAN.md)
├── artifact_manifest (dict | None -- Fase 4, DERIVADO, ver ARTIFACT-MANIFEST.md)
├── traffic_plan     (TrafficPlan | None -- Fase 5, ver PAID-TRAFFIC-ARCHITECT.md)
├── brand            (brand_name, slogan, colors, fonts, visual_direction)
├── assets           (landing_page, creatives, videos, documents, drive_folder)
├── trafego          (channels, campaigns, budgets, results)
└── historico        (decisions, approvals, agent_runs)
```

Cada seção é um `@dataclass` em `memory/project_brain.py`. Muitos campos
ficam `None`/vazios até uma fase futura preenchê-los (`brand`, `assets` e
`trafego` ainda não são tocados por nenhum agente até a Fase 4 -- só
`identidade`, `origem`, `mercado`, `oportunidade`, `decisao`, `blueprint`,
`business_plan`, `production_plan` e `artifact_manifest` são preenchidos
pelos agentes existentes hoje).

**Continuidade real entre agentes (Fase 4)**: todos os agentes da Fase 4
(Business Builder, Product Factory) operam sobre o **MESMO** `project_id` já
criado pelo Opportunity Analyst -- nenhum agente cria um projeto novo pra si
mesmo. `business_plan`/`production_plan`/`artifact_manifest` são só mais
seções do mesmo `ProjectBrain`, salvas com o mesmo `ProjectBrainStore.save()`
de sempre (nenhuma migration, nenhum schema novo no SQLite -- o `content` já
era um JSON opaco, então novos campos no dataclass Python não exigem
nenhuma mudança em `storage/sqlite_memory.py`).

**Fase 5 (Paid Traffic Architect)**: mesmo princípio -- `traffic_plan` é só
mais uma seção do mesmo `ProjectBrain`, mesmo `project_id`, mesmo
`ProjectBrainStore.save()`. Nenhum banco/JSON paralelo foi criado para
armazenar planos de tráfego pago.

## API

```python
from memory.layers import ProjectMemory
from memory.project_brain import ProjectBrainStore
from storage import SQLiteMemory
from config.settings import settings

backend = SQLiteMemory(settings.DB_PATH)
store = ProjectBrainStore(ProjectMemory(backend))

brain = store.create(name="Oferta X", tipo="opportunity")  # gera project_id novo
store.save(brain)                                          # upsert
carregado = store.load(brain.project_id)                   # ou None
todos = store.list_all()                                   # list[ProjectBrain]
```

`tools/opportunity_tools.py` usa exatamente essa API (função
`_get_project_brain_store()`, com conexão SQLite reaproveitada — lazy
singleton por processo).

## Reutilização entre projetos (afiliados, SaaS, VitrinePro, ...)

Tudo trabalha por `project_id`/contexto, sem nada hardcoded para "afiliados"
ou para o ScalaFlow especificamente:
- `identidade.type` é livre (`"opportunity"` hoje; pode ser `"product"`,
  `"client"`, etc. no futuro).
- `origem` guarda de onde veio (plataforma/URL/país/idioma) sem assumir que é
  sempre um anúncio do Meta.
- Nada em `memory/project_brain.py` importa `tools/opportunity_tools.py` nem
  o ScalaFlow — a dependência é só numa direção (tools usa memory, não o
  contrário).

## Limitações

- **Sem lock entre processos**: se dois processos do CRIS OS rodarem ao mesmo
  tempo e investigarem a mesma oferta simultaneamente, o último `save()`
  vence (mesmo comportamento que `project_memory` já tinha antes desta fase —
  não é um problema introduzido agora).
- **Sem índice por campo**: como o conteúdo é um JSON opaco pro SQLite,
  buscar "todos os projetos com score > 80" hoje exige carregar tudo com
  `list_all()` e filtrar em Python. Aceitável na escala atual (uma pessoa,
  dezenas/centenas de projetos); não escala para milhares sem uma revisão.
- **Sem UI**: hoje só é acessível via Python/Telegram (resumo). Não há tela
  para navegar todos os Project Brains.
