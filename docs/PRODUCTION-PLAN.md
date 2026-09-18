# Production Plan (Fase 4)

Plano de produção **específico por tipo de produto**, persistido no Project
Brain. Complementa (não substitui) a Product Factory já implementada na
Fase 3 (`core/product_factory.py`) — ver `docs/PRODUCT-FACTORY.md` para o
gate de aprovação e o princípio "nunca produz sem aprovação", que continuam
absolutos e inalterados.

## O que mudou desde a Fase 3

| | Fase 3 | Fase 4 |
|---|---|---|
| Passos previstos | Uma lista FIXA (9 passos genéricos) para qualquer tipo | Uma lista **específica por `product_type`** (ver abaixo) |
| Persistência | Só existia na resposta do Telegram (`PlanoProducao` efêmero) | Persistido em `ProjectBrain.production_plan` (`ProductionPlan`) |
| Acesso | Só automático, logo após aprovar | Automático (após aprovar) **e** sob demanda ("prepare o plano de produção") |

`core/product_factory.py:criar_plano_inicial` continua sendo a **única**
lógica de decisão de passos/execução — nada foi duplicado. A Fase 4 só:
1. troca a lista fixa de passos por `_passos_para_tipo(product_type)`;
2. converte o resultado (`PlanoProducao`) num `ProductionPlan` persistido via
   a nova função pura `persistir_plano(brain, plano)`;
3. expõe isso sob demanda via `tools/product_factory_tools.py` (novo agente
   `product_factory`), reaproveitado também pelo fluxo automático de
   aprovação (`tools/product_architect_tools.py:_aprovar`) — **um único**
   ponto de preparação (`preparar_plano_producao`), dois pontos de entrada.

## Entregáveis por tipo (não presume ebook)

| Categoria | Tipos (`product_type`) | Entregáveis previstos |
|---|---|---|
| Mini-app / ferramenta | `mini_app`, `ferramenta_web`, `calculadora`, `gerador`, `quiz`, `dashboard`, `app`, `agente_ia`, `skill`, `extensao_navegador`, `template`, `biblioteca_templates`, `kit_digital` | brief, especificação funcional, telas/fluxo, prompt/build spec, stack/backend, landing page, branding, documentação |
| Micro-SaaS | `micro_saas` | brief, requisitos, MVP, arquitetura, onboarding, pricing hypothesis, landing, documentação |
| Conteúdo digital | `ebook`, `guia`, `curso`, `comunidade`, `assinatura` | brief, estrutura/capítulos, conteúdo, capa/mockup, página de vendas, criativos |
| Afiliado | `afiliado` | brief da OFERTA (nunca produto próprio), posicionamento, presell, página, criativos, conteúdo, funil, plano de aquisição |
| Comércio/revenda | `comercio_revenda` | brief, produto, **fornecedor (PENDÊNCIA)**, **margem (HIPÓTESE)**, oferta, página, criativos, canais, **logística/estoque (DEPENDÊNCIA)** |
| Qualquer outro tipo | `servico`, `produto_hibrido`, `produto_fisico`, ou um tipo futuro não mapeado | Cai no fallback genérico (9 passos da Fase 3) — **nunca lança exceção** por um tipo desconhecido |

`comercio_revenda`/`afiliado` marcam explicitamente na própria descrição do
passo quando algo é uma `PENDÊNCIA` (dado real ausente, ex.: fornecedor) ou
`HIPÓTESE` (sem custo real, ex.: margem) — nunca inventa um valor concreto
pra esses casos.

## PLANNABLE vs NOT_CONNECTED (correção pós-teste real)

**Problema encontrado**: após aprovar um `mini_app`, o único artefato real
era um brief textual genérico ("Apresentamos um mini app inovador...") — a
Product Factory nunca tentava planejar de verdade a especificação técnica,
mesmo sem nenhum builder externo conectado.

**Correção**: `NOT_CONNECTED` (`disponivel=False` no Tool Registry) passou a
significar explicitamente "não posso EXECUTAR/CONSTRUIR automaticamente com
uma ferramenta externa" — **nunca** "não posso planejar/escrever a
especificação". Para tipos de "produto digital técnico" (mini-app,
ferramenta, micro-SaaS, etc. — `core/product_factory.py:_TIPOS_ESPECIFICACAO_TECNICA`),
`gerar_especificacao_tecnica` gera, via LLM (ou template determinístico
honesto sem LLM), uma especificação real cobrindo objetivo, problema,
usuário, funcionalidades do MVP, telas, fluxo, dados de entrada/saída,
regras de negócio, proposta de valor, diferenciação, hipótese de
monetização, stack sugerida (como sugestão, não execução), prompt/build
specification, estrutura de landing page e direção de branding — usando o
contexto REAL do projeto (nicho, público, problema, promovidos do candidato
aprovado pelo Product Architect).

Cada `ToolEntry` agora tem um campo `plannable: bool` (`MINI_APP_BUILDER`,
`LANDING_PAGE_BUILDER`, `CODE_GENERATOR`, `GITHUB`, `IMAGE_GENERATOR` são
`plannable=True` mesmo com `disponivel=False`). Um passo `plannable` sem
executor fica marcado `"planejado"` (novo status, distinto de `"concluido"`
— nunca finge que algo foi construído/publicado) — e reaproveita a MESMA
especificação técnica (uma única chamada de LLM cobre todos os passos
plannable desse tipo, cost-first).

## Um único artefato real por chamada (cost-first)

Alguns tipos (ex.: `comercio_revenda`) têm **vários** passos mapeados pra
`COPY_GENERATOR` (brief, produto, margem, oferta, canais). `criar_plano_inicial`
só executa a geração de verdade **uma vez** por chamada — os demais passos
com a mesma capability ficam `pendente`, nunca reexecutam o mesmo artefato
(testado em `tests/test_production_plan.py::test_copy_generator_so_executa_uma_vez...`).

## `ProductionPlan` (persistido)

```python
@dataclass
class ProductionPlan:
    project_id: str
    product_type: str
    steps: list[dict]        # [{"nome","capability","disponivel","status","resultado"}] -- status: concluido | planejado | pendente | indisponivel
    deliverables: list[str]  # nomes dos entregaveis previstos
    dependencies: list[str]  # extraidos dos passos marcados "DEPENDÊNCIA"
    status: str              # DRAFT | IN_PRODUCTION | READY_TO_PUBLISH | PUBLISHED
```

Só chega a existir depois do Product Blueprint estar `APPROVED` (mesmo gate
desde a Fase 3) — por isso `persistir_plano` sempre marca `status =
"IN_PRODUCTION"` (o único artefato real desta fase já foi executado nesse
ponto). `READY_TO_PUBLISH`/`PUBLISHED` são estados reservados para uma fase
futura (nenhuma publicação acontece aqui).

## Comandos pelo Telegram

- "Prepare o plano de produção." → prepara (se ainda não existir) e mostra.
- "Mostre o plano de produção." → reexibe o que já foi preparado, sem
  recalcular (cost-first).
- "Mostre o manifesto atual" / "Qual o status deste projeto?" / "Mostre a
  estrutura atual do projeto" / "Quais artefatos esse projeto precisa?" →
  `GET_CURRENT_PROJECT_MANIFEST` — leitura pura e determinística (ver
  [ARTIFACT-MANIFEST.md](ARTIFACT-MANIFEST.md#get_current_project_manifest-leitura-determinística)).

**Correção de roteamento pós-teste real**: a frase exata "Cris, mostre
somente o manifesto atual deste projeto. Não gere nem altere nada." caía no
assistente genérico ("Não tenho acesso ao manifesto...") porque
`agents/orchestrator.py` nunca tinha "manifesto"/"status do projeto" nos
conjuntos de interceptação determinística — só a própria Tool reconhecia a
palavra, o orchestrator nunca chegava a escolher o agente `product_factory`
pra essa mensagem. Corrigido adicionando essas palavras/frases (incluindo
uma checagem de co-ocorrência "status"/"estrutura" + "projeto", pra cobrir
variações de fraseado como "qual o status **deste** projeto") tanto no
orchestrator quanto no `matcher` da própria Tool. Uma segunda causa
relacionada: `tools/product_factory_tools.py:_contains_any` só fazia
checagem de palavra exata (`tokens & palavras`), nunca substring contra
`palavras` — qualquer pontuação colada ("manifesto.", "projeto?") quebrava
o match. Corrigido para espelhar a mesma lógica de duas camadas
(palavra exata + substring) já usada em `Tool.matches()`.

## Testado

`tests/test_production_plan.py`: passos por tipo, exclusão de passos de
"produto próprio" pra afiliado, marcação de pendência/hipótese em
comércio/revenda, fallback genérico pra tipo desconhecido, execução única do
artefato de copy, persistência e sobrevivência a save/load, gate de
aprovação inalterado.
