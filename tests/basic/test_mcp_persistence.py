#!/usr/bin/env python
"""Phase 3 slice 4: load/save of project-local permission decisions.

The `.aider/mcp-permissions.json` file persists user choices across
sessions — the differentiator vs Claude Code's session-only approvals.

Pure I/O. Resolver tests in test_mcp_permissions.py drive what gets
DONE with the loaded data; this module only owns moving bytes."""

import json

from aider.mcp.persistence import (
    load_permissions,
    save_permissions,
)


def test_load_missing_file_returns_empty(tmp_path):
    """The common case for a fresh project: no file yet, no decisions
    yet. Must NOT raise — the user shouldn't have to create an empty
    file before MCP works."""
    decisions = load_permissions(tmp_path / "missing.json")
    assert decisions == {}


def test_load_round_trip(tmp_path):
    """Save then load gets the same dict back, byte-for-byte equivalent."""
    p = tmp_path / "perms.json"
    original = {
        "filesystem": {"read_file": "auto", "write_file": "ask"},
        "github": {"create_issue": "ask", "delete_repository": "deny"},
    }
    save_permissions(p, original)
    assert load_permissions(p) == original


def test_load_malformed_json_returns_empty(tmp_path):
    """A hand-edited corrupt file must NOT crash aider startup. Drop the
    decisions on the floor (user can recreate) rather than refusing to
    load. The resolver falls through to its defaults; nothing dangerous
    happens — just back to ask-mode for everything."""
    p = tmp_path / "perms.json"
    p.write_text("{this is not valid json")
    assert load_permissions(p) == {}


def test_load_wrong_top_level_shape_returns_empty(tmp_path):
    """If someone manually wrote a top-level list or string instead of
    {server: {tool: mode}}, treat as empty rather than letting weird
    data flow into the resolver. Defense-in-depth."""
    p = tmp_path / "perms.json"
    p.write_text("[\"not\", \"a\", \"dict\"]")
    assert load_permissions(p) == {}


def test_save_creates_parent_directory(tmp_path):
    """Project root may not yet have a .aider/ subdir on first use.
    Save must create it rather than failing with FileNotFoundError."""
    p = tmp_path / "deep" / "nested" / "perms.json"
    save_permissions(p, {"fs": {"read": "auto"}})
    assert p.exists()
    assert json.loads(p.read_text()) == {"fs": {"read": "auto"}}


def test_save_overwrites_existing_atomically(tmp_path):
    """Subsequent save replaces the prior content. After the call, no
    .tmp leftover should remain (atomic write via rename)."""
    p = tmp_path / "perms.json"
    save_permissions(p, {"fs": {"read": "auto"}})
    save_permissions(p, {"fs": {"read": "deny"}})
    assert json.loads(p.read_text()) == {"fs": {"read": "deny"}}
    # No stray temp files
    leftovers = [x for x in tmp_path.iterdir() if x.name != "perms.json"]
    assert leftovers == []


def test_save_ignores_invalid_modes(tmp_path):
    """Defensive: if buggy code tries to save a non-{auto,ask,deny} mode,
    drop that entry rather than persisting garbage that will then be
    silently ignored by the resolver next session."""
    p = tmp_path / "perms.json"
    save_permissions(p, {
        "fs": {"read": "auto", "write": "yolo"},
        "gh": {"x": "ask"},
    })
    loaded = load_permissions(p)
    assert loaded == {"fs": {"read": "auto"}, "gh": {"x": "ask"}}
