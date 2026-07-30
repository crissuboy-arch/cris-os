# CRIS OS

Sistema operacional pessoal da Cris — uma **equipe de agentes de IA** rodando localmente, coordenada por um gerente (Orquestrador). Converse pelo Telegram com seu time de especialistas digitais.

```
Modo AUTO (padrao):
  Voce -> Telegram -> Gateway -> AGENT_ORCHESTRATOR
                                   |- LLM + Keyword fallback -> escolhe o especialista
                                   |- SpecialistAgent -> gera a resposta

Modo CLASSICO (DEFAULT_AGENT=secretary):
  Voce -> Telegram -> Gateway -> ORQUESTRADOR v3
                                   |- IntentRouter -> decide quem trabalha
                                   |- WorkflowEngine -> executa + rastreia
                                   |- ResponseComposer -> resposta unificada
```

---

## Arquitetura

- **Clean Architecture + Event-Driven**: dominio puro no centro, tudo na borda e plugavel
- **ODS integrado**: deteccao automatica do Osmantic Deployment System (Ollama + Open WebUI)
- **3 provedores de IA**: NVIDIA AI (nuvem, modelos 8B+70B) + OpenAI (fallback) + Ollama (local)
- **AgentOrchestrator**: roteamento inteligente entre 8 especialistas (auto ou manual via /use)
- **8 agentes especialistas**: marketing, social_media, vendas, atendimento, programador, pesquisador, copywriter, produtividade
- **Router dedicado 8B**: roteamento rapido (~700ms) com historico reduzido (3 msgs) — modo classico
- **Geracao 70B**: respostas de alta qualidade com contexto completo (12 msgs) — modo classico
- **Fast Path**: saudacoes, sim/nao e comandos com keyword roteados em ~0.1ms (sem LLM)
- **Memoria 4 camadas** (SQLite): conversa -> temporaria -> projetos -> permanente -> conhecimento
- **Plugins**: novo agente = nova pasta em `agents/`; o nucleo nao muda
- **12 agentes legado**: 11 especialistas + 1 orquestrador (gerente) — modo classico
- **5 skills**: `session-handoff` em producao; `browser-tool`, `roast`, `curriculum-builder`, `zavix-product` em scaffold
- **CRIS OS Studio**: interface visual para criar agentes sem codigo (v0.6.0)
- **656 testes**: todos verdes

Arquitetura completa em [ARQUITETURA.md](ARQUITETURA.md).

---

## CRIS OS Studio

Interface visual completa para criar, configurar e testar agentes sem escrever codigo.

### Funcionalidades (v0.6.0)

- **Dashboard**: visao geral dos agentes com metricas e status
- **Editor Visual**: configuracao de instructions, memory, permissions, tools
- **System Prompt Preview**: preview em tempo real do system prompt montado
- **Agent Playground**: teste interativo com input/output/status
- **Templates**: 5 presets de agente para criacao rapida
- **Autenticacao JWT**: login/logout, gestao de usuarios
- **Export/Import**: agentes em formato padronizado
- **Versioning**: historico de versoes com diff visual
- **MCP Integration**: executor MCP via stdio
- **Notifications**: notificacoes Telegram para confirmacoes pendentes
- **Executive Dashboard**: metricas com graficos (recharts)

### Como iniciar o Studio

```powershell
# Backend
cd web/backend
pip install -r requirements.txt
python -m uvicorn routes.studio:app --reload --port 8000

# Frontend
cd web/frontend
npm install
npm run dev
```

Acesse: http://localhost:5173

### Credenciais padrao

| Usuario | Senha | Permissao |
|---------|-------|-----------|
| admin | admin123 | admin |
| editor | editor123 | editor |
| viewer | viewer123 | viewer |

---

## Como instalar

### Pre-requisitos
- Python 3.10+
- [ODS](https://github.com/inematds/ODS) (recomendado) ou Ollama standalone — https://ollama.com
- Conta no Telegram
- (Opcional) Chave de API NVIDIA AI ou OpenAI
- (Opcional) Node.js 18+ (para o Studio)

### Instalar dependencias

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Baixar modelo Ollama (opcional)

```powershell
ollama pull llama3.1
```

### Criar o bot do Telegram
1. Fale com o **@BotFather** no Telegram.
2. Mande `/newbot` e siga as instrucoes.
3. Copie o **token** gerado.
4. (Recomendado) Descubra seu **ID** com **@userinfobot**.

---

## Como configurar o .env

```powershell
copy .env.example .env
```

Preencha no `.env`:

| Variavel | Obrigatorio | Descricao |
|----------|-------------|-----------|
| `TELEGRAM_BOT_TOKEN` | Sim | Token do @BotFather |
| `TELEGRAM_ALLOWED_USER_ID` | Sim | Seu ID numerico |
| `ODS_ENABLED` | Opcional | Ativa integracao ODS (padrao: `true`) |
| `ODS_BASE_URL` | Opcional | URL do Ollama via ODS (padrao: `http://localhost:11434`) |
| `ODS_FALLBACK_URL` | Opcional | URL alternativa ODS (padrao: `http://localhost:8080`) |
| `NVIDIA_API_KEY` | Opcional | Chave da NVIDIA AI (fallback) |
| `OPENAI_API_KEY` | Opcional | Chave da OpenAI (fallback alternativo) |
| `OLLAMA_MODEL` | Opcional | Modelo Ollama local (padrao: `qwen2.5-coder:1.5b`) |
| `DEFAULT_AGENT` | Opcional | `auto` = orquestrador escolhe; `secretary` = modo classico |

---

## Como iniciar

```powershell
python main.py
```

Para validar o nucleo sem Telegram nem Ollama:

```powershell
python -m pytest tests/
```

---

## Como usar pelo Telegram

1. Abra a conversa com seu bot.
2. Mande `/start`.
3. Escreva algo como: _"tenho que gravar um reels, responder cliente e beber agua"_
4. O Orquestrador roteia para o especialista certo. A resposta volta unificada.

---

## Integracao com ODS (Osmantic Deployment System)

O CRIS OS detecta automaticamente o ODS na sua rede local.

### O que o ODS oferece

- **Ollama** — inferencia local de LLM na porta 11434 (Linux Docker) ou 8080 (nativo Windows/macOS)
- **Open WebUI** — interface web de chat na porta 3000
- **Modelos otimizados** — selecao automatica do melhor modelo para seu hardware
- **Extensoes futuras**: Qdrant (RAG vetorial), n8n (automacao), ComfyUI (imagem)

### Deteccao automatica

Quando `ODS_ENABLED=true` (padrao), o CRIS OS:

1. Testa a porta 11434 (Ollama)
2. Se nao responder, testa a porta 8080 (llama-server nativo)
3. Usa a URL ativa para todas as requisicoes de LLM
4. Mostra os modelos carregados

Verifique o status pelo Telegram com o comando `/ods`.

### Fallback quando ODS esta offline

Se o ODS nao estiver rodando, o CRIS OS tenta os provedores na nuvem:

| Provedor | Variavel | Configuracao |
|----------|----------|--------------|
| **NVIDIA** (padrao) | `NVIDIA_API_KEY` | `ODS_FALLBACK_PROVIDER=nvidia` |
| **OpenAI** | `OPENAI_API_KEY` | `ODS_FALLBACK_PROVIDER=openai` |
| **Gemini** | `GEMINI_API_KEY` | `ODS_FALLBACK_PROVIDER=gemini` (futuro) |
| **Anthropic** | — | `ODS_FALLBACK_PROVIDER=anthropic` (futuro) |

Para desativar o ODS e usar apenas provedores remotos:

```ini
ODS_ENABLED=false
ODS_FALLBACK_PROVIDER=nvidia   # ou openai
```

### Comandos do Telegram

| Comando | Descricao |
|---------|-----------|
| `/ods` | Status dos servicos ODS |
| `/ods check` | Teste detalhado de conexao |
| `/ods on` | Ativar ODS (runtime) |
| `/ods off` | Desativar ODS (runtime) |
| `/ods reset` | Limpar cache de status |

### Exemplo de saida do /ods

```
ODS - Status dos Servicos
================================
  [OK] Ollama (porta 11434): ONLINE (42ms)
       Modelos: qwen2.5:1.5b
  [--] llama-server (porta 8080): OFFLINE
  [OK] Open WebUI (porta 3000): ONLINE (120ms)
--------------------------------
  Modelo ativo: qwen2.5:1.5b
  Endpoint: http://localhost:11434
```

---

## Sistema de Agentes Especialistas

O CRIS OS agora conta com **8 agentes especialistas** no modo padrao (`DEFAULT_AGENT=auto`).

### Agentes disponiveis

| Agente | Descricao | Exemplo de uso |
|--------|-----------|----------------|
| `marketing` | Cria campanhas de marketing digital | "Crie uma campanha para o Natal" |
| `social_media` | Cria legendas e posts para redes sociais | "Faca uma legenda para o Instagram" |
| `vendas` | Elabora propostas comerciais | "Monte uma proposta para o cliente X" |
| `atendimento` | Responde clientes com educacao | "Responda a reclamacao do Joao" |
| `programador` | Desenvolve codigo e scripts | "Crie um script para automatizar" |
| `pesquisador` | Pesquisa concorrentes e fornecedores | "Pesquise precos de hospedagem" |
| `copywriter` | Cria textos persuasivos | "Crie uma pagina de vendas" |
| `produtividade` | Organiza rotina e prioriza tarefas | "Planeje meu dia" |

### Como funciona o roteamento

```
Mensagem do usuario
  |
  v
AgentOrchestrator
  |
  +-- Usuario tem agente fixo? (via /use) -----> Agente fixo
  |
  +-- Mensagem curta e tem ultimo agente? -----> Mesmo agente
  |
  +-- LLM classifica a mensagem ---------------> Agente escolhido
  |
  +-- Keyword fallback ------------------------> Agente por palavra-chave
  |
  +-- Nenhum agente encontrado ----------------> Mensagem de erro
  |
  v
SpecialistAgent.generate() -> Resposta via Ollama/ODS
```

O roteamento tem 4 niveis:

1. **Agente fixo** (via `/use marketing`): todas as mensagens vao para o agente escolhido
2. **Followup**: mensagens curtas como "continua" ou "sim" reusam o ultimo agente
3. **LLM**: o modelo local classifica a mensagem e escolhe o melhor agente
4. **Keyword fallback**: se o LLM falhar, palavras-chave no texto fazem o roteamento

### Comandos do Telegram

| Comando | Descricao |
|---------|-----------|
| `/agents` | Lista todos os agentes especialistas |
| `/agent` | Mostra o agente ativo no momento |
| `/use <nome>` | Fixa um agente (ex.: `/use marketing`) |
| `/use auto` | Volta ao modo automatico |

### Exemplos

```
/usuario: Crie uma legenda para o Instagram
/orquestrador: Roteia para social_media
/agente: [legenda criada]

/usuario: Mande uma proposta para o cliente
/orquestrador: Roteia para vendas
/agente: [proposta elaborada]

/usuario: continua
/orquestrador: Detecta followup, reusa ultimo agente (vendas)
/agente: [continuacao da proposta]
```

### Como adicionar um novo agente

1. Crie o prompt em `agents/prompts.py`
2. Crie o arquivo do agente em `agents/seu_agente.py` seguindo o modelo:

```python
from agents.base_specialist import create_agent
from agents.prompts import SEU_PROMPT

name = "seu_agente"
description = "Descricao do seu agente"
system_prompt = SEU_PROMPT

def create(llm):
    return create_agent(name, description, system_prompt, llm)
```

3. Adicione o modulo em `agents/__init__.py` na lista `AGENT_MODULES`
4. Adicione keywords em `agents/orchestrator.py` no metodo `_rotear_por_keyword`
5. Adicione o alias em `_normalizar_nome` se quiser atalhos

O agente sera descoberto automaticamente na proxima inicializacao.

---

## Estrutura das pastas

```
cris-os/
  core/             # Nucleo: dominio, portas, aplicacao, eventos, plugins
  agents/           # 8 especialistas + AgentOrchestrator + 12 agentes legado
  skills/           # 5 skills (1 em producao, 4 em scaffold)
  services/         # Servicos externos: ods_client.py
  memory/           # Camadas de memoria (L1-L4) + facade
  storage/          # SQLite (memoria + event log + tasks + lease)
  llm/              # Provedores: nvidia.py, ollama.py, openai_compat.py, router.py
  channels/         # Telegram (canais: whatsapp, discord, email em roadmap)
  config/           # settings.py (leitura do .env)
  tools/            # Ferramentas (browser, MCP)
  agent_builder/    # CRIS OS Studio: AgentBuilder, DynamicAgent, Store, API
  web/              # CRIS OS Studio: Frontend (React) + Backend (FastAPI)
  tests/            # 656 testes
  data/             # cris_os.db (runtime)
  scripts/          # Scripts uteis (run, preflight, test_nvidia)
```

---

## Agentes existentes

| Agente | Dominio | Status | Descricao |
|--------|---------|--------|-----------|
| secretary | pessoal | Producao | Agenda, rotina, lembretes, saude |
| atendimento | atendimento | Draft | Atendimento a clientes |
| curriculo | curriculo | Draft | Criacao e revisao de curriculos |
| financeiro | financeiro | Draft | Controle financeiro, receitas, metas |
| mkvideos | conteudo | Draft | Producao de video (roteiro a legenda) |
| pesquisador | pesquisa | Draft | Pesquisa de concorrentes e precos |
| pinklogic | pinklogic | Draft | SaaS, automacoes e IA |
| scalaflow | scalaflow | Draft | Mineracao, anuncios e nichos |
| social-media | marketing | Draft | Redes sociais e estrategias |
| vitrinepro | vitrinepro | Draft | Negocios locais e presenca digital |
| zavix | zavix | Draft | Loja Zavix.online |

---

## Skills existentes

| Skill | Versao | Status | Descricao |
|-------|--------|--------|-----------|
| session-handoff | 1.0.0 | Producao | Transferencia de contexto entre agentes |
| browser-tool | 0.1.0 | Scaffold | Navegacao web read-only |
| curriculum-builder | 0.1.0 | Scaffold | Criacao de curriculos |
| roast | 0.1.0 | Scaffold | Feedback criativo |
| zavix-product | 0.1.0 | Scaffold | Catalogo de produtos Zavix |

---

## Roadmap resumido

- **v1.0.0** ✅ CRIS OS oficial - Telegram + confirmacao humana + persistencia + metrics
- **v1.1.0** Dashboard executivo avancado (metricas por periodo, exportacao de relatorios)
- **v1.2.0** Multi-usuario com papeis (admin, editor, viewer)
- **v1.3.0** Integracoes externas (Calendar, WhatsApp, etc.)
- Ferramentas reais: Google Calendar, Drive, GitHub, busca web
- Novos canais: WhatsApp, Discord, Email, Instagram
- Lembrete proativo e automacoes agendadas
- Segunda maquina (replicacao + failover)
- Memoria semantica e camada de cognicao

Roadmap completo em [ROADMAP.md](ROADMAP.md). Arquitetura completa em [ARQUITETURA.md](ARQUITETURA.md).

---

## Status Atual

- **CRIS OS Studio v0.6.0** — interface visual completa
- **CRIS OS v1.0** — versao oficial estavel.
- **Integracao ODS** concluida (deteccao automatica + `/ods` no Telegram).
- Integracao NVIDIA AI concluida (router 8B + geracao 70B).
- Provedor OpenAI (fallback alternativo).
- Telegram funcionando com confirmacao humana (botoes inline + comandos).
- Persistencia de conversas, logs e metricas.
- Fallback automatico entre ODS, NVIDIA, OpenAI e Ollama.
- **656 testes**, todos verdes.
- Arquitetura congelada nesta versao.
