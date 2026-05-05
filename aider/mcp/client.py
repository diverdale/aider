"""Per-server MCP stdio client wrapper.

Wraps `mcp.client.stdio.stdio_client` + `mcp.ClientSession` into a single
object whose lifecycle (`connect()` / `disconnect()`) can span more than one
`async with` block. The manager is the typical owner; tests instantiate
`Client` directly.

Design choices match `docs/mcp/research.md` D1 (stdio only) and D5 (use the
SDK's session, never roll our own JSON-RPC)."""

from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClientError(RuntimeError):
    pass


class Client:
    def __init__(self, name, server_config):
        self.name = name
        self.config = server_config
        self._session = None
        self._stack = None

    async def connect(self):
        if self._session is not None:
            return
        self._stack = AsyncExitStack()
        params = StdioServerParameters(
            command=self.config["command"],
            args=self.config.get("args") or [],
            env=self.config.get("env") or None,
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()

    async def list_tools(self):
        if self._session is None:
            raise MCPClientError(f"client '{self.name}' not connected")
        result = await self._session.list_tools()
        out = []
        for tool in result.tools:
            entry = {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema,
            }
            ann = getattr(tool, "annotations", None)
            if ann is not None:
                # Convert the SDK Pydantic model to a plain dict so the
                # permission resolver and JSON persistence can consume it
                # without depending on mcp.types.
                if hasattr(ann, "model_dump"):
                    entry["annotations"] = ann.model_dump(exclude_none=True)
                elif isinstance(ann, dict):
                    entry["annotations"] = ann
            out.append(entry)
        return out

    async def call_tool(self, name, arguments):
        if self._session is None:
            raise MCPClientError(f"client '{self.name}' not connected")
        result = await self._session.call_tool(name, arguments)
        return {
            "is_error": bool(result.isError),
            "content": [
                {"type": item.type, "text": getattr(item, "text", None)}
                for item in result.content
            ],
        }

    async def disconnect(self):
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
        self._session = None
