# Product Blueprint

Proposta estruturada de produto para uma oportunidade já investigada. Vive
**dentro** do Project Brain (`ProjectBrain.blueprint`) — não é uma memória
paralela. Implementado em `memory/project_brain.py`.

## Por que não é uma segunda memória

"Build for one today, architecture for many tomorrow" — mas isso não
significa criar infraestrutura nova a cada conceito. O `ProductBlueprint` é
só mais uma seção do `ProjectBrain` (igual `oportunidade`, `decisao`,
`produto`), serializada no mesmo JSON, salva pela mesma
`ProjectBrainStore`, na mesma tabela `project_memory` (`data/cris_os.db`)
que já existia desde a Fase 2.

## Campos

```python
ProductBlueprint
├── project_id, user_id, tenant_id, opportunity_id   # autocontido (ver "Multiusuário futuro")
├── created_at, updated_at
├── market, country, language, niche, target_audience  # herdado da oportunidade
├── problem, opportunity_summary
├── recommended_product_type          # None ate a evidencia justificar (ver abaixo)
├── alternative_product_types: list[str]
├── product_concept, core_value, transformation, mechanism, differentiation
├── mvp_scope, production_complexity, estimated_speed_to_mvp
├── required_tools: list[str], required_integrations: list[str]
├── monetization_options: list[str], suggested_offer_structure
├── evidence, assumptions, risks, missing_evidence: list[str]
├── decision_status   # DRAFT | PENDING_APPROVAL | APPROVED | REJECTED | NEEDS_RESEARCH | IN_PRODUCTION | COMPLETED
├── reasoning_summary
├── candidates: list[dict]            # hipoteses (ver "Candidatos vs. recomendação")
└── generated_by                      # "openrouter:inteligente" | "fallback_deterministico" | "sem_evidencia"
```

## Candidatos vs. recomendação (correção pós-teste real)

O primeiro teste real revelou um erro de design: tratar "evidência
insuficiente para **decidir/aprovar**" como se fosse "evidência
insuficiente para **gerar hipóteses**". Corrigido separando dois conceitos:

- **`candidates`** — de 3 a 5 formatos plausíveis, cada um com sua própria
  hipótese de público/problema/motivo/dificuldade/velocidade de MVP/
  monetização/evidências a favor e ausentes/nível de confiança
  (`BAIXO`/`MEDIO`/`ALTO`). Populado sempre que houver **qualquer**
  evidência real (headline, copy, nicho ou score) — mesmo que nenhum
  candidato seja confiável o bastante para virar uma recomendação. Só fica
  vazio quando **realmente** não há nada (nem headline, nem copy, nem
  nicho, nem score) — nesse caso extremo o LLM nem é chamado (custo zero).
- **`recommended_product_type`** — só é preenchido quando o próprio modelo
  sinaliza `ready_for_approval: true` no contrato JSON (ver
  [OPPORTUNITY-ANALYST.md](OPPORTUNITY-ANALYST.md) não, ver
  [PRODUCT-ARCHITECT.md](PRODUCT-ARCHITECT.md#contrato-json-com-o-llm)).
  Enquanto isso não acontece, `decision_status = NEEDS_RESEARCH` **mas os
  candidatos continuam visíveis** — a resposta ao usuário nunca vira só
  "evidência insuficiente" quando há hipóteses reais para mostrar.

## Estados (`decision_status`)

| Estado | Significado |
|---|---|
| `DRAFT` | Valor inicial de um `ProductBlueprint()` vazio (nunca chega ao usuário assim) |
| `NEEDS_RESEARCH` | Sem confiança para recomendar; `candidates` mostra hipóteses (ou vazio se não há evidência nenhuma) |
| `PENDING_APPROVAL` | Há uma recomendação (`recommended_product_type`) aguardando decisão humana |
| `APPROVED` | Aprovado explicitamente pela Cris — Product Factory pode iniciar |
| `REJECTED` | Rejeitado; próxima alternativa já promovida (ou `NEEDS_RESEARCH` se não sobrar nenhuma) |
| `IN_PRODUCTION` | Product Factory já montou o plano inicial |
| `COMPLETED` | Reservado para fases futuras (não usado ainda) |

## Multiusuário futuro

`user_id`/`tenant_id` existem no schema mas **não são preenchidos** nesta
fase (`None`) — o CRIS OS ainda atende uma única pessoa. O que já foi
resolvido é o **isolamento de contexto por sessão** (ver
[PRODUCT-ARCHITECT.md](PRODUCT-ARCHITECT.md#persistência-por-usuáriochat)),
que é o alicerce que torna preencher esses dois campos, no futuro, uma
mudança aditiva — não uma reescrita.
