# OS Audit — 2026-06-29

**Goal:** Sistema operacional pessoal da Cris (equipe de agentes), com a **Fase 1**
(Secretária via Telegram + Ollama + Orquestrador) pronta para funcionar.

> Auditoria no formato do os-coach, adaptada: o CRIS OS tem **duas camadas** — a
> de governança (estes `.md`) e o **runtime Python** que roda de verdade. As notas
> consideram as duas.

## Scorecard
| Camada | Nota | Por quê (uma linha específica) |
|---|---|---|
| Identity | **Solid** | `CLAUDE.md` define a alma, a dona (Cris), a missão e 4 recusas. |
| Substrate | **Started** | `substrate/compendium.md` destila Cris + 9 projetos + equipe, mas a Base de Conhecimento de runtime (L4, FTS5) está **vazia** e falta ferramenta de ingestão. |
| Rules | **Solid** | `rules/always.md` + `never.md` são concretos e testáveis (ex.: "tudo passa pelo Orquestrador"). |
| Skills | **Missing** | Não há conceito de skill ainda; os agentes executam os jobs direto. **Adiar de propósito** (não inventar busywork). |
| Tools | **Started** | `tools.md` inventaria as conexões; só **Ollama + Telegram** ativos; Calendar/Drive/GitHub/n8n/WhatsApp/MCP planejados, **não ligados**. |
| Agents | **Solid (compounding)** | 11 agentes + Orquestrador descobertos por `manifest.json`; novo agente = nova pasta. |

## As três jogadas que mais importam (em ordem)
1. **Operacional (destravar a Fase 1)** — criar `.env`
   (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_ID`, `OLLAMA_MODEL=llama3.1`),
   `pip install -r requirements.txt`, `ollama pull llama3.1`, `python main.py`.
   É o que separa "arquitetura pronta" de "a Cris falando com a Secretária **hoje**".
2. **Substrate** — manter `substrate/compendium.md` e `memory/seed.py` **espelhados**;
   depois, reunir 1–2 documentos reais da Cris para a L4 (quando houver ingestão).
3. **Cognição** — **revisar** a camada (Planner/Executor/Supervisor) **antes** de
   implementar, como combinado, para não acoplar inteligência sobre fundação não revisada.

## O que já está funcionando
- Arquitetura v3 sólida (Clean Architecture, event-driven, memória em 4 camadas,
  plugins) com **11 smoke tests passando**.
- Identity + Rules já dão ao sistema **alma e guardrails** claros, em português e
  fiéis à filosofia "**só o Orquestrador fala com a Cris**".

## A única coisa para fazer agora
Configurar o `.env` e rodar `python main.py` para a Secretária responder no
Telegram — **Fase 1 no ar**.
