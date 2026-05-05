#!/usr/bin/env python

import sys

import pytest

from aider.mcp.manager import Manager

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _server_entry(tool_name="echo"):
    """Build a server config dict that spawns the test fixture with a
    parameterized tool name, so multi-server tests can exercise dispatch."""
    return {
        "command": sys.executable,
        "args": ["-m", "tests.basic._mcp_test_server"],
        "env": {"MCP_TEST_TOOL_NAME": tool_name},
        "enabled": True,
    }


async def test_start_all_brings_one_server_running():
    """A single configured server transitions to `running` after start_all
    and its tools are visible via list_tools()."""
    mgr = Manager({"echo-srv": _server_entry()})
    try:
        await mgr.start_all()
        states = mgr.list_servers()
        assert states["echo-srv"]["state"] == "running"
        tools = await mgr.list_tools()
        names = [t["name"] for t in tools]
        assert "echo" in names
        # Tools must be tagged with their originating server so the coder
        # can route call_tool back to the right client.
        echo = next(t for t in tools if t["name"] == "echo")
        assert echo["server"] == "echo-srv"
    finally:
        await mgr.stop_all()


async def test_disabled_server_is_skipped():
    """`enabled: false` servers don't get spawned. State is `disabled`, no
    Client is created, and their tools never appear in list_tools()."""
    cfg = {
        "live": _server_entry(),
        "off": {**_server_entry(), "enabled": False},
    }
    mgr = Manager(cfg)
    try:
        await mgr.start_all()
        states = mgr.list_servers()
        assert states["live"]["state"] == "running"
        assert states["off"]["state"] == "disabled"
        servers_with_tools = {t["server"] for t in await mgr.list_tools()}
        assert servers_with_tools == {"live"}
    finally:
        await mgr.stop_all()


async def test_failed_server_is_isolated():
    """A server with a bogus command transitions to `failed`; other
    servers in the same start_all batch are unaffected. start_all itself
    does not raise."""
    cfg = {
        "good": _server_entry(),
        "bad": {"command": "/nonexistent/path/to/nothing", "args": [], "enabled": True},
    }
    mgr = Manager(cfg)
    try:
        await mgr.start_all()  # must not raise
        states = mgr.list_servers()
        assert states["good"]["state"] == "running"
        assert states["bad"]["state"] == "failed"
        assert states["bad"]["error"]  # non-empty error message
        # Tools from the good server still listed; bad server contributes none.
        servers = {t["server"] for t in await mgr.list_tools()}
        assert servers == {"good"}
    finally:
        await mgr.stop_all()


async def test_list_tools_aggregates_across_servers():
    """With two servers each exposing a uniquely-named tool, list_tools
    returns both, each tagged with its origin."""
    mgr = Manager({
        "alpha": _server_entry(tool_name="alpha_echo"),
        "beta": _server_entry(tool_name="beta_echo"),
    })
    try:
        await mgr.start_all()
        tools = await mgr.list_tools()
        by_name = {t["name"]: t["server"] for t in tools}
        assert by_name == {"alpha_echo": "alpha", "beta_echo": "beta"}
    finally:
        await mgr.stop_all()


async def test_call_tool_dispatches_to_named_server():
    """call_tool routes to the right client based on the `server` argument,
    even when both servers expose tools with similar interfaces."""
    mgr = Manager({
        "one": _server_entry(tool_name="t_one"),
        "two": _server_entry(tool_name="t_two"),
    })
    try:
        await mgr.start_all()
        r1 = await mgr.call_tool("one", "t_one", {"text": "hello"})
        r2 = await mgr.call_tool("two", "t_two", {"text": "world"})
        assert r1["content"][0]["text"] == "t_one: hello"
        assert r2["content"][0]["text"] == "t_two: world"
    finally:
        await mgr.stop_all()


async def test_call_tool_unknown_server_raises():
    """Calling a server that isn't running raises a clear MCPManagerError —
    the coder loop should see this and report it, not crash."""
    from aider.mcp.manager import MCPManagerError

    mgr = Manager({"only": _server_entry()})
    try:
        await mgr.start_all()
        with pytest.raises(MCPManagerError, match="ghost"):
            await mgr.call_tool("ghost", "t", {})
    finally:
        await mgr.stop_all()


async def test_restart_keeps_server_running():
    """restart() disconnects and respawns a running server. Post-restart
    the state is still `running` and its tools remain queryable. The fixture
    server has no persistent state so we can't observe the process change
    directly — observable contract is: still running, still answering."""
    mgr = Manager({"echo-srv": _server_entry()})
    try:
        await mgr.start_all()
        await mgr.restart("echo-srv")
        states = mgr.list_servers()
        assert states["echo-srv"]["state"] == "running"
        result = await mgr.call_tool("echo-srv", "echo", {"text": "post-restart"})
        assert result["content"][0]["text"] == "echo: post-restart"
    finally:
        await mgr.stop_all()


async def test_restart_unknown_server_raises():
    """restart() of a name that isn't in the original config raises
    MCPManagerError — guards against typos in `/mcp restart <name>`."""
    from aider.mcp.manager import MCPManagerError

    mgr = Manager({"only": _server_entry()})
    try:
        await mgr.start_all()
        with pytest.raises(MCPManagerError, match="unknown"):
            await mgr.restart("nonexistent")
    finally:
        await mgr.stop_all()
