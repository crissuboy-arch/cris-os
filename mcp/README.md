# 🔌 mcp/ — Model Context Protocol

Preparação para o CRIS OS falar **MCP** nos dois sentidos:

- **Cliente**: consumir servidores MCP externos e expor suas capacidades como
  `Tool` para os agentes (ex.: um servidor MCP de e-mail, de banco, de browser).
- **Servidor**: expor as ferramentas do CRIS para outros clientes MCP (ex.: o
  próprio Claude Code acessando suas ferramentas).

## Status
- ✅ Porta definida em [core/contracts/mcp.py](../core/contracts/mcp.py) (`MCPClient`).
- 🔴 Adaptador cliente/servidor — fase futura.

## Por que já existe a porta
Tool Calling já é usado pelo Orquestrador para delegar e pelos agentes (futuro)
para usar ferramentas. MCP é só **mais uma fonte de ferramentas**: um adaptador
que transforma ferramentas MCP em `Tool`. Deixar a porta pronta evita refatorar o
núcleo quando o MCP entrar.
