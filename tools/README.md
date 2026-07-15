# 🛠️ tools/ — Ferramentas dos agentes

As "mãos" dos agentes: ações no mundo real. Cada ferramenta implementa a porta
[core/contracts/tool.py](../core/contracts/tool.py) (`name`, `description`,
`schema()`, `run()`). São **diferentes dos canais**: canal = como a Cris fala com
o sistema; ferramenta = o que os agentes fazem.

| Ferramenta | Status | Para quem |
|---|---|---|
| Google Calendar | 🔴 Planejado | Secretária (agenda, lembretes) |
| Google Drive | 🔴 Planejado | Vários (arquivos) |
| GitHub | 🔴 Planejado | PinkLogic / dev |
| n8n | 🔴 Planejado | Automações |
| Busca na web | 🔴 Planejado | Pesquisador, ScalaFlow |
| Memória (escrita) | 🔴 Planejado | Todos (registrar decisões/ideias) |

## Como funciona (próximas fases)
1. Criar `tools/<nome>/` com uma classe que cumpra a porta `Tool`.
2. Registrar no `ToolRegistry` ([core/registry.py](../core/registry.py)).
3. Declarar a ferramenta no `manifest.json` do agente que pode usá-la.
4. O `BaseAgent` passa os schemas ao LLM e executa as `tool_calls` num laço.

> A infraestrutura de tool-calling já existe (o Orquestrador usa para delegar).
> Estender para ferramentas reais é incremental, sem reescrever o núcleo.
