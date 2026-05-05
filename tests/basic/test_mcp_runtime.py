#!/usr/bin/env python
"""Tests for aider.mcp.runtime — the sync wrapper that runs the asyncio
event loop for Manager in a background thread, so aider's sync REPL can
talk to MCP servers without restarting a loop per call.

These tests are deliberately synchronous (no anyio marks) — the whole
point of Runtime is to expose a sync API."""

import sys

import pytest

from aider.mcp.manager import Manager
from aider.mcp.runtime import MCPRuntime


def _server_entry(tool_name="echo"):
    return {
        "command": sys.executable,
        "args": ["-m", "tests.basic._mcp_test_server"],
        "env": {"MCP_TEST_TOOL_NAME": tool_name},
        "enabled": True,
    }


def test_runtime_lifecycle_start_list_stop():
    """start() blocks until servers are running; sync list_tools sees them;
    stop() shuts everything down cleanly. The whole flow happens with no
    explicit asyncio in the test."""
    mgr = Manager({"echo-srv": _server_entry()})
    rt = MCPRuntime(mgr)
    try:
        rt.start()
        states = rt.list_servers()
        assert states["echo-srv"]["state"] == "running"
        tools = rt.list_tools()
        assert any(t["name"] == "echo" for t in tools)
    finally:
        rt.stop()


def test_runtime_call_tool_sync():
    """The whole point: a sync caller can dispatch a tool call and get a
    result back without writing async code."""
    mgr = Manager({"echo-srv": _server_entry()})
    rt = MCPRuntime(mgr)
    try:
        rt.start()
        result = rt.call_tool("echo-srv", "echo", {"text": "hi"})
        assert result["is_error"] is False
        assert result["content"][0]["text"] == "echo: hi"
    finally:
        rt.stop()


def test_runtime_stop_idempotent():
    """Calling stop() before start() and twice in a row are both no-ops.
    aider's atexit hook will rely on this — it can't know whether
    runtime ever successfully started."""
    rt = MCPRuntime(Manager({}))
    rt.stop()  # never started
    rt.stop()  # still safe
    rt.start()
    rt.stop()
    rt.stop()  # already stopped


def test_runtime_propagates_tool_errors():
    """An MCPManagerError from the underlying async call surfaces as the
    same exception type to the sync caller — wrapping shouldn't swallow
    or change error types."""
    from aider.mcp.manager import MCPManagerError

    rt = MCPRuntime(Manager({"only": _server_entry()}))
    try:
        rt.start()
        with pytest.raises(MCPManagerError, match="ghost"):
            rt.call_tool("ghost", "echo", {"text": "x"})
    finally:
        rt.stop()
