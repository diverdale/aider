#!/usr/bin/env python
"""Minimal MCP stdio server for `test_mcp_client.py`.

Exposes a single `echo` tool that returns its input prefixed with "echo: ".
Underscore-prefixed filename so pytest's default collection skips it; this
module is only ever launched as a subprocess by the client tests.

Spawn line: `python -m tests.basic._mcp_test_server`."""

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("test-echo-server")


@server.list_tools()
async def _list_tools():
    return [
        Tool(
            name="echo",
            description="Echo back the input string.",
            inputSchema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        )
    ]


@server.call_tool()
async def _call_tool(name, arguments):
    if name != "echo":
        raise ValueError(f"unknown tool: {name}")
    text = (arguments or {}).get("text", "")
    return [TextContent(type="text", text=f"echo: {text}")]


async def _main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_main())
