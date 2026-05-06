"""Conversions between MCP tool definitions and litellm/OpenAI tool schemas.

MCP tools come from `Manager.list_tools()` as plain dicts of the shape
`{name, description, inputSchema, server}`. litellm's `tools=` parameter
expects OpenAI's function-tool format:

    {"type": "function",
     "function": {"name": ..., "description": ..., "parameters": <json schema>}}

Tool names are namespaced as `mcp__<server>__<tool>` (Claude Code's
de facto convention) so a tool call from the model can be routed back
to the right server without an out-of-band lookup."""

_PREFIX = "mcp__"


def qualify(server, tool_name):
    return f"{_PREFIX}{server}__{tool_name}"


def parse_qualified_name(qualified):
    """Return (server, tool_name) for a qualified MCP tool name, or
    (None, qualified) for any name that doesn't follow the convention.

    The split point is the FIRST `__` after the `mcp__` prefix so server
    names cannot contain `__`, but tool names may."""
    if not qualified.startswith(_PREFIX):
        return None, qualified
    rest = qualified[len(_PREFIX) :]
    if "__" not in rest:
        return None, qualified
    server, tool = rest.split("__", 1)
    return server, tool


def to_openai_tool(server, mcp_tool):
    """Convert one MCP tool dict to the OpenAI tool-format dict litellm
    accepts via `tools=`. Substitutes an empty object schema when
    `inputSchema` is missing — providers reject tool defs without
    `parameters`."""
    return {
        "type": "function",
        "function": {
            "name": qualify(server, mcp_tool["name"]),
            "description": mcp_tool.get("description") or "",
            "parameters": (
                mcp_tool.get("inputSchema")
                or {
                    "type": "object",
                    "properties": {},
                }
            ),
        },
    }


def to_openai_tools(mcp_tools):
    """Convert the flat list returned by `Manager.list_tools()` (each
    entry tagged with `server`) into the OpenAI `tools=[]` array."""
    return [to_openai_tool(t["server"], t) for t in mcp_tools]
