# MARCO 1 — CRIS OS ↔ SCALAFLOW ↔ TELEGRAM

**Data do marco:** 17/09/2026
**Status:** ✅ Funcionando localmente (piloto, sem Ollama)

## Objetivo

Provar o ciclo completo:

```
Cris (Telegram) → CRIS OS → interpretação determinística da intenção
→ ScalaFlow (Supabase, dado real) → resposta formatada no Telegram
```

Sem depender de mineração nova, sem alterar o ScalaFlow web, sem alterar o
schema do Supabase, e — para este piloto — sem exigir o Ollama rodando.

## Arquitetura atual (deste fluxo)

```
Telegram (usuário autorizado)
  │
  ▼
channels/telegram/bot.py  (TelegramChannel._on_message)
  │  monta IncomingMessage(channel, sender_id=update.effective_user.id, text)
  ▼
core/gateway.py  (Gateway.handle)
  │  1) checa TELEGRAM_ALLOWED_USER_ID (Gateway._autorizado)
  │  2) delega para o orquestrador
  ▼
agents/orchestrator.py  (AgentOrchestrator.handle → _escolher_agente)
  │  ordem de decisão:
  │  1. agente fixado via /use
  │  2. followup (mensagem curta reaproveitando o último agente)
  │  3. INTERCEPTAÇÃO DETERMINÍSTICA do ScalaFlow (_eh_comando_scalaflow) — 
  │     NÃO chama LLM se a mensagem tiver palavra-chave do ScalaFlow
  │  4. roteamento normal (LLM primeiro, keyword como fallback) — para
  │     qualquer coisa que não seja ScalaFlow (ex.: "Oi", inalterado)
  ▼
agents/scalaflow_intel.py  (SpecialistAgent "scalaflow_intel")
  │  agents/base_specialist.py: generate() tenta uma Tool antes do LLM
  ▼
tools/scalaflow_tools.py  (Tool "top_produtos_scalaflow")
  │  _buscar_top_produtos(texto) faz parsing 100% determinístico
  │  (regex/dicionários — sem IA) de: limite, país, plataforma, nicho/
  │  palavra-chave, salvos/favoritos/escalados
  ▼
Supabase REST (PostgREST) — tabelas reais:
  │  collected_ads     (anúncios coletados, tem score/created_at/ad_url/etc.)
  │  user_ad_actions   (action='saved'|'favorite', ad_id → collected_ads.id)
  ▼
Resposta formatada (texto simples, sem JSON) → volta pela mesma cadeia →
update.message.reply_text(resposta) no Telegram
```

### Componentes envolvidos
- `channels/telegram/bot.py` — canal Telegram (python-telegram-bot).
- `core/gateway.py` — autorização + ponto único de entrada do núcleo.
- `core/runtime.py` — composition root (monta tudo); `build(check_llm=...)`.
- `agents/orchestrator.py` — `AgentOrchestrator`, interceptação determinística.
- `agents/scalaflow_intel.py` — agente especialista (prompt + tools).
- `agents/prompts.py` — `SCALAFLOW_INTEL_PROMPT` (fallback caso a Tool não bata).
- `tools/scalaflow_tools.py` — a Tool real (`top_produtos_scalaflow`), parsing
  determinístico e consulta HTTP ao Supabase.
- `config/settings.py` — `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
  `REQUIRE_LLM_ON_STARTUP`.

## Integração com o ScalaFlow

Fontes reais confirmadas lendo o código do ScalaFlow
(`escalaflow-insights/src/routes/_authenticated/*.tsx` e `src/lib/queries.ts`):

| Tela do ScalaFlow            | Fonte real                                                        |
|-------------------------------|--------------------------------------------------------------------|
| Central de Mineração          | `collected_ads` (todas as colunas usadas existem: score, created_at, advertiser, ad_url, etc.) |
| Ofertas Salvas                | `user_ad_actions` com `action='saved'`, join em `collected_ads` por `ad_id` |
| Favoritos                     | `user_ad_actions` com `action='favorite'`, join em `collected_ads` por `ad_id` |
| Ofertas Escaladas             | **NÃO é uma ação salva.** É `collected_ads.score >= 80` (a tela apenas limita a exibição a 50). Confirmado lendo `ofertas-escaladas.tsx` / `queries.ts`. |

`produtos_minerados` existe no banco mas está com 0 registros — **não é usada**
pelo piloto.

## Integração com o Supabase

- Acesso via API REST (PostgREST), usando `requests` — nenhuma lib nova de
  cliente Supabase.
- Autenticação com a **service_role key** (não a anon key), porque as tabelas
  têm RLS (`auth.uid() = user_id`) e o CRIS OS não loga como nenhum usuário.
- TLS: nesta máquina, o Avast (Web/Mail Shield) intercepta HTTPS com uma CA
  própria que o `certifi` (lista pública da Mozilla) corretamente não confia.
  Corrigido com o pacote `truststore`, que faz o `ssl`/`urllib3` verificarem
  contra o CA store do **sistema operacional** (o mesmo que o `curl`/Windows já
  usam) — **sem desativar verificação de certificado**. Ver
  `tools/scalaflow_tools.py` (injeção feita no topo do módulo).

## Autorização no Telegram

- `TELEGRAM_ALLOWED_USER_ID` no `.env` — se preenchido, só esse ID numérico do
  Telegram pode falar com o bot (`core/gateway.py:Gateway._autorizado`).
- Qualquer outro `sender_id` recebe: *"Este é um assistente pessoal privado.
  Acesso não autorizado."* e a mensagem NUNCA chega ao orquestrador nem ao
  ScalaFlow/Supabase.
- O `sender_id` usado é sempre `str(update.effective_user.id)` — o mesmo ID
  numérico que o Telegram entrega, sem lógica extra.

## Variáveis de ambiente necessárias (sem valores)

```
TELEGRAM_BOT_TOKEN=            # token do @BotFather
TELEGRAM_ALLOWED_USER_ID=      # seu ID numérico do Telegram
SUPABASE_URL=                  # URL do projeto ScalaFlow no Supabase
SUPABASE_SERVICE_KEY=          # service_role key (NÃO a anon key)
DEFAULT_AGENT=auto             # ativa o AgentOrchestrator (necessário p/ scalaflow_intel)
REQUIRE_LLM_ON_STARTUP=false   # PILOTO: permite subir sem Ollama (ver seção abaixo)
```

## Como iniciar

```powershell
pip install -r requirements.txt
python main.py
```

Aguarde a linha `Canal Telegram iniciado. Aguardando mensagens...` no log.

## Como reiniciar

Qualquer mudança no `.env` só é lida na inicialização (via `python-dotenv`).
Depois de editar o `.env`:

```powershell
# encontrar o processo
tasklist /FI "IMAGENAME eq python.exe"
# encerrar
taskkill /PID <pid> /F
# subir de novo
python main.py
```

## Como testar

Pelo Telegram, para o bot autorizado, mandar mensagens como as da seção
"TESTES CONFIRMADOS" abaixo. Para testar sem gastar uma consulta real, dá para
chamar a função direto:

```powershell
python -c "from tools.scalaflow_tools import _buscar_top_produtos; print(_buscar_top_produtos('top 5 anuncios'))"
```

## Consultas atualmente suportadas (parsing determinístico, sem IA)

A `Tool` "top_produtos_scalaflow" (`tools/scalaflow_tools.py`) entende, no
texto livre do usuário:
- **limite**: primeiro número de 1 a 20 encontrado na frase (padrão: 5).
- **país**: aliases em português (`brasil`→BR, `estados unidos`/`eua`/`usa`→US,
  `espanha`→ES, `mexico`→MX, `portugal`→PT, `canada`→CA, `franca`→FR,
  `alemanha`→DE, `italia`→IT, `reino unido`/`inglaterra`→GB).
- **plataforma**: `facebook`, `instagram`, `tiktok`, `google`, `youtube`.
- **nicho/palavra-chave**: padrão "de X" no final da frase (ex.: "anúncios de
  IA").
- **salvos** / **favoritos** / **escalados** (`score >= 80`): por palavra na
  frase (`salv`, `favorit`, `escalad`).
- Ordenação: sempre por `score DESC` (não precisa pedir "mais quentes" — já é
  o padrão).

## TESTES CONFIRMADOS

Testados de ponta a ponta (função real, consultando o Supabase de produção do
ScalaFlow):

- ✅ "Pesquise no ScalaFlow os 5 anúncios mais quentes" → 5 anúncios, score
  desc, com anunciante/título/plataforma/país/nicho/resumo da copy/link.
- ✅ "Me dê os 10 melhores anúncios" (sem menção a "ScalaFlow") → roteado
  corretamente via keyword `anúncios`/`melhores`.
- ✅ "Quais são as melhores ofertas dos Estados Unidos?" → filtro país=US
  aplicado, todos os resultados com `country=US`.
- ✅ "Me dê os melhores anúncios do Brasil" → filtro país=BR aplicado, todos
  com `country=BR`.
- ✅ "Me mostre 5 anúncios de IA" → nicho/palavra-chave extraído ("ia").
- ✅ "Mostre minhas ofertas salvas" → 12 resultados reais via
  `user_ad_actions(action='saved')` (bate com a produção).
- ✅ "Mostre meus favoritos" → 8 resultados reais via
  `user_ad_actions(action='favorite')` (bate com a produção).
- ✅ "Mostre 5/10 ofertas escaladas" → filtro `collected_ads.score >= 80`
  (167 anúncios elegíveis no banco; a UI do ScalaFlow só limita a exibição a
  50 — não é uma contagem real de 50 "ações").
- ✅ Roteamento por Telegram real: mensagem autorizada, chega ao gateway,
  intercepta como `scalaflow_intel` **sem chamar o LLM**, responde com dado
  real.
- ✅ Autorização: ID fora de `TELEGRAM_ALLOWED_USER_ID` recebeu "Acesso não
  autorizado" (confirmado em teste real antes do ID correto ser configurado).
- ✅ Testes automatizados: `pytest tests/` (excluindo 3 arquivos com uma
  falha de ordenação pré-existente e não relacionada — ver "Limitações") →
  317 passed. Os 3 arquivos isolados → 108 passed.

## Erros encontrados durante a implementação (e correções)

1. **`SSLCertVerificationError` ao consultar o Supabase.**
   Causa: Avast Web/Mail Shield intercepta HTTPS localmente com CA própria;
   `certifi` (bundle público da Mozilla) corretamente não confia nela.
   Correção: injetar `truststore.inject_into_ssl()` em
   `tools/scalaflow_tools.py`, fazendo o `ssl` usar o CA store do Windows
   (mesma fonte de confiança que o `curl` já usa). **Não desativa verificação
   de certificado.**

2. **"Ofertas Escaladas" não batia com a produção (retornava 0).**
   Causa: a implementação inicial assumia `user_ad_actions.action='scaled'`,
   mas essa ação não existe na produção (0 registros). A regra real (lida no
   código do ScalaFlow) é `collected_ads.score >= 80`.
   Correção: `tools/scalaflow_tools.py` agora usa `score >= 80` para
   "escalados", não uma ação salva.

3. **`AttributeError: 'function' object has no attribute 'handle'`.**
   Causa: em `core/runtime.py`, quando `DEFAULT_AGENT=auto`, a variável
   `handler` recebia `agent_orchestrator.handle` (o método já vinculado) em
   vez do objeto `agent_orchestrator`. O `Gateway.handle()` então tentava
   chamar `.handle` de novo em cima de uma função, o que quebrava **qualquer**
   mensagem em modo automático — não era específico do ScalaFlow, só nunca
   tinha sido exercitado de ponta a ponta pelo Telegram antes.
   Correção (uma linha, `core/runtime.py`):
   ```diff
   -            handler = agent_orchestrator.handle
   +            handler = agent_orchestrator
   ```

4. **Startup exigia o Ollama respondendo, mesmo para comandos 100%
   determinísticos.**
   `core/runtime.py:build()` já tinha um parâmetro `check_llm` (usado nos
   testes para montar o sistema offline). Adicionamos a flag de configuração
   `REQUIRE_LLM_ON_STARTUP` (padrão `true`, preserva o comportamento normal)
   para permitir, só quando explicitamente desligada no `.env`, subir o
   Telegram mesmo com o Ollama offline — registrando apenas um WARNING.

5. **Mensagens do ScalaFlow esperavam o Ollama responder (ou falhar) antes de
   cair no agente certo.**
   O roteamento padrão sempre tentava o LLM primeiro. Como o `scalaflow_intel`
   é 100% determinístico, adicionamos uma interceptação por palavra-chave
   **antes** da tentativa de LLM em `agents/orchestrator.py`
   (`_eh_comando_scalaflow`), só para esse agente — o restante do roteamento
   (LLM primeiro, keyword como fallback) continua igual para todo o resto.

## Limitações atuais

- **Ollama não é usado neste piloto** (`REQUIRE_LLM_ON_STARTUP=false`). Sem
  ele, qualquer mensagem que não seja do ScalaFlow (ex.: "Oi", perguntas
  gerais) cai no agente geral, que tenta o LLM, falha, e retorna uma mensagem
  de erro amigável — não trava o processo, mas não responde de verdade.
- Parsing de país/plataforma/nicho é por palavra-chave simples (dicionário +
  regex), não NLU real — frases fora dos padrões testados podem não filtrar
  como esperado (mas nunca inventam dado: na ausência de filtro reconhecido,
  simplesmente lista por score, sem enganar).
- O campo `country` em `collected_ads` é inconsistente na origem (alguns
  registros têm código de país tipo `"US"`, outros têm emoji de bandeira) —
  o filtro por país só funciona de forma confiável para os códigos de 2
  letras mapeados.
- `TELEGRAM_ALLOWED_USER_ID` com um único ID = uso de uma pessoa só (não é
  multi-tenant; ver visão futura abaixo).
- 3 arquivos de teste (`tests/plugins/test_cris_notes.py`,
  `tests/agent_builder/test_agent_builder.py`,
  `tests/agent/test_agent_runtime.py`) falham quando rodados **junto** com o
  resto da suíte completa (`pytest tests/`), mas passam 100% quando rodados
  isolados. Confirmado que essa falha já existia **antes** de qualquer mudança
  deste marco (reproduzida com `git stash -u`, num checkout limpo). É uma
  dependência de ordem de execução dos testes pré-existente, não tratada
  aqui.

## Como restaurar este estado se uma alteração futura quebrar o sistema

1. `git log` e localize o commit deste marco (mensagem: `feat(cris-os):
   checkpoint telegram scalaflow integration milestone 1`).
2. Para comparar o que mudou depois: `git diff <hash-do-marco> -- <arquivo>`.
3. Para reverter um arquivo específico ao estado do marco:
   `git checkout <hash-do-marco> -- <arquivo>`.
4. Os arquivos-chave deste fluxo (não mexer sem entender o impacto):
   `core/gateway.py`, `core/runtime.py` (linha do `handler =
   agent_orchestrator`), `agents/orchestrator.py` (interceptação
   determinística), `tools/scalaflow_tools.py`, `agents/scalaflow_intel.py`.
5. O `.env` **não é versionado** — se precisar recriar, use `.env.example`
   como base e preencha os valores reais (nunca commitar o `.env`).

## NÃO QUEBRAR

Comportamentos que qualquer alteração futura deve preservar:

- `Gateway._autorizado` continua checando `TELEGRAM_ALLOWED_USER_ID` antes de
  qualquer processamento — nenhuma mensagem de um ID não autorizado deve
  chegar ao orquestrador.
- `AgentOrchestrator._escolher_agente` continua interceptando comandos do
  ScalaFlow **antes** de tentar o LLM (não reintroduzir uma chamada ao Ollama
  no caminho de comandos determinísticos).
- `tools/scalaflow_tools.py` continua **nunca inventando dado**: se a consulta
  falhar ou vier vazia, a resposta diz isso explicitamente — nunca preenche
  com exemplo fictício.
- "Ofertas Escaladas" continua usando `collected_ads.score >= 80` — não
  reintroduzir a suposição de `user_ad_actions.action='scaled'` (essa ação não
  existe na produção).
- `core/runtime.py`: `handler` (quando `DEFAULT_AGENT=auto`) continua sendo o
  objeto `agent_orchestrator`, nunca `agent_orchestrator.handle`.
- Nenhum segredo (`TELEGRAM_BOT_TOKEN`, `SUPABASE_SERVICE_KEY`) deve ser
  logado, impresso ou commitado. `.env` continua fora do Git.
- Nada neste fluxo escreve no Supabase/ScalaFlow — é somente leitura
  (`SELECT` via REST). Preservar esse caráter read-only enquanto não houver
  uma decisão explícita em contrário.

---

## VISÃO FUTURA — SCALAFLOW + AGENTE PARA CLIENTES

**Isto é documentação de intenção. Nada aqui foi implementado.**

A arquitetura atual (piloto, uma pessoa, um bot, uma chave de serviço) poderia
evoluir para um modelo multi-tenant onde cada cliente do ScalaFlow tem:

- conta própria;
- dados isolados (RLS real por `user_id`, não a service key global usada
  hoje);
- agente próprio (instância de `scalaflow_intel` configurada por cliente);
- permissões próprias (o que cada cliente pode consultar/fazer);
- memória/contexto próprios (sem vazamento entre clientes);
- limites de uso (rate limiting, cotas de consulta);
- consultas ao ScalaFlow em linguagem natural (podendo evoluir para usar LLM
  de forma segura, não só parsing determinístico);
- acesso pelo painel do ScalaFlow e/ou por um bot de Telegram próprio por
  cliente;
- planos de assinatura;
- controle de consumo de IA (custos por cliente, se algum dia usar LLM pago);
- auditoria e segurança multi-tenant (quem acessou o quê, quando).

**Importante:** nessa arquitetura futura, `TELEGRAM_BOT_TOKEN`, IDs de
usuário, credenciais, memória e dados **não podem ser compartilhados entre
clientes** — cada cliente precisa de isolamento real (nem que seja lógico,
com `user_id` sempre filtrado, nunca só a service key "vê tudo" como hoje).

Isso **não será construído agora**. Este marco é sobre provar que o ciclo
básico funciona, com um único usuário (a Cris), de forma segura e
determinística.
