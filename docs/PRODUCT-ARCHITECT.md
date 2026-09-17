# Product Architect

Agente que recebe uma oportunidade já investigada (Opportunity Analyst +
Decision Engine) e propõe **hipóteses de formato de produto**, gerenciando
aprovação/rejeição humana antes de qualquer produção. Implementado em
`agents/product_architect.py` + `tools/product_architect_tools.py` +
`core/product_architect.py`.

Fluxo: `ScalaFlow → Opportunity Analyst → Decision Engine → PRODUCT
ARCHITECT → aprovação humana → Product Factory`.

## Por que usa LLM (diferente do Decision Engine)

O Decision Engine (Fase 2) decide entre 5 caminhos usando regras
determinísticas simples (contagem de fontes com sinal). Escolher **qual
formato de produto** faz sentido entre 22 opções — pesando público,
problema, complexidade de produção, velocidade de MVP, monetização — exige
julgamento que uma tabela de regras não cobre com honestidade. Por isso usa
o OpenRouter (tier **INTELIGENTE**, a mesma arquitetura da Fase 2.5), com
fallback determinístico quando o OpenRouter não está disponível.

## Vocabulário fechado de formatos

`core/product_architect.py:PRODUCT_TYPES` — 22 formatos (mini_app,
ferramenta_web, calculadora, gerador, quiz, dashboard, micro_saas, app,
agente_ia, skill, extensao_navegador, template, biblioteca_templates,
kit_digital, ebook, guia, curso, comunidade, assinatura, servico,
produto_hibrido, produto_fisico) + `afiliado`/`comercio_revenda` (cobrem os
caminhos `AFFILIATE`/`COMMERCE_RESALE` do Decision Engine). Qualquer tipo
fora dessa lista, vindo do LLM, é **descartado** na validação — nunca
aceito às cegas.

## Contrato JSON com o LLM

O prompt (`core/product_architect.py:_prompt`) exige exatamente:

```json
{
  "candidates": [
    {"product_type": "...", "audience_hypothesis": "...", "problem": "...",
     "why_it_fits": "...", "production_difficulty": "baixa|media|alta",
     "estimated_speed_to_mvp": "...", "monetization": ["..."],
     "supporting_evidence": ["..."], "missing_evidence": ["..."],
     "confidence": "BAIXO|MEDIO|ALTO"}
    // 3 a 5 itens
  ],
  "recommendation": {"product_type": "..." ou null, "reasoning_summary": "...", "ready_for_approval": true|false},
  "assumptions": ["..."],
  "risks": ["..."]
}
```

`ready_for_approval` só deve ser `true` quando a evidência for realmente
forte — o próprio prompt instrui: "na dúvida, `false`". Isso é o que produz
a distinção candidatos-vs-recomendação documentada em
[PRODUCT-BLUEPRINT.md](PRODUCT-BLUEPRINT.md#candidatos-vs-recomendação).

## Persistência por usuário/chat (correção pós-teste real)

**Problema encontrado no primeiro teste real pelo Telegram**: "qual
oportunidade está em foco" vivia numa variável Python
(`_foco_atual_project_id`) em `tools/opportunity_tools.py` — perdida a cada
restart do processo, e compartilhada por **todos** os usuários (sem
isolamento). Depois de reiniciar o bot, "essa oportunidade" respondia "não
sei a qual oportunidade você se refere", mesmo já tendo investigado uma
antes.

**Correção**: `memory/project_brain.py:UserFocusStore` persiste o foco
reaproveitando a **mesma** infraestrutura do Project Brain
(`ProjectMemory`/`data/cris_os.db`) — não cria uma segunda fonte de
verdade. Cada foco é um `KnowledgeItem` guardado sob uma chave lógica
`__focus__:<session>` (nunca colide com um `project_id` real, que sempre
começa com `proj_`). `session` é `IncomingMessage.session`
(`"telegram:6460872429"`, canal+usuário) — já existia no core, não foi uma
invenção nova.

Isso exigiu **threadar `session` por toda a cadeia de chamada**:
`Gateway.handle` → `AgentOrchestrator.handle` → `SpecialistAgent.generate(message, session)`
→ `Tool.execute(input_text, session)` → `fn(entrada, session)`. Para não
quebrar as dezenas de `Tool`s existentes (`coding_tools.py`,
`copy_tools.py`, `sales_tools.py`, etc., todas com `fn(entrada)` de um
argumento só), `Tool.execute` usa `inspect.signature` para só passar
`session` às funções que declaram esse segundo parâmetro — as demais
continuam recebendo só o texto, sem precisar mudar uma linha.

**Testado de verdade**: `tests/test_persistencia_foco.py` simula um
restart real — fecha a conexão SQLite, abre outra a partir do **mesmo
arquivo**, e confirma que o foco (e o `ProjectBrain` inteiro) continuam
recuperáveis. Confirmado também manualmente: reboot completo do computador,
`project_id` idêntico (`proj_cb094b4ef6a4`) recuperado do disco.

**Isolamento**: duas sessões diferentes nunca compartilham foco —
`tests/test_persistencia_foco.py` cobre isso com duas sessões simultâneas,
cada uma com seu próprio projeto, confirmando que atualizar uma não afeta a
outra.

**Limitação ainda real**: `user_id`/`tenant_id` continuam não populados no
`ProductBlueprint` em si (ver [PRODUCT-BLUEPRINT.md](PRODUCT-BLUEPRINT.md)).
O que foi resolvido é o isolamento de *contexto de conversa*, não uma
autenticação/autorização multiusuário completa (fora de escopo desta fase).

## Reconhecimento de link da Meta Ads Library (correção pós-teste real)

**Problema encontrado**: colar um link puro (`https://www.facebook.com/ads/library/?id=...`)
sem nenhuma palavra-chave fazia a mensagem cair no LLM genérico, que
respondia "não consigo abrir links externos" — o roteamento determinístico
não tinha nenhum jeito de reconhecer "isto é uma referência a um anúncio do
ScalaFlow" sem uma palavra como "investigue".

**Correção**: `tools/opportunity_tools.py:detectar_ad_library_id` (regex
para o padrão da URL ou um ID numérico cru) é usado em **dois** pontos:

1. `agents/orchestrator.py:_eh_comando_opportunity` — o roteamento
   reconhece o link e força a interceptação determinística (nunca chama o
   LLM para decidir o agente).
2. `Tool.matcher` (novo campo opcional em `tools/base.py:Tool`) — mesmo com
   o agente certo já escolhido, a própria Tool precisa "achar" a mensagem;
   sem isso, ainda cairia no LLM genérico dentro do agente.

Um link com um ID que **não existe** no ScalaFlow devolve uma mensagem
clara ("Não encontrei nenhum anúncio com ad_library_id=... no ScalaFlow.")
— nunca inventa dado, nunca aciona o LLM genérico.

## Divisão de mensagens longas do Telegram (correção pós-teste real)

**Problema encontrado**: uma resposta com 3-5 hipóteses de produto (cada
uma com ~8 linhas) facilmente passa dos 4096 caracteres que o Telegram
aceita por mensagem — `reply_text` levantava
`telegram.error.BadRequest: Message is too long` e a resposta **nunca
chegava**, mesmo tendo sido gerada corretamente (OpenRouter respondeu,
custo foi cobrado).

**Correção**: `channels/telegram/bot.py:_dividir_mensagem` quebra qualquer
resposta acima de 4000 caracteres em várias mensagens, cortando em quebras
de linha (nunca no meio de uma palavra). Aplica-se a **qualquer** agente,
não só ao Product Architect — protege o sistema inteiro contra esse limite.

## Aprovação humana (nunca automática)

- Só um conjunto fechado de palavras/frases conta como aprovação:
  `aprovado`, `aprovada`, `aprovo`, `autorizado`, `autorizo`, `confirmado`,
  `confirmo`, `pode criar`, `pode seguir`, `pode produzir`, `pode começar`,
  `bora criar`. Rejeição: `rejeitado`, `rejeito`, `não gostei`, `quero
  outra`, `outra alternativa`.
- **Só conta como continuação** (aprovação/rejeição) quando o **último
  agente da conversa** já era o `product_architect` — uma frase ambígua em
  outro contexto nunca é interpretada como aprovação (testado
  explicitamente: uma pergunta contendo a palavra "aprovar" dentro de uma
  pergunta exploratória — "...sem aprovar nenhum ainda?" — nunca dispara o
  gate).
- Quando não há uma recomendação única (só hipóteses), aprovar exige **citar
  o formato pelo nome** (ex.: "Aprovo o formato curso") — nunca adivinha
  qual candidato o usuário quis dizer.
- Toda aprovação/rejeição fica registrada em
  `ProjectBrain.historico.approvals`.

## Testes confirmados (real, pelo Telegram)

- Link da Meta Ads Library reconhecido deterministicamente, oportunidade
  real recuperada (Ana Martin / US / score 99).
- "Investigue essa oportunidade" / "Que produto deveríamos criar?" / "Quais
  formatos são candidatos?" — todos operando sobre o **mesmo** `project_id`
  (`proj_cb094b4ef6a4`).
- Reinício do processo **e** reboot completo do computador — foco e
  `ProjectBrain` recuperados do disco, mesmo `project_id`.
- Pergunta exploratória contendo "aprovar" não disparou aprovação.
- Resposta de hipóteses (>4000 caracteres) entregue dividida, sem erro do
  Telegram.
- Reaproveitamento de candidatos já calculados sem nova chamada ao
  OpenRouter (custo zero na segunda pergunta sobre o mesmo formato).

## Limitações conhecidas

- Paráfrases não previstas de "quais alternativas" (ex.: "quais formatos
  são candidatos" sem a palavra "alternativas") podem não reconhecer
  candidatos já calculados e disparar uma nova chamada ao LLM — coberto
  parcialmente (`candidatos`, `possibilidades`, `hipóteses`, `comparar` já
  reconhecidos), mas não é uma cobertura semântica completa.
- `user_id`/`tenant_id` do `ProductBlueprint` continuam vazios (ver
  [PRODUCT-BLUEPRINT.md](PRODUCT-BLUEPRINT.md#multiusuário-futuro)).
- O classificador de roteamento do `AgentOrchestrator` ainda não usa o tier
  ECONÔMICO (limitação já documentada desde a Fase 2.5, inalterada aqui).
- Sem análise qualitativa de copy via IA fora do próprio Product Architect
  — Opportunity Analyst continua 100% determinístico, por design.
