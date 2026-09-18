# Tool Registry

Catálogo de ferramentas de **produção** de ativos que a Product Factory usa,
sem acoplar a Factory a nenhum fornecedor específico. Implementado em
`core/tool_registry.py`.

**Não confundir** com `tools/base.py:Tool` (as ferramentas dos *agentes* do
Telegram, ex.: `top_produtos_scalaflow`). Este registry é sobre ferramentas
de *produção* de ativos (gerar imagem, gerar vídeo, publicar site) — um
conceito novo da Fase 3.

## Princípio: não hardcodar fornecedor

A Product Factory pede uma **capability** (ex.: `COPY_GENERATOR`) e recebe
quem estiver registrado para ela. Hoje é o OpenRouter; amanhã pode ser
outra coisa, sem mudar o código da Factory.

```python
registry.executar(COPY_GENERATOR, blueprint=blueprint, llm=llm_economico)
```

## Status legível por capability (Fase 4)

Além do booleano `disponivel` (o que o código usa pra decidir se executa),
cada `ToolEntry` agora também tem um `status` legível — `AVAILABLE`,
`AVAILABLE_MANUAL` (existe, mas só de forma manual/fora do CRIS OS) ou
`NOT_CONNECTED`. Não substitui `disponivel`; é só uma etiqueta mais rica pra
exibir/documentar.

## PLANNABLE vs NOT_CONNECTED (correção pós-teste real)

`NOT_CONNECTED` significa "não posso EXECUTAR/CONSTRUIR automaticamente com
uma ferramenta externa" — **nunca** "não posso PLANEJAR ou ESCREVER a
especificação". Cada `ToolEntry` tem um campo `plannable: bool`: quando
`True` (mesmo com `disponivel=False`), a Product Factory ainda gera uma
especificação/brief real via LLM para essa capability (ver
[PRODUCTION-PLAN.md](PRODUCTION-PLAN.md#plannable-vs-not_connected-correção-pós-teste-real)).
Bug real corrigido: antes disso existir, um `mini_app` aprovado só recebia
um brief textual genérico, mesmo sem builder conectado — a Cris já podia
planejar a especificação técnica internamente, só não estava fazendo isso.

## Capabilities de PRODUÇÃO de ativos

| Capability | Status | Plannable? | Fornecedor | Observação |
|---|---|---|---|---|
| `COPY_GENERATOR` | **AVAILABLE** | — | OpenRouter (tier econômico) | Único executor real — prova o contrato ponta a ponta |
| `MINI_APP_BUILDER` | **AVAILABLE_MANUAL** | **Sim** | ferramenta manual da Cris | A Cris já tem um criador próprio (prompt → mini-app); a Product Factory não pode executá-la sozinha, mas PLANEJA (especificação/prompt de build) via LLM |
| `IMAGE_GENERATOR` | NOT_CONNECTED | **Sim** | — | Geração de imagem em si não acontece; direção/brief de branding (texto) é plannable |
| `VIDEO_GENERATOR` | NOT_CONNECTED | Não | — | Assets caros não gerados nem planejados em detalhe nesta fase |
| `LANDING_PAGE_BUILDER` | NOT_CONNECTED | **Sim** | — | Deploy não acontece; copy/estrutura da landing é plannable |
| `CODE_GENERATOR` | NOT_CONNECTED | **Sim** | — | Execução não acontece; especificação técnica é plannable |
| `DRIVE_STORAGE` | NOT_CONNECTED | Não | — | Fundação apenas |
| `GITHUB` | NOT_CONNECTED | **Sim** | — | Deploy/push não acontece; índice de documentação é plannable |
| `VERCEL` | NOT_CONNECTED | Não | — | Fundação apenas |

## Capabilities de PLANEJAMENTO comercial (Fase 4)

| Capability | Status | Observação |
|---|---|---|
| `SALES_PAGE_PLANNER` | NOT_CONNECTED | Gerado hoje INLINE dentro do Business Plan único (`core/business_builder.py`), não como execução separada |
| `FUNNEL_PLANNER` | NOT_CONNECTED | Idem |
| `EMAIL_SEQUENCE_PLANNER` | NOT_CONNECTED | Idem |
| `CONTENT_PLANNER` | NOT_CONNECTED | Idem |
| `LAUNCH_PLANNER` | NOT_CONNECTED | Idem |

Essas 5 capabilities existem hoje como **campos** do `BusinessPlan`
(`sales_page_structure`, `funnel_structure`, `email_sequence`,
`content_strategy`, `launch_strategy`), calculados numa única chamada de LLM
— reservadas aqui só pra documentar a intenção de uma fase futura separar
isso em execuções independentes.

## Por que `BUSINESS_BUILDER` e `PRODUCT_FACTORY` NÃO estão registrados aqui

Este registry cataloga capabilities de **produção de ativos**, não os
próprios agentes/fases que o consomem. `business_builder` e
`product_factory` são agentes completos (`agents/business_builder.py`,
`agents/product_factory.py`), invocados diretamente pelo orchestrator — nunca
através de `registry.executar(...)`. Registrá-los aqui seria uma capability
"de mentirinha" (nunca executada por este mecanismo) — "nada de capability
falsa" é uma regra explícita desde a Fase 4.

## Nunca crasha a Product Factory

```python
def executar(self, capability, **kwargs) -> str:
    entry = self._entries.get(capability)
    if not entry:
        return f"Capability '{capability}' nao esta registrada..."
    if not entry.disponivel or not entry.executor:
        return f"Capability '{capability}' registrada mas indisponivel ({entry.observacao})."
    try:
        return entry.executor(**kwargs)
    except Exception as exc:
        return f"Falha ao executar '{capability}': {exc}"
```

Uma capability desconhecida ou indisponível nunca lança exceção — devolve
uma mensagem clara. Testado em `tests/test_product_architect.py`.

## Como registrar uma nova capability (fase futura)

```python
registry.registrar(
    MINI_APP_BUILDER,
    provider_name="nome-do-fornecedor",
    disponivel=True,
    executor=minha_funcao_que_gera_o_mini_app,
    observacao="descricao curta",
)
```

Nenhuma mudança na Product Factory é necessária — ela já sabe checar
`registry.disponivel(capability)` antes de tentar usar.
