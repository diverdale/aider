#!/usr/bin/env python
"""Minimal MCP stdio server for `test_mcp_client.py` and `test_mcp_manager.py`.

Exposes one tool whose name is read from `MCP_TEST_TOOL_NAME` (default
`echo`). The tool returns its input prefixed with `<tool_name>: `. Multi-
server tests spawn several instances with distinct tool names so dispatch
can be tested by name alone.

Underscore-prefixed filename so pytest's default collection skips it; this
module is only launched as a subprocess by the tests.

Spawn line: `python -m tests.basic._mcp_test_server`."""

import asyncio
import os

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

TOOL_NAME = os.environ.get("MCP_TEST_TOOL_NAME", "echo")

server = Server("test-echo-server")


@server.list_tools()
async def _list_tools():
    return [
        Tool(
            name=TOOL_NAME,
            description=f"Echo back the input string, prefixed with '{TOOL_NAME}: '.",
            inputSchema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        )
    ]


@server.call_tool()
async def _call_tool(name, arguments):
    if name != TOOL_NAME:
        raise ValueError(f"unknown tool: {name}")
    text = (arguments or {}).get("text", "")
    return [TextContent(type="text", text=f"{TOOL_NAME}: {text}")]


async def _main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_main())
