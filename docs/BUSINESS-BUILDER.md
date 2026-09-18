# Business Builder

Agente que recebe um **Product Blueprint JA APROVADO** (Product Architect +
aprovação humana) e organiza a estrutura comercial em torno dele. Implementado
em `core/business_builder.py` + `tools/business_builder_tools.py` +
`agents/business_builder.py`.

Fluxo: `Product Architect → APROVAÇÃO HUMANA DO PRODUTO → BUSINESS BUILDER →
Product Factory`.

## Diferença para o Product Architect

O Product Architect (Fase 3) decide **QUAL FORMATO** de produto faz sentido.
O Business Builder (Fase 4) nunca reabre essa decisão — ele recebe o formato
já aprovado e decide **COMO transformar isso em negócio**: modelo, oferta,
monetização, funil, conteúdo, lançamento.

## Por que usa o tier ECONÔMICO (não o INTELIGENTE)

Estruturar uma oferta em cima de um formato **já aprovado** é uma tarefa mais
simples que escolher entre 22 formatos possíveis (isso já foi decidido).
Pedido explícito da Fase 4: "o Business Builder não precisa usar modelo caro
para tarefas simples" — por isso usa `OPENROUTER_MODEL_ECONOMICO`, com
fallback determinístico (sem LLM) quando o OpenRouter não estiver disponível.

## Não presume ebook

O vocabulário fechado do Product Architect (`core/product_architect.py:PRODUCT_TYPES`)
continua sendo a referência. O Business Builder funciona com qualquer um dos
22+2 formatos (mini-app, curso, micro-SaaS, afiliado, comércio/revenda,
etc.) — o formato aprovado no blueprint é passado como contexto, nunca
reescolhido.

## Contrato JSON com o LLM

Uma única chamada gera o `BusinessPlan` inteiro (todas as seções de uma vez —
cost-first, nunca uma chamada por seção). Campos principais
(`memory/project_brain.py:BusinessPlan`):

```
business_model, value_proposition, target_audience, problem, solution,
positioning, mechanism, main_offer, monetization_format,
price, price_is_hypothesis, bonuses, order_bump, upsell, downsell,
acquisition_channels, sales_channels,
sales_page_structure, headline, promise, key_arguments, objections, cta,
funnel_structure, email_sequence (5 itens), content_strategy, content_channels,
launch_strategy, plan_30_days,
evidence, assumptions, missing_evidence, risks, dependencies, next_steps,
approval_status, generated_by
```

## Regra de ouro: preço sem benchmark real é SEMPRE hipótese

`price_is_hypothesis` nunca é aceito como `false` vindo do LLM se não houver
um `price` concreto junto — o parsing (`core/business_builder.py:construir_plano_negocio`)
força `price_is_hypothesis=True` sempre que `price` for `None`, mesmo que o
LLM tenha (por erro) mandado `false`. Nenhum preço é apresentado como fato
confirmado sem dado real por trás.

## Nunca inventa métricas de tráfego

O prompt proíbe explicitamente vendas, receita, CPA, ROAS, conversão,
demanda ou tamanho de mercado — nenhum desses números existe ainda (não há
tráfego pago rodando). Estruturalmente, o próprio dataclass `BusinessPlan`
**não tem campo** para nenhuma dessas métricas (testado em
`tests/test_business_builder.py::test_nao_existe_campo_para_metricas_proibidas`)
— não é só uma instrução no prompt, é uma garantia de schema.

## Evidência do concorrente ≠ fato do produto novo (correção pós-teste real)

O anúncio de origem (`origem.source_headline`/`source_copy`) é passado como
contexto para o LLM entender público/problema/mecanismo/linguagem de
mercado — mas isso não é fonte de verdade sobre o produto que a Cris está
criando. Correção real: o LLM chegou a gerar campos como "Acesso Vitalício"
e "Lista de Fornecedor Incluso" (herdados do anúncio do concorrente) como
se fossem características do produto novo. Todos os campos textuais do
`BusinessPlan` passam por `core/evidence_guard.py:sanitizar_claims_herdadas`
antes de serem persistidos — fatos inventados/urgência-garantia sem oferta
real/promessas de resultado são removidos; ideias de funcionalidade ainda
não construída (ex.: "comunidade de usuários") são reescritas como hipótese
explícita, nunca apagadas. Ver [PRODUCT-ARCHITECT.md](PRODUCT-ARCHITECT.md#separação-evidência-do-concorrente--copy-do-produto-novo-correção-pós-teste-real)
para o detalhamento completo do Evidence Guard.

## Separação DADO / EVIDÊNCIA / HIPÓTESE / RECOMENDAÇÃO / PENDÊNCIA

A formatação da resposta no Telegram (`tools/business_builder_tools.py:_formatar_plano_negocio`)
tem uma seção dedicada "HONESTIDADE" que sempre separa:
- **Evidências** (`evidence`): o que já foi coletado antes (Opportunity
  Analyst/Product Architect).
- **Hipóteses assumidas** (`assumptions`): o que o Business Builder está
  assumindo sem confirmação.
- **Pendências** (`missing_evidence`): o que falta pra confirmar.
- **Riscos**, **dependências** e **próximos passos**.

## Gate de segurança (nunca avança sem produto aprovado)

`core/business_builder.py:blueprint_aprovado(brain)` checa
`brain.blueprint.esta_aprovado()`. Se o produto ainda não foi aprovado,
`tools/business_builder_tools.py:gerenciar_negocio` responde:

> "Esse produto ainda não foi aprovado. Primeiro precisamos aprovar o
> Product Blueprint [...]"

— nunca avança silenciosamente, nunca inventa uma aprovação. Testado em
`tests/test_fase4_tools.py::test_business_builder_bloqueia_produto_nao_aprovado`.

**Correção pós-teste real**: o gate originalmente comparava
`decision_status == "APPROVED"` direto. Mas a Product Factory avança esse
mesmo campo para `"IN_PRODUCTION"` **imediatamente** após a aprovação (no
mesmo fluxo de `_aprovar`) — então, no instante em que o Business Builder
lia o Project Brain (mesmo poucos segundos depois), a checagem exata
retornava `False` mesmo com uma aprovação real e persistida. Corrigido com
`ProductBlueprint.esta_aprovado()` (reconhece `APPROVED`, `IN_PRODUCTION` e
`COMPLETED` como "já aprovado") — a mesma fonte de verdade (`decision_status`),
sem campo novo.

**Business Plan tem seu próprio gate de aprovação, separado**:
`BusinessPlan.esta_aprovado()` só é `True` para `approval_status ==
"APPROVED"` — `READY_FOR_APPROVAL` (o estado em que o plano sempre termina
ao ser gerado) nunca conta como aprovado. Nenhuma ação desta fase depende
disso ainda (nada publica/gasta), mas o método existe para qualquer gate
futuro (ex.: publicação) que precise checar isso sem inventar um campo novo.

## Persistência e continuidade (reaproveita a Fase 3, sem memória paralela)

- Usa o **mesmo** foco por sessão (`tools/opportunity_tools.py:get_foco_atual`)
  já validado na Fase 3 (restart/reboot, isolamento por usuário/canal) —
  nenhum mecanismo novo de "projeto atual" foi criado.
- `brain.business_plan` é só mais um campo do `ProjectBrain` já existente,
  salvo com o mesmo `ProjectBrainStore.save()` — mesmo `project_id` do
  Opportunity Analyst/Product Architect, nunca um projeto novo.

## Cache (cost-first)

Uma vez calculado, `brain.business_plan` é reexibido sem nova chamada ao
OpenRouter quando a pessoa pede pra "ver"/"mostrar" o plano de novo — só
recalcula se pedir explicitamente para "montar"/"montar de novo". Testado em
`tests/test_fase4_tools.py::test_business_builder_nao_gasta_llm_de_novo_ao_mostrar_plano_ja_calculado`.

## O que o Business Builder NUNCA faz

Só planeja. Nunca publica, compra domínio, envia e-mail real, cria/altera
conta externa, faz deploy ou gasta dinheiro — isso pertence a uma fase
futura, com aprovação humana explícita separada (ver `docs/PRODUCT-FACTORY.md`
para o mesmo princípio aplicado à produção de ativos).

## Limitações conhecidas

- Sem dado de tráfego pago real, todo o funil/conteúdo/lançamento é
  **planejamento**, não validação — nada aqui prova que a oferta vai vender.
- `email_sequence` é sempre um plano de 5 e-mails; não há envio real (fora
  de escopo, ver seção "NÃO IMPLEMENTAR AINDA" do pedido da Fase 4).
- O Business Builder não tem gate de aprovação próprio (`approval_status`
  fica em `READY_FOR_APPROVAL` após gerado) porque nenhuma ação desta fase
  consome essa aprovação ainda — só o gate do Product Blueprint (herdado da
  Fase 3) é absoluto.
