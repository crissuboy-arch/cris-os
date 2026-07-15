# Tools / Connections (tools.md)

> **Camada 5.** Inventário das conexões do CRIS OS com o mundo. **Read-only por
> padrão.** Segredos **nunca** no repositório (ficam no `.env`). Esta é a visão de
> **governança**; o roadmap de **engenharia** está em [tools/README.md](tools/README.md).

## Ativas (Fase 1)
| Conexão | Para quê | Acesso | Segredo | Status |
|---|---|---|---|---|
| **Ollama** (local) | IA local que pensa pelos agentes | uso local | não | ativo — `llm/ollama.py` |
| **Telegram** | canal de conversa com a Cris | ler + responder (só à Cris) | `TELEGRAM_BOT_TOKEN` (`.env`) | ativo — `channels/telegram/` |

## Planejadas (NÃO conectar ainda — requer aprovação)
| Conexão | Para quê | Acesso sugerido | Como ligar depois |
|---|---|---|---|
| Google Calendar | agenda/lembretes da Secretária | **read-only** primeiro | tool + porta MCP |
| Google Drive | documentos para a Base de Conhecimento (L4) | **read-only** | tool de ingestão |
| GitHub | repositórios (PinkLogic / dev) | **read-only** | tool / MCP |
| n8n | automações | webhook/evento | adaptador + Event Bus |
| WhatsApp | canal adicional | ler + responder | novo `channel` |
| MCP (servidores externos) | expor ferramentas externas como `Tool` | varia | `core/contracts/mcp.py` |

## Regras de conexão
- **Read-only por padrão.** Write só onde for indispensável e **com aprovação** (ver [rules/never.md](rules/never.md)).
- **Nenhum segredo no repositório.** Tudo via `.env` (já no `.gitignore`).
- Cada nova conexão é um **adaptador plugável** — não muda o núcleo (ver `tools/` e `mcp/`).
