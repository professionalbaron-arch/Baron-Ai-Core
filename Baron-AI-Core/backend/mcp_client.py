"""
BARON CORE - Model Context Protocol (MCP) Client Bridge
Inspired by Moltis 'moltis-mcp' & 'moltis-mcp-agent-bridge'.
Features:
- Connects to external MCP Servers (stdio / JSON-RPC 2.0)
- Dynamically discovers external tools & prompts
- Executes remote MCP tools seamlessly within Baron's tool registry
"""

import os
import sys
import json
import logging
import subprocess
import threading
from typing import Dict, Any, List, Optional

logger = logging.getLogger("BaronMCP")


class MCPProcessServer:
    """Manages an external stdio-based MCP server process."""
    def __init__(self, name: str, command: List[str], env: Optional[Dict[str, str]] = None):
        self.name = name
        self.command = command
        self.env = env or os.environ.copy()
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 1
        self._lock = threading.Lock()
        self.capabilities = {}
        self.tools = []

    def start(self) -> bool:
        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=self.env
            )
            # Send MCP Initialize Request
            init_res = self._send_rpc("initialize", {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "Baron-AI-Core", "version": "2.0.0"},
                "capabilities": {}
            })
            if init_res:
                self.capabilities = init_res.get("capabilities", {})
                # Send initialized notification
                self._send_rpc("notifications/initialized", {}, is_notification=True)
                # Fetch available tools
                tools_res = self._send_rpc("tools/list", {})
                if tools_res:
                    self.tools = tools_res.get("tools", [])
                logger.info(f"MCP server '{self.name}' connected with {len(self.tools)} tools.")
                return True
        except Exception as e:
            logger.warning(f"Could not start MCP server '{self.name}': {e}")
        return False

    def _send_rpc(self, method: str, params: Dict[str, Any], is_notification: bool = False) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self.process or self.process.poll() is not None:
                return None

            req = {"jsonrpc": "2.0", "method": method, "params": params}
            if not is_notification:
                req["id"] = self._request_id
                self._request_id += 1

            try:
                line = json.dumps(req) + "\n"
                self.process.stdin.write(line)
                self.process.stdin.flush()

                if is_notification:
                    return None

                response_line = self.process.stdout.readline()
                if response_line:
                    res_json = json.loads(response_line)
                    return res_json.get("result")
            except Exception as e:
                logger.error(f"MCP RPC call '{method}' failed: {e}")
        return None

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        res = self._send_rpc("tools/call", {"name": tool_name, "arguments": arguments})
        if res:
            return res.get("content", res)
        return {"error": "Tool call failed or empty response."}

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass


class BaronMCPManager:
    """Central manager for active MCP servers."""
    def __init__(self):
        self.servers: Dict[str, MCPProcessServer] = {}

    def register_server(self, name: str, command: List[str]) -> bool:
        server = MCPProcessServer(name, command)
        if server.start():
            self.servers[name] = server
            return True
        return False

    def list_all_tools(self) -> List[Dict[str, Any]]:
        all_tools = []
        for s_name, srv in self.servers.items():
            for t in srv.tools:
                all_tools.append({
                    "server": s_name,
                    "name": f"mcp_{s_name}_{t.get('name')}",
                    "description": t.get("description", ""),
                    "inputSchema": t.get("inputSchema", {})
                })
        return all_tools


# Global MCP Manager
mcp_manager = BaronMCPManager()
