#!/usr/bin/env python

import sys

import pytest

from aider.mcp.client import Client

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    """Pin the async backend to asyncio. The SDK uses anyio internally so
    either backend would work, but tests are deterministic if we pick one."""
    return "asyncio"


def _echo_server_config():
    return {
        "command": sys.executable,
        "args": ["-m", "tests.basic._mcp_test_server"],
    }


async def test_client_connects_and_lists_tools():
    """Spawn the test echo server, connect, list its tools. The fixture server
    exposes exactly one tool named `echo`."""
    client = Client("test-echo", _echo_server_config())
    try:
        await client.connect()
        tools = await client.list_tools()
        names = [t["name"] for t in tools]
        assert names == ["echo"]
    finally:
        await client.disconnect()


async def test_client_calls_tool_and_returns_text():
    """Calling `echo` with `text="hello"` returns the server's prefixed
    response. The test asserts on the wrapped result shape, not on the SDK's
    internal types — callers shouldn't need to know about `TextContent`."""
    from aider.mcp.client import Client

    client = Client("test-echo", _echo_server_config())
    try:
        await client.connect()
        result = await client.call_tool("echo", {"text": "hello"})
        assert result["is_error"] is False
        text_parts = [c["text"] for c in result["content"] if c["type"] == "text"]
        assert text_parts == ["echo: hello"]
    finally:
        await client.disconnect()


async def test_list_tools_before_connect_raises():
    """list_tools without a prior connect() is a clear error, not a hang or
    a generic AttributeError."""
    from aider.mcp.client import MCPClientError

    client = Client("not-connected", _echo_server_config())
    with pytest.raises(MCPClientError, match="not connected"):
        await client.list_tools()


async def test_disconnect_is_idempotent():
    """Calling disconnect on a never-connected (or already-disconnected)
    client doesn't raise. Manager will rely on this when shutting down a
    set of servers some of which may never have connected."""
    client = Client("never", _echo_server_config())
    await client.disconnect()  # no-op
    await client.disconnect()  # also no-op
    # Now connect, disconnect twice — second call must still be safe.
    await client.connect()
    await client.disconnect()
    await client.disconnect()
