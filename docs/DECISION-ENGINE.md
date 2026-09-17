# Decision Engine

Decide o caminho de uma oportunidade a partir de evidência real — **sem
LLM**, 100% determinístico. Implementado em `core/decision_engine.py`
(módulo puro, sem I/O, fácil de testar — ver `tests/test_opportunity_analyst.py`).

## Caminhos possíveis

`CREATE_OWN_PRODUCT` · `AFFILIATE` · `COMMERCE_RESALE` · `INVESTIGATE_MORE` · `DISCARD`

## Regras (nesta ordem — a primeira que bater decide)

1. Sem `score` do ScalaFlow → `INVESTIGATE_MORE` (dado essencial ausente).
2. `score < 50` → `DISCARD` (motivo registrado no Project Brain, para não
   reanalisar a mesma oferta de novo).
3. Nenhuma fonte externa (TikTok/Instagram/YouTube/Trends) confirmou sinal →
   `INVESTIGATE_MORE`.
4. Só **1** fonte externa confirmou → `INVESTIGATE_MORE` (pede mais fontes).
5. **2 ou mais** fontes externas confirmaram → `AFFILIATE`.

## Por que o motor NUNCA decide `CREATE_OWN_PRODUCT` ou `COMMERCE_RESALE` sozinho

Decisão de produto explícita da Cris: **"produto viral não significa
automaticamente produto lucrativo"** e **"não assumir automaticamente que
tudo deve virar produto próprio"**.

Tecnicamente: o ScalaFlow mineira **anúncios**, não fornecedores, programas
de afiliados, comissões, estoque ou modelo de negócio. O motor não tem
informação suficiente para recomendar "crie um produto" ou "revenda isso"
com responsabilidade — então nunca chega lá sozinho. Esses dois caminhos
continuam existindo como valores válidos em `CAMINHOS_VALIDOS`, prontos para
quando:
- uma fase futura conectar uma fonte real de dado de fornecedor/afiliação, ou
- a própria Cris decidir manualmente e registrar isso no Project Brain
  (`decisao.recommended_path`, `decisao.user_approved`).

## `evidence_level`

- `"baixo"`: 0 fontes externas (ou score ausente/baixo).
- `"medio"`: 1–2 fontes externas.
- `"alto"`: 3+ fontes externas.

## Seções 5–7 do pedido original (produto próprio / afiliação / comércio)

Implementadas como **preparo estrutural honesto**, não como análise
fabricada:

- `sugerir_formatos_produto_proprio(decisao)` — só retorna algo quando
  `decisao.path == "CREATE_OWN_PRODUCT"` (hoje isso nunca acontece
  automaticamente — ver acima). Retorna uma estrutura placeholder explícita
  ("formato ainda não é avaliado automaticamente nesta fase"), pronta para
  uma fase futura preencher com avaliação real por nicho/formato.
- `preparar_analise_afiliacao(sinais)` — sempre retorna
  `"Sem evidencia disponivel (ScalaFlow nao mineira programas de afiliados)."`
  para `programa_afiliados`, e `None` para plataforma/comissão/países/
  moeda/restrições/checkout/presell — porque **não existe fonte de dado**
  para isso ainda. Nunca afirma que existe um programa sem evidência.
- `preparar_analise_comercio(sinais)` — mesma lógica para
  demanda/fornecedor/margem/preço/logística: `"Sem evidencia disponivel"` +
  aviso explícito de não comprar/criar loja/contratar fornecedor nesta fase.

## Aprovação humana

Toda decisão sai com `decision_status = "PENDING_APPROVAL"`
(`ProjectBrain.decisao.decision_status`). A Cris pode pesquisar, analisar,
comparar e organizar livremente; qualquer ação envolvendo dinheiro,
campanhas, publicação, e-mails externos, contas externas ou compras
**exige autorização explícita** e **não está implementada nesta fase**.

## Testes confirmados

Ver `tests/test_opportunity_analyst.py` (9 testes de Decision Engine, todos
sem rede):
- score baixo → `DISCARD`.
- score ausente → `INVESTIGATE_MORE`.
- 0 fontes → `INVESTIGATE_MORE`.
- 1 fonte → `INVESTIGATE_MORE`.
- 2+ fontes → `AFFILIATE`.
- nunca retorna `CREATE_OWN_PRODUCT`/`COMMERCE_RESALE` sozinho (testado com
  score alto + 4 fontes confirmadas — mesmo assim fica em `AFFILIATE`).
- `sugerir_formatos_produto_proprio` vazio fora de `CREATE_OWN_PRODUCT`.
- `preparar_analise_afiliacao`/`preparar_analise_comercio` nunca inventam
  programa/demanda.

## Limitações

- Regras são heurísticas simples (contagem de fontes + limiar de score), não
  um "score de oportunidade" ponderado. Servem para este piloto; uma versão
  futura pode pesar `viral_score`/`engagement_score`/`avg_interest` de forma
  mais fina.
- Não considera o **histórico de decisões anteriores** da Cris (ex.: "ela
  sempre descarta ofertas deste nicho") — isso ficaria natural de acrescentar
  usando o próprio Project Brain (`historico.decisions` de outros projetos),
  mas não foi implementado agora.
