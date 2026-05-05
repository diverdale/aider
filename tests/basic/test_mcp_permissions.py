#!/usr/bin/env python
"""Phase 3 slice 2: pure permission-resolution function.

Resolves a tool call's permission mode from four sources, in priority
order (highest wins):

1. Persisted decision in .aider/mcp-permissions.json (user said "always"
   or "never" earlier).
2. Per-tool override in mcp.yml (servers.<name>.permissions.<tool>).
3. Per-server default_permission in mcp.yml.
4. Tool's MCP annotations: readOnlyHint=True → auto; otherwise → ask.
5. Hard fallback: ask.

No I/O. No UI. Just the table of precedence."""

from aider.mcp.permissions import resolve_permission


def _tool(name="read", read_only=None, destructive=None):
    annotations = {}
    if read_only is not None:
        annotations["readOnlyHint"] = read_only
    if destructive is not None:
        annotations["destructiveHint"] = destructive
    out = {"name": name, "server": "fs"}
    if annotations:
        out["annotations"] = annotations
    return out


def _srv(default=None, perms=None):
    return {
        "default_permission": default,
        "permissions": perms or {},
    }


def test_persisted_decision_wins_over_everything():
    """User clicked 'Always for this tool' once; that decision overrides
    every other source. Even a destructive annotation doesn't downgrade
    a persisted `auto`."""
    mode = resolve_permission(
        "fs", "read",
        tool_meta=_tool(destructive=True),
        server_config=_srv(default="ask", perms={"read": "deny"}),
        persisted={"fs": {"read": "auto"}},
    )
    assert mode == "auto"


def test_per_tool_config_wins_over_default_and_annotations():
    """Per-tool override in mcp.yml beats the server default and any tool
    annotation. This is how a careful user explicitly says 'auto for
    list_dir, ask for delete' regardless of how the server self-labels."""
    mode = resolve_permission(
        "fs", "delete",
        tool_meta=_tool(read_only=False),
        server_config=_srv(default="auto", perms={"delete": "deny"}),
        persisted={},
    )
    assert mode == "deny"


def test_per_server_default_used_when_no_per_tool():
    """No per-tool override → fall to server's default_permission."""
    mode = resolve_permission(
        "fs", "anything",
        tool_meta=_tool(),
        server_config=_srv(default="auto"),
        persisted={},
    )
    assert mode == "auto"


def test_read_only_annotation_yields_auto():
    """The whole point of readOnlyHint: tools the server explicitly marks
    safe run silently by default. No prompts for read_file, list_dir, etc."""
    mode = resolve_permission(
        "fs", "read",
        tool_meta=_tool(read_only=True),
        server_config=_srv(),
        persisted={},
    )
    assert mode == "auto"


def test_destructive_annotation_yields_ask_not_deny():
    """destructiveHint adds info but doesn't IMPLY deny — many destructive
    tools are intentional (delete_branch, drop_table). Default to ask so
    the user confirms; explicit deny is for the user's mcp.yml."""
    mode = resolve_permission(
        "fs", "rm_rf",
        tool_meta=_tool(destructive=True),
        server_config=_srv(),
        persisted={},
    )
    assert mode == "ask"


def test_no_annotation_no_config_falls_back_to_ask():
    """The conservative default. A server that doesn't annotate its tools
    AND doesn't have any user config falls to ask — better to interrupt
    than to surprise."""
    mode = resolve_permission(
        "fs", "mystery",
        tool_meta={"name": "mystery", "server": "fs"},
        server_config=_srv(),
        persisted={},
    )
    assert mode == "ask"


def test_persisted_for_different_tool_does_not_apply():
    """Persisted decisions are scoped (server, tool). A persisted decision
    on `read` must NOT leak into a decision on `write`."""
    mode = resolve_permission(
        "fs", "write",
        tool_meta=_tool(name="write", read_only=False),
        server_config=_srv(),
        persisted={"fs": {"read": "auto"}},
    )
    assert mode == "ask"


def test_persisted_for_different_server_does_not_apply():
    """Cross-server isolation: a decision on filesystem.read doesn't apply
    to github.read. Server names are part of the key."""
    mode = resolve_permission(
        "github", "read",
        tool_meta=_tool(read_only=True),
        server_config=_srv(default="ask"),  # default ask wins over auto-from-readonly? no, server default beats annotation
        persisted={"fs": {"read": "auto"}},
    )
    # Annotation says auto, server default says ask. Per priority: server
    # default beats annotation.
    assert mode == "ask"


def test_invalid_persisted_value_falls_through():
    """Defensive: if mcp-permissions.json got corrupted with an unknown
    value, ignore that source and continue resolution. Don't crash; the
    user can clear the file later."""
    mode = resolve_permission(
        "fs", "read",
        tool_meta=_tool(read_only=True),
        server_config=_srv(),
        persisted={"fs": {"read": "yolo"}},
    )
    # Falls through invalid persisted, lands on annotation auto.
    assert mode == "auto"
