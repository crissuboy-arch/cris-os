# Opportunity Analyst

Agente que investiga **uma** oferta específica do ScalaFlow (diferente do
`scalaflow_intel`, que lista/filtra várias). Implementado em
`agents/opportunity_analyst.py` + `tools/opportunity_tools.py`.

## Como é acionado (sem LLM)

`agents/orchestrator.py` intercepta por palavra-chave, **antes** de tentar o
LLM e **antes** da interceptação do `scalaflow_intel` (para "investigue
minhas ofertas" não virar uma listagem):

```
investigue, investigar, investigacao, analise, analisar, analisa,
oportunidade, oportunidades, sinais, sinal, caminho, decisao, decision
```

## Como resolve QUAL oferta investigar

Não há um seletor explícito de oferta na conversa ainda (ver Limitações).
Ordem de resolução, em `tools/opportunity_tools.py:_resolver_oferta`:

1. **URL/ID explícito** na mensagem (ex.: um link
   `facebook.com/ads/library/?id=NNNN` ou um número longo) → busca exata por
   `ad_library_id`.
2. Mensagem menciona **"favorito"** → o favorito de maior score
   (reaproveita `tools/scalaflow_tools.py:_buscar_anuncios(somente_favoritos=True)`).
3. Mensagem menciona **"salv"** (salvei/salvo/salva) → a oferta salva de
   maior score.
4. Mensagem menciona **"escalad"** → a oferta escalada (`score >= 80`) de
   maior score.
5. Caso contrário → a oferta de maior score no ScalaFlow, sem filtro.

Isso **reaproveita** a função já existente do Marco 1 em vez de duplicar
lógica de consulta ao Supabase.

## Como cruza sinais reais (TikTok obrigatório, conforme pedido)

O ScalaFlow já mineira TikTok, Instagram, YouTube e Google Trends para as
tabelas `tiktok_minerados`, `instagram_minerados`, `youtube_minerados` e
`google_trends_minerados` (confirmado lendo
`escalaflow-insights/supabase/migrations/`). **Nada disso foi reconstruído**
— o Opportunity Analyst só lê (SELECT) essas tabelas.

**Importante, e declarado sempre no relatório**: essas tabelas **não têm
chave estrangeira** para `collected_ads`. `tiktok_minerados.hashtag`,
`instagram_minerados.search`, `youtube_minerados.query` e
`google_trends_minerados.keyword` são só o termo que foi minerado — não um
ID de anúncio. Por isso a correlação é **por palavra-chave**
(`ilike '%termo%'`), usando nesta ordem de prioridade:

1. `collected_ads.keyword` (o termo de busca que o próprio ScalaFlow salvou
   ao minerar o anúncio — o mais confiável).
2. `collected_ads.niche`, só se for diferente de `"Geral"` (que é o valor de
   ~96% dos anúncios reais na base — não é um termo de busca útil).
3. `collected_ads.advertiser`.

Se nenhum termo tiver correspondência (ou não houver termo nenhum), a fonte
volta **"Sem evidência disponível nesta fonte."** — nunca inventa.

## O que NÃO é preenchido (de propósito)

Público, problema, promessa, mecanismo, ângulos e padrões criativos exigiriam
interpretar o *texto* do anúncio — isso é trabalho de LLM/humano, e esta fase
não usa LLM. Essas seções não aparecem no relatório resumido do Telegram;
ficam marcadas internamente como
`"Sem analise qualitativa disponivel nesta fase (requer IA, nao habilitada)."`
em vez de inventadas.

"Concorrência" no relatório é uma contagem **objetiva e interna** — quantos
outros anúncios no próprio ScalaFlow usam o mesmo `keyword` — não é dado de
concorrência de mercado real.

## Resposta no Telegram

```
🔎 OPORTUNIDADE ANALISADA

Produto: <advertiser ou headline>
Mercado: <país>
Score: <score>

Sinais:
Tiktok: ...
Instagram: ...
Youtube: ...
Google_trends: ...
Concorrencia (ScalaFlow, interno): ...

CAMINHO: <emoji> <label>
Motivo: ...
Risco principal: ...
Proximo passo: ...

Projeto: <project_id>
```

O relatório completo (todos os sinais, métricas cruas) fica no Project Brain
(`docs/PROJECT-BRAIN.md`), não no Telegram.

## Testes confirmados

- "Cris, investigue minha melhor oferta." → resolve por score, cruza sinais
  reais, decide, salva no Project Brain.
- "Cris, investigue meus favoritos." / "...minhas ofertas salvas." /
  "...as ofertas escaladas." → resolução por ação funciona.
- Re-investigar a **mesma** oferta reaproveita o **mesmo** `project_id`
  (não cria projeto duplicado) e acumula histórico (`agent_runs`,
  `decisions`).
- Oferta inexistente (`ad_library_id` que não existe) → mensagem clara, sem
  exceção.
- Oferta sem `keyword`/nicho útil/anunciante → zero chamadas de rede extras,
  "Sem evidência disponível" em todas as fontes (cost-first).
- Falha de rede/timeout em qualquer fonte → capturada, não derruba o
  processo, segue para as próximas fontes.

## Limitações

- **Sem contexto de conversa**: "Cris, isso aparece no TikTok?" (perguntando
  sobre a oportunidade discutida na mensagem anterior) **não funciona ainda**
  — a mensagem não contém nenhuma das palavras-chave de interceptação nem
  começa com uma palavra de "followup" (o mecanismo de followup existente
  exige que a PRIMEIRA palavra da mensagem seja um gatilho como "isso"/"sim";
  como a Cris normalmente escreve "Cris, isso...", a primeira palavra é
  "Cris," e o followup não dispara). Um pedido autocontido funciona bem hoje
  (ex.: "Investigue se aparece no TikTok a oferta com o ID ..."). Ligar isso
  a um project_id "em foco" fica para uma fase futura.
- Deliberadamente **não** adicionei "tiktok"/"instagram"/"youtube" às
  palavras-chave de interceptação do Opportunity Analyst: essas palavras já
  pertencem ao agente `social_media` (ex.: "crie uma legenda pro meu
  tiktok"); adicioná-las quebraria o roteamento desse agente para qualquer
  menção a uma rede social.
- Seleção de oferta por "melhor score" / "salvei" / "favorito" pega o de
  **maior score** dentro do filtro, não necessariamente o mais recente
  (mesma ordenação que `tools/scalaflow_tools.py` já usa).
- `niche` inconsistente na origem (quase sempre "Geral") limita a correlação
  por nicho — já mitigado priorizando `keyword`.
