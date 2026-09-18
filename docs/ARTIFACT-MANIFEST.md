# Artifact Manifest (Fase 4)

Representação **lógica** das pastas/entregáveis de um projeto — independente
de Google Drive. Implementado em `core/artifact_manifest.py`.

## Princípio: DERIVADO, nunca uma segunda fonte de verdade

`gerar_manifest(brain)` reconstrói o manifest **do zero** a partir do estado
atual do `ProjectBrain` a cada chamada. Não existe nenhum dado guardado
separadamente aqui — mudou o brain, o próximo manifest gerado já reflete a
mudança, sem sincronização manual. Testado explicitamente:
`tests/test_artifact_manifest.py::test_manifest_e_derivado_nunca_segunda_fonte_de_verdade`
(duas chamadas sobre o mesmo brain sem nenhuma mudança devolvem exatamente o
mesmo conteúdo) e `test_manifest_reflete_mudanca_no_brain_imediatamente`.

## Não conecta a nenhum serviço externo nesta fase

`manifest["sincronizado_com_drive"]` é sempre `False`. É só a **estrutura**
lógica (pastas + o que cada uma contém hoje), pronta para uma fase futura
sincronizar com um provedor real de storage — nenhuma chamada de rede
acontece na geração do manifest.

## Estrutura de pastas

```
SCALAFLOW/PRODUTOS/<project_id>/
├── 01-Pesquisa/           (headline, copy, score, caminho decidido — Opportunity Analyst)
├── 02-Product-Blueprint/  (formato recomendado, status, nº de candidatos — Product Architect)
├── 03-Branding/           (vazio -- Brand Architect ainda não implementado)
├── 04-Produto/            (entregáveis do Production Plan — Product Factory)
├── 05-Pagina-de-Vendas/   (headline/estrutura — Business Builder)
├── 06-Criativos/          (vazio -- geração de imagem não habilitada nesta fase)
├── 07-Videos/             (vazio -- geração de vídeo não habilitada nesta fase)
├── 08-Copy/               (brief textual real, quando já gerado)
├── 09-Funil/              (estrutura do funil — Business Builder)
├── 10-Trafego-Pago/       (vazio -- fora de escopo até esta fase)
├── 11-Resultados/         (vazio -- nenhuma campanha rodou ainda)
└── MASTER-PROJECT.json    (resumo: project_id, tipo, status do blueprint/business plan/produção)
```

Cada pasta nunca lança exceção por falta de dado — sem informação, ela
aparece com `status: "vazio"` (ou uma explicação curta do motivo, ex. "vazio
(geração de imagem/vídeo não habilitada nesta fase)"), nunca inventa
conteúdo.

## `MASTER-PROJECT.json`

```python
{
    "project_id": "...", "nome": "...",
    "tipo_produto": "...",            # brain.blueprint.recommended_product_type
    "status_blueprint": "...",        # brain.blueprint.decision_status
    "status_business_plan": "...",    # brain.business_plan.approval_status
    "status_producao": "...",         # brain.production_plan.status
    "atualizado_em": "...",
}
```

Derivado do `ProjectBrain` a cada geração — nunca editado manualmente, nunca
uma segunda fonte de verdade (mesmo princípio do manifest inteiro).

## GET_CURRENT_PROJECT_MANIFEST (leitura determinística) — correção pós-teste real

**Problema encontrado (2 rounds de correção)**:
1. `tools/product_factory_tools.py` só regenerava o manifest quando
   `brain.artifact_manifest` ainda era `None` — depois disso, servia um
   snapshot **congelado** (gerado logo após a aprovação, antes do Business
   Builder rodar) para sempre. Resultado: `status_business_plan` aparecia
   `None` no MASTER-PROJECT mesmo com um Business Plan já persistido
   minutos depois.
2. A frase real "Cris, mostre somente o manifesto atual deste projeto. Não
   gere nem altere nada." caía no assistente genérico ("Não tenho acesso ao
   manifesto...") — o `AgentOrchestrator` nunca reconhecia "manifesto"/
   "status do projeto" na sua interceptação determinística (só a própria
   Tool reconhecia a palavra internamente).

**Correção**: `tools/product_factory_tools.py:get_current_project_manifest`
é uma função de leitura **pura**: chama só `gerar_manifest` (determinística,
sem I/O) e formata com `formatar_manifesto_get_current` — **nunca** salva
nada de volta no Project Brain (zero escrita), **nunca** chama LLM, **nunca**
exige que o plano de produção já exista (pastas sem dado aparecem "vazias").
`agents/orchestrator.py` e o `matcher` da própria Tool passaram a reconhecer
"manifesto"/"manifest" e uma checagem de co-ocorrência "status"/"estrutura"
+ "projeto" (cobre variações de fraseado sem depender de uma frase fixa).

**Formato de resposta**: minimalista de propósito — só status curtos por
pasta (nunca despeja o conteúdo completo do Business Plan ou de um
artefato longo):

```
📁 MANIFESTO DO PROJETO

project_id: ...
project_name: ...

01-Pesquisa/
  evidências disponíveis: N
...
MASTER-PROJECT
  status_blueprint: ...
  status_business_plan: ...
  status_producao: ...
  updated_at: ...
```

## Comando pelo Telegram

"Mostre o manifesto atual" / "Qual o status deste projeto?" / "Mostre a
estrutura atual do projeto" / "Quais artefatos esse projeto precisa?" →
`GET_CURRENT_PROJECT_MANIFEST`. Continua atrás do gate de aprovação do
Product Blueprint (`ProductBlueprint.esta_aprovado()`) — nunca uma porta
aberta sem controle.

## Testado

`tests/test_artifact_manifest.py`: as 11 pastas sempre presentes mesmo para
projeto vazio, `sincronizado_com_drive` sempre `False`, natureza derivada
(não é segunda fonte de verdade), reflexo imediato de mudança no brain,
pasta "04-Produto" refletindo o Production Plan real.
`tests/test_fase4_contaminacao_e_sincronia.py`: manifesto reflete Business
Plan gerado depois da produção (correção do bug de sincronia), nunca
inventa aprovação, sobrevive a restart.
`tests/test_fase4_qualidade_e_manifesto_deterministico.py`: zero chamadas
LLM, zero alteração no Project Brain (`store.save` nunca chamado), nunca
despeja o Business Plan inteiro, nunca chama o Business Builder, funciona
sem production plan preparado, continua bloqueado sem aprovação.
`tests/test_fase4_routing.py`: a frase real exata do bug ("Cris, mostre
somente o manifesto atual deste projeto...") e variações roteadas
corretamente pro agente `product_factory`; conversas comuns não capturadas
pela nova detecção.
