"""MCP server manager.

Orchestrates N stdio MCP clients keyed by server name. All enabled servers
are launched in parallel at session start; per-server failures are logged
and isolated rather than blocking the rest. The union of working servers'
tools is exposed via a flat list tagged with each tool's originating
server name."""

import asyncio

from aider.mcp.client import Client


class MCPManagerError(RuntimeError):
    pass


class Manager:
    def __init__(self, servers_config):
        self.servers_config = servers_config or {}
        self._clients = {}
        self._states = {name: {"state": "stopped", "error": None} for name in self.servers_config}

    async def start_all(self):
        """Launch all enabled servers in parallel. Per-server failures are
        recorded in state and do not raise; callers inspect list_servers()
        to find failures."""
        coros = []
        for name, cfg in self.servers_config.items():
            if not cfg.get("enabled", True):
                self._states[name] = {"state": "disabled", "error": None}
                continue
            coros.append(self._start_one(name, cfg))
        if coros:
            await asyncio.gather(*coros)

    async def _start_one(self, name, cfg):
        client = Client(name, cfg)
        try:
            await client.connect()
        except Exception as exc:
            self._states[name] = {"state": "failed", "error": str(exc)}
            return
        self._clients[name] = client
        self._states[name] = {"state": "running", "error": None}

    async def stop_all(self):
        """Disconnect every connected client. Errors during disconnect are
        swallowed to avoid masking the original shutdown signal."""
        for client in list(self._clients.values()):
            try:
                await client.disconnect()
            except Exception:
                pass
        self._clients = {}

    def list_servers(self):
        """Snapshot of {name: {state, error}}. Synchronous — safe to call
        from non-async code paths (e.g. /mcp list rendering)."""
        return {name: dict(info) for name, info in self._states.items()}

    async def list_tools(self, server=None):
        """Return a flat list of tool dicts, each tagged with `server`. With
        `server=None`, includes tools from every running client."""
        if server is not None:
            client = self._clients.get(server)
            if client is None:
                raise MCPManagerError(f"server '{server}' is not running")
            tools = await client.list_tools()
            for tool in tools:
                tool["server"] = server
            return tools
        result = []
        for name, client in self._clients.items():
            tools = await client.list_tools()
            for tool in tools:
                tool["server"] = name
                result.append(tool)
        return result

    async def call_tool(self, server, name, arguments):
        client = self._clients.get(server)
        if client is None:
            raise MCPManagerError(f"server '{server}' is not running")
        return await client.call_tool(name, arguments)

    async def restart(self, server_name):
        """Disconnect (if connected) then re-spawn one server.

        Useful for `/mcp restart <name>` after the user fixes a config
        problem or wants to recover from a crash. The server must be in
        the original config — restart cannot create a new server entry."""
        if server_name not in self.servers_config:
            raise MCPManagerError(f"unknown server '{server_name}'")
        client = self._clients.pop(server_name, None)
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass
        cfg = self.servers_config[server_name]
        if not cfg.get("enabled", True):
            self._states[server_name] = {"state": "disabled", "error": None}
            return
        self._states[server_name] = {"state": "stopped", "error": None}
        await self._start_one(server_name, cfg)
