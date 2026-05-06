#!/usr/bin/env python
"""Tests for the /mcp slash command family in aider/commands.py.

Mirrors the cmd_skills test pattern: real InputOutput, mocked Coder,
real Commands instance with mcp_runtime set directly on it (the
attribute base_coder.__init__ will populate in the live runtime)."""

import sys
from unittest import mock
from unittest.mock import MagicMock

from aider.commands import Commands
from aider.io import InputOutput
from aider.mcp.manager import Manager
from aider.mcp.runtime import MCPRuntime


def _server_entry(tool_name="echo"):
    return {
        "command": sys.executable,
        "args": ["-m", "tests.basic._mcp_test_server"],
        "env": {"MCP_TEST_TOOL_NAME": tool_name},
        "enabled": True,
    }


def _make_cmd(runtime):
    """Build a Commands instance wired to `runtime` the same way base_coder
    will wire it at session start."""
    io = InputOutput(pretty=False, fancy_input=False, yes=True)
    coder = MagicMock()
    cmd = Commands(io, coder)
    cmd.mcp_runtime = runtime
    return cmd, io


def _captured(mock_output):
    return "\n".join(str(c.args[0]) for c in mock_output.call_args_list if c.args)


def test_cmd_mcp_list_shows_running_servers():
    rt = MCPRuntime(Manager({"echo-srv": _server_entry()}))
    try:
        rt.start()
        cmd, io = _make_cmd(rt)
        with mock.patch.object(io, "tool_output") as out:
            cmd.cmd_mcp("list")
        rendered = _captured(out)
        assert "echo-srv" in rendered
        assert "running" in rendered
    finally:
        rt.stop()


def test_cmd_mcp_default_subcommand_is_list():
    """No-arg `/mcp` defaults to listing servers — cheapest path to status."""
    rt = MCPRuntime(Manager({"echo-srv": _server_entry()}))
    try:
        rt.start()
        cmd, io = _make_cmd(rt)
        with mock.patch.object(io, "tool_output") as out:
            cmd.cmd_mcp("")
        assert "echo-srv" in _captured(out)
    finally:
        rt.stop()


def test_cmd_mcp_tools_lists_tools_with_server_attribution():
    rt = MCPRuntime(Manager({"echo-srv": _server_entry()}))
    try:
        rt.start()
        cmd, io = _make_cmd(rt)
        with mock.patch.object(io, "tool_output") as out:
            cmd.cmd_mcp("tools")
        rendered = _captured(out)
        assert "echo" in rendered
        # Tool listing must show which server each tool came from so users
        # can disambiguate when names overlap across servers.
        assert "echo-srv" in rendered
    finally:
        rt.stop()


def test_cmd_mcp_tools_scoped_to_one_server():
    """`/mcp tools <server>` filters to that server only."""
    rt = MCPRuntime(
        Manager(
            {
                "alpha": _server_entry(tool_name="alpha_echo"),
                "beta": _server_entry(tool_name="beta_echo"),
            }
        )
    )
    try:
        rt.start()
        cmd, io = _make_cmd(rt)
        with mock.patch.object(io, "tool_output") as out:
            cmd.cmd_mcp("tools alpha")
        rendered = _captured(out)
        assert "alpha_echo" in rendered
        assert "beta_echo" not in rendered
    finally:
        rt.stop()


def test_cmd_mcp_restart_known_server():
    rt = MCPRuntime(Manager({"echo-srv": _server_entry()}))
    try:
        rt.start()
        cmd, _io = _make_cmd(rt)
        cmd.cmd_mcp("restart echo-srv")  # must not raise
        assert rt.list_servers()["echo-srv"]["state"] == "running"
    finally:
        rt.stop()


def test_cmd_mcp_restart_unknown_reports_error_not_raises():
    rt = MCPRuntime(Manager({"echo-srv": _server_entry()}))
    try:
        rt.start()
        cmd, io = _make_cmd(rt)
        with mock.patch.object(io, "tool_error") as err:
            cmd.cmd_mcp("restart ghost")  # underlying MCPManagerError
        assert err.called  # surfaced as a tool_error, not propagated
        rendered = "\n".join(str(c.args[0]) for c in err.call_args_list if c.args)
        assert "ghost" in rendered or "unknown" in rendered.lower()
    finally:
        rt.stop()


def test_cmd_mcp_no_runtime_reports_actionable_error():
    """When aider boots without MCP config, /mcp should print a helpful
    message naming the config file paths — not crash."""
    io = InputOutput(pretty=False, fancy_input=False, yes=True)
    coder = MagicMock()
    cmd = Commands(io, coder)
    cmd.mcp_runtime = None
    with mock.patch.object(io, "tool_error") as err:
        cmd.cmd_mcp("list")
    assert err.called
    rendered = "\n".join(str(c.args[0]) for c in err.call_args_list if c.args)
    assert "mcp.yml" in rendered.lower()


def test_cmd_mcp_unknown_subcommand_shows_usage():
    rt = MCPRuntime(Manager({"echo-srv": _server_entry()}))
    try:
        rt.start()
        cmd, io = _make_cmd(rt)
        with mock.patch.object(io, "tool_output") as out:
            cmd.cmd_mcp("not-a-real-subcommand")
        rendered = _captured(out)
        assert "Usage" in rendered or "usage" in rendered
    finally:
        rt.stop()
