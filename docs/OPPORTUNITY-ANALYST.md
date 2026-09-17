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

**Continuação sem palavra inicial fixa** (corrigido na revisão da Fase 2):
se o **último agente da conversa** já foi o `opportunity_analyst`, uma
mensagem nova que contenha um nome de plataforma (tiktok/meta/facebook/
instagram/youtube/google/trends) ou uma referência ("essa", "isso",
"aquela", "dessa", "nessa", "aparece", "evidência", "fonte") continua
roteando para o `opportunity_analyst` — **sem exigir que a frase comece**
com essa palavra. Isso só entra em jogo quando o agente anterior já era o
Opportunity Analyst, então não risca o roteamento de mensagens novas e não
relacionadas (ex.: "crie uma legenda pro meu tiktok" continua indo pro
`social_media` normalmente, porque o último agente não era o Opportunity
Analyst). Ver `AgentOrchestrator._eh_continuacao_opportunity` e
`_CONTINUACAO_OPORTUNIDADE_KEYWORDS` em `agents/orchestrator.py`.

Essa mesma lista de palavras também precisa existir nas *keywords* da
`Tool` em `tools/opportunity_tools.py:get_tools()` — o `SpecialistAgent`
re-checa a Tool de forma independente do roteamento do orchestrator: sem
isso, o agente era escolhido certo mas não achava a ferramenta e caía no
LLM (bug real encontrado e corrigido nesta revisão).

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
5. Mensagem usa uma **palavra de referência** ("essa", "isso", "aquela",
   "dessa", "nessa", "este", ...) → reusa o **projeto em foco**: a última
   oportunidade investigada (`_foco_atual_project_id`), buscando o anúncio
   de novo pelo `source_offer_id` salvo no Project Brain — nunca escolhe
   "a melhor oferta" do zero quando a mensagem claramente se refere a algo
   já discutido. Se não houver nenhum foco ainda (primeira mensagem da
   sessão), responde pedindo pra indicar a oportunidade em vez de adivinhar.
6. Caso contrário (nenhum sinal explícito, ex.: "investigue minha melhor
   oferta") → a oferta de maior score no ScalaFlow, sem filtro.

Isso **reaproveita** a função já existente do Marco 1 em vez de duplicar
lógica de consulta ao Supabase.

**Limitação conhecida e aceita nesta fase**: o "projeto em foco" é global
por processo, não por usuário (`tools/opportunity_tools.py` mantém uma
única variável, não um dicionário por `user_id`). Isso é seguro enquanto o
CRIS OS atende uma única pessoa (`TELEGRAM_ALLOWED_USER_ID`). Passar a ser
por usuário exigiria mudar a assinatura hoje compartilhada de `Tool.fn`
(`tools/base.py`), que só recebe o texto da mensagem — fica para quando o
multi-tenant for implementado de verdade.

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
- Sequência real de conversa testada de ponta a ponta (mesmo
  `AgentOrchestrator`, mesmo `user_id`): "investigue uma das minhas melhores
  ofertas" → "analise esta oportunidade" → "quais sinais temos dessa
  oportunidade?" → "isso aparece no TikTok?" → "qual caminho faz sentido
  para essa oportunidade?" — as 5 mensagens respondem sobre o **mesmo**
  projeto, sem repetir link nem reintroduzir a oferta.

## Limitações

- "tiktok"/"instagram"/"youtube"/etc. **não** entram na interceptação
  *primária* do Opportunity Analyst (`_OPPORTUNITY_KEYWORDS`): essas
  palavras já pertencem ao agente `social_media` (ex.: "crie uma legenda pro
  meu tiktok"), e usá-las como gatilho primário quebraria o roteamento desse
  agente para qualquer menção a uma rede social. Elas só valem como sinal de
  **continuação** (`_CONTINUACAO_OPORTUNIDADE_KEYWORDS`), e só quando o
  último agente da conversa já era o Opportunity Analyst — daí não conflita.
- O "projeto em foco" (contexto do follow-up) é global por processo, não
  por usuário — ver a nota na seção "Como resolve QUAL oferta investigar".
- Seleção de oferta por "melhor score" / "salvei" / "favorito" pega o de
  **maior score** dentro do filtro, não necessariamente o mais recente
  (mesma ordenação que `tools/scalaflow_tools.py` já usa).
- `niche` inconsistente na origem (quase sempre "Geral") limita a correlação
  por nicho — já mitigado priorizando `keyword`.
