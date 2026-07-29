"""
StudioMcpExecutor — executor MCP (Model Context Protocol) real via stdio.

Descobre ferramentas de um servidor MCP, executa com timeout/retry,
e trata erros de comunicacao.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 30
MAX_RETRIES = 2
JSONRPC_VERSION = "2.0"


@dataclass
class McpServer:
    """Configuracao de um servidor MCP."""
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout_s: int = DEFAULT_TIMEOUT_S
    enabled: bool = True


@dataclass
class McpTool:
    """Uma ferramenta descoberta de um servidor MCP."""
    name: str
    description: str
    input_schema: dict = field(default_factory=dict)
    server_name: str = ""


class StudioMcpExecutor:
    """Executor MCP via subprocess (stdio)."""

    def __init__(self) -> None:
        self._servers: dict[str, McpServer] = {}
        self._tools: dict[str, McpTool] = {}
        self._capabilities: dict[str, dict] = {}

    def register_server(self, config: dict) -> McpServer:
        """Registra um servidor MCP."""
        server = McpServer(
            name=config.get("name", "unnamed"),
            command=config.get("command", ""),
            args=config.get("args", []),
            env=config.get("env", {}),
            timeout_s=config.get("timeout_s", DEFAULT_TIMEOUT_S),
            enabled=config.get("enabled", True),
        )
        if not server.command:
            raise ValueError(f"MCP server '{server.name}' precisa de um command")
        self._servers[server.name] = server
        logger.info("MCP server registered: %s (%s)", server.name, server.command)
        return server

    def unregister_server(self, name: str) -> bool:
        if name in self._servers:
            del self._servers[name]
            # Remove tools from this server
            self._tools = {k: v for k, v in self._tools.items() if v.server_name != name}
            return True
        return False

    def discover_tools(self, server_name: str | None = None) -> list[McpTool]:
        """Descobre ferramentas de servidores MCP."""
        discovered: list[McpTool] = []
        servers = [self._servers[server_name]] if server_name else [
            s for s in self._servers.values() if s.enabled
        ]

        for server in servers:
            try:
                tools = self._discover_server_tools(server)
                for tool in tools:
                    tool.server_name = server.name
                    self._tools[f"{server.name}.{tool.name}"] = tool
                discovered.extend(tools)
                logger.info("Discovered %d tools from MCP server '%s'", len(tools), server.name)
            except Exception as exc:
                logger.error("Failed to discover tools from '%s': %s", server.name, exc)

        return discovered

    def list_tools(self) -> list[dict]:
        """Lista todas as ferramentas MCP descobertas."""
        return [
            {
                "name": t.name,
                "full_name": f"{t.server_name}.{t.name}",
                "description": t.description,
                "server": t.server_name,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    def list_servers(self) -> list[dict]:
        """Lista servidores registrados."""
        return [
            {
                "name": s.name,
                "command": s.command,
                "args": s.args,
                "enabled": s.enabled,
                "timeout_s": s.timeout_s,
            }
            for s in self._servers.values()
        ]

    def execute(self, tool_full_name: str, params: dict | None = None) -> dict:
        """Executa uma ferramenta MCP."""
        tool = self._tools.get(tool_full_name)
        if tool is None:
            return {"success": False, "error": f"Ferramenta MCP '{tool_full_name}' nao encontrada"}

        server = self._servers.get(tool.server_name)
        if server is None or not server.enabled:
            return {"success": False, "error": f"Servidor MCP '{tool.server_name}' indisponivel"}

        return self._call_tool(server, tool, params or {})

    def _discover_server_tools(self, server: McpServer) -> list[McpTool]:
        """Envia tools/list para o servidor MCP via stdio."""
        request = {
            "jsonrpc": JSONRPC_VERSION,
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        response = self._send_request(server, request)
        if response is None or "error" in response:
            return []

        tools_data = response.get("result", {}).get("tools", [])
        return [
            McpTool(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in tools_data
        ]

    def _call_tool(self, server: McpServer, tool: McpTool, params: dict) -> dict:
        """Chama uma ferramenta MCP via stdio com retry."""
        request = {
            "jsonrpc": JSONRPC_VERSION,
            "id": int(time.time() * 1000),
            "method": "tools/call",
            "params": {
                "name": tool.name,
                "arguments": params,
            },
        }

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._send_request(server, request)
                if response is None:
                    if attempt < MAX_RETRIES:
                        logger.warning("MCP call attempt %d failed, retrying...", attempt + 1)
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    return {"success": False, "error": "Servidor MCP nao respondeu"}

                if "error" in response:
                    error = response["error"]
                    return {
                        "success": False,
                        "error": f"MCP error: {error.get('message', str(error))}",
                        "code": error.get("code", -1),
                    }

                result = response.get("result", {})
                # MCP tools/call returns {content: [{type, text}]}
                content = result.get("content", [])
                if content:
                    texts = [c.get("text", str(c)) for c in content if isinstance(c, dict)]
                    return {"success": True, "output": "\n".join(texts), "data": result}
                return {"success": True, "data": result}

            except Exception as exc:
                if attempt < MAX_RETRIES:
                    logger.warning("MCP call attempt %d error: %s", attempt + 1, exc)
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return {"success": False, "error": str(exc)}

        return {"success": False, "error": "Max retries exceeded"}

    def _send_request(self, server: McpServer, request: dict) -> dict | None:
        """Envia request JSON-RPC para o servidor via stdio."""
        try:
            proc = subprocess.Popen(
                [server.command] + server.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**dict(__import__("os").environ), **server.env},
                text=True,
                timeout=server.timeout_s,
            )

            # Send request
            message = json.dumps(request) + "\n"
            stdout, stderr = proc.communicate(input=message, timeout=server.timeout_s)

            if proc.returncode != 0:
                logger.error("MCP server '%s' exited with code %d: %s", server.name, proc.returncode, stderr[:500])
                return None

            # Parse response (may be multiple lines, take the last JSON object)
            for line in reversed(stdout.strip().split("\n")):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue

            return None

        except subprocess.TimeoutExpired:
            logger.error("MCP server '%s' timed out", server.name)
            try:
                proc.kill()
            except Exception:
                pass
            return None
        except FileNotFoundError:
            logger.error("MCP command not found: %s", server.command)
            return None
        except Exception as exc:
            logger.error("MCP communication error: %s", exc)
            return None


# Singleton
_mcp_executor: StudioMcpExecutor | None = None


def get_mcp_executor() -> StudioMcpExecutor:
    global _mcp_executor
    if _mcp_executor is None:
        _mcp_executor = StudioMcpExecutor()
    return _mcp_executor
