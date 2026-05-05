#!/usr/bin/env python
"""Tests for aider/mcp/tool_schemas.py — MCP↔litellm tool name and
schema conversion.

The MCP tool registry returns plain dicts shaped like
{name, description, inputSchema, server}. litellm's `tools=` parameter
expects OpenAI's function-tool format. Tool names are namespaced with
the `mcp__<server>__<tool>` convention so a tool call from the model
can be routed back to the right server."""

from aider.mcp.tool_schemas import (
    parse_qualified_name,
    qualify,
    to_openai_tool,
    to_openai_tools,
)


def test_qualify_namespaces_with_double_underscore():
    """`mcp__<server>__<tool>` is the de facto convention; we adopt it for
    cross-tool compatibility (Claude Code, opencode use the same)."""
    assert qualify("filesystem", "read_file") == "mcp__filesystem__read_file"


def test_parse_round_trip():
    """Whatever qualify produces, parse must invert."""
    name = qualify("github", "create_issue")
    server, tool = parse_qualified_name(name)
    assert server == "github"
    assert tool == "create_issue"


def test_parse_unqualified_returns_none_server():
    """A non-MCP function name (e.g., aider's own legacy func tools) parses
    to (None, original) so the caller can route by absence-of-server."""
    assert parse_qualified_name("plain_function") == (None, "plain_function")
    assert parse_qualified_name("mcp__no_separator") == (None, "mcp__no_separator")


def test_parse_keeps_underscores_in_tool_name():
    """Server names contain no `__` per our convention; tool names may
    (`__init__`, `_call_tool`). The split is on the FIRST `__` after the
    `mcp__` prefix."""
    server, tool = parse_qualified_name("mcp__fs__has_double__under")
    assert server == "fs"
    assert tool == "has_double__under"


def test_to_openai_tool_shape():
    mcp_tool = {
        "name": "read_file",
        "description": "Read a file from disk.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "server": "filesystem",
    }
    out = to_openai_tool("filesystem", mcp_tool)
    assert out == {
        "type": "function",
        "function": {
            "name": "mcp__filesystem__read_file",
            "description": "Read a file from disk.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    }


def test_to_openai_tool_handles_missing_optional_fields():
    """A spartan MCP tool with no description and no inputSchema must still
    convert — providers reject tool defs without a `parameters` field, so
    we substitute an empty object schema."""
    mcp_tool = {"name": "ping", "server": "x"}
    out = to_openai_tool("x", mcp_tool)
    assert out["function"]["name"] == "mcp__x__ping"
    assert out["function"]["description"] == ""
    assert out["function"]["parameters"] == {"type": "object", "properties": {}}


def test_to_openai_tools_uses_each_tools_server_attribution():
    """Manager.list_tools tags each tool with its originating server. The
    converter must use that tag, not assume a single shared namespace —
    multi-server configs are the whole point."""
    tools = [
        {"name": "a", "server": "alpha", "inputSchema": {}},
        {"name": "b", "server": "beta", "inputSchema": {}},
    ]
    out = to_openai_tools(tools)
    names = [t["function"]["name"] for t in out]
    assert names == ["mcp__alpha__a", "mcp__beta__b"]
