# CRIS OS

Sistema operacional pessoal da Cris — uma **equipe de agentes de IA** rodando localmente, coordenada por um gerente (Orquestrador). Converse pelo Telegram com seu time de especialistas digitais.

```
Voce (Telegram) -> Gateway -> ORQUESTRADOR (gerente)
                                 |- IntentRouter -> decide quem trabalha
                                 |- WorkflowEngine -> executa + rastreia
                                 |- ResponseComposer -> resposta unificada
```

---

## Arquitetura

- **Clean Architecture + Event-Driven**: dominio puro no centro, tudo na borda e plugavel
- **2 provedores de IA**: NVIDIA AI (nuvem, modelos 8B+70B) + Ollama (local, fallback)
- **Router dedicado 8B**: roteamento rapido (~700ms) com historico reduzido (3 msgs)
- **Geracao 70B**: respostas de alta qualidade com contexto completo (12 msgs)
- **Fast Path**: saudacoes, sim/nao e comandos com keyword roteados em ~0.1ms (sem LLM)
- **Memoria 4 camadas** (SQLite): conversa -> temporaria -> projetos -> permanente -> conhecimento
- **Plugins**: novo agente = nova pasta em `agents/`; o nucleo nao muda
- **12 agentes**: 11 especialistas + 1 orquestrador (gerente)
- **5 skills**: `session-handoff` em producao; `browser-tool`, `roast`, `curriculum-builder`, `zavix-product` em scaffold
- **82 testes**: 20 arquivos de teste, todos verdes

Arquitetura completa em [ARQUITETURA.md](ARQUITETURA.md).

---

## Como instalar

### Pre-requisitos
- Python 3.10+
- Ollama (opcional, para fallback local) — https://ollama.com
- Conta no Telegram
- (Opcional) Chave de API NVIDIA AI

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
| `NVIDIA_API_KEY` | Opcional | Chave da NVIDIA AI (se nao definir, usa Ollama) |
| `NVIDIA_ROUTER_MODEL` | Opcional | Modelo de roteamento (padrao: `meta/llama-3.1-8b-instruct`) |
| `NVIDIA_GENERATION_MODEL` | Opcional | Modelo de geracao (padrao: `meta/llama-3.1-70b-instruct`) |
| `OLLAMA_MODEL` | Opcional | Modelo Ollama local (padrao: `qwen2.5-coder:1.5b`) |
| `OLLAMA_HOST` | Opcional | Endereco do Ollama (padrao: `http://localhost:11434`) |
| `DEFAULT_AGENT` | Opcional | Agente padrao (padrao: `secretary`) |

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

## Como trocar entre NVIDIA e Ollama

### Usar NVIDIA (recomendado)
No `.env`:
```ini
NVIDIA_API_KEY=nvapi-sua-chave-aqui
# NVIDIA_GENERATION_MODEL=meta/llama-3.1-70b-instruct
```

### Usar apenas Ollama (local)
No `.env`:
```ini
# NVIDIA_API_KEY=
OLLAMA_MODEL=llama3.1
```

### Fallback automatico
Se o modelo NVIDIA configurado nao estiver disponivel, o sistema cai automaticamente para Ollama. Nenhuma acao necessaria.

---

## Estrutura das pastas

```
cris-os/
  core/             # Nucleo: dominio, portas, aplicacao, eventos, plugins
  agents/           # 12 agentes (orquestrador + 11 especialistas)
  skills/           # 5 skills (1 em producao, 4 em scaffold)
  memory/           # Camadas de memoria (L1-L4) + facade
  storage/          # SQLite (memoria + event log + tasks + lease)
  llm/              # Provedores: nvidia.py, ollama.py, router.py
  channels/         # Telegram (canais: whatsapp, discord, email em roadmap)
  config/           # settings.py (leitura do .env)
  tools/            # Ferramentas (browser, MCP)
  tests/            # 82 testes
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

- Producao dos 11 especialistas (atualmente em draft)
- Ferramentas reais: Google Calendar, Drive, GitHub, busca web
- Novos canais: WhatsApp, Discord, Email, Instagram
- Lembrete proativo e automacoes agendadas
- Segunda maquina (replicacao + failover)
- Memoria semantica e camada de cognicao

Roadmap completo em [ROADMAP.md](ROADMAP.md). Arquitetura completa em [ARQUITETURA.md](ARQUITETURA.md).
